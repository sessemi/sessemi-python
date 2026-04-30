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
    json: str = ""  # populated when target returns application/json (html is empty)
    body_size: int = 0  # size of whichever field (html or json) has content
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
    script_result: dict = field(default=None, repr=False)  # JS script execution result
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
        return self.success and self.body_size > 0

    @property
    def content(self) -> bytes:
        """Raw response bytes — drop-in for requests.Response.content"""
        if self.response is not None:
            return self.response.content
        body = self.html or self.json
        return body.encode("utf-8") if body else b""

    @property
    def text(self) -> str:
        """Response text — drop-in for requests.Response.text"""
        return self.html or self.json


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
        exclude_cookies: list = None,
        headers: dict = None,
        method: str = None,
        body: str = None,
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
            headers:      Custom HTTP headers to send with the request.
                          Dict of {name: value}. Applied on both fast path
                          and browser path (render=True). Host and Connection
                          cannot be overridden.
            method:       HTTP method: "GET", "POST", "PUT", "PATCH", "DELETE".
                          Default: "GET". Only applies to the fast path.
            body:         Request body for POST/PUT/PATCH. Typically URL-encoded
                          form data or a JSON string. Set Content-Type via
                          the headers parameter.

        Returns:
            ScrapeResult with:
                .solved        — True if a challenge was detected and solved
                .warning       — Non-fatal advisory (e.g. DC solve less reliable)
                .pool          — Pool used: "datacenter", "residential", "custom"
                .challenge_type — "clear", "solved", "blocked", "timeout", etc.
                .wait_for_match — "css", "js", "timeout", or ""
        """
        request_body = body  # capture before local 'body' shadows the param
        body = {"url": url, "timeout": timeout or self.timeout}

        if stealth is not None:
            body["stealth"] = stealth
        if pool:
            body["pool"] = pool
        if solve is not None:
            body["solve"] = solve
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
        if exclude_cookies:
            body["exclude_cookies"] = exclude_cookies
        if headers:
            body["headers"] = headers
        if method and method.upper() != "GET":
            body["method"] = method.upper()
        if request_body:
            body["body"] = request_body

        r = retry if retry is not None else self.retries
        ro = retry_on if retry_on is not None else self.retry_on
        if r > 0:
            body["retry"] = r
        if ro:
            body["retry_on"] = ro

        data, resp = self._post("/scrape", body)
        return ScrapeResult.from_json(data, response=resp)

    def script_exec(
        self,
        script: str,
        *,
        session: str,
        timeout: int = None,
    ) -> ScrapeResult:
        """Run JavaScript on the current page in an existing browser session.

        Script-only mode: no URL navigation. The script executes in the
        context of whatever page the session last navigated to, with full
        access to the browser's cookies (including validated _abck, etc.).

        The script body is wrapped in an async IIFE — use ``await`` freely
        and ``return`` the result (will be JSON-serialized).

        Args:
            script:   JavaScript code to execute.
            session:  Session ID (must already exist from a prior scrape).
            timeout:  Max seconds for script execution.

        Returns:
            ScrapeResult with ``script_result`` populated.
            The engine returns ``{"value": "<json_string>"}`` via Marionette;
            use :meth:`parse_script_result` to unwrap.
        """
        body = {
            "script": script,
            "session": session,
            "timeout": timeout or self.timeout,
        }
        data, resp = self._post("/scrape", body)
        return ScrapeResult.from_json(data, response=resp)

    @staticmethod
    def parse_script_result(script_result):
        """Unwrap script_result from engine response.

        The engine wraps as ``{"value": "<json_string>"}`` via Marionette.
        Returns the parsed Python object.
        """
        import json as _json
        if script_result is None:
            return None
        if isinstance(script_result, dict) and "value" in script_result:
            raw = script_result["value"]
            return _json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(script_result, str):
            return _json.loads(script_result)
        return script_result

    def scrape_batch(
        self,
        urls: list,
        *,
        country: str = None,
        render: bool = None,
        solve: bool = None,
        stealth: bool = None,
        block_resources: bool = None,
        headers: dict = None,
        timeout: int = 300,
        poll_interval: float = 2.0,
    ) -> list:
        """Scrape multiple URLs concurrently via async tasks.

        Submits all URLs as async tasks, then polls until all complete
        or the timeout is reached. Returns results in the same order
        as the input URLs.

        Not compatible with the ``session`` parameter (server rejects it).

        Args:
            urls:             List of URLs to scrape.
            country:          Two-letter country code for proxy geolocation.
            render:           Force browser rendering.
            solve:            Attempt anti-bot challenge solving.
            stealth:          Start fast, escalate only when challenged.
            block_resources:  Block images/fonts/media for speed.
            headers:          Custom HTTP headers to forward.
            timeout:          Max seconds to wait for all tasks (default 300).
            poll_interval:    Seconds between poll cycles (default 2.0).

        Returns:
            List of ScrapeResult, one per URL, in input order.
            Failed tasks have success=False with error details.

        Example::

            results = client.scrape_batch(
                ["https://example.com/1", "https://example.com/2"],
                stealth=True,
                country="FR",
            )
            for r in results:
                print(f"{r.url} — {'OK' if r.ok else r.error}")
        """
        if not urls:
            return []

        # Shared params (everything except url)
        shared = {}
        if country is not None:
            shared["country"] = country
        if render is not None:
            shared["render"] = render
        if solve is not None:
            shared["solve"] = solve
        if stealth is not None:
            shared["stealth"] = stealth
        if block_resources is not None:
            shared["block_resources"] = block_resources
        if headers is not None:
            shared["headers"] = headers

        # ── Submit all as async tasks ──
        task_ids = []  # parallel to urls
        for url in urls:
            body = {"url": url, **shared}
            try:
                resp = self._http.post(
                    f"{self.base_url}/scrape?async=true",
                    json=body,
                    timeout=(10, 30),
                )
                if resp.status_code == 202:
                    task_ids.append(resp.json().get("task_id"))
                else:
                    task_ids.append(None)
                    logger.warning("batch: submit failed for %s (HTTP %d)", url[:60], resp.status_code)
            except Exception as exc:
                task_ids.append(None)
                logger.warning("batch: submit error for %s: %s", url[:60], exc)

        submitted = sum(1 for t in task_ids if t is not None)
        logger.info("batch: submitted %d/%d async tasks", submitted, len(urls))

        # Pre-fill failures for tasks that never submitted
        results = [None] * len(urls)
        for i, tid in enumerate(task_ids):
            if tid is None:
                results[i] = ScrapeResult.from_json({
                    "success": False,
                    "url": urls[i],
                    "error": "async task submission failed",
                })

        # ── Poll until all tasks resolve or timeout ──
        pending = {i: tid for i, tid in enumerate(task_ids) if tid is not None}
        deadline = time.monotonic() + timeout

        while pending and time.monotonic() < deadline:
            time.sleep(poll_interval)

            for i, tid in list(pending.items()):
                try:
                    resp = self._http.get(
                        f"{self.base_url}/tasks/{tid}",
                        timeout=(10, 30),
                    )
                    if resp.status_code != 200:
                        continue

                    data = resp.json()
                    status = data.get("status")

                    if status in ("done", "failed"):
                        result_data = data.get("result")
                        if result_data and isinstance(result_data, dict):
                            results[i] = ScrapeResult.from_json(result_data)
                        else:
                            results[i] = ScrapeResult.from_json({
                                "success": False,
                                "url": urls[i],
                                "error": f"task {status} with no result",
                            })
                        del pending[i]
                except Exception:
                    continue

            if pending:
                logger.debug("batch: %d/%d tasks still pending", len(pending), len(urls))

        # Timeout stragglers
        for i in pending:
            results[i] = ScrapeResult.from_json({
                "success": False,
                "url": urls[i],
                "error": f"task timed out after {timeout}s (task_id: {task_ids[i]})",
            })
            logger.warning("batch: task %s timed out for %s", task_ids[i], urls[i][:60])

        ok_count = sum(1 for r in results if r.success)
        logger.info("batch: complete — %d/%d succeeded", ok_count, len(urls))
        return results

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

        # Surface the server's error message for 4xx responses.
        # Without this, raise_for_status() gives a generic "400 Bad Request"
        # and the actual explanation (e.g. "Country targeting requires
        # pool=residential") is lost.
        if resp.status_code >= 400 and resp.status_code < 500:
            msg = data.get("error", resp.text[:200])
            hint = data.get("hint", "")
            detail = f"{msg} ({hint})" if hint else msg
            raise SessemiError(
                f"HTTP {resp.status_code}: {detail}"
            )

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