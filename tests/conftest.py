from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import httpx
import pytest

from crawl4ai_proxy.app import create_app
from crawl4ai_proxy.config import Settings

ENV_KEYS = [
    "LISTEN_IP",
    "LISTEN_PORT",
    "CRAWL4AI_URL",
    "CRAWL4AI_ENDPOINT",
    "CRAWL4AI_API_KEY",
    "PROXY_API_KEY",
    "CRAWL4AI_TIMEOUT",
    "CRAWL4AI_CONNECT_TIMEOUT",
    "MARKDOWN_MODE",
    "ENABLE_TOOL_ENDPOINTS",
    "CRAWL4AI_CRAWLER_CONFIG",
    "LOG_LEVEL",
]

Handler = Callable[[httpx.Request], httpx.Response]


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def app_factory(monkeypatch: pytest.MonkeyPatch) -> Callable[..., Any]:
    def factory(
        handler: Handler,
        env: Mapping[str, str] | None = None,
    ):
        for key, value in (env or {}).items():
            monkeypatch.setenv(key, value)
        settings = Settings.from_env()
        return create_app(settings, transport=httpx.MockTransport(handler))

    return factory


@pytest.fixture
async def client_factory(app_factory: Callable[..., Any]) -> Any:
    clients: list[httpx.AsyncClient] = []

    async def factory(handler: Handler, env: Mapping[str, str] | None = None):
        app = app_factory(handler, env)
        client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        )
        clients.append(client)
        return client

    yield factory

    for client in clients:
        await client.aclose()
