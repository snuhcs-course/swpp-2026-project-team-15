# AI-generated with Claude Code (Opus 5.5), 2026-10-11; review pending by Jaehyuk Choi.
"""Ingredient recognition providers behind one interface, so tests never call a paid API."""

import hashlib
import json
from pathlib import Path
from typing import Protocol

from pydantic import TypeAdapter

from app.schemas import DetectedItem, IngredientCandidate

DETECTED_ITEMS = TypeAdapter(list[DetectedItem])


class VisionError(RuntimeError):
    """The provider could not produce a result for the image."""


class VisionProvider(Protocol):
    def detect(self, image: bytes, mime_type: str) -> list[DetectedItem]: ...


class FixtureVisionProvider:
    """Replays recorded Gemini outputs; the same image always yields the same fixture."""

    def __init__(self, fixture_dir: Path) -> None:
        self._fixtures = [
            DETECTED_ITEMS.validate_python(_read_items(path))
            for path in sorted(fixture_dir.glob("*.json"))
        ]
        if not self._fixtures:
            raise FileNotFoundError(f"No vision fixtures in {fixture_dir}")

    def detect(self, image: bytes, mime_type: str) -> list[DetectedItem]:
        index = int.from_bytes(hashlib.sha256(image).digest()[:4]) % len(self._fixtures)
        return self._fixtures[index]


def _read_items(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))["items"]


def to_candidates(items: list[DetectedItem]) -> list[IngredientCandidate]:
    """Merge items sharing a category, keeping the highest confidence and first-seen order."""
    merged: dict[str, IngredientCandidate] = {}
    for item in items:
        name = item.category.strip()
        if not name:
            continue
        if name in merged:
            existing = merged[name]
            existing.raw_texts.append(item.name_raw)
            existing.confidence = max(existing.confidence, item.confidence)
        else:
            merged[name] = IngredientCandidate(
                name=name, raw_texts=[item.name_raw], confidence=item.confidence
            )
    return list(merged.values())
