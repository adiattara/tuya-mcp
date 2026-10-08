from __future__ import annotations

from typing import Any

import httpx
import pytest

from tuya_mcp.client import HOMES_PATH, SCENE_TRIGGER_PATH, SCENES_PATH, TuyaClient
from tuya_mcp.config import Config
from tuya_mcp.errors import AmbiguousDeviceError, SceneNotFoundError, UnsupportedCommandError
from tuya_mcp.service import NO_SCENES_NOTE, DeviceService

from .conftest import FakeClock, FakeTuya

# Shapes captured from the real v2.0 scene API.
SCENES_BY_HOME: dict[str, list[dict[str, Any]]] = {
    "h1": [
        {"id": "s-on", "name": "mcp-tuya-on", "status": "enable", "type": "scene"},
        {"id": "s-off", "name": "mcp-tuya-off", "status": "enable", "type": "scene"},
        {"id": "a-1", "name": "Sunset automation", "status": "enable", "type": "automation"},
    ],
    "h2": [
        {"id": "s-cabin", "name": "Soirée", "status": "enable", "type": "scene"},
        {"id": "s-old", "name": "Old", "status": "disable", "type": "scene"},
    ],
}


@pytest.fixture
def scenes(fake_tuya: FakeTuya, config: Config) -> list[str]:
    triggered: list[str] = []
    fake_tuya.route(
        HOMES_PATH.format(uid=config.uid),
        lambda r: {
            "success": True,
            "result": [{"home_id": 1, "name": "Home"}, {"home_id": 2, "name": "Cabin"}],
        },
    )

    def rules(request: httpx.Request) -> dict[str, Any]:
        home = "h" + request.url.params["space_id"]
        return {"success": True, "result": {"has_more": False, "list": SCENES_BY_HOME[home]}}

    fake_tuya.route(SCENES_PATH, rules)
    for home in SCENES_BY_HOME.values():
        for rule in home:

            def trigger(request: httpx.Request, scene_id: str = rule["id"]) -> dict[str, Any]:
                triggered.append(scene_id)
                return {"success": True, "result": True}

            fake_tuya.route(SCENE_TRIGGER_PATH.format(scene_id=rule["id"]), trigger)
    return triggered


@pytest.fixture
def service(config: Config, http: httpx.AsyncClient, clock: FakeClock) -> DeviceService:
    return DeviceService(TuyaClient(config, http=http, clock=clock))


async def test_lists_tap_to_run_scenes_of_every_home(
    scenes: list[str], service: DeviceService
) -> None:
    result = await service.list_scenes()
    assert result["count"] == 4
    assert {(s["name"], s["home"]) for s in result["scenes"]} == {
        ("mcp-tuya-on", "Home"),
        ("mcp-tuya-off", "Home"),
        ("Soirée", "Cabin"),
        ("Old", "Cabin"),
    }
    assert "note" not in result


@pytest.mark.parametrize(
    ("query", "scene_id"), [("mcp-tuya-off", "s-off"), ("SOIRÉE", "s-cabin"), ("s-on", "s-on")]
)
async def test_trigger_by_name_or_id(
    scenes: list[str], service: DeviceService, query: str, scene_id: str
) -> None:
    result = await service.trigger_scene(query)
    assert scenes == [scene_id]
    assert result["triggered"] is True


async def test_unknown_scene_lists_names(scenes: list[str], service: DeviceService) -> None:
    with pytest.raises(SceneNotFoundError, match="mcp-tuya-on"):
        await service.trigger_scene("party")
    assert scenes == []


async def test_automations_cannot_be_triggered(scenes: list[str], service: DeviceService) -> None:
    with pytest.raises(SceneNotFoundError):
        await service.trigger_scene("Sunset automation")


async def test_disabled_scene_is_refused(scenes: list[str], service: DeviceService) -> None:
    with pytest.raises(UnsupportedCommandError, match="disabled"):
        await service.trigger_scene("old")
    assert scenes == []


async def test_ambiguous_scene(scenes: list[str], service: DeviceService) -> None:
    SCENES_BY_HOME["h2"].append({"id": "dup", "name": "MCP-TUYA-ON", "type": "scene"})
    try:
        with pytest.raises(AmbiguousDeviceError, match="Several scenes"):
            await service.trigger_scene("mcp-tuya-on")
    finally:
        SCENES_BY_HOME["h2"].pop()
    assert scenes == []


async def test_no_scenes(fake_tuya: FakeTuya, config: Config, service: DeviceService) -> None:
    fake_tuya.route(
        HOMES_PATH.format(uid=config.uid),
        lambda r: {"success": True, "result": [{"home_id": 1, "name": "Home"}]},
    )
    fake_tuya.route(SCENES_PATH, lambda r: {"success": True, "result": {"list": []}})

    assert (await service.list_scenes())["note"] == NO_SCENES_NOTE
    with pytest.raises(SceneNotFoundError, match="Tap-to-Run"):
        await service.trigger_scene("anything")
