# AI-generated with Claude Code (Sonnet 5.5), 2026-11-03; reviewed by Jaehyuk Choi.
"""Send the frames chosen by each selection variant to the vision model and write predictions.

Offline by default: without --allow-live-api this only prints the plan (number of requests,
images and the expected input tokens). The cheap vision model counts a fixed 258 input tokens per
image, so a request with N images costs about 8 + 258 * N input tokens (measured).

Selection file (frames are JPEGs, 1024 px long side, quality 85, no metadata):
  {"fridges": {"A01": {"single": ["a01_s0.jpg"], "overlap": ["f1.jpg", "f2.jpg"]}}}
Paths are relative to --frames-dir.

Usage from the repository root:
  PYTHONPATH=server:research uv run --project server --locked python \\
      -m experiments.capture.recognition.predict SELECTION.json OUT.json --frames-dir DIR
  # real calls: add --allow-live-api; the key is read from OPENROUTER_API_KEY only
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path

ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "google/gemini-2.5-flash-lite"
TOKENS_BASE, TOKENS_PER_IMAGE = 8, 258
SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name_raw": {"type": "string"},
                    "category": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["name_raw", "category", "confidence"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}


def server_prompt() -> str:
    from app.vision.gemini import PROMPT

    return PROMPT


def expected_input_tokens(images: int) -> int:
    return TOKENS_BASE + TOKENS_PER_IMAGE * images


def build_plan(selection: dict, repeats: int, mode: str) -> list[dict]:
    """One request per (fridge, variant, repeat) in multi_image mode, or one per frame otherwise.

    A frame used by several variants of one fridge is requested once per repeat and reused.
    """
    plan = []
    for fridge, variants in selection["fridges"].items():
        for repeat in range(repeats):
            seen: set[str] = set()
            for variant, paths in variants.items():
                if mode == "multi_image":
                    plan.append(
                        {
                            "fridge": fridge,
                            "variant": variant,
                            "repeat": repeat,
                            "paths": list(paths),
                        }
                    )
                else:
                    for p in paths:
                        if p not in seen:
                            seen.add(p)
                            plan.append(
                                {"fridge": fridge, "variant": None, "repeat": repeat, "paths": [p]}
                            )
    return plan


def send_openrouter(payload: dict) -> dict:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise SystemExit("OPENROUTER_API_KEY is not set")
    req = urllib.request.Request(
        ENDPOINT,
        json.dumps(payload).encode(),
        {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.load(resp)


def request_payload(prompt: str, images: list[bytes], model: str) -> dict:
    content = [{"type": "text", "text": prompt}] + [
        {
            "type": "image_url",
            "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(b).decode()},
        }
        for b in images
    ]
    return {
        "model": model,
        "temperature": 0,
        "max_tokens": 2048,
        "messages": [{"role": "user", "content": content}],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "detected_items", "strict": True, "schema": SCHEMA},
        },
        "provider": {"require_parameters": True},
    }


def parse_response(data: dict) -> tuple[list[str], bool]:
    """Candidate category names and whether the reply was a complete, valid answer."""
    try:
        choice = data["choices"][0]
        items = json.loads(choice["message"]["content"])["items"]
        names = [i["category"] for i in items]
        valid = choice.get("finish_reason") == "stop" and all(isinstance(n, str) for n in names)
        return (names if valid else []), valid
    except (KeyError, IndexError, ValueError, TypeError):
        return [], False


def run_plan(
    plan: list[dict],
    frames_dir: Path,
    send: Callable[[dict], dict],
    prompt: str,
    model: str = MODEL,
) -> list[dict]:
    runs = []
    for step in plan:
        images = [(frames_dir / p).read_bytes() for p in step["paths"]]
        t = time.perf_counter()
        data = send(request_payload(prompt, images, model))
        names, valid = parse_response(data)
        runs.append(
            {
                "fridge": step["fridge"],
                "variant": step["variant"],
                "repeat": step["repeat"],
                "paths": step["paths"],
                "frames": [names],
                "schema_valid": valid,
                "latency_ms": round((time.perf_counter() - t) * 1000),
                "prompt_tokens": (data.get("usage") or {}).get("prompt_tokens"),
                "frames_sent": len(images),
            }
        )
    return runs


def per_frame_runs(selection: dict, answers: list[dict]) -> list[dict]:
    """Assemble per-frame answers into one run per (fridge, variant, repeat) for the scorer."""
    by_frame = {(a["fridge"], a["repeat"], a["paths"][0]): a for a in answers}
    runs = []
    for fridge, variants in selection["fridges"].items():
        repeats = sorted({a["repeat"] for a in answers if a["fridge"] == fridge})
        for repeat in repeats:
            for variant, paths in variants.items():
                parts = [by_frame[(fridge, repeat, p)] for p in paths]
                runs.append(
                    {
                        "fridge": fridge,
                        "variant": variant,
                        "repeat": repeat,
                        "frames": [p["frames"][0] for p in parts],
                        "schema_valid": all(p["schema_valid"] for p in parts),
                        "latency_ms": sum(p["latency_ms"] for p in parts),
                        "prompt_tokens": sum(p["prompt_tokens"] or 0 for p in parts),
                        "frames_sent": len(paths),
                    }
                )
    return runs


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("selection")
    ap.add_argument("out")
    ap.add_argument("--frames-dir", required=True)
    ap.add_argument("--mode", choices=["per_frame", "multi_image"], default="per_frame")
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--allow-live-api", action="store_true", help="make real, billed requests")
    args = ap.parse_args(argv)
    selection = json.loads(Path(args.selection).read_text(encoding="utf-8"))
    plan = build_plan(selection, args.repeats, args.mode)
    images = sum(len(s["paths"]) for s in plan)
    tokens = sum(expected_input_tokens(len(s["paths"])) for s in plan)
    print(f"{len(plan)} requests, {images} images, about {tokens} input tokens ({args.model})")
    if not args.allow_live_api:
        print("dry run: nothing was sent; add --allow-live-api to send")
        return
    answers = run_plan(plan, Path(args.frames_dir), send_openrouter, server_prompt(), args.model)
    runs = per_frame_runs(selection, answers) if args.mode == "per_frame" else answers
    Path(args.out).write_text(
        json.dumps({"runs": runs}, ensure_ascii=False, indent=1), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
