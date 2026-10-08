from __future__ import annotations

import logging

import httpx
import pytest

from tuya_mcp import server
from tuya_mcp.client import DEVICES_PATH, TuyaClient
from tuya_mcp.config import Config
from tuya_mcp.logging_utils import configure_logging

from .conftest import ACCESS_TOKEN, SECRET, FakeClock, FakeTuya


async def test_secrets_never_logged_in_debug(
    config: Config,
    fake_tuya: FakeTuya,
    http: httpx.AsyncClient,
    clock: FakeClock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_tuya.route(DEVICES_PATH, lambda r: {"success": True, "result": {"devices": []}})
    configure_logging("DEBUG")
    client = TuyaClient(config, http=http, clock=clock)

    await client.list_devices()
    logging.getLogger("test").debug("leak attempt: %s %s", SECRET, f"{ACCESS_TOKEN}-1")
    logging.getLogger("httpx").debug("headers %s", {"access_token": f"{ACCESS_TOKEN}-1"})

    err = capsys.readouterr().err
    assert "leak attempt" in err
    assert SECRET not in err
    assert f"{ACCESS_TOKEN}-1" not in err
    assert "refresh-xyz" not in err


def test_missing_config_exits_with_named_variable(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("TUYA_ACCESS_ID", raising=False)
    monkeypatch.setenv("TUYA_ACCESS_SECRET", SECRET)
    monkeypatch.setenv("TUYA_UID", "uid")

    with pytest.raises(SystemExit) as exc_info:
        server.main()

    assert exc_info.value.code == 2
    err = capsys.readouterr().err
    assert "TUYA_ACCESS_ID" in err
    assert SECRET not in err
