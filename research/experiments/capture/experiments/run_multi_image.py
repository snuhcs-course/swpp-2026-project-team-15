# AI-generated with Claude Code (Sonnet 5.5), 2026-11-04; reviewed by Jaehyuk Choi.
"""Send the frames chosen by each selection arm to the vision model, one request per arm.

Offline by default: without ``--allow-live-api`` this only decodes the clips, applies the arms and
prints the plan (requests, frames, expected input tokens). The cheap vision model counts a fixed
258 input tokens per image, so N images cost about 8 + 258 N input tokens (measured).

Frames are prepared as the app does it: long side 1024 px, JPEG quality 85, no metadata. Requests
go through the server's own provider (``app.vision.openrouter``), one request with all frames, so
the production multi-view prompt applies; an arm may swap in the ``visible-only`` prompt.

Arms are defined in ``arms.json``; clip ids follow the answer key (A01, A02, ... in file order, or
``--clip-map``). Predictions are written in the format ``recognition/score.py`` reads. Blank-frame
inputs (``type: blank``) check whether the model invents items when nothing is visible; they have
no answer key and are summarised by the share of empty answers.

Usage from the repository root (OpenCV and numpy are declared on the command line):

  PYTHONPATH=server:research uv run --project server --locked \\
      --with opencv-python-headless --with numpy \\
      python -m experiments.capture.experiments.run_multi_image --videos DIR [--offline-report]
  # real calls: add --allow-live-api --out data/capture-experiments/predictions.json
  # (the key is read from OPENROUTER_API_KEY only)
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from collections import defaultdict
from pathlib import Path

from experiments.capture.experiments import frame_similarity as fsim

MODEL = "google/gemini-2.5-flash-lite"
TOKENS_BASE, TOKENS_PER_IMAGE = 8, 258
DEFAULT_ARMS = Path(__file__).with_name("arms.json")
VISIBLE_ONLY = (
    "List only items you can actually see; never guess typical fridge contents. "
    "If no food is visible (for example the photos are black, blurred or empty), "
    "return an empty list. "
)


def expected_tokens(images: int) -> int:
    return TOKENS_BASE + TOKENS_PER_IMAGE * images


def multi_prompt(count: int, variant: str) -> str:
    from app.vision.gemini import multi_view_prompt

    base = multi_view_prompt(count)
    if variant == "current":
        return base
    marker = "For each item give name_raw"
    return base.replace(marker, VISIBLE_ONLY + marker, 1)


# --- clips ------------------------------------------------------------------------------------


def clip_ids(videos: Path, clip_map: dict[str, str] | None) -> dict[str, Path]:
    if clip_map:
        return {cid: videos / name for cid, name in clip_map.items()}
    files = sorted(p for p in videos.iterdir() if p.suffix.lower() in {".mp4", ".mov"})
    return {f"A{i:02d}": p for i, p in enumerate(files, start=1)}


def analyse_clip(path: Path, measures: list[str]) -> dict:
    """One pass over a clip: timestamps (ns), sharpness and features of every frame."""
    import cv2

    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    ts: list[int] = []
    sharp: list[float] = []
    feats: dict[str, list] = {m: [] for m in measures}
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        t = int(cap.get(cv2.CAP_PROP_POS_MSEC) * 1e6)
        ts.append(t if t > 0 or not ts else round(len(ts) * 1e9 / fps))
        sharp.append(fsim.frame_sharpness(frame))
        for name, vec in fsim.frame_features(frame, measures).items():
            feats[name].append(vec)
    cap.release()
    return {"ts": ts, "sharp": sharp, "feats": feats}


def jpegs(path: Path, indices: set[int]) -> dict[int, bytes]:
    """The app's frame preparation for the wanted frames: 1024 px long side, q85, no metadata."""
    import cv2

    cap = cv2.VideoCapture(str(path))
    out: dict[int, bytes] = {}
    for i in range(max(indices) + 1 if indices else 0):
        ok, frame = cap.read()
        if not ok:
            break
        if i in indices:
            out[i] = encode(frame)
    cap.release()
    return out


def encode(frame) -> bytes:
    import cv2

    h, w = frame.shape[:2]
    scale = 1024 / max(h, w)
    if scale < 1:
        frame = cv2.resize(
            frame, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA
        )
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        raise RuntimeError("JPEG encoding failed")
    return buf.tobytes()


def blank_frames(kind: str, count: int, source: Path | None) -> list[bytes]:
    import cv2
    import numpy as np

    shape = (576, 1024, 3)
    if kind == "black":
        frame = np.zeros(shape, np.uint8)
    elif kind == "white":
        frame = np.full(shape, 255, np.uint8)
    elif kind == "noise":
        rng = np.random.default_rng(0)
        frame = np.clip(rng.normal(8, 3, shape), 0, 255).astype(np.uint8)
    elif kind == "blurred":
        if source is None:
            raise SystemExit("blurred blank frames need a real frame: pass --videos")
        cap = cv2.VideoCapture(str(source))
        ok, real = cap.read()
        cap.release()
        if not ok:
            raise SystemExit(f"cannot read a frame from {source}")
        frame = cv2.GaussianBlur(cv2.resize(real, (1024, 576)), (0, 0), 40)
    else:
        raise ValueError(f"unknown blank kind {kind!r}")
    return [encode(frame)] * count


# --- plan -------------------------------------------------------------------------------------


def needed_measures(arms: list[dict]) -> list[str]:
    return sorted({a["measure"] for a in arms if "measure" in a})


def build_plan(arms: list[dict], clips: dict[str, dict], replicates: int) -> list[dict]:
    """One request per (arm, clip, replicate); blank arms one per (kind, repeat)."""
    plan = []
    for arm in arms:
        if arm["type"] == "blank":
            for kind in arm["kinds"]:
                for repeat in range(arm.get("repeats", 5)):
                    plan.append(
                        {
                            "arm": arm["name"],
                            "fridge": f"blank-{kind}",
                            "repeat": repeat,
                            "kind": kind,
                            "frames": arm.get("frames", 8),
                            "prompt": arm.get("prompt", "current"),
                        }
                    )
            continue
        for cid, meta in clips.items():
            for rep in range(replicates):
                frames = fsim.select_frames(
                    arm, meta["ts"], meta["sharp"], meta["feats"], rep, replicates, cid
                )
                plan.append(
                    {
                        "arm": arm["name"],
                        "fridge": cid,
                        "repeat": rep,
                        "indices": frames,
                        "frames": len(frames),
                        "prompt": arm.get("prompt", "current"),
                    }
                )
    return plan


def print_plan(plan: list[dict], price_in: float, price_out: float) -> None:
    by_arm: dict[str, list[dict]] = defaultdict(list)
    for p in plan:
        by_arm[p["arm"]].append(p)
    print(f"{'arm':<22}{'requests':>9}{'frames/request':>16}{'input tokens':>14}")
    total_tokens = 0
    for arm, items in by_arm.items():
        tokens = sum(expected_tokens(p["frames"]) for p in items)
        total_tokens += tokens
        print(
            f"{arm:<22}{len(items):>9}{statistics.mean(p['frames'] for p in items):>16.1f}"
            f"{tokens:>14,}"
        )
    est = total_tokens / 1e6 * price_in + len(plan) * 600 / 1e6 * price_out
    print(
        f"{len(plan)} requests, {total_tokens:,} input tokens; estimated cost about ${est:.3f} "
        f"at {price_in}/{price_out} USD per million tokens (assumed list price: check it first)"
    )


def offline_report(clips: dict[str, dict], measures: list[str]) -> None:
    """How redundant do the app's frames look, and do the measures agree on removal order?"""
    for cid, meta in clips.items():
        base = fsim.phased_time_bins(meta["ts"], meta["sharp"])
        print(f"{cid}: {len(meta['ts'])} frames, {len(base)} selected")
        orders = {}
        for m in measures:
            feats = meta["feats"][m]
            sims = [
                fsim.similarity(m, feats[i], feats[j])
                for a, i in enumerate(base)
                for j in base[a + 1 :]
            ]
            orders[m] = fsim.removal_order(base, meta["sharp"], feats, m)
            near = sum(s >= 0.9 for s in sims)
            print(
                f"  {m:<5} pairs >= 0.9: {near}/{len(sims)}  median similarity "
                f"{statistics.median(sims):.2f}"
            )
        names = list(orders)
        for i, a in enumerate(names):
            for b in names[i + 1 :]:
                rank = {m: {f: r for r, f in enumerate(orders[m])} for m in (a, b)}
                tau = fsim.kendall_tau_b([rank[a][f] for f in base], [rank[b][f] for f in base])
                print(f"  removal order agreement {a}/{b}: tau {tau:.2f}")


# --- live -------------------------------------------------------------------------------------


def run_live(plan: list[dict], clips: dict[str, Path], blank_source: Path | None) -> list[dict]:
    from app.vision.exceptions import VisionError
    from app.vision.openrouter import OpenRouterVisionProvider
    from app.vision.providers import ImageInput

    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise SystemExit("OPENROUTER_API_KEY is not set")
    provider = OpenRouterVisionProvider(key, MODEL)
    wanted: dict[str, set[int]] = defaultdict(set)
    for p in plan:
        wanted[p["fridge"]].update(p.get("indices", []))
    frames = {cid: jpegs(clips[cid], idx) for cid, idx in wanted.items() if cid in clips}
    runs = []
    for n, p in enumerate(plan, start=1):
        if "kind" in p:
            data = blank_frames(p["kind"], p["frames"], blank_source)
        else:
            data = [frames[p["fridge"]][i] for i in p["indices"]]
        images = [ImageInput(d, "image/jpeg") for d in data]
        valid, names = True, []
        try:
            prompt = multi_prompt(len(images), p["prompt"])
            names = [i.category for i in provider._request(images, prompt)]
        except VisionError:
            valid = False
        runs.append(
            {
                "fridge": p["fridge"],
                "variant": p["arm"],
                "repeat": p["repeat"],
                "candidates": names,
                "frames_sent": len(images),
                "prompt_tokens": expected_tokens(len(images)),
                "schema_valid": valid,
            }
        )
        print(
            f"{n}/{len(plan)} {p['arm']} {p['fridge']} r{p['repeat']}: {len(names)} items",
            file=sys.stderr,
        )
    return runs


def summarise_blank(runs: list[dict]) -> None:
    blank = [r for r in runs if r["fridge"].startswith("blank-")]
    for arm in sorted({r["variant"] for r in blank}):
        mine = [r for r in blank if r["variant"] == arm]
        empty = sum(1 for r in mine if r["schema_valid"] and not r["candidates"])
        print(f"{arm}: {empty}/{len(mine)} answers were empty lists")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--videos", type=Path, help="directory with the clips")
    ap.add_argument("--clip-map", type=Path, help='json {"A01": "file.mp4", ...}')
    ap.add_argument("--arms", type=Path, default=DEFAULT_ARMS)
    ap.add_argument("--only", help="comma-separated arm names to run")
    ap.add_argument("--replicates", type=int, default=3)
    ap.add_argument("--max-calls", type=int, default=150)
    ap.add_argument("--price-in", type=float, default=0.10, help="USD per million input tokens")
    ap.add_argument("--price-out", type=float, default=0.40, help="USD per million output tokens")
    ap.add_argument("--offline-report", action="store_true")
    ap.add_argument("--allow-live-api", action="store_true")
    ap.add_argument("--out", type=Path, default=Path("data/capture-experiments/predictions.json"))
    args = ap.parse_args(argv)

    arms = json.loads(args.arms.read_text(encoding="utf-8"))["arms"]
    if args.only:
        wanted = set(args.only.split(","))
        arms = [a for a in arms if a["name"] in wanted]
    needs_clips = any(a["type"] != "blank" for a in arms) or args.offline_report
    paths: dict[str, Path] = {}
    clips: dict[str, dict] = {}
    measures = needed_measures(arms) or (["edge", "hist"] if args.offline_report else [])
    if args.offline_report:
        measures = sorted(set(measures) | {"edge", "gray", "hist"})
    if needs_clips:
        if not args.videos:
            raise SystemExit("--videos is required for clip arms")
        clip_map = json.loads(args.clip_map.read_text()) if args.clip_map else None
        paths = clip_ids(args.videos, clip_map)
        clips = {cid: analyse_clip(p, measures) for cid, p in paths.items()}
    if args.offline_report:
        offline_report(clips, measures)
        return
    plan = build_plan(arms, clips, args.replicates)
    print_plan(plan, args.price_in, args.price_out)
    if not args.allow_live_api:
        print("dry run: no request was sent (add --allow-live-api to send them)")
        return
    if len(plan) > args.max_calls:
        raise SystemExit(f"plan has {len(plan)} requests, above --max-calls {args.max_calls}")
    blank_source = next(iter(paths.values()), None)
    runs = run_live(plan, paths, blank_source)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"runs": runs}, ensure_ascii=False), encoding="utf-8")
    summarise_blank(runs)
    print(f"wrote {len(runs)} runs to {args.out}; score them with recognition/score.py")


if __name__ == "__main__":
    main()
