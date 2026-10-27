from __future__ import annotations

from typing import Any

import httpx

from .config import Settings


class UpstreamError(Exception):
    def __init__(self, status_code: int, error: str, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.error = error
        self.detail = detail


class Crawl4AIClient:
    def __init__(
        self,
        settings: Settings,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                settings.crawl4ai_timeout,
                connect=settings.crawl4ai_connect_timeout,
            ),
            transport=transport,
            follow_redirects=False,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    def _headers(self) -> dict[str, str]:
        if self.settings.crawl4ai_api_key:
            return {"Authorization": f"Bearer {self.settings.crawl4ai_api_key}"}
        return {}

    async def _post(self, url: str, payload: dict[str, Any]) -> Any:
        try:
            response = await self._client.post(url, json=payload, headers=self._headers())
        except httpx.TimeoutException as exc:
            raise UpstreamError(
                502,
                "bad gateway",
                f"Crawl4AI request timed out: {exc.__class__.__name__}",
            ) from exc
        except httpx.HTTPError as exc:
            raise UpstreamError(502, "bad gateway", f"Crawl4AI request failed: {exc}") from exc

        if response.status_code >= 400:
            detail = self._response_detail(response)
            if response.status_code in {401, 403}:
                raise UpstreamError(
                    502,
                    "bad gateway",
                    f"Crawl4AI authentication failed ({response.status_code}): {detail}",
                )
            if 400 <= response.status_code < 500:
                raise UpstreamError(
                    400,
                    "bad request",
                    f"Crawl4AI rejected the request ({response.status_code}): {detail}",
                )
            raise UpstreamError(
                502,
                "bad gateway",
                f"Crawl4AI returned {response.status_code}: {detail}",
            )

        try:
            return response.json()
        except ValueError as exc:
            raise UpstreamError(
                502,
                "bad gateway",
                "invalid json received from crawl api",
            ) from exc

    @staticmethod
    def _response_detail(response: httpx.Response) -> str:
        try:
            data = response.json()
        except ValueError:
            return response.text[:500]
        if isinstance(data, dict):
            return str(data.get("detail") or data.get("error") or data)[:500]
        return str(data)[:500]

    async def crawl(self, urls: list[str]) -> Any:
        payload: dict[str, Any] = dict(self.settings.crawler_config or {})
        payload["urls"] = urls
        return await self._post(self.settings.crawl_endpoint, payload)

    async def markdown(self, url: str, filter_type: str, query: str | None) -> dict[str, Any]:
        payload: dict[str, Any] = {"url": url, "f": filter_type}
        if query:
            payload["q"] = query
        data = await self._post(self.settings.markdown_endpoint, payload)
        if not isinstance(data, dict):
            raise UpstreamError(502, "bad gateway", "Crawl4AI returned an unexpected /md response")
        return data

    async def html(self, url: str) -> dict[str, Any]:
        data = await self._post(self.settings.html_endpoint, {"url": url})
        if not isinstance(data, dict):
            raise UpstreamError(
                502,
                "bad gateway",
                "Crawl4AI returned an unexpected /html response",
            )
        return data
