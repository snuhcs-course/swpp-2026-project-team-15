# AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""Item 2: what the vision model returns for a photo the server calls incomplete.

Run from server/:
    PYTHONPATH=. uv run python ../research/experiments/recheck_leftovers/probe_photo.py \
    --out FILE PHOTO.jpg [PHOTO.jpg ...]
Needs OPENROUTER_API_KEY and OPENROUTER_VISION_MODEL. The raw answer text is not saved.
"""

import argparse
import json
import os
from pathlib import Path

import httpx

from app.vision.exceptions import VisionError
from app.vision.openrouter import OpenRouterVisionProvider


class Recorder(httpx.BaseTransport):
    def __init__(self):
        self.inner = httpx.HTTPTransport()
        self.seen: list[dict] = []

    def handle_request(self, request):
        response = self.inner.handle_request(request)
        response.read()
        body = response.json()
        choice = (body.get("choices") or [{}])[0]
        content = (choice.get("message") or {}).get("content") or ""
        self.seen.append(
            {
                "finish_reason": choice.get("finish_reason"),
                "native_finish_reason": choice.get("native_finish_reason"),
                "usage": body.get("usage"),
                "content_chars": len(content),
                "content_head": content[:400],
                "content_tail": content[-80:],
            }
        )
        return response


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("photos", nargs="+")
    args = parser.parse_args()
    out = []
    for photo in args.photos:
        rec = Recorder()
        model = os.environ.get("OPENROUTER_VISION_MODEL", "google/gemini-2.5-flash")
        provider = OpenRouterVisionProvider(os.environ["OPENROUTER_API_KEY"], model, transport=rec)
        try:
            items = provider.detect(Path(photo).read_bytes(), "image/jpeg")
            result = {"ok": True, "items": len(items)}
        except VisionError as exc:
            result = {"ok": False, "error": str(exc)}
        out.append({"photo": Path(photo).name, **result, "calls": rec.seen})
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps(out, ensure_ascii=False)[:2500])


if __name__ == "__main__":
    main()
