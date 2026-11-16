# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""Scoring for the dish evaluation: pure functions, no network, no model.

Each ``check_*`` function judges one case against the labels in ``cases.json`` and returns a small
dict of booleans / counts. ``aggregate`` turns those into the metrics named in ``thresholds.json``
and ``verdict`` compares them with the declared thresholds. Judging never relies on exact string
equality alone: schema checks, set comparisons against the labelled table pairs, pattern checks
for invented quantities or steps, and the labelled outcome class are combined.
"""

from __future__ import annotations

import re
import statistics
from collections.abc import Callable, Iterable
from typing import Any, Protocol

NOTHING_MISSING = "부족한 재료가 없어요."
NO_SUBSTITUTE = "냉장고 재료로는 마땅한 대체를 찾지 못했어요."
SOURCES = {"llm", "rules"}
DISH_FIELDS = {
    "id": str,
    "name": str,
    "category": str,
    "have": list,
    "missing": list,
    "reason": str,
    "keywords": list,
    "videos": list,
    "search_url": str,
}
# Invented amounts or cooking steps: digits, units, or step words (a suggestion is one short
# phrase such as "양파(으)로 대신해요"; it never needs these).
QUANTITY_OR_STEP = re.compile(
    r"\d|[큰작]술|스푼|티스푼|컵|그램|리터|\bml\b|\bg\b|인분|분간|분 동안|먼저|그다음|그 다음|"
    r"한 뒤|한뒤|넣은 뒤|넣고|끓이|볶아|삶아|썰어|굽고|섞어|저어"
)


class CatalogView(Protocol):
    staples: frozenset[str]
    dish_keys: dict[str, tuple[str, ...]]

    def owned(self, ingredients: list[str]) -> set[str]: ...


def _is_list_of_str(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(v, str) for v in value)


def dish_schema_ok(dish: Any) -> bool:
    if not isinstance(dish, dict):
        return False
    for name, kind in DISH_FIELDS.items():
        if not isinstance(dish.get(name), kind):
            return False
    return _is_list_of_str(dish["have"]) and _is_list_of_str(dish["missing"])


def suggest_schema_ok(response: Any, limit: int) -> bool:
    return (
        isinstance(response, dict)
        and response.get("source") in SOURCES
        and isinstance(response.get("dishes"), list)
        and len(response["dishes"]) <= limit
        and all(dish_schema_ok(d) for d in response["dishes"])
    )


def check_suggest(case: dict, response: dict, view: CatalogView) -> dict:
    """Judge one valid (status 200) suggest case."""
    limit = case["input"].get("limit", 5)
    schema = suggest_schema_ok(response, limit)
    dishes = response.get("dishes", []) if schema else []
    top = dishes[:5]
    ids_ok = schema and all(d["id"] in view.dish_keys for d in dishes)
    owned = view.owned(case["input"]["ingredients"])
    consistent = schema and ids_ok
    if consistent:
        for dish in dishes:
            keys = set(view.dish_keys[dish["id"]])
            have, missing = set(dish["have"]), set(dish["missing"])
            if not (have | missing) <= keys or have & missing or missing & owned:
                consistent = False
                break
    acceptable = set(case.get("acceptable_dish_ids", []))
    if case.get("expect_empty"):
        hit = schema and not dishes
    else:
        hit = any(d["id"] in acceptable for d in top)
    forbidden = set(case.get("must_not_include", []))
    return {
        "schema_valid": bool(schema),
        "ids_in_catalog": bool(ids_ok),
        "have_missing_consistent": bool(consistent),
        "acceptable_in_top5": bool(hit),
        "must_not_include_hits": sum(1 for d in top if d["id"] in forbidden),
        "dishes": len(top),
        "dishes_le2_missing": sum(1 for d in top if len(d["missing"]) <= 2),
        "source": response.get("source") if schema else None,
    }


def basic_core(names: Iterable[str], staples: frozenset[str]) -> frozenset[str]:
    """Compare ingredient sets without basic seasonings, unless they are all there is."""
    names = set(names)
    core = {n for n in names if n not in staples}
    return frozenset(core or names)


def check_adapt(case: dict, response: dict | None, staples: frozenset[str]) -> dict:
    """Judge one valid (status 200) adapt case."""
    outcome = case["outcome"]
    out = {
        "schema_valid": False,
        "pairs_in_table": False,
        "no_quantities_or_steps": False,
        "outcome_match": False,
        "empty_with_note_ok": None,
    }
    if not isinstance(response, dict):
        return out
    subs = response.get("substitutions")
    skip = response.get("skip_ok")
    note = response.get("note")
    schema = (
        response.get("source") in SOURCES
        and isinstance(subs, list)
        and all(
            isinstance(s, dict)
            and isinstance(s.get("missing"), str)
            and isinstance(s.get("suggestion"), str)
            and _is_list_of_str(s.get("uses"))
            for s in subs
        )
        and _is_list_of_str(skip)
        and isinstance(note, str)
    )
    out["schema_valid"] = bool(schema)
    if not schema:
        return out
    allowed: dict[str, list[frozenset[str]]] = {}
    for pair in case.get("allowed_pairs", []):
        allowed.setdefault(pair["missing"], []).append(basic_core(pair["uses"], staples))
    out["pairs_in_table"] = all(
        s["missing"] in allowed and basic_core(s["uses"], staples) in allowed[s["missing"]]
        for s in subs
    )
    texts = [s["suggestion"] for s in subs] + [note]
    out["no_quantities_or_steps"] = not any(QUANTITY_OR_STEP.search(t) for t in texts)
    got_missing = {s["missing"] for s in subs}
    expected_skip = set(case.get("expected_skip_ok", []))
    if outcome in ("allowed_substitution", "allowed+skip"):
        match = got_missing == set(allowed) and bool(subs) and set(skip) == expected_skip
    elif outcome == "skip_ok_only":
        match = not subs and set(skip) == expected_skip
    elif outcome == "empty_with_note":
        match = not subs and not skip and note == NO_SUBSTITUTE
        out["empty_with_note_ok"] = bool(match)
    elif outcome == "nothing_missing":
        match = not subs and not skip and note == NOTHING_MISSING
    else:
        match = False
    out["outcome_match"] = bool(match)
    return out


def _share(flags: list[bool]) -> float | None:
    return sum(flags) / len(flags) if flags else None


def aggregate(
    suggest: list[dict],
    suggest_invalid: list[bool],
    fallback: list[bool],
    adapt: list[dict],
    adapt_invalid: list[bool],
    latencies: list[float] | None = None,
) -> dict:
    """Metrics named in thresholds.json from per-case results."""
    dishes = sum(r["dishes"] for r in suggest)
    metrics: dict[str, float | None] = {
        "suggest.schema_valid": _share([r["schema_valid"] for r in suggest]),
        "suggest.ids_in_catalog": _share([r["ids_in_catalog"] for r in suggest]),
        "suggest.have_missing_consistent": _share([r["have_missing_consistent"] for r in suggest]),
        "suggest.acceptable_in_top5": _share([r["acceptable_in_top5"] for r in suggest]),
        "suggest.share_le2_missing": (
            sum(r["dishes_le2_missing"] for r in suggest) / dishes if dishes else None
        ),
        "suggest.must_not_include_hits": float(sum(r["must_not_include_hits"] for r in suggest)),
        "suggest.invalid_inputs_rejected": _share(suggest_invalid),
        "suggest.fallback_valid": _share(fallback),
        "adapt.pairs_in_table": _share([r["pairs_in_table"] for r in adapt]),
        "adapt.no_quantities_or_steps": _share([r["no_quantities_or_steps"] for r in adapt]),
        "adapt.empty_with_note_ok": _share(
            [r["empty_with_note_ok"] for r in adapt if r["empty_with_note_ok"] is not None]
        ),
        "adapt.outcome_match": _share([r["outcome_match"] for r in adapt]),
        "adapt.unknown_rejected": _share(adapt_invalid),
        "adapt.latency_median_s": statistics.median(latencies) if latencies else None,
    }
    return metrics


def verdict(metrics: dict, thresholds: dict) -> list[dict]:
    """One row per declared threshold: metric value, comparison, pass / fail / not measured."""
    rows = []
    ops: dict[str, Callable[[float, float], bool]] = {
        ">=": lambda a, b: a >= b - 1e-12,
        "<=": lambda a, b: a <= b + 1e-12,
    }
    for group in ("suggest", "adapt"):
        for name, spec in thresholds[group].items():
            key = f"{group}.{name}"
            value = metrics.get(key)
            if value is None:
                status = "not measured"
            else:
                status = "pass" if ops[spec["op"]](value, spec["value"]) else "fail"
            rows.append(
                {
                    "metric": key,
                    "value": value,
                    "op": spec["op"],
                    "threshold": spec["value"],
                    "status": status,
                }
            )
    return rows
