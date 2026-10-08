"""Tool behaviours, independent of the MCP layer."""

from __future__ import annotations

import json
import logging
from typing import Any

from .client import TuyaClient
from .errors import (
    DeviceOfflineError,
    SceneNotFoundError,
    TuyaAPIError,
    UnsupportedCommandError,
)
from .lighting import (
    LightCapabilities,
    decode_colour,
    encode_colour,
    light_summary,
    require,
    require_hue,
    require_percent,
    switch_code,
)
from .models import Device
from .resolver import resolve_scene

logger = logging.getLogger(__name__)

LIGHT_OFF_NOTE = (
    "The light is currently off, so the change is not visible yet. "
    "Call tuya_turn_on to switch it on."
)


NO_SCENES_NOTE = (
    "This account has no tap-to-run scene. Create one in the Tuya Smart / "
    "Smart Life app (Scenes > + > Tap-to-Run)."
)


class DeviceService:
    def __init__(self, client: TuyaClient) -> None:
        self._client = client

    # -- Discovery & state ------------------------------------------------

    async def list_devices(self) -> dict[str, Any]:
        devices = await self._client.devices(refresh=True)
        return {"count": len(devices), "devices": [d.to_dict() for d in devices]}

    async def get_status(self, query: str) -> dict[str, Any]:
        device = await self._client.find_device(query)
        status = await self._client.get_status(device.id)
        result: dict[str, Any] = {**_identity(device), "status": status}
        caps = LightCapabilities.from_spec(await self._client.get_specification(device.id))
        if caps.is_light:
            result["light"] = light_summary(caps, status)
        return result

    async def get_info(self, query: str) -> dict[str, Any]:
        device = await self._client.find_device(query)
        info = await self._client.get_device(device.id)
        try:
            info["firmware"] = await self._client.get_firmware(device.id)
        except TuyaAPIError as exc:
            logger.info("Firmware unavailable for %s: %s", device.id, exc)
            info["firmware"] = "not available for this device"
        return info

    async def get_specifications(self, query: str) -> dict[str, Any]:
        device = await self._client.find_device(query)
        spec = await self._client.get_specification(device.id)
        return {**_identity(device), **spec.to_dict()}

    # -- Basic control ----------------------------------------------------

    async def turn(self, query: str, on: bool | None) -> dict[str, Any]:
        """Switch on (True), off (False) or toggle (None)."""
        device = await self._online_device(query)
        spec = await self._client.get_specification(device.id)
        code = switch_code(spec)
        require(code, device.name, "on/off")
        assert code is not None
        if on is None:
            status = await self._client.get_status(device.id)
            on = not bool(status.get(code))
        return await self._send(device, [{"code": code, "value": on}])

    async def send_command(self, query: str, code: str, value: Any) -> dict[str, Any]:
        device = await self._online_device(query)
        spec = await self._client.get_specification(device.id)
        dp = spec.functions.get(code)
        if dp is None:
            available = ", ".join(spec.functions) or "none"
            raise UnsupportedCommandError(
                f"{device.name!r} has no command code {code!r}. Available codes: {available}."
            )
        if dp.type.lower() == "json" and isinstance(value, dict | list):
            value = json.dumps(value, separators=(",", ":"))
        return await self._send(device, [{"code": code, "value": value}])

    # -- Lighting ---------------------------------------------------------

    async def set_brightness(self, query: str, brightness: float) -> dict[str, Any]:
        require_percent("brightness", brightness)
        device, caps, status = await self._light(query)

        # In colour mode, brightness is the colour's own intensity: keep the colour.
        current = decode_colour(status.get(caps.colour.code)) if caps.colour else None
        if caps.colour and status.get(caps.work_mode or "") == "colour" and current:
            colour = json.dumps(
                {
                    "h": current.get("h", 0),
                    "s": current.get("s", 0),
                    "v": caps.colour.value.from_percent(brightness),
                },
                separators=(",", ":"),
            )
            commands: list[dict[str, Any]] = [{"code": caps.colour.code, "value": colour}]
        else:
            require(caps.bright, device.name, "brightness")
            assert caps.bright is not None
            code, scale = caps.bright
            commands = [
                *self._mode(caps, "white"),
                {"code": code, "value": scale.from_percent(brightness)},
            ]
        return await self._send(device, commands, status=status, caps=caps)

    async def set_color_temperature(self, query: str, temperature: float) -> dict[str, Any]:
        require_percent("temperature", temperature)
        device, caps, status = await self._light(query)
        require(caps.temp, device.name, "white color temperature")
        assert caps.temp is not None
        code, scale = caps.temp
        commands = [
            *self._mode(caps, "white"),
            {"code": code, "value": scale.from_percent(temperature)},
        ]
        return await self._send(device, commands, status=status, caps=caps)

    async def set_color(
        self, query: str, hue: float, saturation: float, brightness: float
    ) -> dict[str, Any]:
        require_hue(hue)
        require_percent("saturation", saturation)
        require_percent("brightness", brightness)
        device, caps, status = await self._light(query)
        require(caps.colour, device.name, "colour")
        assert caps.colour is not None
        colour = encode_colour(caps.colour, hue, saturation, brightness)
        commands = [*self._mode(caps, "colour"), {"code": caps.colour.code, "value": colour}]
        return await self._send(device, commands, status=status, caps=caps)

    # -- Scenes -----------------------------------------------------------

    async def list_scenes(self) -> dict[str, Any]:
        scenes = await self._client.list_scenes()
        result: dict[str, Any] = {"count": len(scenes), "scenes": [s.to_dict() for s in scenes]}
        if not scenes:
            result["note"] = NO_SCENES_NOTE
        return result

    async def trigger_scene(self, query: str) -> dict[str, Any]:
        scenes = await self._client.list_scenes()
        if not scenes:
            raise SceneNotFoundError(NO_SCENES_NOTE)
        scene = resolve_scene(query, scenes)
        if not scene.enabled:
            raise UnsupportedCommandError(
                f"Scene {scene.name!r} is disabled. Enable it in the app first. Nothing was sent."
            )
        await self._client.trigger_scene(scene.id)
        return {"scene": scene.name, "id": scene.id, "triggered": True}

    # -- Internals --------------------------------------------------------

    async def _online_device(self, query: str) -> Device:
        device = await self._client.find_device(query)
        if not device.online:
            # The cached list may be stale: confirm before refusing.
            await self._client.devices(refresh=True)
            device = await self._client.find_device(device.id)
        if not device.online:
            raise DeviceOfflineError(
                f"{device.name!r} is offline: check that it is powered and connected "
                "to Wi-Fi. No command was sent."
            )
        return device

    async def _light(self, query: str) -> tuple[Device, LightCapabilities, dict[str, Any]]:
        device = await self._online_device(query)
        caps = LightCapabilities.from_spec(await self._client.get_specification(device.id))
        if not caps.is_light:
            raise UnsupportedCommandError(
                f"{device.name!r} is not a light (category {device.category!r}). "
                "Use tuya_get_device_specifications and tuya_send_command instead."
            )
        status = await self._client.get_status(device.id)
        return device, caps, status

    @staticmethod
    def _mode(caps: LightCapabilities, mode: str) -> list[dict[str, Any]]:
        return [{"code": caps.work_mode, "value": mode}] if caps.work_mode else []

    async def _send(
        self,
        device: Device,
        commands: list[dict[str, Any]],
        *,
        status: dict[str, Any] | None = None,
        caps: LightCapabilities | None = None,
    ) -> dict[str, Any]:
        await self._client.send_commands(device.id, commands)
        result: dict[str, Any] = {**_identity(device), "sent": commands}
        light_off = caps is not None and caps.switch and (status or {}).get(caps.switch) is False
        if light_off:
            result["note"] = LIGHT_OFF_NOTE
        return result


def _identity(device: Device) -> dict[str, Any]:
    return {"device": device.name, "id": device.id}
