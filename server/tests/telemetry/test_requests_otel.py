# AI-generated with Claude Code (Opus 5.5), 2026-11-20; reviewed by Jaehyuk Choi.
"""Request records come from OpenTelemetry but go only to our local file: no network exporter is
installed or configured, whatever OTEL_* variables say."""

import importlib.util

from fastapi.testclient import TestClient
from opentelemetry import trace

from app.main import create_app
from app.telemetry.requests import SinkSpanExporter, record_requests
from tests.conftest import StubVision


class ListSink:
    def __init__(self):
        self.records = []

    def write(self, records):
        self.records.extend(records)


def test_no_network_exporter_is_installed():
    for module in (
        "opentelemetry.exporter.otlp",
        "opentelemetry.exporter.otlp.proto.http",
        "opentelemetry.exporter.otlp.proto.grpc",
        "opentelemetry.exporter.zipkin",
        "opentelemetry.exporter.jaeger",
        "opentelemetry.exporter.prometheus",
    ):
        assert importlib.util.find_spec(module.split(".")[0]) is not None  # the namespace exists
        try:
            found = importlib.util.find_spec(module)
        except ModuleNotFoundError:
            found = None
        assert found is None, module


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
