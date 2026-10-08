import pytest

from tuya_mcp.errors import AmbiguousDeviceError, DeviceNotFoundError
from tuya_mcp.models import Device
from tuya_mcp.resolver import resolve_device

DEVICES = [
    Device(id="a1", name="Salon Lamp", category="dj", online=True),
    Device(id="b2", name="Bedroom", category="dj", online=True),
    Device(id="c3", name="Twin", category="dj", online=True),
    Device(id="d4", name="twin", category="cz", online=False),
]


@pytest.mark.parametrize("query", ["Salon Lamp", "salon lamp", "SALON LAMP", "  salon lamp ", "a1"])
def test_resolves_name_case_insensitively_or_id(query: str) -> None:
    assert resolve_device(query, DEVICES).id == "a1"


def test_unknown_name_lists_available_devices() -> None:
    with pytest.raises(DeviceNotFoundError) as exc_info:
        resolve_device("kitchen", DEVICES)
    message = str(exc_info.value)
    assert "'Salon Lamp'" in message
    assert "'Bedroom'" in message


def test_no_partial_match() -> None:
    with pytest.raises(DeviceNotFoundError):
        resolve_device("salon", DEVICES)


def test_ambiguous_name_lists_candidates() -> None:
    with pytest.raises(AmbiguousDeviceError) as exc_info:
        resolve_device("TWIN", DEVICES)
    message = str(exc_info.value)
    assert "c3" in message
    assert "d4" in message
    assert "Nothing was sent" in message


def test_empty_account() -> None:
    with pytest.raises(DeviceNotFoundError, match="Available devices: none"):
        resolve_device("x", [])
