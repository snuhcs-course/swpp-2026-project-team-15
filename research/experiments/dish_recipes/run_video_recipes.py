# AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""Write recipes from the videos themselves: the comparison study and the recipe file build.

    python -m experiments.dish_recipes.run_video_recipes study   --workdir DIR --allow-live-api
    python -m experiments.dish_recipes.run_video_recipes analyze --workdir DIR
    python -m experiments.dish_recipes.run_video_recipes build   --workdir DIR --videos FILE \
        --model google/gemini-2.5-flash-lite --allow-live-api [--max-calls N]

DIR holds third-party-derived files and must be outside the repository: ``captions/recipes.json``
and ``captions/inputs/<dish>.json`` (the caption-based recipes and their captions, inputs of the
study), ``video-study/<variant>/<dish>.json`` (raw answers), ``recipes.json`` and
``build-report.json`` (the build). Without ``--allow-live-api`` nothing is sent.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from pathlib import Path

from app.dishes.synonyms import with_synonyms

from . import video_recipes as vr
from .common import REPO_ROOT, now_iso
from .validate_recipe import check_recipe, squash, transcript_text

DISHES_FILE = REPO_ROOT / "server" / "app" / "dishes" / "dishes.json"
CRITERIA = json.loads(Path(__file__).with_name("criteria_video.json").read_text(encoding="utf-8"))
VARIANTS: dict[str, str] = CRITERIA["variants"]
MAX_TRIES_PER_DISH = 3


def private_write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=1), encoding="utf-8")
    os.chmod(path, 0o600)


def outside_repo(workdir: Path) -> Path:
    workdir = workdir.resolve()
    if workdir == REPO_ROOT or REPO_ROOT in workdir.parents:
        raise SystemExit("--workdir must be outside the repository (third-party-derived data)")
    return workdir


def dish_names() -> dict[str, str]:
    return {d["id"]: d["name"] for d in json.loads(DISHES_FILE.read_text("utf-8"))["dishes"]}


def canonical(name: str) -> str:
    """One spelling per synonym group, spaces removed, so names from both sources compare."""
    return min(squash(n) for n in with_synonyms([name.strip()]))


# ---------- study ----------


def run_study(workdir: Path, live: bool) -> int:
    captions = json.loads((workdir / "captions" / "recipes.json").read_text("utf-8"))["recipes"]
    names = dish_names()
    planned = [(v, d) for v in VARIANTS for d in sorted(captions)]
    print(f"{len(planned)} calls planned")
    if not live:
        return 0
    for variant, dish in planned:
        out = workdir / "video-study" / variant / f"{dish}.json"
        if out.exists():
            continue
        video = captions[dish]["video"]
        result = vr.call(vr.build_payload(names[dish], video["id"], VARIANTS[variant]))
        private_write(
            out, {"dish": dish, "video": video, "model": VARIANTS[variant], **result.__dict__}
        )
        print(f"{variant} {dish}: ok={result.ok} ${result.cost_usd:.4f} {result.latency_s:.0f}s")
    return 0


def agreement(video_recipe: dict, caption_recipe: dict) -> tuple[float, float, set, set]:
    mine = {canonical(i["name"]) for i in video_recipe["ingredients"]}
    ref = {canonical(i["name"]) for i in caption_recipe["ingredients"]}
    both = mine & ref
    precision = len(both) / len(mine) if mine else 0.0
    recall = len(both) / len(ref) if ref else 0.0
    return precision, recall, mine - ref, ref - mine


def not_in_captions(video_recipe: dict, record: dict) -> list[str]:
    spoken = transcript_text(record)
    return [
        i["name"]
        for i in video_recipe["ingredients"]
        if not any(squash(n) in spoken for n in with_synonyms([i["name"]]))
    ]


def main_agreement(video_recipe: dict, caption_recipe: dict) -> tuple[int, int]:
    """(shared ingredients, of which both sources call main or both call non-main)."""
    ref = {canonical(i["name"]): i["role"] == "main" for i in caption_recipe["ingredients"]}
    shared = same = 0
    for row in video_recipe["ingredients"]:
        key = canonical(row["name"])
        if key in ref:
            shared += 1
            same += (row["role"] == "main") == ref[key]
    return shared, same


def analyze(workdir: Path) -> dict:
    captions = json.loads((workdir / "captions" / "recipes.json").read_text("utf-8"))["recipes"]
    rows, review = [], []
    for variant in VARIANTS:
        for dish in sorted(captions):
            path = workdir / "video-study" / variant / f"{dish}.json"
            if not path.exists():
                continue
            raw = json.loads(path.read_text("utf-8"))
            record_path = workdir / "captions" / "inputs" / f"{dish}.json"
            record = json.loads(record_path.read_text("utf-8"))
            row = {
                "variant": variant,
                "dish": dish,
                "ok": raw["ok"],
                "error": raw["error"],
                "cost_usd": raw["cost_usd"],
                "latency_s": round(raw["latency_s"], 1),
                "prompt_tokens": raw["prompt_tokens"],
                "completion_tokens": raw["completion_tokens"],
            }
            answer = raw.get("answer") or {}
            row["is_requested_dish"] = answer.get("is_requested_dish")
            row["cooked_dish"] = answer.get("cooked_dish", "")
            recipe = vr.to_recipe(dish, raw["video"], answer, "2026-11-19") if answer else None
            if recipe:
                problems = check_recipe(recipe, None)
                p, r, extra, missed = agreement(recipe, captions[dish])
                shared, same = main_agreement(recipe, captions[dish])
                ingredients = recipe["ingredients"]
                seen = vr.evidence(answer)
                row.update(
                    valid=not problems,
                    problems=problems,
                    ingredients=len(ingredients),
                    steps=len(recipe["steps"]),
                    with_amount=sum(1 for i in ingredients if i["amount"]),
                    servings=recipe["servings"],
                    roles={
                        k: sum(1 for i in ingredients if i["role"] == k)
                        for k in ("main", "secondary", "seasoning")
                    },
                    precision=round(p, 3),
                    recall=round(r, 3),
                    only_in_video=sorted(extra),
                    only_in_captions=sorted(missed),
                    main_shared=shared,
                    main_same=same,
                )
                for name in not_in_captions(recipe, record):
                    review.append(
                        {
                            "variant": variant,
                            "dish": dish,
                            "ingredient": name,
                            "evidence": seen.get(name, ""),
                        }
                    )
            rows.append(row)
    summary = {}
    for variant in VARIANTS:
        mine = [r for r in rows if r["variant"] == variant]
        made = [r for r in mine if r.get("valid") is not None]

        def med(key, items=made):
            values = [r[key] for r in items if r.get(key) is not None]
            return statistics.median(values) if values else None

        summary[variant] = {
            "calls": len(mine),
            "answers": sum(1 for r in mine if r["ok"]),
            "recipes": len(made),
            "valid": sum(1 for r in made if r["valid"]),
            "other_dish": sum(1 for r in mine if r["ok"] and r["is_requested_dish"] is False),
            "median_precision": med("precision"),
            "median_recall": med("recall"),
            "median_ingredients": med("ingredients"),
            "median_steps": med("steps"),
            "amount_share": round(
                sum(r["with_amount"] for r in made) / max(1, sum(r["ingredients"] for r in made)), 3
            ),
            "servings_given": sum(1 for r in made if r["servings"]),
            "main_label_agreement": (
                f"{sum(r['main_same'] for r in made)}/{sum(r['main_shared'] for r in made)}"
            ),
            "cost_usd": round(sum(r["cost_usd"] for r in mine), 4),
            "median_cost_usd": med("cost_usd", mine),
            "median_latency_s": med("latency_s", mine),
            "max_latency_s": max((r["latency_s"] for r in mine), default=None),
            "not_in_captions": sum(1 for x in review if x["variant"] == variant),
        }
    result = {"summary": summary, "rows": rows, "review": review}
    private_write(workdir / "video-study" / "analysis.json", result)
    return result


# ---------- build ----------


def build(
    workdir: Path, videos_file: Path, model: str, live: bool, max_calls: int, max_cost: float
) -> dict:
    snapshot = json.loads(videos_file.read_text("utf-8"))["dishes"]
    names = dish_names()
    out_path, report_path = workdir / "recipes.json", workdir / "build-report.json"
    store = json.loads(out_path.read_text("utf-8"))["recipes"] if out_path.exists() else {}
    report = json.loads(report_path.read_text("utf-8")) if report_path.exists() else {"dishes": {}}
    calls = sum(len(d.get("tries", [])) for d in report["dishes"].values())
    spent = sum(t["cost_usd"] for d in report["dishes"].values() for t in d.get("tries", []))
    for dish in sorted(names):
        if dish in store or report["dishes"].get(dish, {}).get("final"):
            continue
        videos = (snapshot.get(dish) or {}).get("videos", [])[:MAX_TRIES_PER_DISH]
        entry = report["dishes"].setdefault(dish, {"tries": []})
        if not videos:
            entry.update(final=True, outcome="no verified video")
            continue
        if not live:
            continue
        for video in videos[len(entry["tries"]) :]:
            if calls >= max_calls or spent >= max_cost:
                private_write(report_path, report)
                print(f"stopped at the cap ({calls} calls, ${spent:.2f})")
                return report
            result = vr.call(vr.build_payload(names[dish], video["id"], model))
            calls += 1
            spent += result.cost_usd
            answer = result.answer or {}
            entry["tries"].append(
                {
                    "video": video["id"],
                    "duration_s": video.get("duration_s"),
                    "ok": result.ok,
                    "error": result.error,
                    "is_requested_dish": answer.get("is_requested_dish"),
                    "cooked_dish": answer.get("cooked_dish", ""),
                    "cost_usd": result.cost_usd,
                    "latency_s": round(result.latency_s, 1),
                }
            )
            # Only the video id is kept: the server looks the title and channel up live.
            recipe = vr.to_recipe(dish, {"id": video["id"]}, answer) if answer else None
            problems = check_recipe(recipe, None) if recipe else ["no recipe"]
            entry["tries"][-1]["problems"] = problems if recipe else []
            if recipe and not problems:
                store[dish] = recipe
                entry.update(final=True, outcome="recipe", video=video["id"])
                break
        else:
            entry.update(final=True, outcome="no usable video among the first verified ones")
        private_write(out_path, {"schema": 1, "recipes": store})
        private_write(report_path, report)
        print(f"{dish}: {entry.get('outcome')} ({len(entry['tries'])} tries)")
    report["finished_at"] = now_iso()
    report["recipes"] = len(store)
    report["cost_usd"] = round(
        sum(t["cost_usd"] for d in report["dishes"].values() for t in d["tries"]), 4
    )
    private_write(out_path, {"schema": 1, "recipes": store})
    private_write(report_path, report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("command", choices=("study", "analyze", "build"))
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--videos", type=Path)
    parser.add_argument("--model", default=VARIANTS["lite"])
    parser.add_argument("--max-calls", type=int, default=300)
    parser.add_argument("--max-cost", type=float, default=5.0, help="USD, build only")
    parser.add_argument("--allow-live-api", action="store_true")
    args = parser.parse_args(argv)
    workdir = outside_repo(args.workdir)
    if args.command == "study":
        return run_study(workdir, args.allow_live_api)
    if args.command == "analyze":
        print(json.dumps(analyze(workdir)["summary"], ensure_ascii=False, indent=1))
        return 0
    if not args.videos:
        print("--videos is required for build", file=sys.stderr)
        return 2
    report = build(
        workdir, args.videos, args.model, args.allow_live_api, args.max_calls, args.max_cost
    )
    print(json.dumps({k: v for k, v in report.items() if k != "dishes"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
