# AI-generated with Claude Code (Opus 5.5), 2026-11-19; not yet reviewed.
"""Finding 3: model and YouTube calls when the same dish's videos are asked for again and again.

Fakes only, no network. Run from server/: uv run python ../research/experiments/server_review/video_calls.py
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "server"))

from app.dishes.videos import VideoCache, VideoFinder, check_seconds  # noqa: E402
from tests.dishes.contracts.fakes import (  # noqa: E402
    FakeStoredVideos,
    FakeVideoSource,
    FakeVideoVerifier,
)

NOW = datetime(2026, 11, 19, tzinfo=UTC)
REPEATS = 10


class Counting:
    def __init__(self, inner, method):
        self.inner, self.method, self.calls = inner, method, 0

    def __getattr__(self, name):
        if name != self.method:
            return getattr(self.inner, name)

        def call(*args, **kwargs):
            self.calls += 1
            return getattr(self.inner, name)(*args, **kwargs)

        return call


def run(stored_ids, usable, proposed):
    verifier = Counting(FakeVideoVerifier(usable), "check")
    source = Counting(FakeVideoSource(proposed), "propose")
    finder = VideoFinder(
        verifier,
        FakeStoredVideos({"d": (NOW, stored_ids)} if stored_ids else {}),
        VideoCache(),
        source,
        checked=VideoCache(ttl=check_seconds(128, 124)),
        now=lambda: NOW,
    )
    for _ in range(REPEATS):
        finder.lookup("d", "요리")
    return {"youtube_calls": verifier.calls, "model_calls": source.calls}


def main():
    a, b = "a" * 11, "b" * 11
    print(
        json.dumps(
            {
                "repeats": REPEATS,
                "check_seconds_for_128_dishes_124_recipes": round(check_seconds(128, 124), 1),
                "stored_and_playable": run([a], {a}, []),
                "nothing_stored_model_finds_nothing_playable": run([], set(), [b]),
                "nothing_stored_model_finds_one": run([], {b}, [b]),
            }
        )
    )


if __name__ == "__main__":
    main()
