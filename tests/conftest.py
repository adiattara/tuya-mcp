from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from typing import Any

import httpx
import pytest

from tuya_mcp.config import Config

SECRET = "super-secret-value"
ACCESS_TOKEN = "token-abc-123"

Handler = Callable[[httpx.Request], dict[str, Any]]


class FakeClock:
    def __init__(self, now: float = 1_700_000_000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


class FakeTuya:
    """Routes requests by path and records them for assertions."""

    def __init__(self) -> None:
        self.routes: dict[str, Handler] = {}
        self.requests: list[httpx.Request] = []
        self.token_calls = 0
        self.route("/v1.0/token", self._token)

    def route(self, path: str, handler: Handler) -> None:
        self.routes[path] = handler

    def _token(self, request: httpx.Request) -> dict[str, Any]:
        self.token_calls += 1
        return {
            "success": True,
            "result": {
                "access_token": f"{ACCESS_TOKEN}-{self.token_calls}",
                "expire_time": 7200,
                "refresh_token": "refresh-xyz",
                "uid": "uid",
            },
        }

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        handler = self.routes.get(request.url.path)
        if handler is None:
            return httpx.Response(404, json={"success": False, "code": 404, "msg": "no route"})
        return httpx.Response(200, json=handler(request))


@pytest.fixture(autouse=True)
def _restore_logging() -> Iterator[None]:
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    root.handlers, root.level = handlers, level


@pytest.fixture
def config() -> Config:
    return Config(access_id="client-id", access_secret=SECRET, uid="uid")


@pytest.fixture
def fake_tuya() -> FakeTuya:
    return FakeTuya()


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def http(fake_tuya: FakeTuya, config: Config) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=config.endpoint, transport=httpx.MockTransport(fake_tuya.handle)
    )
