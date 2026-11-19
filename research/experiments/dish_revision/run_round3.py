# AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""Round 3: recipe names, card-versus-recipe gaps and references to removed steps.

Runs the served Reviser on every served recipe with the fridge = the dish's key ingredients, once
per variant (criteria_round3.json). Dry run by default; results go to the ignored
``data/dish-revision/``. Descriptive numbers only.
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from experiments.dish_tokens.calls import read_key

from app.dishes import prompts
from app.dishes.catalog import Catalog
from app.dishes.llm import DishLLM, DishLLMError
from app.dishes.recipe_names import RecipeNames
from app.dishes.recipes import RecipeStore
from app.dishes.revision import Reviser

HERE = Path(__file__).resolve().parent
OUT = HERE.parents[2] / "data" / "dish-revision"
SERVED = prompts.REVISE_SYSTEM
REFERENCE_RULE = (
    " When you remove or change a step, rewrite or remove every later step and tip that used what"
    " it made (a sauce, broth, batter or cooked part). Each step and tip may name only ingredients"
    " in the revised list or things an earlier step makes."
)


def reference_variant(text: str) -> str:
    """Append the rule to rule 3 of the revision prompt (pure, tested)."""
    anchor = "The ingredient list and the steps must agree."
    if anchor not in text:
        raise ValueError("rule 3 anchor not found")
    return text.replace(anchor, anchor + REFERENCE_RULE, 1)


def card_cases(catalog: Catalog, store: RecipeStore) -> list[dict]:
    """One case per served recipe; the fridge is the dish's key ingredients (pure, tested)."""
    return [
        {"dish_id": d.id, "ingredients": list(d.key_ingredients)}
        for d in catalog.all()
        if store.get(d.id) is not None
    ]


def offline(index, catalog: Catalog, store: RecipeStore) -> dict:
    """Availability without any call: unavailable rows per recipe and by role."""
    per, roles, main_gap = [], Counter(), []
    for case in card_cases(catalog, store):
        recipe = store.get(case["dish_id"])
        owned = index.owned(case["ingredients"])
        status = [index.status(r.name, owned) for r in recipe.ingredients]
        gone = [r for r, s in zip(recipe.ingredients, status, strict=True) if s == "unavailable"]
        per.append(len(gone))
        roles.update(r.role for r in gone)
        if any(r.role == "main" for r in gone):
            main_gap.append(case["dish_id"])
    return {
        "recipes": len(per),
        "unavailable_rows": sum(per),
        "recipes_with_none": sum(n == 0 for n in per),
        "per_recipe": dict(sorted(Counter(per).items())),
        "by_role": dict(roles),
        "main_unavailable_recipes": len(main_gap),
        "main_unavailable_ids": main_gap,
    }


REASK = (
    "\n\nYour previous answer was rejected by a check: {message}. Answer again and follow every "
    "rule."
)


class Recording:
    """A chat model wrapper that keeps every raw answer."""

    def __init__(self, llm) -> None:
        self.llm, self.answers = llm, []

    def complete(self, *args, **kwargs) -> dict:
        data = self.llm.complete(*args, **kwargs)
        self.answers.append(data)
        return data


class ReaskReviser(Reviser):
    """Reviser that asks once more, with the violation message, when the check rejects."""

    def _answer(self, request, recipe, status, ingredients, base):
        data = self.llm.complete(request.system, request.user, request.name, request.schema)
        response, violation = self._judge(data, recipe, status, ingredients, base)
        if violation is None:
            return response
        user = request.user + REASK.format(message=violation.message)
        data = self.llm.complete(request.system, user, request.name, request.schema)
        return self._judge(data, recipe, status, ingredients, base)[0]


class TokenLog(logging.Handler):
    """Collects (input, output) tokens from the model client's log line, one entry per call."""

    def __init__(self) -> None:
        super().__init__(logging.INFO)
        self.calls: list[tuple[int, int]] = []

    def emit(self, record: logging.LogRecord) -> None:
        if record.msg.startswith("dish model call") and len(record.args) == 5:
            self.calls.append((record.args[3] or 0, record.args[4] or 0))


def run(variant: str, index, catalog, store, llm) -> list[dict]:
    llm = Recording(llm)
    reviser = (ReaskReviser if variant.startswith("N3") else Reviser)(catalog, index, llm, store)
    tokens = TokenLog()
    logging.getLogger("app.dishes.llm").addHandler(tokens)
    logging.getLogger("app.dishes.llm").setLevel(logging.INFO)
    rows = []
    for case in card_cases(catalog, store):
        before, seen = len(tokens.calls), len(llm.answers)
        started = time.monotonic()
        try:
            r = reviser.revise(case["dish_id"], case["ingredients"])
            out = {
                "status": r.status,
                "code": r.error.code if r.error else None,
                "refusal": r.refusal_reason,
                "unavailable": sum(s == "unavailable" for s in r.availability),
                "revised": r.revised.model_dump() if r.revised else None,
                "changes": [c.model_dump() for c in r.changes],
            }
        except DishLLMError as exc:
            out = {"status": "provider_error", "code": str(exc)[:80]}
        out["seconds"] = round(time.monotonic() - started, 2)
        out["calls"] = tokens.calls[before:]
        out["answers"] = llm.answers[seen:]
        rows.append({"variant": variant, **case, **out})
        print(variant, case["dish_id"], out["status"], out.get("code"), flush=True)
    logging.getLogger("app.dishes.llm").removeHandler(tokens)
    return rows


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--allow-live-api", action="store_true")
    p.add_argument("--recipes", type=Path, required=True, help="served recipe file (untracked)")
    p.add_argument("--variants", default="N0,N1,N2")
    a = p.parse_args(argv)
    catalog = Catalog.load()
    store = RecipeStore.load(a.recipes)
    names = RecipeNames.load()
    indexes = {"N0": catalog, "N1": names, "N2": names, "N3": names, "N3a": names}
    result: dict = {
        "started": datetime.now(UTC).isoformat(timespec="seconds"),
        "offline": {"N0": offline(catalog, catalog, store), "N1": offline(names, catalog, store)},
    }
    print(
        json.dumps(
            {
                k: {x: y for x, y in v.items() if x != "main_unavailable_ids"}
                for k, v in result["offline"].items()
            },
            ensure_ascii=False,
        )
    )
    if not a.allow_live_api:
        return 0
    llm = DishLLM(api_key=read_key())
    for variant in a.variants.split(","):
        with_rule = variant in ("N2", "N3")
        prompts.REVISE_SYSTEM = reference_variant(SERVED) if with_rule else SERVED
        result[variant] = run(variant, indexes[variant], catalog, store, llm)
    prompts.REVISE_SYSTEM = SERVED
    OUT.mkdir(parents=True, exist_ok=True)
    tag = "" if a.variants == "N0,N1,N2" else "-" + a.variants.replace(",", "-")
    path = OUT / f"round3{tag}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=1))
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


def in_range_refs(data: dict, n_rows: int, n_steps: int) -> dict:
    """The answer with every out-of-range row or step reference dropped (pure, tested)."""
    changes = []
    for c in data.get("changes") or []:
        if not isinstance(c, dict):
            changes.append(c)
            continue
        refs = c.get("ingredient_refs")
        steps = c.get("step_refs")
        changes.append(
            c
            | {
                "ingredient_refs": [i for i in refs if isinstance(i, int) and 1 <= i <= n_rows]
                if isinstance(refs, list)
                else refs,
                "step_refs": [i for i in steps if isinstance(i, int) and 1 <= i <= n_steps]
                if isinstance(steps, list)
                else steps,
            }
        )
    return data | {"changes": changes}
