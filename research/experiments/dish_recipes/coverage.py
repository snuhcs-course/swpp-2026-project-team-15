# AI-generated with Claude Code (Sonnet 5.5), 2026-11-18; reviewed by Jaehyuk Choi.
"""Coverage report of the saved snapshot and caption inputs (no network, no model).

cd server && PYTHONPATH=.:../research uv run python -m experiments.dish_recipes.coverage
"""

from __future__ import annotations

import json
from collections import Counter
from statistics import median

from app.dishes.catalog import Catalog

from .common import COVERAGE_FILE, INPUTS_DIR, MISSING_FILE, VIDEOS_FILE, load_json, save_json


def build_report(dish_ids: list[str], snapshot: dict, inputs: dict[str, dict], missing: dict):
    with_video = [d for d in dish_ids if snapshot.get(d, {}).get("videos")]
    chars = sorted(r["caption_chars"] for r in inputs.values())
    kinds = Counter(r["video"]["caption_kind"] for r in inputs.values())
    languages = Counter(r["video"]["language"] for r in inputs.values())
    rank = Counter(
        next(
            (i for i, v in enumerate(snapshot[d]["videos"]) if v["id"] == r["video"]["id"]),
            -1,
        )
        for d, r in inputs.items()
        if d in snapshot
    )
    return {
        "dishes": len(dish_ids),
        "with_video": len(with_video),
        "with_captions": len(inputs),
        "no_captions": sorted(missing),
        "not_tried": sorted(set(with_video) - set(inputs) - set(missing)),
        "caption_kind": dict(kinds),
        "caption_language": dict(languages),
        "video_rank_used": {str(k + 1): v for k, v in sorted(rank.items()) if k >= 0},
        "caption_chars": {
            "min": chars[0] if chars else None,
            "median": int(median(chars)) if chars else None,
            "max": chars[-1] if chars else None,
        },
    }


def main() -> int:
    ids = list(Catalog.load().dishes)
    snapshot = load_json(VIDEOS_FILE, {"dishes": {}})["dishes"]
    inputs = {}
    if INPUTS_DIR.exists():
        for path in sorted(INPUTS_DIR.glob("*.json")):
            if not path.name.startswith("_"):
                inputs[path.stem] = json.loads(path.read_text(encoding="utf-8"))
    report = build_report(ids, snapshot, inputs, load_json(MISSING_FILE, {}))
    save_json(COVERAGE_FILE, report)
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
