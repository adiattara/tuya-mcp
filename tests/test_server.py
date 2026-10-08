from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from mcp.server.mcpserver.exceptions import ToolError

from tuya_mcp.client import DEVICES_PATH, TuyaClient
from tuya_mcp.config import Config
from tuya_mcp.server import build_server

from .conftest import FakeClock, FakeTuya
from .fixtures import FakeHome

EXPECTED_TOOLS = {
    "tuya_list_devices",
    "tuya_get_device_status",
    "tuya_get_device_info",
    "tuya_get_device_specifications",
    "tuya_turn_on",
    "tuya_turn_off",
    "tuya_toggle",
    "tuya_send_command",
    "tuya_set_brightness",
    "tuya_set_color_temperature",
    "tuya_set_color",
    "tuya_list_scenes",
    "tuya_trigger_scene",
}


async def test_all_tools_are_exposed_with_clean_descriptions(
    config: Config, http: httpx.AsyncClient, clock: FakeClock
) -> None:
    mcp = build_server(TuyaClient(config, http=http, clock=clock))
    tools = {tool.name: tool for tool in await mcp.list_tools()}
    assert set(tools) >= EXPECTED_TOOLS
    for tool in tools.values():
        assert tool.description
        assert "\n        " not in tool.description


async def test_list_devices_tool(
    config: Config, fake_tuya: FakeTuya, http: httpx.AsyncClient, clock: FakeClock
) -> None:
    fake_tuya.route(
        DEVICES_PATH,
        lambda r: {
            "success": True,
            "result": {
                "devices": [{"id": "d1", "name": "Salon", "category": "dj", "online": True}]
            },
        },
    )
    mcp = build_server(TuyaClient(config, http=http, clock=clock))

    result: Any = await mcp.call_tool("tuya_list_devices", {})
    assert not result.is_error
    assert json.loads(result.content[0].text) == {
        "count": 1,
        "devices": [{"id": "d1", "name": "Salon", "category": "dj", "online": True}],
    }


async def test_set_color_tool_end_to_end(
    config: Config, fake_tuya: FakeTuya, http: httpx.AsyncClient, clock: FakeClock
) -> None:
    home = FakeHome(fake_tuya)
    mcp = build_server(TuyaClient(config, http=http, clock=clock))

    result: Any = await mcp.call_tool("tuya_set_color", {"device": "salon lamp", "hue": 240})
    assert not result.is_error
    assert home.last_commands()[-1] == {
        "code": "colour_data_v2",
        "value": '{"h":240,"s":1000,"v":1000}',
    }


async def test_out_of_range_rejected_by_schema(
    config: Config, fake_tuya: FakeTuya, http: httpx.AsyncClient, clock: FakeClock
) -> None:
    FakeHome(fake_tuya)
    mcp = build_server(TuyaClient(config, http=http, clock=clock))
    with pytest.raises(ToolError):
        await mcp.call_tool("tuya_set_brightness", {"device": "Salon Lamp", "brightness": 150})
    assert fake_tuya.requests == []


async def test_tuya_errors_reach_the_agent_as_tool_errors(
    config: Config, fake_tuya: FakeTuya, http: httpx.AsyncClient, clock: FakeClock
) -> None:
    fake_tuya.route(
        DEVICES_PATH, lambda r: {"success": False, "code": 1106, "msg": "permission deny"}
    )
    mcp = build_server(TuyaClient(config, http=http, clock=clock))

    with pytest.raises(ToolError, match="permission deny"):
        await mcp.call_tool("tuya_list_devices", {})


async def test_unknown_device_message_reaches_agent(
    config: Config, fake_tuya: FakeTuya, http: httpx.AsyncClient, clock: FakeClock
) -> None:
    FakeHome(fake_tuya)
    mcp = build_server(TuyaClient(config, http=http, clock=clock))
    with pytest.raises(ToolError, match="Available devices"):
        await mcp.call_tool("tuya_turn_on", {"device": "garage"})
