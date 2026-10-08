"""Configuration loaded exclusively from environment variables."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

DEFAULT_ENDPOINT = "https://openapi.tuyaeu.com"
DEFAULT_CACHE_TTL = 60
DEFAULT_LOG_LEVEL = "WARNING"

REQUIRED_VARS = ("TUYA_ACCESS_ID", "TUYA_ACCESS_SECRET", "TUYA_UID")


class ConfigError(Exception):
    """Raised when the environment does not provide a usable configuration."""


@dataclass(frozen=True)
class Config:
    access_id: str
    access_secret: str = field(repr=False)
    uid: str
    endpoint: str = DEFAULT_ENDPOINT
    cache_ttl: int = DEFAULT_CACHE_TTL
    log_level: str = DEFAULT_LOG_LEVEL

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Config:
        env = os.environ if env is None else env
        values = {name: env.get(name, "").strip() for name in REQUIRED_VARS}
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise ConfigError(
                "Missing required environment variable(s): "
                + ", ".join(missing)
                + ". See the README setup section to obtain them from iot.tuya.com."
            )

        return cls(
            access_id=values["TUYA_ACCESS_ID"],
            access_secret=values["TUYA_ACCESS_SECRET"],
            uid=values["TUYA_UID"],
            endpoint=_parse_endpoint(env.get("TUYA_API_ENDPOINT", "")),
            cache_ttl=_parse_cache_ttl(env.get("TUYA_CACHE_TTL", "")),
            log_level=_parse_log_level(env.get("TUYA_LOG_LEVEL", "")),
        )


def _parse_endpoint(raw: str) -> str:
    endpoint = raw.strip().rstrip("/")
    if not endpoint:
        return DEFAULT_ENDPOINT
    if not endpoint.startswith(("https://", "http://")):
        endpoint = "https://" + endpoint
    return endpoint


def _parse_cache_ttl(raw: str) -> int:
    raw = raw.strip()
    if not raw:
        return DEFAULT_CACHE_TTL
    try:
        ttl = int(raw)
    except ValueError:
        raise ConfigError(
            f"TUYA_CACHE_TTL must be a whole number of seconds, got {raw!r}."
        ) from None
    if ttl < 0:
        raise ConfigError(f"TUYA_CACHE_TTL must be >= 0, got {ttl}.")
    return ttl


def _parse_log_level(raw: str) -> str:
    level = raw.strip().upper() or DEFAULT_LOG_LEVEL
    if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise ConfigError(
            f"TUYA_LOG_LEVEL must be one of DEBUG, INFO, WARNING, ERROR, CRITICAL, got {raw!r}."
        )
    return level
