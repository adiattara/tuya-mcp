"""Lighting capabilities discovered from a device specification, and scale conversions.

Agents speak in friendly scales (percent, 0-360 hue). Devices use their own
ranges (e.g. 10-1000 brightness), read from their specification rather than
hard-coded, since codes and ranges differ between models (``bright_value`` vs
``bright_value_v2``, saturation over 0-255 vs 0-1000...).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .errors import InvalidValueError, UnsupportedCommandError
from .models import DataPoint, Specification

SWITCH_CODES = ("switch_led", "switch", "switch_1")
BRIGHT_CODES = ("bright_value_v2", "bright_value")
TEMP_CODES = ("temp_value_v2", "temp_value")
COLOUR_CODES = ("colour_data_v2", "colour_data")
WORK_MODE_CODE = "work_mode"

# Used when a specification omits ranges.
DEFAULT_BRIGHT_RANGE = (10, 1000)
DEFAULT_TEMP_RANGE = (0, 1000)
DEFAULT_HUE_RANGE = (0, 360)
DEFAULT_SV_RANGE = (0, 1000)


@dataclass(frozen=True)
class Range:
    min: int
    max: int

    @classmethod
    def of(cls, values: dict[str, Any], default: tuple[int, int]) -> Range:
        try:
            return cls(int(values["min"]), int(values["max"]))
        except (KeyError, TypeError, ValueError):
            return cls(*default)

    def from_percent(self, percent: float) -> int:
        return round(self.min + percent / 100 * (self.max - self.min))

    def to_percent(self, value: float) -> int:
        if self.max == self.min:
            return 100
        return round((value - self.min) / (self.max - self.min) * 100)


@dataclass(frozen=True)
class ColourCapability:
    code: str
    hue: Range
    saturation: Range
    value: Range


@dataclass(frozen=True)
class LightCapabilities:
    switch: str | None
    work_mode: str | None
    bright: tuple[str, Range] | None
    temp: tuple[str, Range] | None
    colour: ColourCapability | None

    @property
    def is_light(self) -> bool:
        return self.bright is not None or self.colour is not None

    @classmethod
    def from_spec(cls, spec: Specification) -> LightCapabilities:
        functions = spec.functions
        bright = _first(functions, BRIGHT_CODES)
        temp = _first(functions, TEMP_CODES)
        colour = _first(functions, COLOUR_CODES)
        return cls(
            switch=switch_code(spec),
            work_mode=WORK_MODE_CODE if WORK_MODE_CODE in functions else None,
            bright=(bright.code, Range.of(bright.values, DEFAULT_BRIGHT_RANGE)) if bright else None,
            temp=(temp.code, Range.of(temp.values, DEFAULT_TEMP_RANGE)) if temp else None,
            colour=_colour(colour) if colour else None,
        )


def switch_code(spec: Specification) -> str | None:
    """The on/off code: a known one, else the only boolean function."""
    for code in SWITCH_CODES:
        if code in spec.functions:
            return code
    booleans = [dp.code for dp in spec.functions.values() if dp.type.lower() == "boolean"]
    switches = [code for code in booleans if code.startswith("switch")]
    return switches[0] if len(switches) == 1 else None


def require_percent(name: str, value: float) -> None:
    if not 0 <= value <= 100:
        raise InvalidValueError(f"{name} must be between 0 and 100, got {value}. Nothing was sent.")


def require_hue(value: float) -> None:
    if not 0 <= value <= 360:
        raise InvalidValueError(f"hue must be between 0 and 360, got {value}. Nothing was sent.")


def require(capability: Any, device_name: str, what: str) -> None:
    if capability is None:
        raise UnsupportedCommandError(
            f"{device_name!r} does not support {what}. "
            "Use tuya_get_device_specifications to see its codes, then tuya_send_command."
        )


def encode_colour(colour: ColourCapability, hue: float, saturation: float, value: float) -> str:
    """Tuya expects the colour as a compact JSON string."""
    payload = {
        "h": round(min(max(hue, colour.hue.min), colour.hue.max)),
        "s": colour.saturation.from_percent(saturation),
        "v": colour.value.from_percent(value),
    }
    return json.dumps(payload, separators=(",", ":"))


def decode_colour(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except ValueError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def light_summary(caps: LightCapabilities, status: dict[str, Any]) -> dict[str, Any]:
    """Status in the same friendly scales the lighting tools accept."""
    summary: dict[str, Any] = {}
    if caps.switch and caps.switch in status:
        summary["on"] = bool(status[caps.switch])
    if caps.work_mode and caps.work_mode in status:
        summary["mode"] = status[caps.work_mode]
    if caps.bright and caps.bright[0] in status:
        summary["brightness"] = caps.bright[1].to_percent(status[caps.bright[0]])
    if caps.temp and caps.temp[0] in status:
        summary["color_temperature"] = caps.temp[1].to_percent(status[caps.temp[0]])
    if caps.colour and caps.colour.code in status:
        hsv = decode_colour(status[caps.colour.code])
        if hsv and {"h", "s", "v"} <= hsv.keys():
            summary["color"] = {
                "hue": hsv["h"],
                "saturation": caps.colour.saturation.to_percent(hsv["s"]),
                "brightness": caps.colour.value.to_percent(hsv["v"]),
            }
    return summary


def _first(functions: dict[str, DataPoint], codes: tuple[str, ...]) -> DataPoint | None:
    return next((functions[code] for code in codes if code in functions), None)


def _colour(dp: DataPoint) -> ColourCapability:
    def part(key: str, default: tuple[int, int]) -> Range:
        values = dp.values.get(key)
        return Range.of(values if isinstance(values, dict) else {}, default)

    return ColourCapability(
        code=dp.code,
        hue=part("h", DEFAULT_HUE_RANGE),
        saturation=part("s", DEFAULT_SV_RANGE),
        value=part("v", DEFAULT_SV_RANGE),
    )
