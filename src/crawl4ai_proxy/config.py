from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


class ConfigError(ValueError):
    """Raised when environment configuration is invalid."""


def _env(env: Mapping[str, str], name: str, default: str | None = None) -> str | None:
    value = env.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _env_int(env: Mapping[str, str], name: str, default: int) -> int:
    raw = _env(env, name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer") from exc


def _env_float(env: Mapping[str, str], name: str, default: float) -> float:
    raw = _env(env, name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number") from exc


def _env_bool(env: Mapping[str, str], name: str, default: bool) -> bool:
    raw = _env(env, name)
    if raw is None:
        return default
    value = raw.lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ConfigError(f"{name} must be a boolean")


@dataclass(frozen=True)
class Settings:
    listen_ip: str = "0.0.0.0"
    listen_port: int = 8000
    crawl4ai_url: str = "http://crawl4ai:11235"
    crawl4ai_endpoint: str | None = None
    crawl4ai_api_key: str | None = None
    proxy_api_key: str | None = None
    crawl4ai_timeout: float = 330.0
    crawl4ai_connect_timeout: float = 10.0
    markdown_mode: str = "auto"
    enable_tool_endpoints: bool = True
    crawler_config: dict[str, Any] | None = None
    log_level: str = "INFO"

    @property
    def crawl_endpoint(self) -> str:
        return self.crawl4ai_endpoint or f"{self.crawl4ai_url}/crawl"

    @property
    def markdown_endpoint(self) -> str:
        return f"{self.crawl4ai_url}/md"

    @property
    def html_endpoint(self) -> str:
        return f"{self.crawl4ai_url}/html"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        values = os.environ if env is None else env

        crawl4ai_url = (_env(values, "CRAWL4AI_URL") or "http://crawl4ai:11235").rstrip("/")
        if not crawl4ai_url.startswith(("http://", "https://")):
            raise ConfigError("CRAWL4AI_URL must start with http:// or https://")

        crawl4ai_endpoint = _env(values, "CRAWL4AI_ENDPOINT")
        if crawl4ai_endpoint:
            crawl4ai_endpoint = crawl4ai_endpoint.rstrip("/")
            if not crawl4ai_endpoint.startswith(("http://", "https://")):
                raise ConfigError("CRAWL4AI_ENDPOINT must start with http:// or https://")

        markdown_mode = (_env(values, "MARKDOWN_MODE") or "auto").lower()
        if markdown_mode not in {"auto", "raw", "fit"}:
            raise ConfigError("MARKDOWN_MODE must be one of: auto, raw, fit")

        crawler_config: dict[str, Any] | None = None
        raw_crawler_config = _env(values, "CRAWL4AI_CRAWLER_CONFIG")
        if raw_crawler_config:
            try:
                parsed = json.loads(raw_crawler_config)
            except json.JSONDecodeError as exc:
                raise ConfigError("CRAWL4AI_CRAWLER_CONFIG must be valid JSON") from exc
            if not isinstance(parsed, dict):
                raise ConfigError("CRAWL4AI_CRAWLER_CONFIG must be a JSON object")
            if "urls" in parsed:
                raise ConfigError("CRAWL4AI_CRAWLER_CONFIG must not override urls")
            crawler_config = parsed

        listen_port = _env_int(values, "LISTEN_PORT", 8000)
        if not 1 <= listen_port <= 65535:
            raise ConfigError("LISTEN_PORT must be between 1 and 65535")

        timeout = _env_float(values, "CRAWL4AI_TIMEOUT", 330.0)
        connect_timeout = _env_float(values, "CRAWL4AI_CONNECT_TIMEOUT", 10.0)
        if timeout <= 0 or connect_timeout <= 0:
            raise ConfigError("Crawl4AI timeouts must be greater than zero")

        return cls(
            listen_ip=_env(values, "LISTEN_IP") or "0.0.0.0",
            listen_port=listen_port,
            crawl4ai_url=crawl4ai_url,
            crawl4ai_endpoint=crawl4ai_endpoint,
            crawl4ai_api_key=_env(values, "CRAWL4AI_API_KEY"),
            proxy_api_key=_env(values, "PROXY_API_KEY"),
            crawl4ai_timeout=timeout,
            crawl4ai_connect_timeout=connect_timeout,
            markdown_mode=markdown_mode,
            enable_tool_endpoints=_env_bool(values, "ENABLE_TOOL_ENDPOINTS", True),
            crawler_config=crawler_config,
            log_level=(_env(values, "LOG_LEVEL") or "INFO").upper(),
        )
