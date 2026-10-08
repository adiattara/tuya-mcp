import pytest

from tuya_mcp.config import DEFAULT_ENDPOINT, Config, ConfigError

BASE = {"TUYA_ACCESS_ID": "id", "TUYA_ACCESS_SECRET": "s3cr3t", "TUYA_UID": "uid"}


def test_defaults() -> None:
    config = Config.from_env(BASE)
    assert config.endpoint == DEFAULT_ENDPOINT
    assert config.cache_ttl == 60
    assert config.log_level == "WARNING"


def test_missing_variables_are_all_named() -> None:
    with pytest.raises(ConfigError) as exc_info:
        Config.from_env({"TUYA_ACCESS_ID": "id", "TUYA_UID": "  "})
    message = str(exc_info.value)
    assert "TUYA_ACCESS_SECRET" in message
    assert "TUYA_UID" in message
    assert "TUYA_ACCESS_ID" not in message


def test_secret_not_in_repr() -> None:
    assert "s3cr3t" not in repr(Config.from_env(BASE))


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://openapi.tuyaus.com/", "https://openapi.tuyaus.com"),
        ("openapi.tuyain.com", "https://openapi.tuyain.com"),
    ],
)
def test_endpoint_normalization(raw: str, expected: str) -> None:
    assert Config.from_env({**BASE, "TUYA_API_ENDPOINT": raw}).endpoint == expected


@pytest.mark.parametrize("raw", ["abc", "-1"])
def test_invalid_cache_ttl(raw: str) -> None:
    with pytest.raises(ConfigError, match="TUYA_CACHE_TTL"):
        Config.from_env({**BASE, "TUYA_CACHE_TTL": raw})


def test_invalid_log_level() -> None:
    with pytest.raises(ConfigError, match="TUYA_LOG_LEVEL"):
        Config.from_env({**BASE, "TUYA_LOG_LEVEL": "loud"})
