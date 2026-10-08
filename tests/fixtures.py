"""Payloads modelled on a real LSC Smart Connect lamp (category dj, *_v2 codes)."""

from __future__ import annotations

import json
from typing import Any

import httpx

from tuya_mcp.client import COMMANDS_PATH, DEVICES_PATH, SPECIFICATION_PATH, STATUS_PATH

from .conftest import FakeTuya

LAMP_ID = "lamp1"
PLUG_ID = "plug1"

LAMP_SPEC: dict[str, Any] = {
    "category": "dj",
    "functions": [
        {"code": "switch_led", "type": "Boolean", "values": "{}"},
        {
            "code": "work_mode",
            "type": "Enum",
            "values": '{"range":["white","colour","scene","music"]}',
        },
        {
            "code": "bright_value_v2",
            "type": "Integer",
            "values": '{"min":10,"max":1000,"scale":0,"step":1}',
        },
        {
            "code": "temp_value_v2",
            "type": "Integer",
            "values": '{"min":0,"max":1000,"scale":0,"step":1}',
        },
        {
            "code": "colour_data_v2",
            "type": "Json",
            "values": '{"h":{"min":0,"max":360},"s":{"min":0,"max":1000},"v":{"min":0,"max":1000}}',
        },
        {
            "code": "countdown_1",
            "type": "Integer",
            "values": '{"unit":"s","min":0,"max":86400,"scale":0,"step":1}',
        },
    ],
    "status": [],
}

PLUG_SPEC: dict[str, Any] = {
    "category": "cz",
    "functions": [
        {"code": "switch_1", "type": "Boolean", "values": "{}"},
        {"code": "countdown_1", "type": "Integer", "values": '{"min":0,"max":86400}'},
    ],
    "status": [],
}


class FakeHome:
    """A stateful lamp and plug behind the fake Tuya cloud."""

    def __init__(self, tuya: FakeTuya) -> None:
        self.tuya = tuya
        self.devices: list[dict[str, Any]] = [
            {"id": LAMP_ID, "name": "Salon Lamp", "category": "dj", "online": True},
            {"id": PLUG_ID, "name": "Desk Plug", "category": "cz", "online": True},
        ]
        self.specs = {LAMP_ID: LAMP_SPEC, PLUG_ID: PLUG_SPEC}
        self.state: dict[str, dict[str, Any]] = {
            LAMP_ID: {
                "switch_led": True,
                "work_mode": "white",
                "bright_value_v2": 1000,
                "temp_value_v2": 500,
                "colour_data_v2": '{"h":240,"s":1000,"v":1000}',
            },
            PLUG_ID: {"switch_1": False},
        }
        self.commands: list[tuple[str, list[dict[str, Any]]]] = []
        tuya.route(DEVICES_PATH, lambda r: {"success": True, "result": {"devices": self.devices}})
        for device_id in self.specs:
            tuya.route(SPECIFICATION_PATH.format(device_id=device_id), self._spec)
            tuya.route(STATUS_PATH.format(device_id=device_id), self._status)
            tuya.route(COMMANDS_PATH.format(device_id=device_id), self._command)

    @staticmethod
    def _device_id(request: httpx.Request) -> str:
        return request.url.path.split("/")[4]

    def _spec(self, request: httpx.Request) -> dict[str, Any]:
        return {"success": True, "result": self.specs[self._device_id(request)]}

    def _status(self, request: httpx.Request) -> dict[str, Any]:
        state = self.state[self._device_id(request)]
        return {"success": True, "result": [{"code": k, "value": v} for k, v in state.items()]}

    def _command(self, request: httpx.Request) -> dict[str, Any]:
        device_id = self._device_id(request)
        commands = json.loads(request.content)["commands"]
        self.commands.append((device_id, commands))
        for command in commands:
            self.state[device_id][command["code"]] = command["value"]
        return {"success": True, "result": True}

    def last_commands(self) -> list[dict[str, Any]]:
        return self.commands[-1][1]
