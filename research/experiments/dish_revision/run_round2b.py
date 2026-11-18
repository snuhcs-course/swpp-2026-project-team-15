# AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""Round 2b: the revision prompt with and without the 'keep owned and assumed rows' sentence.

Runs the served Reviser on the frozen synthetic cases (and optionally one demo case against a
recipe file) once per prompt variant. Results go to the ignored ``data/dish-revision/``.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from experiments.dish_tokens.calls import read_key

from app.dishes import prompts
from app.dishes.catalog import Catalog
from app.dishes.llm import DishLLM, DishLLMError
from app.dishes.recipes import RecipeStore
from app.dishes.revision import Reviser

HERE = Path(__file__).resolve().parent
OUT = HERE.parents[2] / "data" / "dish-revision"
KEEP_SENTENCE = (
    " Keep every owned or assumed source ingredient that the revised recipe still uses in the"
    " ingredient list, with its source amount; only omitted or replaced ingredients leave the list."
)
OLD = prompts.REVISE_SYSTEM


def keep_variant(text: str) -> str:
    """Insert the sentence after rule 2's first sentence (pure, tested)."""
    anchor = "in the ingredient list, steps and tips."
    if anchor not in text:
        raise ValueError("rule 2 anchor not found")
    return text.replace(anchor, anchor + KEEP_SENTENCE, 1)


def dropped_assumed(response, status: list[str]) -> int:
    if response is None or response.revised is None:
        return 0
    kept = {r.name for r in response.revised.ingredients}
    return sum(
        1
        for row, s in zip(response.original.ingredients, status, strict=True)
        if s == "assumed" and row.name not in kept
    )


def run(cases: list[dict], store: RecipeStore, catalog: Catalog, llm: DishLLM) -> list[dict]:
    rows = []
    for case in cases:
        reviser = Reviser(catalog, catalog, llm, store)
        recipe = store.get(case["dish_id"])
        status = reviser.availability(recipe, case["ingredients"])
        try:
            r = reviser.revise(case["dish_id"], case["ingredients"])
            out = {"status": r.status, "code": r.error.code if r.error else None}
            out["dropped_assumed"] = dropped_assumed(r, status)
        except DishLLMError as exc:
            out = {"status": "provider_error", "code": str(exc)[:80], "dropped_assumed": 0}
        rows.append({"id": case["id"], "expect": case.get("expect"), **out})
        print(case["id"], case.get("expect"), out["status"], out["code"])
    return rows


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--allow-live-api", action="store_true")
    p.add_argument("--demo-recipes", type=Path, help="served recipe file for the tofu-pan case")
    a = p.parse_args(argv)
    if not a.allow_live_api:
        print("dry run: 36 synthetic cases x 2 variants (+1 demo case x 2)")
        return 0
    catalog = Catalog.load()
    llm = DishLLM(api_key=read_key())
    cases = json.loads((HERE / "cases.json").read_text())["cases"]
    synthetic = RecipeStore.load(HERE / "fixtures.json")
    result: dict = {"started": datetime.now(UTC).isoformat()}
    for name, text in (("old", OLD), ("keep", keep_variant(OLD))):
        prompts.REVISE_SYSTEM = text
        result[name] = {"synthetic": run(cases, synthetic, catalog, llm)}
        if a.demo_recipes:
            demo = RecipeStore.load(a.demo_recipes)
            demo_case = [{"id": "demo-tofu-pan", "dish_id": "tofu-pan", "ingredients": ["두부"]}]
            result[name]["demo"] = run(demo_case, demo, catalog, llm)
    prompts.REVISE_SYSTEM = OLD
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"round2b-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=1))
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
