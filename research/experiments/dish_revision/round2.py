# AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""Round 2 of the revision study: refusal before the call and main-ingredient preservation.

Pure functions (no model, no network). One model answer per case is shared by the four variants,
because the variants differ only in steps before and after the call:

- current: the server as it is (answer check only)
- prescreen: refuse without a call when an ingredient the dish is named after is unavailable
- main-kept: after the answer check, a dropped main ingredient means "refuse" (or a failure when
  the user had it) and a removed one-character ingredient may not stay in a step
- both: prescreen, then main-kept
"""

from __future__ import annotations

from statistics import median

from app.dishes.revision_check import (
    RefusalNeeded,
    Violation,
    check,
    check_main_kept,
    check_short_mentions,
    identity_missing,
)
from app.dishes.roles import IngredientIndex
from app.dishes.schemas import SourceRecipe

VARIANTS = ("current", "prescreen", "main-kept", "both")
_PRESCREEN = {"prescreen", "both"}
_STRICT = {"main-kept", "both"}


def _key(text: str) -> str:
    return text.strip().replace(" ", "")


def build_real_cases(recipes: dict[str, SourceRecipe], index: IngredientIndex) -> list[dict]:
    """Two fridges per recipe, fixed by rule before any call (one labeller's draft).

    a: every ingredient except the first main one that is not a staple -> expect refuse.
    b: every ingredient except the first two secondary ones that are not staples -> expect revise
       (skipped when the recipe has none).
    """
    cases: list[dict] = []
    for dish_id in sorted(recipes):
        recipe = recipes[dish_id]
        names = [r.name for r in recipe.ingredients]

        def not_staple(name: str) -> bool:
            return index.status(name, set()) != "assumed"

        mains = [r.name for r in recipe.ingredients if r.role == "main" and not_staple(r.name)]
        if mains:
            gone = mains[0]
            cases.append(
                {
                    "id": f"{dish_id}:a",
                    "dish_id": dish_id,
                    "ingredients": [n for n in names if n != gone],
                    "expect": "refuse",
                    "note": f"missing main {gone}",
                }
            )
        seconds = [
            r.name for r in recipe.ingredients if r.role == "secondary" and not_staple(r.name)
        ][:2]
        if seconds:
            cases.append(
                {
                    "id": f"{dish_id}:b",
                    "dish_id": dish_id,
                    "ingredients": [n for n in names if n not in seconds],
                    "expect": "revise",
                    "note": "missing secondary " + ", ".join(seconds),
                }
            )
    return cases


def prescreened(variant: str, dish_name: str, recipe: SourceRecipe, status: list[str]) -> list[str]:
    return identity_missing(dish_name, recipe, status) if variant in _PRESCREEN else []


def decide(
    variant: str,
    raw: dict | None,
    recipe: SourceRecipe,
    dish_name: str,
    status: list[str],
    index: IngredientIndex,
    owned: list[str],
) -> dict:
    """Outcome of one case under one variant: status, code, whether the model was needed."""
    if prescreened(variant, dish_name, recipe, status):
        return {"status": "refused", "code": "prescreen", "call": False}
    if raw is None:
        return {"status": "error", "code": "no_answer", "call": True}
    if raw.get("can_revise") is False:
        reason = raw.get("refusal_reason")
        ok = isinstance(reason, str) and reason.strip()
        return {
            "status": "refused" if ok else "failed",
            "code": None if ok else "incomplete",
            "call": True,
        }
    try:
        revised, changes = check(raw, recipe, status, index, owned)
        if variant in _STRICT:
            check_main_kept(recipe, status, revised, changes)
            check_short_mentions(recipe, status, revised)
    except RefusalNeeded:
        return {"status": "refused", "code": "refuse_needed", "call": True}
    except Violation as violation:
        return {"status": "failed", "code": violation.code, "call": True}
    flags = unavailable_left(recipe, status, raw)
    return {"status": "revised", "code": None, "call": True, "flags": flags}


def unavailable_left(recipe: SourceRecipe, status: list[str], raw: dict) -> list[str]:
    """Unavailable source ingredients whose name still appears anywhere in an accepted answer
    (plain substring, one-character names included). A screen for manual review, not a rule."""
    rows = raw.get("ingredients") if isinstance(raw.get("ingredients"), list) else []
    texts = [r.get("name", "") for r in rows if isinstance(r, dict)]
    texts += [t for t in raw.get("steps", []) if isinstance(t, str)]
    texts += [t for t in raw.get("tips", []) if isinstance(t, str)]
    flat = _key(" ".join(texts))
    return [
        r.name
        for r, s in zip(recipe.ingredients, status, strict=True)
        if s == "unavailable" and _key(r.name) and _key(r.name) in flat
    ]


def _rate(num: int, den: int) -> float | None:
    return num / den if den else None


def summarize(rows: list[dict]) -> dict:
    """Counts and shares of one variant over the given cases. Each row: expect, status, code."""
    refuse = [r for r in rows if r["expect"] == "refuse"]
    revise = [r for r in rows if r["expect"] == "revise"]
    refused = [r for r in rows if r["status"] == "refused"]
    codes: dict[str, int] = {}
    for r in rows:
        if r["status"] == "failed":
            codes[r["code"]] = codes.get(r["code"], 0) + 1
    return {
        "cases": len(rows),
        "expect_refuse": len(refuse),
        "expect_revise": len(revise),
        "wrong_accepted": sum(r["status"] == "revised" for r in refuse),
        "refused_when_expected": sum(r["status"] == "refused" for r in refuse),
        "failed_when_refuse_expected": sum(r["status"] == "failed" for r in refuse),
        "revised_when_expected": sum(r["status"] == "revised" for r in revise),
        "wrongful_refusals": sum(r["status"] == "refused" for r in revise),
        "failed_when_revise_expected": sum(r["status"] == "failed" for r in revise),
        "refusal_recall": _rate(sum(r["status"] == "refused" for r in refuse), len(refuse)),
        "refusal_precision": _rate(sum(r["expect"] == "refuse" for r in refused), len(refused)),
        "failure_codes": codes,
        "model_calls": sum(1 for r in rows if r.get("call")),
        "accepted_with_flags": sum(1 for r in rows if r.get("flags")),
    }


def transitions(before: list[dict], after: list[dict]) -> list[dict]:
    """Cases whose outcome differs between two variants (same order of rows)."""
    return [
        {
            "id": a["id"],
            "expect": a["expect"],
            "from": a["status"],
            "to": b["status"],
            "code": b["code"],
        }
        for a, b in zip(before, after, strict=True)
        if (a["status"], a["code"]) != (b["status"], b["code"])
    ]


def latency_cost(calls: list[dict]) -> dict:
    lat = sorted(c["latency_s"] for c in calls if c.get("latency_s") is not None)
    return {
        "calls": len(calls),
        "median_latency_s": median(lat) if lat else None,
        "max_latency_s": lat[-1] if lat else None,
        "total_cost_usd": sum(c.get("cost_usd", 0.0) for c in calls),
    }
