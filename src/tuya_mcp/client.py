"""Async client for the Tuya Cloud OpenAPI: signing, token cache, error surfacing."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

import httpx

from .config import Config
from .errors import DeviceNotFoundError, TuyaAPIError, TuyaConnectionError
from .logging_utils import redactor
from .models import Device, Scene, Specification
from .resolver import resolve_device
from .signing import QueryValue, build_url, sign, string_to_sign

logger = logging.getLogger(__name__)

TOKEN_PATH = "/v1.0/token"
DEVICES_PATH = "/v1.0/iot-01/associated-users/devices"
DEVICE_PATH = "/v1.0/iot-03/devices/{device_id}"
STATUS_PATH = "/v1.0/iot-03/devices/{device_id}/status"
SPECIFICATION_PATH = "/v1.0/iot-03/devices/{device_id}/specification"
COMMANDS_PATH = "/v1.0/iot-03/devices/{device_id}/commands"
FIRMWARE_PATH = "/v2.0/cloud/thing/{device_id}/firmware"
HOMES_PATH = "/v1.0/users/{uid}/homes"
SCENES_PATH = "/v2.0/cloud/scene/rule"
SCENE_TRIGGER_PATH = "/v2.0/cloud/scene/rule/{scene_id}/actions/trigger"

# Device info fields never returned to the agent (secrets, location, network).
PRIVATE_DEVICE_FIELDS = {"local_key", "ip", "lat", "lon", "uuid", "sn", "owner_id", "uid"}

# Refresh the token this many seconds before Tuya says it expires.
TOKEN_REFRESH_MARGIN = 60
# Tuya codes meaning the access token is no longer valid.
TOKEN_INVALID_CODES = {1010, 1011, 1012, 1400}
DEVICES_PAGE_SIZE = 20
MAX_DEVICE_PAGES = 50
REQUEST_TIMEOUT = 10.0
# How long a sent value overrides the cloud status. Some devices (e.g. LSC
# Smart Connect lamps) execute commands but report their new state late or
# never, so the cloud status alone would make toggles and reads wrong.
SENT_STATE_TTL = 300


_UNKNOWN: Any = object()


@dataclass
class _SentValue:
    value: Any
    cloud_value_when_sent: Any
    sent_at: float


@dataclass
class _Token:
    access_token: str
    expires_at: float


class TuyaClient:
    def __init__(
        self,
        config: Config,
        *,
        http: httpx.AsyncClient | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._config = config
        self._http = http or httpx.AsyncClient(base_url=config.endpoint, timeout=REQUEST_TIMEOUT)
        self._clock = clock
        self._token: _Token | None = None
        self._token_lock = asyncio.Lock()
        self._devices: list[Device] | None = None
        self._devices_fetched_at = 0.0
        self._specs: dict[str, Specification] = {}
        self._cloud_status: dict[str, dict[str, Any]] = {}
        self._sent: dict[str, dict[str, _SentValue]] = {}
        redactor.add(config.access_secret)

    async def aclose(self) -> None:
        await self._http.aclose()

    # -- Public API -----------------------------------------------------

    async def devices(self, *, refresh: bool = False) -> list[Device]:
        """Device list, cached for ``cache_ttl`` seconds."""
        expired = self._clock() - self._devices_fetched_at >= self._config.cache_ttl
        if refresh or expired or self._devices is None:
            self._devices = await self.list_devices()
            self._devices_fetched_at = self._clock()
        return self._devices

    async def find_device(self, query: str) -> Device:
        """Resolve a name or id; refresh the cache once before giving up."""
        try:
            return resolve_device(query, await self.devices())
        except DeviceNotFoundError:
            return resolve_device(query, await self.devices(refresh=True))

    async def get_status(self, device_id: str) -> dict[str, Any]:
        """Cloud status, overlaid with values this server sent recently.

        A sent value wins until the cloud reports a different value than it
        did at send time (someone changed it elsewhere, e.g. in the app), the
        cloud catches up, or ``SENT_STATE_TTL`` elapses.
        """
        result = await self.request("GET", STATUS_PATH.format(device_id=device_id))
        cloud = {str(item["code"]): item.get("value") for item in result or [] if "code" in item}
        self._cloud_status[device_id] = cloud

        status = dict(cloud)
        sent = self._sent.get(device_id, {})
        now = self._clock()
        for code, entry in list(sent.items()):
            cloud_value = cloud.get(code)
            expired = now - entry.sent_at >= SENT_STATE_TTL
            caught_up = cloud_value == entry.value
            changed_elsewhere = (
                entry.cloud_value_when_sent is not _UNKNOWN
                and cloud_value != entry.cloud_value_when_sent
            )
            if expired or caught_up or changed_elsewhere:
                del sent[code]
            else:
                status[code] = entry.value
        return status

    async def get_device(self, device_id: str) -> dict[str, Any]:
        result = await self.request("GET", DEVICE_PATH.format(device_id=device_id))
        return {k: v for k, v in (result or {}).items() if k not in PRIVATE_DEVICE_FIELDS}

    async def get_firmware(self, device_id: str) -> list[dict[str, Any]]:
        result = await self.request("GET", FIRMWARE_PATH.format(device_id=device_id))
        return [
            {"module": item.get("type_desc"), "version": item.get("current_version")}
            for item in result or []
        ]

    async def get_specification(self, device_id: str) -> Specification:
        """A device's capabilities never change at runtime: cached for the process."""
        if device_id not in self._specs:
            result = await self.request("GET", SPECIFICATION_PATH.format(device_id=device_id))
            self._specs[device_id] = Specification.from_api(result or {})
        return self._specs[device_id]

    async def list_homes(self) -> list[dict[str, str]]:
        result = await self.request("GET", HOMES_PATH.format(uid=self._config.uid))
        return [
            {"id": str(home["home_id"]), "name": str(home.get("name") or home["home_id"])}
            for home in result or []
            if "home_id" in home
        ]

    async def list_scenes(self) -> list[Scene]:
        """Tap-to-run scenes of every home (automations are excluded)."""
        homes = await self.list_homes()
        results = await asyncio.gather(
            *(self.request("GET", SCENES_PATH, params={"space_id": h["id"]}) for h in homes)
        )
        scenes: list[Scene] = []
        for home, result in zip(homes, results, strict=True):
            result = result or {}
            if result.get("has_more"):
                logger.warning(
                    "Home %s has more scenes than one page; extra ones are skipped", home["id"]
                )
            scenes.extend(
                Scene.from_api(rule, home["name"])
                for rule in result.get("list") or []
                if rule.get("type", "scene") == "scene"
            )
        return scenes

    async def trigger_scene(self, scene_id: str) -> None:
        await self.request("POST", SCENE_TRIGGER_PATH.format(scene_id=scene_id))

    async def send_commands(self, device_id: str, commands: list[dict[str, Any]]) -> None:
        await self.request(
            "POST", COMMANDS_PATH.format(device_id=device_id), body={"commands": commands}
        )
        cloud = self._cloud_status.get(device_id)
        sent = self._sent.setdefault(device_id, {})
        for command in commands:
            code = str(command["code"])
            before = cloud.get(code, _UNKNOWN) if cloud is not None else _UNKNOWN
            sent[code] = _SentValue(command["value"], before, self._clock())

    async def list_devices(self) -> list[Device]:
        """Return every device of the app account linked to the cloud project (uncached)."""
        devices: list[Device] = []
        last_row_key = ""
        for _ in range(MAX_DEVICE_PAGES):
            params: dict[str, QueryValue] = {"size": DEVICES_PAGE_SIZE}
            if last_row_key:
                params["last_row_key"] = last_row_key
            result = await self.request("GET", DEVICES_PATH, params=params)
            devices.extend(Device.from_api(item) for item in result.get("devices") or [])
            last_row_key = str(result.get("last_row_key") or "")
            if not result.get("has_more") or not last_row_key:
                break
        return devices

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, QueryValue] | None = None,
        body: Any = None,
    ) -> Any:
        """Send a signed business request and return its ``result`` field."""
        try:
            return await self._signed_request(method, path, params, body)
        except TuyaAPIError as exc:
            if exc.code not in TOKEN_INVALID_CODES:
                raise
            logger.info("Access token rejected by Tuya (code %s), refreshing", exc.code)
            self._token = None
            return await self._signed_request(method, path, params, body)

    # -- Internals ------------------------------------------------------

    async def _signed_request(
        self,
        method: str,
        path: str,
        params: Mapping[str, QueryValue] | None,
        body: Any,
    ) -> Any:
        access_token = await self._access_token()
        return await self._send(method, path, params, body, access_token=access_token)

    async def _access_token(self) -> str:
        async with self._token_lock:
            now = self._clock()
            if self._token is None or now >= self._token.expires_at - TOKEN_REFRESH_MARGIN:
                self._token = await self._fetch_token()
            return self._token.access_token

    async def _fetch_token(self) -> _Token:
        logger.debug("Requesting a new Tuya access token")
        result = await self._send("GET", TOKEN_PATH, {"grant_type": 1}, None, access_token="")
        access_token = str(result["access_token"])
        redactor.add(access_token)
        redactor.add(str(result.get("refresh_token") or ""))
        expires_in = int(result.get("expire_time") or 0)
        return _Token(access_token=access_token, expires_at=self._clock() + expires_in)

    async def _send(
        self,
        method: str,
        path: str,
        params: Mapping[str, QueryValue] | None,
        body: Any,
        *,
        access_token: str,
    ) -> Any:
        url = build_url(path, params)
        content = b"" if body is None else json.dumps(body, separators=(",", ":")).encode()
        t = str(int(self._clock() * 1000))
        nonce = uuid.uuid4().hex
        signature = sign(
            client_id=self._config.access_id,
            secret=self._config.access_secret,
            t=t,
            nonce=nonce,
            access_token=access_token,
            string_to_sign=string_to_sign(method, url, content),
        )
        headers = {
            "client_id": self._config.access_id,
            "t": t,
            "nonce": nonce,
            "sign_method": "HMAC-SHA256",
            "sign": signature,
        }
        if access_token:
            headers["access_token"] = access_token
        if body is not None:
            headers["Content-Type"] = "application/json"

        logger.debug("Tuya request %s %s", method, url)
        try:
            response = await self._http.request(method, url, headers=headers, content=content)
        except httpx.HTTPError as exc:
            raise TuyaConnectionError(
                f"Could not reach the Tuya Cloud at {self._config.endpoint}: {exc}"
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise TuyaConnectionError(
                f"Unreadable response from the Tuya Cloud (HTTP {response.status_code})."
            ) from exc

        if not isinstance(payload, dict) or not payload.get("success"):
            code = payload.get("code") if isinstance(payload, dict) else None
            msg = payload.get("msg") if isinstance(payload, dict) else None
            raise TuyaAPIError(code, msg)
        return payload.get("result")
