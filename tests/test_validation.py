from __future__ import annotations

import httpx


def ok_handler(_: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"success": True, "results": []})


async def test_rejects_wrong_content_type(client_factory) -> None:
    client = await client_factory(ok_handler)
    response = await client.post(
        "/crawl",
        content="{}",
        headers={"content-type": "text/plain"},
    )

    assert response.status_code == 400
    assert response.json()["error"] == "content type must be application/json"


async def test_rejects_invalid_json(client_factory) -> None:
    client = await client_factory(ok_handler)
    response = await client.post(
        "/crawl",
        content="{not json",
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 400
    assert response.json()["error"] == "invalid json"


async def test_rejects_wrong_urls_type(client_factory) -> None:
    client = await client_factory(ok_handler)
    response = await client.post("/crawl", json={"urls": "https://example.com"})

    assert response.status_code == 400
    assert response.json()["error"] == "invalid request"


async def test_rejects_empty_urls(client_factory) -> None:
    client = await client_factory(ok_handler)
    response = await client.post("/crawl", json={"urls": []})

    assert response.status_code == 400
    assert response.json()["error"] == "invalid request"


async def test_rejects_empty_url_string(client_factory) -> None:
    client = await client_factory(ok_handler)
    response = await client.post("/crawl", json={"urls": ["   "]})

    assert response.status_code == 400
    assert response.json()["error"] == "invalid request"


async def test_rejects_too_many_urls(client_factory) -> None:
    client = await client_factory(ok_handler)
    response = await client.post(
        "/crawl",
        json={"urls": [f"https://example.com/{index}" for index in range(101)]},
    )

    assert response.status_code == 400
    assert response.json()["error"] == "invalid request"


async def test_method_not_allowed(client_factory) -> None:
    client = await client_factory(ok_handler)
    response = await client.get("/crawl")

    assert response.status_code == 405
    assert response.json()["error"] == "method not allowed"


async def test_unknown_path(client_factory) -> None:
    client = await client_factory(ok_handler)
    response = await client.get("/nope")

    assert response.status_code == 404
    assert response.json()["error"] == "not found"
