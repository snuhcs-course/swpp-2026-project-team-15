# AI-generated with Claude Code (Opus 5.5), 2026-11-20; reviewed by Jaehyuk Choi.
"""One record per request: route template, status and time, never the body or the query. This
counts server errors for every app build, including builds without app events."""

import time

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import RequestResponseEndpoint

from app.telemetry.sink import TelemetrySink

SKIPPED = {"/health", "/ready", "/telemetry/events"}


def record_requests(app: FastAPI, sink: TelemetrySink) -> None:
    @app.middleware("http")
    async def timing(request: Request, call_next: RequestResponseEndpoint) -> Response:
        started = time.perf_counter()
        code = 500
        try:
            response = await call_next(request)
            code = response.status_code
            return response
        finally:
            route = request.scope.get("route")
            path = getattr(route, "path", None) or "unmatched"
            if path not in SKIPPED:
                sink.write(
                    [
                        {
                            "kind": "request",
                            "t": int(time.time() * 1000),
                            "method": request.method,
                            "route": path,
                            "status": code,
                            "ms": round((time.perf_counter() - started) * 1000),
                        }
                    ]
                )
