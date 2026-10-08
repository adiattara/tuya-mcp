# tuya-mcp

MCP server to control Tuya / Smart Life devices (e.g. LSC Smart Connect lamps)
through the official Tuya Cloud API.

> Work in progress.

**Setup:** follow the step-by-step [Tuya Cloud setup guide](docs/SETUP.md)
(developer account, cloud project, app linking, credentials, MCP client).

## Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `TUYA_ACCESS_ID` | yes | — | Access ID of your Tuya cloud project |
| `TUYA_ACCESS_SECRET` | yes | — | Access Secret (never logged) |
| `TUYA_UID` | yes | — | UID of the linked Tuya / Smart Life app account |
| `TUYA_API_ENDPOINT` | no | `https://openapi.tuyaeu.com` | Region endpoint |
| `TUYA_CACHE_TTL` | no | `60` | Device list cache, in seconds |
| `TUYA_LOG_LEVEL` | no | `WARNING` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

Region endpoints: EU `openapi.tuyaeu.com`, US `openapi.tuyaus.com`,
CN `openapi.tuyacn.com`, IN `openapi.tuyain.com`.

## Tools

| Tool | What it does |
|---|---|
| `tuya_list_devices` | List devices with id, name, category, online state |
| `tuya_get_device_status` | Current state; lights also get a friendly summary |
| `tuya_get_device_info` | Model, product, firmware versions |
| `tuya_get_device_specifications` | Data point codes and ranges |
| `tuya_turn_on` / `tuya_turn_off` / `tuya_toggle` | On / off for any device |
| `tuya_set_brightness` | 0-100 %; keeps the colour in colour mode |
| `tuya_set_color_temperature` | 0 = warm white, 100 = cold white |
| `tuya_set_color` | Hue 0-360, saturation and brightness 0-100 % |
| `tuya_list_scenes` / `tuya_trigger_scene` | Tap-to-run scenes |
| `tuya_send_command` | Raw data point command for anything else |

Devices and scenes are addressed by the name shown in the app
(case-insensitive) or by id.

## Run

From a checkout (the package is not on PyPI yet):

```bash
uv sync
uv run tuya-mcp
```

## Development

```bash
uv run pytest
uv run ruff check .
uv run mypy src tests
```

## License

MIT
