from __future__ import annotations

import logging
import secrets
from contextlib import asynccontextmanager
from typing import Literal

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import __version__
from .client import Crawl4AIClient, UpstreamError
from .config import Settings
from .mapping import documents_from_crawl_response

logger = logging.getLogger(__name__)

PROTECTED_EXEMPT_PATHS = {"/health", "/openapi.json", "/docs", "/redoc", "/docs/oauth2-redirect"}


class CrawlRequest(BaseModel):
    urls: list[str] = Field(
        min_length=1,
        max_length=100,
        description="URLs to crawl. Open WebUI sends these in batches of up to 20.",
    )

    @field_validator("urls")
    @classmethod
    def validate_urls(cls, urls: list[str]) -> list[str]:
        if any(not url.strip() for url in urls):
            raise ValueError("urls must not contain empty strings")
        return urls


class MarkdownToolRequest(BaseModel):
    url: str = Field(min_length=1, description="Absolute http/https URL to fetch")
    filter: Literal["fit", "raw", "bm25", "llm"] = Field(
        default="fit",
        description="Crawl4AI content filter mode",
    )
    query: str | None = Field(
        default=None,
        description="Optional query used by BM25 or LLM filtering",
    )


class HtmlToolRequest(BaseModel):
    url: str = Field(min_length=1, description="Absolute http/https URL to fetch")


def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def _error(status_code: int, error: str, detail: str) -> JSONResponse:
    return JSONResponse({"error": error, "detail": detail}, status_code=status_code)


def create_app(
    settings: Settings | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    crawl4ai = Crawl4AIClient(settings, transport=transport)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        await crawl4ai.aclose()

    app = FastAPI(
        title="Crawl4AI Proxy",
        description=(
            "A small proxy that adapts Crawl4AI to Open WebUI's External Web Loader "
            "and exposes a safe subset of Crawl4AI endpoints as OpenAPI tools."
        ),
        version=__version__,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.crawl4ai = crawl4ai

    json_paths = {"/crawl"}
    if settings.enable_tool_endpoints:
        json_paths.update({"/tools/markdown", "/tools/html"})

    @app.middleware("http")
    async def request_guard(request: Request, call_next):
        if settings.proxy_api_key and request.url.path not in PROTECTED_EXEMPT_PATHS:
            token = _extract_bearer(request.headers.get("authorization"))
            if token is None or not secrets.compare_digest(token, settings.proxy_api_key):
                return JSONResponse(
                    {"error": "unauthorized", "detail": "invalid or missing API key"},
                    status_code=401,
                    headers={"WWW-Authenticate": "Bearer"},
                )

        if request.method in {"POST", "PUT", "PATCH"} and request.url.path in json_paths:
            content_type = request.headers.get("content-type", "")
            if not content_type.lower().startswith("application/json"):
                return _error(
                    400,
                    "content type must be application/json",
                    f"received {content_type or 'no content type'}",
                )

        return await call_next(request)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = exc.errors()
        invalid_json = any(error.get("type") == "json_invalid" for error in errors)
        detail = "; ".join(
            f"{'.'.join(str(part) for part in error.get('loc', []))}: {error.get('msg')}"
            for error in errors[:5]
        )
        return _error(400, "invalid json" if invalid_json else "invalid request", detail)

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        names = {
            400: "bad request",
            401: "unauthorized",
            403: "forbidden",
            404: "not found",
            405: "method not allowed",
        }
        return _error(exc.status_code, names.get(exc.status_code, "error"), str(exc.detail))

    @app.exception_handler(UpstreamError)
    async def upstream_error_handler(request: Request, exc: UpstreamError) -> JSONResponse:
        logger.warning("Upstream error for %s %s: %s", request.method, request.url.path, exc.detail)
        return _error(exc.status_code, exc.error, exc.detail)

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error for %s %s", request.method, request.url.path)
        return _error(500, "internal server error", "unexpected proxy error")

    @app.post(
        "/crawl",
        operation_id="crawl_urls",
        summary="Crawl URLs for Open WebUI",
        description=(
            "Crawl a batch of URLs and return Open WebUI External Web Loader documents. "
            "Each document contains page_content and metadata.source."
        ),
    )
    async def crawl(payload: CrawlRequest, request: Request) -> JSONResponse:
        client = request.client.host if request.client else "unknown"
        logger.info("Crawl request for %d URL(s) from %s", len(payload.urls), client)
        data = await crawl4ai.crawl(payload.urls)
        documents = documents_from_crawl_response(data, settings.markdown_mode)
        logger.info("Returning %d document(s)", len(documents))
        return JSONResponse(documents)

    if settings.enable_tool_endpoints:

        @app.post(
            "/tools/markdown",
            operation_id="fetch_markdown",
            summary="Fetch a page as Markdown",
            description="Convert a page into clean Markdown using Crawl4AI's /md endpoint.",
        )
        async def fetch_markdown(payload: MarkdownToolRequest) -> JSONResponse:
            data = await crawl4ai.markdown(payload.url, payload.filter, payload.query)
            markdown = data.get("markdown")
            if not isinstance(markdown, str):
                raise UpstreamError(502, "bad gateway", "Crawl4AI /md did not return markdown")
            return JSONResponse({"url": payload.url, "markdown": markdown})

        @app.post(
            "/tools/html",
            operation_id="fetch_html",
            summary="Fetch preprocessed HTML",
            description="Fetch a page as sanitized HTML using Crawl4AI's /html endpoint.",
        )
        async def fetch_html(payload: HtmlToolRequest) -> JSONResponse:
            data = await crawl4ai.html(payload.url)
            html = data.get("html")
            if not isinstance(html, str):
                raise UpstreamError(502, "bad gateway", "Crawl4AI /html did not return html")
            return JSONResponse({"url": payload.url, "html": html})

    @app.get("/health", include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {"name": "crawl4ai-proxy", "version": __version__}

    return app
