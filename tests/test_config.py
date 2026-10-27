from __future__ import annotations

import pytest

from crawl4ai_proxy.config import ConfigError, Settings


def test_defaults() -> None:
    settings = Settings.from_env({})

    assert settings.listen_ip == "0.0.0.0"
    assert settings.listen_port == 8000
    assert settings.crawl4ai_url == "http://crawl4ai:11235"
    assert settings.crawl_endpoint == "http://crawl4ai:11235/crawl"
    assert settings.markdown_endpoint == "http://crawl4ai:11235/md"
    assert settings.html_endpoint == "http://crawl4ai:11235/html"
    assert settings.markdown_mode == "auto"
    assert settings.enable_tool_endpoints is True
    assert settings.crawl4ai_api_key is None
    assert settings.proxy_api_key is None


def test_crawl4ai_url_is_normalized() -> None:
    settings = Settings.from_env({"CRAWL4AI_URL": "http://crawl4ai-app:11235/"})

    assert settings.crawl4ai_url == "http://crawl4ai-app:11235"
    assert settings.crawl_endpoint == "http://crawl4ai-app:11235/crawl"
    assert settings.markdown_endpoint == "http://crawl4ai-app:11235/md"


def test_crawl4ai_endpoint_override() -> None:
    settings = Settings.from_env(
        {
            "CRAWL4AI_URL": "http://crawl4ai-app:11235",
            "CRAWL4AI_ENDPOINT": "http://other:9000/custom-crawl/",
        }
    )

    assert settings.crawl_endpoint == "http://other:9000/custom-crawl"
    assert settings.markdown_endpoint == "http://crawl4ai-app:11235/md"


def test_keys_and_auth_settings() -> None:
    settings = Settings.from_env(
        {
            "CRAWL4AI_API_KEY": "upstream",
            "PROXY_API_KEY": "inbound",
        }
    )

    assert settings.crawl4ai_api_key == "upstream"
    assert settings.proxy_api_key == "inbound"


def test_empty_keys_are_none() -> None:
    settings = Settings.from_env({"CRAWL4AI_API_KEY": "", "PROXY_API_KEY": "  "})

    assert settings.crawl4ai_api_key is None
    assert settings.proxy_api_key is None


def test_crawler_config() -> None:
    settings = Settings.from_env(
        {"CRAWL4AI_CRAWLER_CONFIG": '{"crawler_config": {"cache_mode": "bypass"}}'}
    )

    assert settings.crawler_config == {"crawler_config": {"cache_mode": "bypass"}}


@pytest.mark.parametrize(
    ("env", "message"),
    [
        ({"CRAWL4AI_URL": "crawl4ai:11235"}, "CRAWL4AI_URL"),
        ({"CRAWL4AI_ENDPOINT": "crawl4ai:11235/crawl"}, "CRAWL4AI_ENDPOINT"),
        ({"MARKDOWN_MODE": "clean"}, "MARKDOWN_MODE"),
        ({"LISTEN_PORT": "nope"}, "LISTEN_PORT"),
        ({"LISTEN_PORT": "0"}, "LISTEN_PORT"),
        ({"CRAWL4AI_TIMEOUT": "0"}, "timeouts"),
        ({"ENABLE_TOOL_ENDPOINTS": "maybe"}, "ENABLE_TOOL_ENDPOINTS"),
        ({"CRAWL4AI_CRAWLER_CONFIG": "[]"}, "JSON object"),
        ({"CRAWL4AI_CRAWLER_CONFIG": "{"}, "valid JSON"),
        ({"CRAWL4AI_CRAWLER_CONFIG": '{"urls": []}'}, "override urls"),
    ],
)
def test_invalid_settings(env: dict[str, str], message: str) -> None:
    with pytest.raises(ConfigError, match=message):
        Settings.from_env(env)
