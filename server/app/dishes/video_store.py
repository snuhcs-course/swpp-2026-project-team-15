# AI-generated with Claude Code (Sonnet 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""Video lists stored per dish, read once from a snapshot file.

The file is ``{"schema": 1, "dishes": {dish_id: {"fetched_at": ISO time, "videos": [...]}}}`` with
a video id under ``"id"`` in each video. Only the ids are used: the server looks the videos up
again before it serves them. An entry older than 30 days is ignored, because the YouTube API terms
do not allow keeping API data longer.
"""

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

SCHEMA = 1
MAX_AGE = timedelta(days=30)
VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}")


class VideoStore:
    def __init__(self, entries: dict[str, tuple[datetime, list[str]]] | None = None):
        self._entries = entries or {}

    @classmethod
    def load(cls, path: Path | str | None) -> "VideoStore":
        """An empty store without a path; a path that cannot be read or parsed is an error."""
        if not path:
            return cls()
        return cls.load_data(json.loads(Path(path).read_text(encoding="utf-8")))

    @classmethod
    def load_data(cls, data: dict) -> "VideoStore":
        if data.get("schema") != SCHEMA or not isinstance(data.get("dishes"), dict):
            raise ValueError("video file: expected {'schema': 1, 'dishes': {...}}")
        entries: dict[str, tuple[datetime, list[str]]] = {}
        for dish_id, raw in data["dishes"].items():
            try:
                fetched = datetime.fromisoformat(raw["fetched_at"])
                ids = [video["id"] for video in raw["videos"]]
            except (KeyError, TypeError, ValueError):
                raise ValueError(f"video file: invalid entry for {dish_id}") from None
            if not all(isinstance(i, str) and VIDEO_ID.fullmatch(i) for i in ids):
                raise ValueError(f"video file: invalid video id for {dish_id}")
            if fetched.tzinfo is None:
                fetched = fetched.replace(tzinfo=UTC)
            entries[dish_id] = (fetched, ids)
        return cls(entries)

    def fresh_ids(self, dish_id: str, now: datetime) -> list[str]:
        """The stored ids in their stored order; empty when missing or older than 30 days."""
        entry = self._entries.get(dish_id)
        if entry is None or now - entry[0] >= MAX_AGE:
            return []
        return entry[1]

    def __len__(self) -> int:
        return len(self._entries)
