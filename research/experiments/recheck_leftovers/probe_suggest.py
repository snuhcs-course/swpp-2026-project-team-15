# AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""Item 1: the raw model answer for a fridge and what the server keeps of it.

Run from server/: uv run python ../research/experiments/recheck_leftovers/probe_suggest.py \
    --out FILE --calls 3 라면 양파 돼지고기
Needs the dish model key in the environment (OPENROUTER_API_KEY or DISH_LLM_API_KEY).
"""

import argparse
import json
import os
from pathlib import Path

from app.dishes.dependencies import build_dish_parts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--calls", type=int, default=3)
    parser.add_argument("ingredients", nargs="+")
    args = parser.parse_args()
    parts = build_dish_parts(dict(os.environ), os.environ.get("OPENROUTER_API_KEY", ""))
    service = parts.service
    answers = []
    llm = service.llm
    original = llm.complete

    def record(*a, **k):
        out = original(*a, **k)
        answers.append(out)
        return out

    llm.complete = record
    runs = []
    for _ in range(args.calls):
        answers.clear()
        kept = [d.name for d in service.suggest(args.ingredients).dishes]
        named = [d.get("name") for d in answers[0].get("dishes", [])] if answers else []
        dropped = [n for n in named if n not in kept]
        runs.append({"named": named, "kept": kept, "dropped_by_server": dropped})
    dish = next(d for d in service.catalog.all() if d.name == "짜장라면")
    uses = {i: service.catalog.uses(dish, i) for i in args.ingredients}
    result = {"fridge": args.ingredients, "runs": runs, "jjajang_uses": uses}
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps(result, ensure_ascii=False)[:1500])


if __name__ == "__main__":
    main()
