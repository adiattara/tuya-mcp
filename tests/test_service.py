from __future__ import annotations

import json
from collections.abc import Awaitable, Callable

import httpx
import pytest

from tuya_mcp.client import COMMANDS_PATH, DEVICES_PATH, TuyaClient
from tuya_mcp.config import Config
from tuya_mcp.errors import (
    AmbiguousDeviceError,
    DeviceNotFoundError,
    DeviceOfflineError,
    InvalidValueError,
    UnsupportedCommandError,
)
from tuya_mcp.service import LIGHT_OFF_NOTE, DeviceService

from .conftest import FakeClock, FakeTuya
from .fixtures import LAMP_ID, PLUG_ID, FakeHome


@pytest.fixture
def home(fake_tuya: FakeTuya) -> FakeHome:
    return FakeHome(fake_tuya)


@pytest.fixture
def service(config: Config, http: httpx.AsyncClient, clock: FakeClock) -> DeviceService:
    return DeviceService(TuyaClient(config, http=http, clock=clock))


def _paths(tuya: FakeTuya, path: str) -> int:
    return sum(1 for r in tuya.requests if r.url.path == path)


# -- Resolution & cache -----------------------------------------------------


async def test_device_list_is_cached_for_ttl(
    home: FakeHome, service: DeviceService, fake_tuya: FakeTuya, clock: FakeClock
) -> None:
    await service.get_status("salon lamp")
    await service.get_status("Salon Lamp")
    assert _paths(fake_tuya, DEVICES_PATH) == 1

    clock.now += 61
    await service.get_status(LAMP_ID)
    assert _paths(fake_tuya, DEVICES_PATH) == 2


async def test_new_device_found_without_restart(home: FakeHome, service: DeviceService) -> None:
    await service.get_status("Salon Lamp")  # warms the cache
    home.devices.append({"id": "new1", "name": "Kitchen", "category": "dj", "online": True})
    home.specs["new1"] = home.specs[LAMP_ID]
    home.state["new1"] = {}
    from tuya_mcp.client import SPECIFICATION_PATH, STATUS_PATH

    home.tuya.route(STATUS_PATH.format(device_id="new1"), lambda r: {"success": True, "result": []})
    home.tuya.route(
        SPECIFICATION_PATH.format(device_id="new1"),
        lambda r: {"success": True, "result": home.specs["new1"]},
    )

    assert (await service.get_status("kitchen"))["id"] == "new1"


async def test_unknown_and_ambiguous_names(
    home: FakeHome, service: DeviceService, clock: FakeClock
) -> None:
    with pytest.raises(DeviceNotFoundError, match="Salon Lamp"):
        await service.turn("garage", True)

    clock.now += 61  # let the cached list expire
    home.devices.append({"id": "dup", "name": "salon lamp", "category": "dj", "online": True})
    with pytest.raises(AmbiguousDeviceError):
        await service.turn("Salon Lamp", True)
    assert home.commands == []


# -- Reading ----------------------------------------------------------------


async def test_status_includes_light_summary(home: FakeHome, service: DeviceService) -> None:
    result = await service.get_status("Salon Lamp")
    assert result["status"]["switch_led"] is True
    assert result["light"] == {
        "on": True,
        "mode": "white",
        "brightness": 100,
        "color_temperature": 50,
        "color": {"hue": 240, "saturation": 100, "brightness": 100},
    }


async def test_plug_status_has_no_light_summary(home: FakeHome, service: DeviceService) -> None:
    assert "light" not in await service.get_status("Desk Plug")


async def test_specifications(home: FakeHome, service: DeviceService) -> None:
    result = await service.get_specifications("Salon Lamp")
    codes = [f["code"] for f in result["functions"]]
    assert "bright_value_v2" in codes
    assert result["functions"][2]["values"] == {"min": 10, "max": 1000, "scale": 0, "step": 1}


async def test_info_hides_private_fields_and_tolerates_missing_firmware(
    home: FakeHome, service: DeviceService, fake_tuya: FakeTuya
) -> None:
    fake_tuya.route(
        f"/v1.0/iot-03/devices/{LAMP_ID}",
        lambda r: {
            "success": True,
            "result": {
                "id": LAMP_ID,
                "model": "5325001600",
                "local_key": "secret",
                "ip": "1.2.3.4",
            },
        },
    )
    fake_tuya.route(
        f"/v2.0/cloud/thing/{LAMP_ID}/firmware",
        lambda r: {"success": False, "code": 1106, "msg": "permission deny"},
    )
    info = await service.get_info("Salon Lamp")
    assert info["model"] == "5325001600"
    assert "local_key" not in info
    assert "ip" not in info
    assert info["firmware"] == "not available for this device"


# -- On / off ---------------------------------------------------------------


async def test_turn_on_off_toggle(home: FakeHome, service: DeviceService) -> None:
    await service.turn("Salon Lamp", False)
    assert home.last_commands() == [{"code": "switch_led", "value": False}]

    await service.turn("Desk Plug", True)
    assert home.last_commands() == [{"code": "switch_1", "value": True}]

    await service.turn("Desk Plug", None)
    assert home.last_commands() == [{"code": "switch_1", "value": False}]


async def test_offline_device_is_refused(home: FakeHome, service: DeviceService) -> None:
    home.devices[0]["online"] = False
    with pytest.raises(DeviceOfflineError, match="offline"):
        await service.turn("Salon Lamp", True)
    assert home.commands == []


async def test_device_back_online_is_not_refused_from_stale_cache(
    home: FakeHome, service: DeviceService
) -> None:
    home.devices[0]["online"] = False
    await service.get_status("Salon Lamp")  # caches offline
    home.devices[0]["online"] = True
    await service.turn("Salon Lamp", True)
    assert home.last_commands() == [{"code": "switch_led", "value": True}]


async def test_device_without_switch(home: FakeHome, service: DeviceService) -> None:
    home.specs[PLUG_ID] = {"category": "wsdcg", "functions": []}
    with pytest.raises(UnsupportedCommandError, match="tuya_send_command"):
        await service.turn("Desk Plug", True)


# -- Generic command --------------------------------------------------------


async def test_send_command(home: FakeHome, service: DeviceService, fake_tuya: FakeTuya) -> None:
    await service.send_command("Desk Plug", "countdown_1", 60)
    assert home.last_commands() == [{"code": "countdown_1", "value": 60}]
    request = fake_tuya.requests[-1]
    assert request.url.path == COMMANDS_PATH.format(device_id=PLUG_ID)
    assert json.loads(request.content) == {"commands": [{"code": "countdown_1", "value": 60}]}


async def test_send_command_serializes_json_values(home: FakeHome, service: DeviceService) -> None:
    await service.send_command("Salon Lamp", "colour_data_v2", {"h": 1, "s": 2, "v": 3})
    assert home.last_commands() == [{"code": "colour_data_v2", "value": '{"h":1,"s":2,"v":3}'}]


async def test_send_command_unknown_code(home: FakeHome, service: DeviceService) -> None:
    with pytest.raises(UnsupportedCommandError, match="switch_1"):
        await service.send_command("Desk Plug", "switch_led", True)
    assert home.commands == []


# -- Lighting ---------------------------------------------------------------


async def test_brightness_in_white_mode(home: FakeHome, service: DeviceService) -> None:
    result = await service.set_brightness("Salon Lamp", 50)
    assert home.last_commands() == [
        {"code": "work_mode", "value": "white"},
        {"code": "bright_value_v2", "value": 505},
    ]
    assert "note" not in result


async def test_brightness_zero_is_minimum_not_off(home: FakeHome, service: DeviceService) -> None:
    await service.set_brightness("Salon Lamp", 0)
    assert {"code": "bright_value_v2", "value": 10} in home.last_commands()
    assert all(c["code"] != "switch_led" for c in home.last_commands())


async def test_brightness_in_colour_mode_keeps_colour(
    home: FakeHome, service: DeviceService
) -> None:
    home.state[LAMP_ID]["work_mode"] = "colour"
    home.state[LAMP_ID]["colour_data_v2"] = '{"h":240,"s":800,"v":1000}'
    await service.set_brightness("Salon Lamp", 50)
    assert home.last_commands() == [
        {"code": "colour_data_v2", "value": '{"h":240,"s":800,"v":500}'}
    ]


async def test_color_temperature(home: FakeHome, service: DeviceService) -> None:
    await service.set_color_temperature("Salon Lamp", 0)
    assert home.last_commands() == [
        {"code": "work_mode", "value": "white"},
        {"code": "temp_value_v2", "value": 0},
    ]


async def test_color(home: FakeHome, service: DeviceService) -> None:
    await service.set_color("Salon Lamp", 240, 100, 50)
    assert home.last_commands() == [
        {"code": "work_mode", "value": "colour"},
        {"code": "colour_data_v2", "value": '{"h":240,"s":1000,"v":500}'},
    ]


async def test_light_off_is_reported_not_switched_on(
    home: FakeHome, service: DeviceService
) -> None:
    home.state[LAMP_ID]["switch_led"] = False
    result = await service.set_color("Salon Lamp", 120, 100, 100)
    assert result["note"] == LIGHT_OFF_NOTE
    assert all(c["code"] != "switch_led" for c in home.last_commands())


@pytest.mark.parametrize(
    ("call", "match"),
    [
        (lambda s: s.set_brightness("Salon Lamp", 101), "between 0 and 100"),
        (lambda s: s.set_color_temperature("Salon Lamp", -5), "between 0 and 100"),
        (lambda s: s.set_color("Salon Lamp", 400, 50, 50), "between 0 and 360"),
        (lambda s: s.set_color("Salon Lamp", 10, 150, 50), "between 0 and 100"),
    ],
)
async def test_out_of_range_sends_nothing(
    home: FakeHome,
    service: DeviceService,
    fake_tuya: FakeTuya,
    call: Callable[[DeviceService], Awaitable[object]],
    match: str,
) -> None:
    with pytest.raises(InvalidValueError, match=match):
        await call(service)
    assert fake_tuya.requests == []


async def test_lighting_on_non_light_is_refused(home: FakeHome, service: DeviceService) -> None:
    with pytest.raises(UnsupportedCommandError, match="not a light"):
        await service.set_brightness("Desk Plug", 50)
    assert home.commands == []


# -- Devices that report their state late (real LSC lamp behaviour) ---------


@pytest.fixture
def lagging_home(home: FakeHome, fake_tuya: FakeTuya) -> FakeHome:
    """Commands are executed but the cloud status never changes."""
    from tuya_mcp.client import COMMANDS_PATH

    def ignore_state(request: httpx.Request) -> dict[str, object]:
        home.commands.append((LAMP_ID, json.loads(request.content)["commands"]))
        return {"success": True, "result": True}

    fake_tuya.route(COMMANDS_PATH.format(device_id=LAMP_ID), ignore_state)
    return home


async def test_toggle_twice_with_lagging_status(
    lagging_home: FakeHome, service: DeviceService
) -> None:
    await service.turn("Salon Lamp", None)
    await service.turn("Salon Lamp", None)
    assert [c[1][0]["value"] for c in lagging_home.commands] == [False, True]


async def test_status_reflects_sent_values_until_ttl(
    lagging_home: FakeHome, service: DeviceService, clock: FakeClock
) -> None:
    await service.turn("Salon Lamp", False)
    assert (await service.get_status("Salon Lamp"))["light"]["on"] is False

    clock.now += 301
    assert (await service.get_status("Salon Lamp"))["light"]["on"] is True


async def test_brightness_in_colour_mode_uses_sent_colour(
    lagging_home: FakeHome, service: DeviceService
) -> None:
    await service.set_color("Salon Lamp", 120, 100, 100)
    await service.set_brightness("Salon Lamp", 50)
    assert lagging_home.commands[-1][1] == [
        {"code": "colour_data_v2", "value": '{"h":120,"s":1000,"v":500}'}
    ]


async def test_change_made_in_app_wins_over_sent_value(
    lagging_home: FakeHome, service: DeviceService
) -> None:
    await service.get_status("Salon Lamp")
    await service.turn("Salon Lamp", False)
    lagging_home.state[LAMP_ID]["work_mode"] = "colour"  # unrelated change
    assert (await service.get_status("Salon Lamp"))["light"]["on"] is False

    lagging_home.state[LAMP_ID]["switch_led"] = "app-changed"  # cloud now reports a new value
    status = await service.get_status("Salon Lamp")
    assert status["status"]["switch_led"] == "app-changed"


async def test_off_note_after_turning_off_with_lagging_status(
    lagging_home: FakeHome, service: DeviceService
) -> None:
    await service.turn("Salon Lamp", False)
    result = await service.set_color("Salon Lamp", 240, 100, 100)
    assert result["note"] == LIGHT_OFF_NOTE
