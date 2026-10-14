# AI-generated with Claude Code (Opus 5.5), 2026-10-14; review pending by Jaehyuk Choi.
"""Measure ingredient recognition on the 2026-09-30 real photos through a running server.

Each photo is uploaded unchanged to POST /analyze. A ground-truth item counts as found when
one of its accepted names appears in a returned candidate name. Candidates that match no
item are listed for manual review; they may be real items the ground truth omits.

Usage (server running with VISION_PROVIDER=gemini):
    uv run python evaluation/vision_benchmark.py PHOTO_DIR [--server URL] [--out results.json]
PHOTO_DIR holds one folder per image (e.g. 04_garlic_eggs/garlic_eggs.jpg), as in the
benchmark archive. Photos are not committed.
"""

import argparse
import json
import time
from pathlib import Path

import httpx

GROUND_TRUTH = Path(__file__).with_name("ground_truth.json")


def matches(candidate: str, accepted_names: list[str]) -> bool:
    return any(name in candidate for name in accepted_names)


def score(expected: dict[str, list[str]], candidates: list[str]) -> dict:
    found = [item for item, names in expected.items() if any(matches(c, names) for c in candidates)]
    unmatched = [c for c in candidates if not any(matches(c, names) for names in expected.values())]
    return {
        "found": found,
        "missed": [item for item in expected if item not in found],
        "unmatched_candidates": unmatched,
    }


def photo_in(folder: Path) -> Path:
    [photo] = [p for p in folder.glob("*.jpg") if not p.name.startswith("yolo")]
    return photo


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("photo_dir", type=Path)
    parser.add_argument("--server", default="http://127.0.0.1:8000")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    images = json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))["images"]
    results = {}
    with httpx.Client(base_url=args.server, timeout=60) as client:
        for image_id, expected in images.items():
            photo = photo_in(args.photo_dir / image_id)
            started = time.perf_counter()
            response = client.post(
                "/analyze", files={"image": (photo.name, photo.read_bytes(), "image/jpeg")}
            )
            response.raise_for_status()
            candidates = [c["name"] for c in response.json()["candidates"]]
            results[image_id] = {
                "seconds": round(time.perf_counter() - started, 1),
                "candidates": candidates,
                **score(expected, candidates),
            }
            print(f"{image_id}: {len(results[image_id]['found'])}/{len(expected)} {candidates}")

    total = sum(len(expected) for expected in images.values())
    found = sum(len(r["found"]) for r in results.values())
    summary = {"items": total, "found": found, "recall": round(found / total, 3)}
    print(json.dumps(summary, ensure_ascii=False))
    if args.out:
        report = {"summary": summary, "images": results}
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
