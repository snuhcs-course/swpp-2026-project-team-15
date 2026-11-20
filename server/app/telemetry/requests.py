# AI-generated with Claude Code (Opus 5.5), 2026-11-20; reviewed by Jaehyuk Choi.
"""One record per request, measured by OpenTelemetry's FastAPI instrumentation and written by our
own exporter to the local usage file: method, route template, status and duration under the
OpenTelemetry HTTP names, never the body, the query or a header. This counts server errors for
every app build, including builds without app events.

Nothing leaves the server: the tracer provider is private to the app (not the global one), its
only span processor holds the exporter below, and no network exporter package is installed, so
OTEL_* exporter variables have nothing to switch on (tests/telemetry/test_requests_otel.py)."""

from collections.abc import Sequence

from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.trace import SpanKind

from app.telemetry.sink import TelemetrySink

SKIPPED = "health,ready,telemetry/events"  # probes and the usage upload itself


class SinkSpanExporter(SpanExporter):
    """Writes each finished server span as one usage record; other spans are ignored."""

    def __init__(self, sink: TelemetrySink):
        self._sink = sink

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        records = [record(s) for s in spans if s.kind is SpanKind.SERVER]
        self._sink.write(records)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        pass


def record(span: ReadableSpan) -> dict:
    """The OpenTelemetry HTTP server names, old or new convention, as the new names."""
    a = span.attributes or {}
    start, end = span.start_time or 0, span.end_time or span.start_time or 0
    return {
        "kind": "request",
        "t": start // 1_000_000,
        "http.request.method": a.get("http.request.method", a.get("http.method")),
        "http.route": a.get("http.route") or "unmatched",
        "http.response.status_code": a.get(
            "http.response.status_code", a.get("http.status_code", 500)
        ),
        "duration_ms": round((end - start) / 1_000_000),
    }


def record_requests(app: FastAPI, sink: TelemetrySink) -> TracerProvider:
    """Instrument ``app`` with a provider of its own; returns it for tests."""
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(SinkSpanExporter(sink)))
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider, excluded_urls=SKIPPED)
    return provider
