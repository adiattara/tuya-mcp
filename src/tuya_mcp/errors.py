"""Errors surfaced to the MCP client."""

from __future__ import annotations


class TuyaError(Exception):
    """Base class for every error reported by this server."""


class TuyaAPIError(TuyaError):
    """The Tuya Cloud answered with ``success: false``.

    The message explains the cause and the fix when the code is known, and
    always ends with the raw Tuya code and message.
    """

    def __init__(self, code: int | str | None, msg: str | None) -> None:
        self.code = code
        self.msg = msg or "unknown error"
        raw = f"Tuya API error {code}: {self.msg}"
        hint = explain(code, self.msg)
        super().__init__(f"{hint} ({raw})" if hint else raw)


class TuyaConnectionError(TuyaError):
    """The Tuya Cloud could not be reached or returned an unreadable response."""


class DeviceNotFoundError(TuyaError):
    """No device matches the requested name or id."""


class AmbiguousDeviceError(TuyaError):
    """Several devices (or scenes) share the requested name."""


class SceneNotFoundError(TuyaError):
    """No scene matches the requested name or id."""


class DeviceOfflineError(TuyaError):
    """The device is offline and cannot receive commands."""


class UnsupportedCommandError(TuyaError):
    """The device does not expose the capability the command needs."""


class InvalidValueError(TuyaError):
    """A value is outside its accepted range. Nothing was sent."""


# -- Tuya error catalog ------------------------------------------------------
# Reference: https://developer.tuya.com/en/docs/iot/error-code?id=K989ruxx88swc

_PROJECT = "iot.tuya.com > Cloud > Development > your project"

_TRIAL = (
    "Your Tuya cloud plan or IoT Core trial has expired or is not subscribed. "
    f"Renew it for free: {_PROJECT} > Service API > IoT Core > Extend Trial Period. "
    "Your Access ID and Secret stay the same."
)
_SECRET = (
    "TUYA_ACCESS_SECRET is wrong. Re-copy the Access Secret from "
    f"{_PROJECT} > Overview > Authorization Key (no quotes, no trailing space)."
)
_CLIENT_ID = (
    "TUYA_ACCESS_ID is wrong, or TUYA_API_ENDPOINT does not match your project's "
    f"data center. Check {_PROJECT} > Overview, and use https://openapi.tuyaeu.com for "
    "Central/Western Europe, openapi.tuyaus.com for America, openapi.tuyacn.com for "
    "China, openapi.tuyain.com for India."
)
_REGION = (
    "This request reached the wrong Tuya data center. Set TUYA_API_ENDPOINT to the "
    "data center of your cloud project."
)
_TOKEN = (
    "Tuya rejected the access token even after a refresh. Restart the server; if it "
    "persists, check TUYA_ACCESS_ID and TUYA_ACCESS_SECRET."
)
_CLOCK = (
    "Tuya rejected the request timestamp. This computer's clock is wrong: enable "
    "automatic time synchronisation."
)
_PERMISSION = (
    "Permission denied by Tuya. Either the IoT Core service is not authorized for "
    f"your cloud project or its free trial expired ({_PROJECT} > Service API > IoT Core "
    "> Extend Trial Period), or this device is not linked to the project "
    f"({_PROJECT} > Devices > Link App Account: the Associated column must not be 0)."
)
_API_NOT_AUTHORIZED = (
    "Your cloud project is not authorized to use this API. Add the missing service in "
    f"{_PROJECT} > Service API (scenes need 'Smart Home Scene Linkage', devices need "
    "'IoT Core')."
)
_BUSY = "Tuya is busy or rate-limiting requests. Wait a few seconds and retry."
_IP = (
    "Your cloud project has an IP allowlist and this computer's IP is not on it. "
    f"Update it in {_PROJECT}, or disable the allowlist."
)
_OFFLINE = (
    "The device is offline: check that it is powered and connected to Wi-Fi. Nothing was executed."
)
_UNSUPPORTED = (
    "The device does not accept this command or value. Check the codes and ranges "
    "with tuya_get_device_specifications."
)
_NO_DEVICE = (
    "Tuya does not know this device for your project. It may have been removed from "
    "the app, or is not linked to the cloud project (Devices > Link App Account)."
)
_NO_SCENE = "This scene no longer exists. List the current ones with tuya_list_scenes."
_UNSUPPORTED_API = (
    "This Tuya API is not available for your project or region. Please report it at "
    "the project's issue tracker."
)

_BY_CODE: dict[int, str] = {
    1001: _SECRET,
    1004: _SECRET,
    1005: _CLIENT_ID,
    1010: _TOKEN,
    1011: _TOKEN,
    1012: _TOKEN,
    1400: _TOKEN,
    1013: _CLOCK,
    1101: _UNSUPPORTED,
    1103: _UNSUPPORTED,
    1106: _PERMISSION,
    1108: _UNSUPPORTED_API,
    1109: _UNSUPPORTED,
    500: _BUSY,
    1110: _BUSY,
    1111: _BUSY,
    1113: _BUSY,
    1199: _BUSY,
    1114: _IP,
    2001: _OFFLINE,
    2003: _UNSUPPORTED,
    2008: _UNSUPPORTED,
    2010: _NO_DEVICE,
    28841001: _TRIAL,
    28841002: _TRIAL,
    28841003: _TRIAL,
    28841004: _TRIAL,
    28841101: _TRIAL,
    28841102: _TRIAL,
    28841103: _TRIAL,
    28841104: _TRIAL,
    28841106: _TRIAL,
    28841105: _API_NOT_AUTHORIZED,
    60009001: _API_NOT_AUTHORIZED,
    40000003: _UNSUPPORTED,
    40000308: _UNSUPPORTED,
    40000801: _OFFLINE,
    40000901: _NO_DEVICE,
    40003904: _NO_SCENE,
}

# Some codes are reused with different meanings: the message decides.
_BY_MESSAGE: tuple[tuple[str, str], ...] = (
    ("clientid", _CLIENT_ID),  # seen live as 2009 "clientId is invalid"
    ("cross-region", _REGION),  # 2007 "IP cross-region"
    ("secret invalid", _SECRET),
    ("sign invalid", _SECRET),
    ("permission deny", _PERMISSION),
    ("device is offline", _OFFLINE),
)


def explain(code: int | str | None, msg: str) -> str | None:
    """Plain-language cause and fix for a Tuya error, or None if unknown."""
    lowered = msg.lower()
    for fragment, hint in _BY_MESSAGE:
        if fragment in lowered:
            return hint
    try:
        return _BY_CODE.get(int(code))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
