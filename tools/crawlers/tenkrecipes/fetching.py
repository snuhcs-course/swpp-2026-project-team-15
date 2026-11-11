# AI-assisted with Codex, 2026-11-11; human review pending.
"""Serial, opt-in source GETs with bounded retries and injectable time/I/O."""

import hashlib
import math
import re
import threading
import time
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit
from uuid import uuid4

import requests


class NetworkDisabled(ValueError):
    """Live I/O was not explicitly enabled."""


def source_url(url: str) -> str:
    """Reject credentials and non-source URLs before any transport access."""
    parts = urlsplit(url)
    if (
        parts.scheme not in ("http", "https")
        or parts.hostname not in ("www.10000recipe.com", "10000recipe.com")
        or parts.username is not None
        or parts.password is not None
        or parts.port not in (None, 80, 443)
        or not re.fullmatch(r"/recipe/(?:list\.html|[0-9]+/?)", parts.path)
    ):
        raise ValueError("Expected a public 10000recipe recipe or list URL")
    return url


def request_source(url, *, timeout, headers):
    """Use a fresh credential-free session and do not follow redirects implicitly."""
    with requests.Session() as session:
        session.trust_env = False
        return session.get(url, timeout=timeout, headers=headers, allow_redirects=False)


class HttpClient:
    """Perform paced GETs; budgets are seconds per client invocation.

    Only response metadata and exception types are logged. Exception messages,
    response headers, and cookies are deliberately excluded from diagnostics.
    """

    def __init__(
        self,
        *,
        transport=request_source,
        sleep=time.sleep,
        monotonic=time.monotonic,
        utcnow=lambda: datetime.now(UTC),
        live=False,
        max_wait=60,
        run_budget=120,
    ):
        for value in (max_wait, run_budget):
            if not math.isfinite(value) or value <= 0:
                raise ValueError("Wait and run budgets must be finite positive seconds")
        self.transport, self.sleep = transport, sleep
        self.monotonic, self.utcnow = monotonic, utcnow
        self.live = live
        self.policy = dict(
            min_interval=2,
            timeout=(10, 30),
            max_attempts=3,
            max_wait=max_wait,
            run_budget=run_budget,
        )
        self._started = monotonic()
        self._last_start = None
        self._lock = threading.Lock()

    def _retry_delay(self, value):
        """Interpret Retry-After seconds or date without turning invalid text into retries."""
        if value is None:
            return 0.0
        try:
            seconds = float(value)
        except (TypeError, ValueError):
            try:
                date = parsedate_to_datetime(value)
                if date.tzinfo is None:
                    date = date.replace(tzinfo=UTC)
                seconds = (date - self.utcnow()).total_seconds()
            except (TypeError, ValueError, OverflowError):
                return 0.0
        return max(0.0, seconds) if math.isfinite(seconds) else 0.0

    def get(self, url):
        """Return body, attempts and status; never retry denial or challenge responses."""
        if not self.live:
            raise NetworkDisabled("Network access requires --live")
        source_url(url)
        with self._lock:
            return self._get(url)

    def _get(self, url):
        attempts, responses = [], []
        body = None
        retry_at = self.monotonic()

        def result(status, reason=None):
            return dict(
                status=status,
                reason=reason,
                body=body,
                attempts=attempts,
                responses=responses,
                retry_not_before=(
                    self.utcnow() + timedelta(seconds=max(0, ready - self.monotonic()))
                ).isoformat()
                if status == "deferred" and ready > self.monotonic()
                else None,
            )

        for number in range(1, self.policy["max_attempts"] + 1):
            now = self.monotonic()
            ready = max(retry_at, (self._last_start + 2) if self._last_start is not None else now)
            wait = max(0.0, ready - now)
            if wait > self.policy["max_wait"]:
                return result("deferred", "wait_budget_exceeded")
            if now - self._started + wait >= self.policy["run_budget"]:
                return result("deferred", "run_budget_exceeded")
            if wait:
                self.sleep(wait)
            self._last_start = self.monotonic()
            attempt = dict(
                attempt_id=uuid4().hex,
                source_url=url,
                number=number,
                started_at=self.utcnow().isoformat(),
            )
            attempts.append(attempt)
            retry_after = None
            try:
                response = self.transport(
                    url,
                    timeout=self.policy["timeout"],
                    headers={"User-Agent": "MyLittleChef-RecipeCollector/0.1"},
                )
                body = response.content
                status_code = response.status_code
                attempt.update(
                    final_url=response.url or url,
                    fetched_at=self.utcnow().isoformat(),
                    status_code=status_code,
                    sha256=hashlib.sha256(body).hexdigest(),
                )
                responses.append(dict(attempt=dict(attempt), body=body))
                if status_code in (401, 403):
                    return result("blocked", "access_denied")
                if re.search(rb"challenge-form|cf-chl-|g-recaptcha", body, re.I):
                    return result("blocked", "challenge")
                if 200 <= status_code < 300:
                    return result("ok")
                retryable = status_code in (429, 500, 502, 503, 504)
                retry_after = response.headers.get("Retry-After")
                if not retryable:
                    return result("failed", "http_error")
            except (requests.Timeout, requests.ConnectionError) as exc:
                attempt.update(error=type(exc).__name__, fetched_at=self.utcnow().isoformat())
            except requests.RequestException as exc:
                attempt.update(error=type(exc).__name__, fetched_at=self.utcnow().isoformat())
                return result("failed", "transport_error")
            if number == self.policy["max_attempts"]:
                return result("failed", "retry_exhausted")
            retry_at = self.monotonic() + self._retry_delay(retry_after)
        raise AssertionError("Unreachable retry loop")
