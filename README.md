# Crawl4AI Proxy

A small, self-hosted proxy that lets [Open WebUI](https://github.com/open-webui/open-webui) use
[Crawl4AI](https://github.com/unclecode/crawl4ai) as its external web loader.

Open WebUI's `external` web loader posts a batch of URLs and expects a JSON array of documents:

```json
[
  {"page_content": "...", "metadata": {"source": "https://example.com"}}
]
```

Crawl4AI's `/crawl` endpoint returns a different shape:

```json
{"success": true, "results": [{"url": "...", "markdown": {...}, "metadata": {...}}]}
```

This proxy translates between them. It also exposes a small, safe subset of Crawl4AI's endpoint
surface as OpenAPI tools for Open WebUI's Tool Server support.

## Features

- Open WebUI External Web Loader adapter at `POST /crawl`.
- Safe OpenAPI tools:
  - `POST /tools/markdown` — fetch a page as Markdown.
  - `POST /tools/html` — fetch preprocessed HTML.
- Optional inbound authentication with `PROXY_API_KEY`.
- Optional upstream authentication with `CRAWL4AI_API_KEY` using
  `Authorization: Bearer <token>`.
- `GET /health` for Docker health checks.
- Automatic `fit_markdown` selection with `raw_markdown` fallback.

## Docker

Build the image:

```bash
docker build -t crawl4ai-proxy:local .
```

Run it on the same Docker network as Crawl4AI and Open WebUI:

```bash
docker run -d \
  --name crawl4ai-proxy \
  --network your-network \
  --restart unless-stopped \
  -e LISTEN_PORT=8000 \
  -e CRAWL4AI_URL=http://crawl4ai-app:11235 \
  crawl4ai-proxy:local
```

If Crawl4AI authentication is enabled, add:

```bash
-e CRAWL4AI_API_KEY=your-crawl4ai-api-token
```

To require Open WebUI to authenticate against the proxy, add:

```bash
-e PROXY_API_KEY=your-proxy-api-key
```

See `docker-compose.example.yml` for a complete example.

## Open WebUI configuration

### Web Search / External Web Loader

In Open WebUI, go to **Admin Panel → Settings → Web Search** and configure the loader:

```text
Web Loader Engine: external
External Web Loader URL: http://crawl4ai-proxy:8000/crawl
External Web Loader API Key: <PROXY_API_KEY value, or any non-empty value if auth is disabled>
```

The web search engine itself (SearXNG, Brave, DuckDuckGo, etc.) still needs to be configured
separately. Crawl4AI does not search the web; it fetches pages that a search engine found.

The same loader is also used when adding a URL to a Knowledge collection.

### Optional OpenAPI Tool Server

The proxy can also be added as an Open WebUI OpenAPI Tool Server:

```text
URL: http://crawl4ai-proxy:8000
OpenAPI path: /openapi.json
```

Then enable the tools you want for a model. Available tools:

- `crawl_urls`
- `fetch_markdown`
- `fetch_html`

The tool server is optional. The External Web Loader works without it.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `LISTEN_IP` | `0.0.0.0` | Bind address |
| `LISTEN_PORT` | `8000` | Listen port |
| `CRAWL4AI_URL` | `http://crawl4ai:11235` | Crawl4AI base URL |
| `CRAWL4AI_ENDPOINT` | unset | Optional full override for the `/crawl` URL |
| `CRAWL4AI_API_KEY` | unset | Bearer token sent to Crawl4AI |
| `PROXY_API_KEY` | unset | Bearer token required from Open WebUI |
| `CRAWL4AI_TIMEOUT` | `330` | Upstream request timeout in seconds |
| `CRAWL4AI_CONNECT_TIMEOUT` | `10` | Upstream connect timeout in seconds |
| `MARKDOWN_MODE` | `auto` | `auto` (fit, then raw), `raw`, or `fit` |
| `ENABLE_TOOL_ENDPOINTS` | `true` | Enable `/tools/markdown` and `/tools/html` |
| `CRAWL4AI_CRAWLER_CONFIG` | unset | Trusted JSON merged into every `/crawl` request |
| `LOG_LEVEL` | `INFO` | Logging level |

`CRAWL4AI_URL` is the base URL; the proxy appends `/crawl`, `/md`, and `/html`.
`CRAWL4AI_ENDPOINT` remains available if the crawl endpoint lives somewhere unusual.

### Crawl4AI authentication

Crawl4AI accepts `Authorization: Bearer <token>` when authentication is enabled. The token may
be its static `CRAWL4AI_API_TOKEN` or an HS256 JWT issued by Crawl4AI. The static token is the
recommended choice for this proxy because it does not expire. Set the same value as
`CRAWL4AI_API_KEY`:

```bash
CRAWL4AI_API_KEY=your-crawl4ai-api-token
```

When `CRAWL4AI_API_KEY` is unset, no `Authorization` header is sent, which works with Crawl4AI
instances running without authentication.

## Endpoint support

| Crawl4AI endpoint | Supported here | Notes |
|---|---|---|
| `/crawl` | Yes, adapted | Used by Open WebUI's external loader |
| `/md` | Yes, as a tool | `POST /tools/markdown` |
| `/html` | Yes, as a tool | `POST /tools/html` |
| `/pdf`, `/screenshot` | No | Binary/base64 results are a poor fit for LLM tools |
| `/execute_js` | No | Security-sensitive; not exposed by default |
| `/ask` | No | Crawl4AI library context, not general web content |
| `/llm/{url}`, `/llm/job*` | No | Open WebUI already has its own model |
| `/crawl/job*`, `/crawl/stream` | No | Not compatible with Open WebUI's synchronous loader |
| `/config/dump`, `/schema`, `/hooks/info` | No | Operational/administrative |
| `/monitor/*`, `/metrics`, `/artifacts/*` | No | Operational/administrative |

Crawl4AI exposes MCP over SSE and WebSocket. Open WebUI's MCP client currently speaks streamable
HTTP, so the OpenAPI tool server path above is the supported option.

## Request behavior

- `/crawl` accepts `{"urls": [...]}` with 1–100 non-empty URL strings.
- Upstream failures are returned as `{"error": "...", "detail": "..."}`.
- Failed or empty crawl results are skipped and logged.
- Metadata values are flattened to strings for compatibility with Open WebUI's vector stores.
- `metadata.source` is always set from the crawled result URL.

## Development

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
ruff check .
pytest
```

Run locally against a Crawl4AI instance:

```bash
CRAWL4AI_URL=http://localhost:9756 python -m crawl4ai_proxy
```

## Security

Crawl4AI currently has no authentication by default. Keep it on a trusted Docker network and do
not expose it directly to the internet. Use `PROXY_API_KEY` to require authentication between
Open WebUI and this proxy, and `CRAWL4AI_API_KEY` when Crawl4AI authentication is enabled.

## License

The project license is in `LICENSE`.
