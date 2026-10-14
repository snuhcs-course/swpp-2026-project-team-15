# AI-generated with Claude Code (Opus 5.5), 2026-10-14; reviewed by Jaehyuk Choi.
"""Measure ingredient recognition on the 2026-09-30 real photos.

Each photo is sent unchanged. A ground-truth item counts as found when one of its accepted
names appears in a returned candidate name. Candidates that match no item are listed for
manual review; they may be real items the ground truth omits.

Usage:
    # through a running server (VISION_PROVIDER=gemini)
    uv run python -m evaluation.vision_benchmark PHOTO_DIR [--server URL] [--out FILE]
    # direct Gemini call to compare models and prompts (reads GEMINI_API_KEY)
    uv run --env-file .env python -m evaluation.vision_benchmark PHOTO_DIR \\
        --model gemini-3.5-flash --prompt clues [--out FILE]
PHOTO_DIR holds one folder per image (e.g. 04_garlic_eggs/garlic_eggs.jpg), as in the
benchmark archive. Photos are not committed.
"""

import argparse
import json
import os
import time
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import httpx
from google import genai
from sqlmodel import Field, SQLModel

from app.vision.exceptions import VisionError, VisionUnavailableError
from app.vision.gemini import PROMPT, GeminiVisionProvider
from app.vision.schemas import DetectedItem
from app.vision.service import to_candidates

GROUND_TRUTH = Path(__file__).with_name("ground_truth.json")
# Waits before retrying when the model is overloaded or rate limited.
RETRY_WAITS_S = (10, 20, 40)


class DetectedItemWithClues(SQLModel):
    """Asks for evidence before the category, approximating the 2026-09-30 reasoning output."""

    name_raw: str
    visual_clues: str = Field(description="Shape, packaging and any label text read")
    category: str
    confidence: float


CLUES_PROMPT = (
    "List the food items visible in this refrigerator or pantry photo. For each item, "
    "first describe the visual clues: shape, packaging, and any label text you can read, "
    "including partly hidden items. Then give name_raw (label text or description as seen), "
    "category (a generic Korean ingredient name usable in a recipe, e.g. 신라면 -> 라면) "
    "and confidence between 0 and 1. Omit non-food objects."
)

PROMPTS = {
    "short": (PROMPT, list[DetectedItem]),
    "clues": (CLUES_PROMPT, list[DetectedItemWithClues]),
}


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


class _TokenCounter:
    """Wraps client.models to add up the tokens each call reports."""

    def __init__(self, models) -> None:
        self._models = models
        self.tokens = 0

    def generate_content(self, **kwargs):
        response = self._models.generate_content(**kwargs)
        if response.usage_metadata:
            self.tokens += response.usage_metadata.total_token_count or 0
        return response


def server_detector(server: str) -> Callable[[bytes], list[str]]:
    client = httpx.Client(base_url=server, timeout=60)

    def detect(photo: bytes) -> list[str]:
        response = client.post("/analyze", files={"image": ("photo.jpg", photo, "image/jpeg")})
        response.raise_for_status()
        return [c["name"] for c in response.json()["candidates"]]

    return detect


def direct_detector(model: str, prompt: str) -> tuple[Callable[[bytes], list[str]], _TokenCounter]:
    text, schema = PROMPTS[prompt]
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    counter = _TokenCounter(client.models)
    # The provider only uses client.models; keep the real client alive alongside the counter.
    provider = GeminiVisionProvider(
        SimpleNamespace(models=counter, client=client), model, prompt=text, response_schema=schema
    )

    def detect(photo: bytes) -> list[str]:
        for wait in RETRY_WAITS_S:
            try:
                return [c.name for c in to_candidates(provider.detect(photo, "image/jpeg"))]
            except VisionUnavailableError:
                time.sleep(wait)
        return [c.name for c in to_candidates(provider.detect(photo, "image/jpeg"))]

    return detect, counter


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("photo_dir", type=Path)
    parser.add_argument("--server", default="http://127.0.0.1:8000")
    parser.add_argument("--model", help="call Gemini directly with this model")
    parser.add_argument("--prompt", choices=PROMPTS, default="short")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    counter = None
    if args.model:
        detect, counter = direct_detector(args.model, args.prompt)
    else:
        detect = server_detector(args.server)

    images = json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))["images"]
    results = {}
    for image_id, expected in images.items():
        started = time.perf_counter()
        try:
            candidates = detect(photo_in(args.photo_dir / image_id).read_bytes())
        except (VisionError, httpx.HTTPError) as exc:
            # A failed photo counts as finding nothing, so recall is never overstated.
            candidates, error = [], str(exc)
        else:
            error = None
        results[image_id] = {
            "seconds": round(time.perf_counter() - started, 1),
            "candidates": candidates,
            "error": error,
            **score(expected, candidates),
        }
        print(f"{image_id}: {len(results[image_id]['found'])}/{len(expected)} {candidates}")

    total = sum(len(expected) for expected in images.values())
    found = sum(len(r["found"]) for r in results.values())
    summary = {
        "failed_images": [k for k, r in results.items() if r["error"]],
        "setup": {"model": args.model or f"server {args.server}", "prompt": args.prompt},
        "items": total,
        "found": found,
        "recall": round(found / total, 3),
        "tokens": counter.tokens if counter else None,
    }
    print(json.dumps(summary, ensure_ascii=False))
    if args.out:
        report = {"summary": summary, "images": results}
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
