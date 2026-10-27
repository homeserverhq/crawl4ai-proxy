from __future__ import annotations

import httpx


def empty_crawl(_: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"success": True, "results": []})


async def test_health(client_factory) -> None:
    client = await client_factory(empty_crawl)
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_root(client_factory) -> None:
    client = await client_factory(empty_crawl)
    response = await client.get("/")

    assert response.status_code == 200
    assert response.json()["name"] == "crawl4ai-proxy"


async def test_openapi_contains_supported_routes(client_factory) -> None:
    client = await client_factory(empty_crawl)
    response = await client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/crawl" in paths
    assert "/tools/markdown" in paths
    assert "/tools/html" in paths
    assert "/health" not in paths


async def test_health_is_exempt_from_proxy_auth(client_factory) -> None:
    client = await client_factory(empty_crawl, env={"PROXY_API_KEY": "secret"})
    response = await client.get("/health")

    assert response.status_code == 200


async def test_openapi_is_exempt_from_proxy_auth(client_factory) -> None:
    client = await client_factory(empty_crawl, env={"PROXY_API_KEY": "secret"})
    response = await client.get("/openapi.json")

    assert response.status_code == 200


async def test_proxy_auth_requires_bearer_token(client_factory) -> None:
    client = await client_factory(empty_crawl, env={"PROXY_API_KEY": "secret"})

    missing = await client.post("/crawl", json={"urls": ["https://example.com"]})
    wrong = await client.post(
        "/crawl",
        json={"urls": ["https://example.com"]},
        headers={"authorization": "Bearer wrong"},
    )
    accepted = await client.post(
        "/crawl",
        json={"urls": ["https://example.com"]},
        headers={"authorization": "Bearer secret"},
    )

    assert missing.status_code == 401
    assert missing.json()["error"] == "unauthorized"
    assert wrong.status_code == 401
    assert accepted.status_code == 200


async def test_tool_endpoints_can_be_disabled(client_factory) -> None:
    client = await client_factory(
        empty_crawl,
        env={"ENABLE_TOOL_ENDPOINTS": "false"},
    )

    openapi = await client.get("/openapi.json")
    markdown = await client.post(
        "/tools/markdown",
        json={"url": "https://example.com"},
    )

    assert "/tools/markdown" not in openapi.json()["paths"]
    assert markdown.status_code == 404
