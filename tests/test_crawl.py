from __future__ import annotations

import json

import httpx
import pytest


def crawl_response(
    *,
    url: str = "https://example.com",
    fit: str = "# Fit markdown",
    raw: str = "# Raw markdown",
    metadata: dict | None = None,
    success: bool = True,
    error_message: str | None = None,
    include_markdown: bool = True,
) -> dict:
    result: dict = {
        "url": url,
        "success": success,
        "metadata": metadata
        if metadata is not None
        else {
            "title": "Example",
            "description": None,
            "empty": "",
            "depth": 2,
            "ok": True,
            "nested": {"a": 1},
        },
    }
    if error_message:
        result["error_message"] = error_message
    if include_markdown:
        result["markdown"] = {
            "raw_markdown": raw,
            "fit_markdown": fit,
        }
    return {"success": True, "results": [result]}


async def test_crawl_maps_fit_markdown_and_metadata(client_factory) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=crawl_response())

    client = await client_factory(handler)
    response = await client.post("/crawl", json={"urls": ["https://example.com"]})

    assert response.status_code == 200
    assert captured["path"] == "/crawl"
    assert captured["body"] == {"urls": ["https://example.com"]}
    assert response.json() == [
        {
            "page_content": "# Fit markdown",
            "metadata": {
                "title": "Example",
                "depth": "2",
                "ok": "true",
                "nested": '{"a": 1}',
                "source": "https://example.com",
            },
        }
    ]


async def test_crawl_auto_falls_back_to_raw(client_factory) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=crawl_response(fit="", raw="# Raw fallback"))

    client = await client_factory(handler)
    response = await client.post("/crawl", json={"urls": ["https://example.com"]})

    assert response.status_code == 200
    assert response.json()[0]["page_content"] == "# Raw fallback"


async def test_crawl_raw_mode(client_factory) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=crawl_response(fit="# Fit", raw="# Raw"))

    client = await client_factory(handler, env={"MARKDOWN_MODE": "raw"})
    response = await client.post("/crawl", json={"urls": ["https://example.com"]})

    assert response.status_code == 200
    assert response.json()[0]["page_content"] == "# Raw"


async def test_crawl_skips_failed_and_empty_results(client_factory) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "success": True,
                "results": [
                    {
                        "url": "https://failed.example",
                        "success": False,
                        "error_message": "boom",
                        "markdown": {"raw_markdown": "ignored", "fit_markdown": "ignored"},
                        "metadata": {},
                    },
                    {
                        "url": "https://empty.example",
                        "success": True,
                        "markdown": {"raw_markdown": "  ", "fit_markdown": ""},
                        "metadata": {},
                    },
                    {
                        "url": "https://ok.example",
                        "success": True,
                        "markdown": {"raw_markdown": "# ok", "fit_markdown": "# fit ok"},
                        "metadata": {},
                    },
                ],
            },
        )

    client = await client_factory(handler)
    response = await client.post(
        "/crawl",
        json={
            "urls": [
                "https://failed.example",
                "https://empty.example",
                "https://ok.example",
            ]
        },
    )

    assert response.status_code == 200
    docs = response.json()
    assert len(docs) == 1
    assert docs[0]["page_content"] == "# fit ok"
    assert docs[0]["metadata"] == {"source": "https://ok.example"}


async def test_crawl_sends_crawl4ai_api_key(client_factory) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers.get("authorization")
        return httpx.Response(200, json=crawl_response())

    client = await client_factory(
        handler,
        env={"CRAWL4AI_API_KEY": "upstream-secret"},
    )
    response = await client.post("/crawl", json={"urls": ["https://example.com"]})

    assert response.status_code == 200
    assert captured["authorization"] == "Bearer upstream-secret"


async def test_crawl_omits_authorization_without_key(client_factory) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers.get("authorization")
        return httpx.Response(200, json=crawl_response())

    client = await client_factory(handler)
    response = await client.post("/crawl", json={"urls": ["https://example.com"]})

    assert response.status_code == 200
    assert captured["authorization"] is None


async def test_crawl_merges_trusted_crawler_config(client_factory) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=crawl_response())

    config = json.dumps({"crawler_config": {"cache_mode": "bypass"}})
    client = await client_factory(
        handler,
        env={"CRAWL4AI_CRAWLER_CONFIG": config},
    )
    response = await client.post("/crawl", json={"urls": ["https://example.com"]})

    assert response.status_code == 200
    assert captured["body"] == {
        "crawler_config": {"cache_mode": "bypass"},
        "urls": ["https://example.com"],
    }


@pytest.mark.parametrize(
    ("status_code", "expected_status", "expected_error"),
    [
        (500, 502, "bad gateway"),
        (401, 502, "bad gateway"),
        (400, 400, "bad request"),
    ],
)
async def test_crawl_maps_upstream_errors(
    client_factory,
    status_code: int,
    expected_status: int,
    expected_error: str,
) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"detail": "upstream failed"})

    client = await client_factory(handler)
    response = await client.post("/crawl", json={"urls": ["https://example.com"]})

    assert response.status_code == expected_status
    assert response.json()["error"] == expected_error
    assert "upstream failed" in response.json()["detail"]


async def test_crawl_maps_invalid_upstream_json(client_factory) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not json", headers={"content-type": "text/plain"})

    client = await client_factory(handler)
    response = await client.post("/crawl", json={"urls": ["https://example.com"]})

    assert response.status_code == 502
    assert response.json()["error"] == "bad gateway"
    assert "invalid json" in response.json()["detail"]


async def test_crawl_maps_upstream_timeout(client_factory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    client = await client_factory(handler)
    response = await client.post("/crawl", json={"urls": ["https://example.com"]})

    assert response.status_code == 502
    assert response.json()["error"] == "bad gateway"
    assert "timed out" in response.json()["detail"]


async def test_crawl_maps_unexpected_upstream_shape(client_factory) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"success": True})

    client = await client_factory(handler)
    response = await client.post("/crawl", json={"urls": ["https://example.com"]})

    assert response.status_code == 502
    assert response.json()["error"] == "bad gateway"
