from __future__ import annotations

import json
import logging
from typing import Any

from .client import UpstreamError

logger = logging.getLogger(__name__)


def select_markdown(markdown: Any, mode: str) -> str:
    if isinstance(markdown, str):
        return markdown
    if not isinstance(markdown, dict):
        return ""

    raw = markdown.get("raw_markdown")
    fit = markdown.get("fit_markdown")
    raw = raw if isinstance(raw, str) else ""
    fit = fit if isinstance(fit, str) else ""

    if mode == "raw":
        return raw
    if mode == "fit":
        return fit or raw
    return fit or raw


def flatten_metadata(metadata: Any, source: str | None) -> dict[str, str]:
    result: dict[str, str] = {}
    if isinstance(metadata, dict):
        for key, value in metadata.items():
            name = str(key)
            if value is None:
                continue
            if isinstance(value, str):
                if value == "":
                    continue
                result[name] = value
            elif isinstance(value, bool):
                result[name] = "true" if value else "false"
            elif isinstance(value, (int, float)):
                result[name] = str(value)
            else:
                try:
                    result[name] = json.dumps(value, ensure_ascii=False, default=str)
                except (TypeError, ValueError):
                    result[name] = str(value)

    if source:
        result["source"] = source
    return result


def documents_from_crawl_response(data: Any, markdown_mode: str) -> list[dict[str, Any]]:
    if not isinstance(data, dict):
        raise UpstreamError(502, "bad gateway", "Crawl4AI returned an unexpected response")

    results = data.get("results")
    if not isinstance(results, list):
        raise UpstreamError(502, "bad gateway", "Crawl4AI response does not contain results")

    documents: list[dict[str, Any]] = []
    for item in results:
        if not isinstance(item, dict):
            continue

        url = item.get("url")
        source = url if isinstance(url, str) and url else None

        if item.get("success") is False:
            logger.warning(
                "Skipping failed crawl result for %s: %s",
                source or "<unknown>",
                item.get("error_message") or "unknown error",
            )
            continue

        content = select_markdown(item.get("markdown"), markdown_mode)
        if not content.strip():
            logger.warning("Skipping empty crawl result for %s", source or "<unknown>")
            continue

        documents.append(
            {
                "page_content": content,
                "metadata": flatten_metadata(item.get("metadata"), source),
            }
        )

    return documents
