# AI-assisted with Codex, 2026-11-11; reviewed by Soohyun An
# Test reorganization assisted by Codex, 2026-11-15; reviewed by Soohyun An
"""Deterministic transport/clock inputs, not replacement collection algorithms."""

import importlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"
LIST_URL = "https://www.10000recipe.com/recipe/list.html?cat2=18&cat4=52&order=reco&page=1"
DETAIL_URL = "https://www.10000recipe.com/recipe/900001"


class FakeClock:
    """Advance virtual time instead of sleeping or depending on execution speed."""

    def __init__(self):
        self.elapsed = 0.0
        self.waits = []

    def monotonic(self):
        return self.elapsed

    def utcnow(self):
        return datetime(2026, 11, 11, tzinfo=UTC) + timedelta(seconds=self.elapsed)

    def sleep(self, seconds):
        assert seconds >= 0
        self.waits.append(seconds)
        self.elapsed += seconds


class FakeResponse:
    """Expose the response attributes consumed by an injected GET transport."""

    def __init__(self, status=200, *, body=b"<html>ok</html>", headers=None, url=None):
        self.status_code = status
        self.content = body
        self.headers = headers or {"Content-Type": "text/html; charset=utf-8"}
        self.url = url

    @property
    def text(self):
        return self.content.decode("utf-8")


class FakeTransport:
    """Return queued responses/exceptions and expose actual request inputs."""

    def __init__(self, clock, *outcomes):
        self.clock = clock
        self.outcomes = list(outcomes)
        self.calls = []

    def __call__(self, url, *, timeout, headers):
        self.calls.append(
            dict(url=url, timeout=timeout, headers=dict(headers), start=self.clock.elapsed)
        )
        assert self.outcomes, "Unexpected request after scripted responses were exhausted"
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        if outcome.url is None:
            outcome.url = url
        return outcome


def fixture_response(name, *, url=None):
    """Return synthetic source bytes; no fixture URL is requested."""
    return FakeResponse(body=(FIXTURES / name).read_bytes(), url=url)


def client_for(*outcomes, **overrides):
    """Construct the HTTP client with fully injected I/O and time sources."""
    module = importlib.import_module("crawlers.tenkrecipes.fetching")
    clock = FakeClock()
    transport = FakeTransport(clock, *outcomes)
    options = dict(
        transport=transport,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
        utcnow=clock.utcnow,
        live=True,
        max_wait=60,
        run_budget=120,
    )
    options.update(overrides)
    return module, module.HttpClient(**options), transport, clock
