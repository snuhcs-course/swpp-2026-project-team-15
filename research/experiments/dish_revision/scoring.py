# AI-generated with Claude Code (Sonnet 5.5), 2026-11-18; reviewed by Jaehyuk Choi.
"""Metrics of the recipe revision study, computed from per-case rows (no model, no network)."""

from __future__ import annotations

from statistics import median

from app.dishes.schemas import SourceRecipe
from app.dishes.synonyms import with_synonyms

THRESHOLDS = {
    "json_valid_rate": (">=", 0.95),
    "post_check_pass_rate": (">=", 0.85),
    "wrongful_refusal_rate": ("<=", 0.10),
    "refusal_recall": (">=", 0.80),
    "refusal_precision": (">=", 0.90),
    "ingredient_reason_coverage": (">=", 0.90),
    "step_reason_coverage": (">=", 0.80),
    "median_latency_s": ("<=", 8.0),
    "mean_cost_usd": ("<=", 0.002),
}


def _key(text: str) -> str:
    return text.strip().replace(" ", "")


def dropped_ingredients(recipe: SourceRecipe, data: dict) -> list[int]:
    """1-based rows of the source ingredients that the raw answer no longer lists."""
    rows = data.get("ingredients")
    kept = {_key(r["name"]) for r in rows if isinstance(r, dict) and isinstance(r.get("name"), str)}
    kept = kept if isinstance(rows, list) else set()
    return [
        i
        for i, row in enumerate(recipe.ingredients, 1)
        if not (with_synonyms([_key(row.name)]) & kept)
    ]


def _refs(data: dict, field: str) -> set[int]:
    out: set[int] = set()
    changes = data.get("changes")
    for change in changes if isinstance(changes, list) else []:
        values = change.get(field) if isinstance(change, dict) else None
        out.update(v for v in values or [] if isinstance(v, int))
    return out


def ingredient_coverage(recipe: SourceRecipe, data: dict) -> tuple[int, int]:
    """(covered, total) over the dropped source ingredients of a raw revising answer."""
    dropped = dropped_ingredients(recipe, data)
    named = _refs(data, "ingredient_refs")
    return sum(1 for i in dropped if i in named), len(dropped)


def changed_steps(recipe: SourceRecipe, data: dict) -> list[int]:
    steps = data.get("steps")
    kept = {s.strip() for s in steps if isinstance(s, str)} if isinstance(steps, list) else set()
    return [s.n for s in recipe.steps if s.text.strip() not in kept]


def step_coverage(recipe: SourceRecipe, data: dict) -> tuple[int, int]:
    """(covered, total) over the source steps whose exact text is missing from the answer."""
    changed = changed_steps(recipe, data)
    named = _refs(data, "step_refs")
    return sum(1 for n in changed if n in named), len(changed)


def _rate(num: int, den: int) -> float | None:
    return num / den if den else None


def summarize(rows: list[dict]) -> dict:
    """Metrics of a run. Each row: id, expect, status, valid, latency_s, cost_usd, coverage."""
    valid = [r for r in rows if r["valid"]]
    answered = [r for r in valid if r["status"] in {"revised", "failed"}]
    expect_revise = [r for r in rows if r["expect"] == "revise"]
    expect_refuse = [r for r in rows if r["expect"] == "refuse"]
    refused = [r for r in rows if r["status"] == "refused"]
    ing = [r["ingredient_coverage"] for r in rows if r.get("ingredient_coverage")]
    stp = [r["step_coverage"] for r in rows if r.get("step_coverage")]
    latencies = [r["latency_s"] for r in rows if r["latency_s"] is not None]
    metrics = {
        "json_valid_rate": _rate(len(valid), len(rows)),
        "post_check_pass_rate": _rate(
            sum(r["status"] == "revised" for r in answered), len(answered)
        ),
        "wrongful_refusal_rate": _rate(
            sum(r["status"] == "refused" for r in expect_revise), len(expect_revise)
        ),
        "refusal_recall": _rate(
            sum(r["status"] == "refused" for r in expect_refuse), len(expect_refuse)
        ),
        "refusal_precision": _rate(sum(r["expect"] == "refuse" for r in refused), len(refused)),
        "ingredient_coverage": None,
        "ingredient_reason_coverage": _rate(sum(c for c, _ in ing), sum(t for _, t in ing)),
        "step_reason_coverage": _rate(sum(c for c, _ in stp), sum(t for _, t in stp)),
        "median_latency_s": median(latencies) if latencies else None,
        "p95_latency_s": sorted(latencies)[int(0.95 * (len(latencies) - 1))] if latencies else None,
        "mean_cost_usd": _rate_float(sum(r["cost_usd"] for r in rows), len(rows)),
    }
    metrics.pop("ingredient_coverage")
    return metrics


def _rate_float(total: float, den: int) -> float | None:
    return total / den if den else None


def verdicts(metrics: dict) -> dict[str, str]:
    out = {}
    for name, (op, limit) in THRESHOLDS.items():
        value = metrics.get(name)
        if value is None:
            out[name] = "n/a"
        elif (value >= limit) if op == ">=" else (value <= limit):
            out[name] = "pass"
        else:
            out[name] = "fail"
    return out
