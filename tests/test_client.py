from __future__ import annotations

from typing import Any

import httpx
import pytest

from tuya_mcp.client import DEVICES_PATH, TuyaClient
from tuya_mcp.config import Config
from tuya_mcp.errors import TuyaAPIError, TuyaConnectionError
from tuya_mcp.models import Device
from tuya_mcp.signing import sign, string_to_sign

from .conftest import SECRET, FakeClock, FakeTuya


def _device(i: int, online: bool = True) -> dict[str, Any]:
    return {
        "id": f"dev{i}",
        "name": f"Lamp {i}",
        "category": "dj",
        "online": online,
        "local_key": "must-not-leak",
    }


def _devices_page(
    devices: list[dict[str, Any]], *, has_more: bool = False, last_row_key: str = ""
) -> dict[str, Any]:
    return {
        "success": True,
        "result": {
            "devices": devices,
            "has_more": has_more,
            "last_row_key": last_row_key,
            "total": len(devices),
        },
    }


async def test_list_devices_parses_response(
    config: Config, fake_tuya: FakeTuya, http: httpx.AsyncClient, clock: FakeClock
) -> None:
    fake_tuya.route(DEVICES_PATH, lambda r: _devices_page([_device(1), _device(2, online=False)]))
    client = TuyaClient(config, http=http, clock=clock)

    devices = await client.list_devices()

    assert devices == [
        Device(id="dev1", name="Lamp 1", category="dj", online=True),
        Device(id="dev2", name="Lamp 2", category="dj", online=False),
    ]
    assert "local_key" not in devices[0].to_dict()


async def test_list_devices_follows_pagination(
    config: Config, fake_tuya: FakeTuya, http: httpx.AsyncClient, clock: FakeClock
) -> None:
    def pages(request: httpx.Request) -> dict[str, Any]:
        if request.url.params.get("last_row_key") == "k1":
            return _devices_page([_device(2)])
        return _devices_page([_device(1)], has_more=True, last_row_key="k1")

    fake_tuya.route(DEVICES_PATH, pages)
    client = TuyaClient(config, http=http, clock=clock)

    assert [d.id for d in await client.list_devices()] == ["dev1", "dev2"]


async def test_token_is_cached_and_refreshed_before_expiry(
    config: Config, fake_tuya: FakeTuya, http: httpx.AsyncClient, clock: FakeClock
) -> None:
    fake_tuya.route(DEVICES_PATH, lambda r: _devices_page([]))
    client = TuyaClient(config, http=http, clock=clock)

    await client.list_devices()
    await client.list_devices()
    assert fake_tuya.token_calls == 1

    clock.now += 7200 - 30  # inside the refresh margin
    await client.list_devices()
    assert fake_tuya.token_calls == 2
    assert fake_tuya.requests[-1].headers["access_token"].endswith("-2")


async def test_requests_are_signed(
    config: Config, fake_tuya: FakeTuya, http: httpx.AsyncClient, clock: FakeClock
) -> None:
    fake_tuya.route(DEVICES_PATH, lambda r: _devices_page([]))
    client = TuyaClient(config, http=http, clock=clock)
    await client.list_devices()

    token_req, devices_req = fake_tuya.requests
    for request, access_token in ((token_req, ""), (devices_req, "token-abc-123-1")):
        url = request.url.raw_path.decode()
        expected = sign(
            client_id="client-id",
            secret=SECRET,
            t=request.headers["t"],
            nonce=request.headers["nonce"],
            access_token=access_token,
            string_to_sign=string_to_sign(request.method, url, request.content),
        )
        assert request.headers["sign"] == expected
        assert request.headers["sign_method"] == "HMAC-SHA256"
        assert len(request.headers["t"]) == 13
    assert "access_token" not in token_req.headers
    assert token_req.url.raw_path == b"/v1.0/token?grant_type=1"


async def test_api_error_is_raised_with_code_and_msg(
    config: Config, fake_tuya: FakeTuya, http: httpx.AsyncClient, clock: FakeClock
) -> None:
    fake_tuya.route(
        DEVICES_PATH, lambda r: {"success": False, "code": 1106, "msg": "permission deny"}
    )
    client = TuyaClient(config, http=http, clock=clock)

    with pytest.raises(TuyaAPIError) as exc_info:
        await client.list_devices()
    assert exc_info.value.code == 1106
    assert "permission deny" in str(exc_info.value)


async def test_invalid_token_triggers_one_refresh_and_retry(
    config: Config, fake_tuya: FakeTuya, http: httpx.AsyncClient, clock: FakeClock
) -> None:
    def devices(request: httpx.Request) -> dict[str, Any]:
        if request.headers["access_token"].endswith("-1"):
            return {"success": False, "code": 1010, "msg": "token invalid"}
        return _devices_page([_device(1)])

    fake_tuya.route(DEVICES_PATH, devices)
    client = TuyaClient(config, http=http, clock=clock)

    assert len(await client.list_devices()) == 1
    assert fake_tuya.token_calls == 2


async def test_network_failure_raises_connection_error(config: Config, clock: FakeClock) -> None:
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("unreachable")

    http = httpx.AsyncClient(base_url=config.endpoint, transport=httpx.MockTransport(boom))
    client = TuyaClient(config, http=http, clock=clock)

    with pytest.raises(TuyaConnectionError, match="Could not reach"):
        await client.list_devices()
