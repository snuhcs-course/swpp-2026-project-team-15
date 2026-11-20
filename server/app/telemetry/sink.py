# AI-generated with Claude Code (Opus 5.5), 2026-11-20; reviewed by Jaehyuk Choi.
"""Where usage records go. The role is one method; the running app writes JSON lines to a file,
tests hand in a list. Created once in main.py and injected (no module-level instance)."""

import json
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol


class TelemetrySink(Protocol):
    def write(self, records: list[dict[str, Any]]) -> None:
        """Store the records in order. Must not raise for a full disk or a closed file: losing
        usage data is better than failing the user's request."""
        ...


class JsonlSink:
    """Appends one JSON object per line. One lock: the server runs requests on a thread pool."""

    def __init__(self, path: Path | str):
        self._path = Path(path)
        self._lock = threading.Lock()

    def write(self, records: list[dict[str, Any]]) -> None:
        if not records:
            return
        lines = "".join(
            json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n" for r in records
        )
        try:
            with self._lock, self._path.open("a", encoding="utf-8") as out:
                out.write(lines)
        except OSError:
            pass  # see the role's contract


def build_telemetry_sink(env: Mapping[str, str]) -> TelemetrySink | None:
    """None (collection off) unless TELEMETRY_FILE names a file in a writable folder."""
    path = env.get("TELEMETRY_FILE", "").strip()
    return JsonlSink(path) if path else None
