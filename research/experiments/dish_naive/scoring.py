# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""Scoring of the naive dish answers against the frozen criteria. Pure functions, no network."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from statistics import median

from app.dishes.synonyms import with_synonyms


def norm(text: str) -> str:
    return text.strip().replace(" ", "")


def owned_set(ingredients: Iterable[str]) -> set[str]:
    return with_synonyms(sorted({norm(i) for i in ingredients if i and i.strip()}))


def is_owned(item: str, owned: set[str]) -> bool:
    """Exact or synonym match after trimming and removing spaces."""
    name = norm(item)
    return bool(name) and (name in owned or bool(with_synonyms([name]) & owned))


def have_subset(
    have: Sequence[str], owned: set[str], staples: frozenset[str] = frozenset()
) -> bool:
    return all(is_owned(h, owned) or norm(h) in staples for h in have)


def missing_disjoint(missing: Sequence[str], owned: set[str]) -> bool:
    return not any(is_owned(m, owned) for m in missing)


def share(num: int, den: int) -> float | None:
    return None if den == 0 else num / den


def case_result(
    raw_names: Sequence[str],
    dishes: Sequence[dict],
    ingredients: Sequence[str],
    names_in_list: set[str],
    reference_ids: set[str],
    missing_counts: dict[str, int],
    staples: frozenset[str],
) -> dict:
    """Per-case counts; ``dishes`` are the checked answers (id, have, missing)."""
    owned = owned_set(ingredients)
    ids = [d["id"] for d in dishes]
    return {
        "raw_names": len(raw_names),
        "raw_names_valid": sum(1 for n in raw_names if n in names_in_list),
        "dishes": len(dishes),
        "have_ok": sum(have_subset(d["have"], owned) for d in dishes),
        "have_ok_staples_allowed": sum(have_subset(d["have"], owned, staples) for d in dishes),
        "missing_ok": sum(missing_disjoint(d["missing"], owned) for d in dishes),
        "reference_size": len(reference_ids),
        "reference_hits": len(reference_ids & set(ids)),
        "le2_missing": sum(1 for i in ids if missing_counts.get(i, 99) <= 2),
    }


def aggregate(results: Sequence[dict]) -> dict:
    t = {k: sum(r[k] for r in results) for k in results[0]} if results else {}
    possible = [r for r in results if r["reference_size"] > 0]
    return {
        "valid_names_share": share(t.get("raw_names_valid", 0), t.get("raw_names", 0)),
        "have_subset_share": share(t.get("have_ok", 0), t.get("dishes", 0)),
        "have_subset_share_with_staples_allowed": share(
            t.get("have_ok_staples_allowed", 0), t.get("dishes", 0)
        ),
        "missing_disjoint_share": share(t.get("missing_ok", 0), t.get("dishes", 0)),
        "nonempty_when_possible": share(sum(r["dishes"] > 0 for r in possible), len(possible)),
        "reference_recall": share(t.get("reference_hits", 0), t.get("reference_size", 0)),
        "reference_precision": share(t.get("reference_hits", 0), t.get("dishes", 0)),
        "reference_le2_missing_share": share(t.get("le2_missing", 0), t.get("dishes", 0)),
    }


def verdict(metrics: dict, thresholds: dict) -> dict[str, bool | None]:
    """True/False per threshold; None when the metric could not be computed."""
    out: dict[str, bool | None] = {}
    for key, rule in thresholds.items():
        value = metrics.get(key)
        if value is None:
            out[key] = None
        elif "min" in rule:
            out[key] = value >= rule["min"]
        else:
            out[key] = value <= rule["max"]
    return out


def median_or_none(values: Sequence[float]) -> float | None:
    return float(median(values)) if values else None
