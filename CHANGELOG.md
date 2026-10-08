# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- MCP server over stdio, configured with environment variables only.
- Tuya Cloud OpenAPI client: HMAC-SHA256 signing (tested against the official
  vectors), cached access token with automatic refresh, secrets redacted from
  every log.
- Discovery tools: `tuya_list_devices`, `tuya_get_device_status`,
  `tuya_get_device_info`, `tuya_get_device_specifications`.
- Control tools: `tuya_turn_on`, `tuya_turn_off`, `tuya_toggle`,
  `tuya_send_command`.
- Lighting tools: `tuya_set_brightness`, `tuya_set_color_temperature`,
  `tuya_set_color`. Data point codes and ranges are read from each device's
  specification (`*_v2` and legacy codes, 0-255 and 0-1000 scales).
- Scene tools: `tuya_list_scenes`, `tuya_trigger_scene`.
- Devices are addressed by their app name (case-insensitive) or id.
- Recently sent values override the cloud status for devices that report
  their state late (e.g. LSC Smart Connect lamps).
- Plain-language explanations for Tuya error codes.
- Step-by-step setup guide in `docs/SETUP.md`.
