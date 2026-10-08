import json

import pytest

from tuya_mcp.errors import InvalidValueError
from tuya_mcp.lighting import (
    LightCapabilities,
    Range,
    encode_colour,
    light_summary,
    require_hue,
    require_percent,
    switch_code,
)
from tuya_mcp.models import Specification

from .fixtures import LAMP_SPEC, PLUG_SPEC


@pytest.mark.parametrize(("percent", "expected"), [(0, 10), (100, 1000), (50, 505), (1, 20)])
def test_brightness_scale(percent: float, expected: int) -> None:
    assert Range(10, 1000).from_percent(percent) == expected


@pytest.mark.parametrize(("value", "expected"), [(10, 0), (1000, 100), (505, 50)])
def test_to_percent(value: int, expected: int) -> None:
    assert Range(10, 1000).to_percent(value) == expected


def test_capabilities_use_v2_codes_and_spec_ranges() -> None:
    caps = LightCapabilities.from_spec(Specification.from_api(LAMP_SPEC))
    assert caps.is_light
    assert caps.switch == "switch_led"
    assert caps.work_mode == "work_mode"
    assert caps.bright == ("bright_value_v2", Range(10, 1000))
    assert caps.temp == ("temp_value_v2", Range(0, 1000))
    assert caps.colour is not None
    assert caps.colour.code == "colour_data_v2"
    assert caps.colour.saturation == Range(0, 1000)


def test_legacy_codes_with_255_saturation() -> None:
    spec = Specification.from_api(
        {
            "category": "dj",
            "functions": [
                {"code": "bright_value", "type": "Integer", "values": '{"min":25,"max":255}'},
                {
                    "code": "colour_data",
                    "type": "Json",
                    "values": '{"h":{"min":0,"max":360},"s":{"min":0,"max":255},'
                    '"v":{"min":0,"max":255}}',
                },
            ],
        }
    )
    caps = LightCapabilities.from_spec(spec)
    assert caps.bright == ("bright_value", Range(25, 255))
    assert caps.colour is not None
    assert json.loads(encode_colour(caps.colour, 240, 100, 50)) == {"h": 240, "s": 255, "v": 128}


def test_encode_colour_is_compact_json_string() -> None:
    caps = LightCapabilities.from_spec(Specification.from_api(LAMP_SPEC))
    assert caps.colour is not None
    assert encode_colour(caps.colour, 240, 100, 50) == '{"h":240,"s":1000,"v":500}'
    assert encode_colour(caps.colour, 0, 0, 0) == '{"h":0,"s":0,"v":0}'
    assert encode_colour(caps.colour, 360, 100, 100) == '{"h":360,"s":1000,"v":1000}'


def test_plug_is_not_a_light_but_has_a_switch() -> None:
    spec = Specification.from_api(PLUG_SPEC)
    assert not LightCapabilities.from_spec(spec).is_light
    assert switch_code(spec) == "switch_1"


@pytest.mark.parametrize("value", [-1, 100.5, 250])
def test_percent_out_of_range(value: float) -> None:
    with pytest.raises(InvalidValueError, match="between 0 and 100"):
        require_percent("brightness", value)


@pytest.mark.parametrize("value", [-0.1, 361])
def test_hue_out_of_range(value: float) -> None:
    with pytest.raises(InvalidValueError, match="between 0 and 360"):
        require_hue(value)


def test_light_summary_in_friendly_scales() -> None:
    caps = LightCapabilities.from_spec(Specification.from_api(LAMP_SPEC))
    summary = light_summary(
        caps,
        {
            "switch_led": True,
            "work_mode": "colour",
            "bright_value_v2": 505,
            "temp_value_v2": 0,
            "colour_data_v2": '{"h":353,"s":1000,"v":500}',
        },
    )
    assert summary == {
        "on": True,
        "mode": "colour",
        "brightness": 50,
        "color_temperature": 0,
        "color": {"hue": 353, "saturation": 100, "brightness": 50},
    }
