"""MCP server exposing Tuya devices as tools (stdio transport)."""

from __future__ import annotations

import functools
import inspect
import logging
import sys
from collections.abc import Awaitable, Callable
from typing import Annotated, Any, ParamSpec, TypeVar

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from .client import TuyaClient
from .config import Config, ConfigError
from .errors import TuyaError
from .logging_utils import configure_logging
from .service import DeviceService

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")

DeviceArg = Annotated[
    str, Field(description="Device name as shown in the app (case-insensitive) or device id")
]
Percent = Annotated[float, Field(ge=0, le=100)]

INSTRUCTIONS = """\
Controls Tuya / Smart Life devices. Refer to devices by the name shown in the
app or by id. Light settings do not switch a light on: if a response contains a
note saying the light is off, call tuya_turn_on. For devices without a dedicated
tool, read tuya_get_device_specifications then use tuya_send_command."""


def _reported(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
    """Turn Tuya errors into tool errors whose message reaches the agent verbatim."""

    @functools.wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return await func(*args, **kwargs)
        except TuyaError as exc:
            raise ToolError(str(exc)) from exc

    wrapper.__doc__ = inspect.cleandoc(func.__doc__ or "")
    return wrapper


def build_server(client: TuyaClient) -> MCPServer:
    mcp = MCPServer("tuya", instructions=INSTRUCTIONS)
    service = DeviceService(client)

    # -- Discovery & state ------------------------------------------------

    @mcp.tool()
    @_reported
    async def tuya_list_devices() -> dict[str, Any]:
        """List every device of the linked Tuya / Smart Life account.

        Returns each device's id, name (as shown in the app), category and
        whether it is currently online.
        """
        return await service.list_devices()

    @mcp.tool()
    @_reported
    async def tuya_get_device_status(device: DeviceArg) -> dict[str, Any]:
        """Current state of a device (switches, brightness, colour...).

        Lights also get a `light` summary in the same scales the lighting
        tools accept (percent, hue 0-360).
        """
        return await service.get_status(device)

    @mcp.tool()
    @_reported
    async def tuya_get_device_info(device: DeviceArg) -> dict[str, Any]:
        """Model, product, firmware versions and other details of a device."""
        return await service.get_info(device)

    @mcp.tool()
    @_reported
    async def tuya_get_device_specifications(device: DeviceArg) -> dict[str, Any]:
        """Data point codes a device accepts (functions) and reports (status), with ranges.

        Use it before tuya_send_command.
        """
        return await service.get_specifications(device)

    # -- Basic control ----------------------------------------------------

    @mcp.tool()
    @_reported
    async def tuya_turn_on(device: DeviceArg) -> dict[str, Any]:
        """Switch a device on."""
        return await service.turn(device, True)

    @mcp.tool()
    @_reported
    async def tuya_turn_off(device: DeviceArg) -> dict[str, Any]:
        """Switch a device off."""
        return await service.turn(device, False)

    @mcp.tool()
    @_reported
    async def tuya_toggle(device: DeviceArg) -> dict[str, Any]:
        """Switch a device on if it is off, off if it is on."""
        return await service.turn(device, None)

    @mcp.tool()
    @_reported
    async def tuya_send_command(
        device: DeviceArg,
        code: Annotated[str, Field(description="Data point code, e.g. 'switch_1'")],
        value: Annotated[
            bool | int | float | str | dict[str, Any] | list[Any],
            Field(description="Value matching the code's type and range"),
        ],
    ) -> dict[str, Any]:
        """Send a raw data point command to any device.

        Escape hatch for devices or features without a dedicated tool. Read the
        accepted codes and ranges with tuya_get_device_specifications first.
        """
        return await service.send_command(device, code, value)

    # -- Lighting ---------------------------------------------------------

    @mcp.tool()
    @_reported
    async def tuya_set_brightness(
        device: DeviceArg,
        brightness: Annotated[
            Percent, Field(description="0-100 percent; 0 is the minimum, not off")
        ],
    ) -> dict[str, Any]:
        """Set a light's brightness.

        In colour mode the current colour is kept and only its intensity
        changes; otherwise the light switches to white mode. Does not switch
        the light on.
        """
        return await service.set_brightness(device, brightness)

    @mcp.tool()
    @_reported
    async def tuya_set_color_temperature(
        device: DeviceArg,
        temperature: Annotated[Percent, Field(description="0 = warm white, 100 = cold white")],
    ) -> dict[str, Any]:
        """Set a light's white temperature and switch it to white mode.

        Does not switch the light on.
        """
        return await service.set_color_temperature(device, temperature)

    @mcp.tool()
    @_reported
    async def tuya_set_color(
        device: DeviceArg,
        hue: Annotated[float, Field(ge=0, le=360, description="0-360: 0 red, 120 green, 240 blue")],
        saturation: Annotated[Percent, Field(description="0-100 percent; 0 is white")] = 100,
        brightness: Annotated[Percent, Field(description="0-100 percent")] = 100,
    ) -> dict[str, Any]:
        """Set a light's colour and switch it to colour mode.

        Does not switch the light on.
        """
        return await service.set_color(device, hue, saturation, brightness)

    # -- Scenes -----------------------------------------------------------

    @mcp.tool()
    @_reported
    async def tuya_list_scenes() -> dict[str, Any]:
        """List the tap-to-run scenes of the linked account, with their home."""
        return await service.list_scenes()

    @mcp.tool()
    @_reported
    async def tuya_trigger_scene(
        scene: Annotated[
            str, Field(description="Scene name as shown in the app (case-insensitive) or scene id")
        ],
    ) -> dict[str, Any]:
        """Run a tap-to-run scene."""
        return await service.trigger_scene(scene)

    return mcp


def main() -> None:
    try:
        config = Config.from_env()
    except ConfigError as exc:
        print(f"tuya-mcp: {exc}", file=sys.stderr)
        sys.exit(2)

    configure_logging(config.log_level)
    logger.info("Starting tuya-mcp against %s", config.endpoint)
    build_server(TuyaClient(config)).run()


if __name__ == "__main__":
    main()
