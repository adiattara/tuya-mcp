import pytest

from tuya_mcp.errors import TuyaAPIError, explain


@pytest.mark.parametrize(
    ("code", "msg", "expected"),
    [
        (1106, "permission deny", "Extend Trial Period"),
        (1106, "permission deny", "Link App Account"),
        (28841002, "Cloud development plan expired", "Access ID and Secret stay the same"),
        (28841004, "Trial Edition quota is exhausted", "Extend Trial Period"),
        (28841105, "Project is not authorized to use this API", "Smart Home Scene Linkage"),
        (2009, "clientId is invalid", "TUYA_ACCESS_ID"),
        (1005, "clientId invalid", "TUYA_API_ENDPOINT"),
        (1004, "sign invalid", "TUYA_ACCESS_SECRET"),
        (1001, "secret invalid", "TUYA_ACCESS_SECRET"),
        (1013, "request time is invalid", "clock"),
        (2007, "IP cross-region", "data center"),
        (2001, "device is offline", "Wi-Fi"),
        (40000801, "Device offline", "Wi-Fi"),
        (2008, "command or value not support", "tuya_get_device_specifications"),
        (1199, "your requests are too frequent", "retry"),
        ("1106", "permission deny", "IoT Core"),
    ],
)
def test_known_errors_are_explained(code: int | str, msg: str, expected: str) -> None:
    hint = explain(code, msg)
    assert hint is not None
    assert expected in hint


def test_message_keeps_raw_code_for_known_errors() -> None:
    message = str(TuyaAPIError(1106, "permission deny"))
    assert message.startswith("Permission denied by Tuya.")
    assert message.endswith("(Tuya API error 1106: permission deny)")


@pytest.mark.parametrize(("code", "msg"), [(99999, "something new"), (None, "boom"), ("x", "?")])
def test_unknown_errors_stay_raw(code: int | str | None, msg: str) -> None:
    assert explain(code, msg) is None
    assert str(TuyaAPIError(code, msg)) == f"Tuya API error {code}: {msg}"
