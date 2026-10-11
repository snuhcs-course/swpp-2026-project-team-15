# AI-generated with Claude Code (Opus 5.5), 2026-10-11; review pending by Jaehyuk Choi.
"""Recognition providers behind one interface, so tests never call a paid API."""

import hashlib
import json
from pathlib import Path
from typing import Protocol

from pydantic import TypeAdapter

from app.vision.schemas import DetectedItem

DETECTED_ITEMS = TypeAdapter(list[DetectedItem])


class VisionProvider(Protocol):
    def detect(self, image: bytes, mime_type: str) -> list[DetectedItem]: ...


class FixtureVisionProvider:
    """Replays recorded Gemini outputs; the same image always yields the same fixture."""

    def __init__(self, fixture_dir: Path) -> None:
        self._fixtures = [
            DETECTED_ITEMS.validate_python(json.loads(path.read_text(encoding="utf-8"))["items"])
            for path in sorted(fixture_dir.glob("*.json"))
        ]
        if not self._fixtures:
            raise FileNotFoundError(f"No vision fixtures in {fixture_dir}")

    def detect(self, image: bytes, mime_type: str) -> list[DetectedItem]:
        index = int.from_bytes(hashlib.sha256(image).digest()[:4]) % len(self._fixtures)
        return self._fixtures[index]
