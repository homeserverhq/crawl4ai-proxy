from __future__ import annotations

import json

import httpx


async def test_markdown_tool(client_factory) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        captured["authorization"] = request.headers.get("authorization")
        return httpx.Response(200, json={"markdown": "# Hello", "success": True})

    client = await client_factory(
        handler,
        env={"CRAWL4AI_API_KEY": "upstream-secret"},
    )
    response = await client.post(
        "/tools/markdown",
        json={"url": "https://example.com", "filter": "fit"},
    )

    assert response.status_code == 200
    assert response.json() == {"url": "https://example.com", "markdown": "# Hello"}
    assert captured["path"] == "/md"
    assert captured["body"] == {"url": "https://example.com", "f": "fit"}
    assert captured["authorization"] == "Bearer upstream-secret"


async def test_markdown_tool_query_passthrough(client_factory) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"markdown": "result", "success": True})

    client = await client_factory(handler)
    response = await client.post(
        "/tools/markdown",
        json={"url": "https://example.com", "filter": "bm25", "query": "hello"},
    )

    assert response.status_code == 200
    assert captured["body"] == {
        "url": "https://example.com",
        "f": "bm25",
        "q": "hello",
    }


async def test_html_tool(client_factory) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"html": "<main>Hello</main>", "success": True})

    client = await client_factory(handler)
    response = await client.post("/tools/html", json={"url": "https://example.com"})

    assert response.status_code == 200
    assert response.json() == {"url": "https://example.com", "html": "<main>Hello</main>"}
    assert captured["path"] == "/html"
    assert captured["body"] == {"url": "https://example.com"}


async def test_markdown_tool_rejects_bad_upstream_shape(client_factory) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"success": True})

    client = await client_factory(handler)
    response = await client.post("/tools/markdown", json={"url": "https://example.com"})

    assert response.status_code == 502
    assert response.json()["error"] == "bad gateway"


async def test_tool_rejects_wrong_content_type(client_factory) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"markdown": "unused"})

    client = await client_factory(handler)
    response = await client.post(
        "/tools/markdown",
        content="{}",
        headers={"content-type": "text/plain"},
    )

    assert response.status_code == 400
    assert response.json()["error"] == "content type must be application/json"


async def test_tool_validation_error(client_factory) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"markdown": "unused"})

    client = await client_factory(handler)
    response = await client.post("/tools/markdown", json={"url": ""})

    assert response.status_code == 400
    assert response.json()["error"] == "invalid request"
