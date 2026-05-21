# sessemi

Python client and CLI for the [Sessemi](https://sessemi.com) web scraping API. Scrape sites protected by Cloudflare, DataDome, and Akamai — one line of code.

## Install

```bash
pip install sessemi
```

## Quick start

```python
from sessemi import Sessemi

client = Sessemi(key="your_api_key")
result = client.scrape("https://www.leboncoin.fr/recherche?category=10", country="FR")

print(result.content)       # page HTML
print(result.status_code)   # 200
print(result.solved)        # True — challenge was solved
```

Or from the command line:

```bash
export SESSEMI_KEY=your_api_key

sessemi scrape "https://www.idealista.com/en/venta-viviendas/" -c ES
sessemi scrape "https://www.nike.com/w/shoes" -f json -o shoes.json
sessemi credits
```

Get a free API key at [app.sessemi.com](https://app.sessemi.com).

## Client

### `Sessemi(key, url, timeout, retries)`

```python
from sessemi import Sessemi

# From constructor
client = Sessemi(key="sk_...")

# Or from environment variables
# SESSEMI_KEY, SESSEMI_URL, SESSEMI_TIMEOUT, SESSEMI_RETRIES
client = Sessemi()
```

### `client.scrape(url, **kwargs) → ScrapeResult`

```python
result = client.scrape(
    "https://www.example.com",
    country="FR",          # geo-target (auto-selects residential proxy)
    render=True,           # force browser rendering for JS-heavy pages
    session="my-session",  # persist cookies/IP across requests
    headers={"Accept": "application/json"},
    solve=True,            # enable challenge solving (default for residential)
    block_resources=True,  # skip images/fonts/css for speed
    wait_for="css:.product-list",  # wait for element before returning
    screenshot=True,       # capture screenshot
)

result.content              # page content (HTML or JSON string)
result.ok                   # True if success and body_size > 0
result.status_code          # HTTP status
result.body_size            # content size in bytes
result.challenge_provider   # "cloudflare", "datadome", "akamai", or ""
result.solved               # True if a challenge was solved
result.credits_charged      # credits used
result.credits_remaining    # credits left this cycle
result.duration_ms          # server-side duration
result.cookies              # response cookies
result.screenshot           # screenshot bytes (if requested)
result.error                # error message on failure
```

### `client.scrape_batch(urls, **kwargs) → list[ScrapeResult]`

Scrape multiple URLs concurrently using async tasks. Submits all URLs, polls until complete.

```python
results = client.scrape_batch(
    ["https://example.com/1", "https://example.com/2", "https://example.com/3"],
    country="US",
    timeout=300,
)
for r in results:
    print(f"{r.url} — {'OK' if r.ok else r.error}")
```

### `client.health() → dict`

```python
status = client.health()
# {"status": "healthy", "workers": 10, ...}
```

## CLI

```
sessemi scrape URL [options]
sessemi credits
sessemi health
```

### Options

```
-c, --country CODE    Country code (FR, US, DE, ES, ...)
-p, --pool POOL       Proxy pool: residential | datacenter
-s, --session NAME    Named session for cookie persistence
-f, --format FMT      Output: html (default) | json
-o, --output FILE     Save to file
-q, --quiet           Suppress status output
--render              Force browser rendering
--screenshot          Capture screenshot (use with -o)
--headers JSON        Custom headers as JSON string
-m, --method METHOD   HTTP method (default: GET)
```

### Examples

```bash
# Scrape with geo-targeting
sessemi scrape "https://www.leboncoin.fr/recherche?category=10" -c FR

# JSON output piped to jq
sessemi scrape "https://www.idealista.com/en/" -c ES -f json | jq .

# Save to file
sessemi scrape "https://www.nike.com/w/shoes" -o shoes.html

# Check credits
sessemi credits
```

## Configuration

All config works via constructor args or environment variables:

| Env var | Default | Description |
|---------|---------|-------------|
| `SESSEMI_KEY` | — | API key (required) |
| `SESSEMI_URL` | `https://api.sessemi.com` | API base URL |
| `SESSEMI_TIMEOUT` | `60` | Default timeout per scrape (seconds) |
| `SESSEMI_RETRIES` | `3` | Retry count on failure |
| `SESSEMI_RETRY_ON` | `blocked` | Comma-separated failure types to retry |

## Links

- [Sessemi](https://sessemi.com) — web scraping API
- [Documentation](https://sessemi.com/docs)
- [MCP server](https://github.com/sessemi/sessemi-mcp) — use Sessemi from AI agents
- [Examples](https://github.com/sessemi/sessemi-examples)
- [Get API key](https://app.sessemi.com)
