# open sessemi
import os
import time
import logging
import base64
from dataclasses import dataclass, field
from typing import Optional, List

import requests as _requests

logger = logging.getLogger("sessemi")

_UNSET = object()


@dataclass
class ScrapeResult:
    success: bool
    url: str
    html: str = ""
    html_size: int = 0
    cookies: list = field(default_factory=list)
    user_agent: str = ""
    worker_id: int = -1
    proxy_used: str = ""
    proxy_port: int = 0
    country: str = ""
    session: str = ""
    challenge_type: str = ""
    challenge_provider: str = ""
    wait_for_match: str = ""
    failure_type: str = ""
    status_code: int = 0
    duration_ms: int = 0
    queued_ms: int = 0
    retry_count: int = 0
    error: str = ""
    warning: str = ""
    pool: str = ""
    solved: bool = False
    credits_charged: int = 0
    credits_remaining: int = 0
    resolved_url: str = ""
    screenshot: bytes = b""
    response: _requests.Response = field(default=None, repr=False)

    @classmethod
    def from_json(cls, data: dict, response: _requests.Response = None) -> "ScrapeResult":
        ss_b64 = data.pop("screenshot", None)
        known = {k for k in cls.__dataclass_fields__}
        obj = cls(**{k: v for k, v in data.items() if k in known})
        if ss_b64:
            obj.screenshot = base64.b64decode(ss_b64)
        obj.response = response
        return obj

    @property
    def ok(self) -> bool:
        return self.success and self.html_size > 0

    @property
    def content(self) -> bytes:
        """Raw response bytes — drop-in for requests.Response.content"""
        if self.response is not None:
            return self.response.content
        return self.html.encode("utf-8") if self.html else b""

    @property
    def text(self) -> str:
        """Response text — drop-in for requests.Response.text"""
        return self.html


class SessemiError(Exception):
    pass


class SessemiTimeout(SessemiError):
    pass


class SessemiUnavailable(SessemiError):
    pass


class Sessemi:
    """
    All config from env vars or constructor args:
        SESSEMI_URL      - base URL (e.g. https://xxx.ngrok-free.app)
        SESSEMI_KEY      - API key
        SESSEMI_TIMEOUT  - default timeout per scrape (seconds)
        SESSEMI_RETRIES  - default retry count
        SESSEMI_RETRY_ON - comma-separated failure types to retry on
    """

    def __init__(
        self,
        url: str = _UNSET,
        key: str = _UNSET,
        timeout: int = _UNSET,
        retries: int = _UNSET,
        retry_on: list = _UNSET,
    ):
        self.base_url = (
            url if url is not _UNSET
            else os.environ.get("SESSEMI_URL", "https://api.sessemi.com")
        )

        self.api_key = (
            key if key is not _UNSET
            else os.environ.get("SESSEMI_KEY", "")
        )

        self.timeout = (
            timeout if timeout is not _UNSET
            else int(os.environ.get("SESSEMI_TIMEOUT", "60"))
        )

        self.retries = (
            retries if retries is not _UNSET
            else int(os.environ.get("SESSEMI_RETRIES", "3"))
        )

        self.retry_on = (
            retry_on if retry_on is not _UNSET
            else [x.strip() for x in os.environ.get("SESSEMI_RETRY_ON", "blocked").split(",") if x.strip()]
        )

        self._http = _requests.Session()
        if self.api_key:
            self._http.headers["X-API-Key"] = self.api_key

    def scrape(
        self,
        url: str,
        *,
        stealth: bool = None,
        pool: str = None,
        solve: bool = None,
        region: str = None,
        timeout: int = None,
        proxy: str = None,
        country: str = None,
        session: str = None,
        screenshot: bool = False,
        block_resources: bool = False,
        wait_for: str = None,
        wait_for_js: str = None,
        wait_timeout: int = None,
        retry: int = None,
        retry_on: list = None,
        render: bool = False,
    ) -> ScrapeResult:
        """
        Scrape a URL through api

        Args:
            url:          Target URL to scrape.
            pool:         Proxy pool: "datacenter" (1 credit) or "residential"
                          (10 credits, solving included). Default: datacenter.
            solve:        Enable challenge solving (Cloudflare, Akamai, DataDome).
                          Default: True for residential, False for datacenter.
                          Datacenter + solve = 6 credits (budget option).
            region:       Residential proxy region: "eu", "na", "as", "af", "oc", "sa".
                          Also accepts full names: "europe", "north_america", etc.
                          Only with pool="residential".
            timeout:      Max seconds for the scrape (default: self.timeout).
            proxy:        Per-request proxy URL. Supports standard format
                          "http://user:pass@host:port" and colon format
                          "host:port:user:pass". Server expands {session_id}
                          and {country} automatically.
                          Use "none"/"direct" for no proxy, or omit for server default.
            country:      Proxy country code (e.g. "FR", "DE"). Only with
                          pool="residential".
            session:      Session ID — pins request to a specific worker so cookies
                          and IP persist across requests. Any string works.
            screenshot:   If True, include base64 PNG screenshot in response.
            wait_for:     CSS selector(s) to wait for after page load. Comma-
                          separated for OR (e.g. ".products, .no-results").
                          Use for AJAX-loaded content.
            wait_for_js:  JS expression that returns truthy when page is ready.
                          Use for text matching or complex conditions, e.g.
                          "document.querySelector('h1')?.textContent.includes('Résultat')"
                          Can be combined with wait_for — first match wins.
            wait_timeout: Max seconds to wait for selector/JS (default: 10).
            retry:        Max retries on failure (default: self.retries).
            retry_on:     Failure types to retry on (default: self.retry_on).
                          Options: "server_error", "challenge_timeout",
                          "challenge_unsolved", "navigate_failed", "blocked".

        Returns:
            ScrapeResult with:
                .solved        — True if a challenge was detected and solved
                .warning       — Non-fatal advisory (e.g. DC solve less reliable)
                .pool          — Pool used: "datacenter", "residential", "custom"
                .challenge_type — "clear", "solved", "blocked", "timeout", etc.
                .wait_for_match — "css", "js", "timeout", or ""
        """
        body = {"url": url, "timeout": timeout or self.timeout}

        if stealth is not None:
            body["stealth"] = stealth
        if pool:
            body["pool"] = pool
        if solve is not None:
            body["solve"] = solve
        if region:
            body["region"] = region
        if proxy:
            body["proxy"] = proxy
        if country:
            body["country"] = country.upper()
        if session:
            body["session"] = session
        if screenshot:
            body["screenshot"] = True
        if block_resources:
            body["block_resources"] = True
        if wait_for:
            body["wait_for"] = wait_for
        if wait_for_js:
            body["wait_for_js"] = wait_for_js
        if wait_timeout is not None:
            body["wait_timeout"] = wait_timeout
        if render:
            body["render"] = True

        r = retry if retry is not None else self.retries
        ro = retry_on if retry_on is not None else self.retry_on
        if r > 0:
            body["retry"] = r
        if ro:
            body["retry_on"] = ro

        data, resp = self._post("/scrape", body)
        return ScrapeResult.from_json(data, response=resp)

    def screenshot(self, url: str, *, timeout: int = None) -> bytes:
        resp = self._http.post(
            f"{self.base_url}/screenshot",
            json={"url": url, "timeout": timeout or self.timeout},
            timeout=(timeout or self.timeout) + 30,
        )
        resp.raise_for_status()
        return resp.content

    def health(self) -> dict:
        resp = self._http.get(f"{self.base_url}/health", timeout=10)
        resp.raise_for_status()
        return resp.json()

    def sessions(self) -> dict:
        resp = self._http.get(f"{self.base_url}/sessions", timeout=10)
        resp.raise_for_status()
        return resp.json()

    def delete_session(self, session_id: str) -> dict:
        resp = self._http.delete(
            f"{self.base_url}/session",
            params={"id": session_id},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    def ping(self) -> bool:
        try:
            h = self.health()
            return h.get("status") in ("healthy", "busy", "queuing")
        except Exception:
            return False

    def _post(self, path: str, body: dict) -> tuple:
        req_timeout = body.get("timeout", self.timeout) + 60
        t0 = time.monotonic()
        try:
            resp = self._http.post(
                f"{self.base_url}{path}",
                json=body,
                timeout=req_timeout,
            )
        except _requests.exceptions.Timeout:
            raise SessemiTimeout(f"request timed out after {req_timeout}s")
        except (
            _requests.exceptions.ConnectionError,
            _requests.exceptions.ChunkedEncodingError,
        ) as e:
            raise SessemiUnavailable(f"cannot reach {self.base_url}: {e}")

        # Parse JSON safely — ngrok/proxies may return HTML error pages
        try:
            data = resp.json()
        except (ValueError, _requests.exceptions.JSONDecodeError):
            # Not JSON — likely ngrok 502/504 HTML page or tunnel expired
            snippet = resp.text[:200].strip()
            if resp.status_code >= 500:
                raise SessemiUnavailable(
                    f"upstream error (HTTP {resp.status_code}): {snippet}")
            elif resp.status_code == 404:
                raise SessemiUnavailable(
                    f"endpoint not found (HTTP 404) — check SESSEMI_URL: {snippet}")
            else:
                raise SessemiError(
                    f"non-JSON response (HTTP {resp.status_code}): {snippet}")

        if resp.status_code == 429:
            raise SessemiUnavailable(data.get("error", "queue full"))

        resp.raise_for_status()

        elapsed = int((time.monotonic() - t0) * 1000)
        url_short = body.get("url", "?")[:60]
        if data.get("success"):
            logger.debug("✓ %s (%dms w%s)", url_short, elapsed, data.get("worker_id", "?"))
        else:
            logger.warning("✗ %s → %s (%dms)", url_short, data.get("failure_type", "?"), elapsed)

        if data.get("warning"):
            logger.warning("⚠ %s: %s", url_short, data["warning"])

        return data, resp