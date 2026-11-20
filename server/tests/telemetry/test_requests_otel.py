# AI-generated with Claude Code (Opus 5.5), 2026-11-20; reviewed by Jaehyuk Choi.
"""Request records come from OpenTelemetry but go only to our local file: no network exporter is
installed or configured, whatever OTEL_* variables say."""

import importlib.metadata

import pytest
from fastapi.testclient import TestClient
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from app.main import create_app
from app.telemetry.requests import SinkSpanExporter, record_requests
from tests.conftest import StubVision


class ListSink:
    def __init__(self):
        self.records = []

    def write(self, records):
        self.records.extend(records)


def test_no_exporter_package_beyond_the_sdk_is_installed():
    # A network exporter (OTLP, Zipkin, Prometheus, ...) ships as an opentelemetry-exporter-*
    # distribution and registers itself under these entry-point groups; the SDK brings only
    # "console". With none installed, no OTEL_* variable can switch one on.
    names = {(d.metadata["Name"] or "").lower() for d in importlib.metadata.distributions()}
    assert not {n for n in names if n.startswith("opentelemetry-exporter")}
    for group in (
        "opentelemetry_traces_exporter",
        "opentelemetry_metrics_exporter",
        "opentelemetry_logs_exporter",
    ):
        found = {e.name for e in importlib.metadata.entry_points(group=group)}
        assert found <= {"console"}, (group, found)


def test_the_app_refuses_a_global_provider_from_auto_instrumentation(monkeypatch):
    monkeypatch.setattr(trace, "get_tracer_provider", lambda: TracerProvider())
    with pytest.raises(RuntimeError):
        record_requests(create_app(StubVision()), ListSink())


def test_the_only_exporter_is_ours_even_with_otel_variables_set(monkeypatch):
    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "otlp")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector.invalid:4318")
    sink = ListSink()
    app = create_app(StubVision())
    provider = record_requests(app, sink)
    processors = provider._active_span_processor._span_processors
    assert [type(p.span_exporter) for p in processors] == [SinkSpanExporter]
    # The app's provider is private: the process-wide one stays the no-op default.
    assert not isinstance(trace.get_tracer_provider(), type(provider))
    TestClient(app).get("/dishes")
    assert [r["http.route"] for r in sink.records] == ["/dishes"]


def test_a_dish_route_containing_a_skipped_word_is_still_recorded():
    sink = ListSink()
    app = create_app(StubVision())
    record_requests(app, sink)
    client = TestClient(app)
    client.get("/dishes/already-ready/recipe")
    client.get("/ready")
    assert [r["http.route"] for r in sink.records] == ["/dishes/{dish_id}/recipe"]
