# AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""Round 5 of the answer-format study: spelling versus run-to-run variation, and a list limit.

Pure builders (no network). B_served is the request the server sends today; B_cap_K limits the
dish array to K items in the answer format and says so in one sentence. K comes from the catalog
by the fixed procedure in ``criteria_round5.json``. See that file for the plan.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from app.dishes.catalog import Catalog
from app.dishes.choices import suggest_choices
from app.dishes.prompts import suggest_request

from . import formats

HERE = Path(__file__).resolve().parent
CAP_SENTENCE = (
    " Return at most {k} dishes, choosing those the user can cook with the fewest missing "
    "ingredients."
)


def criteria() -> dict:
    return json.loads((HERE / "criteria_round5.json").read_text(encoding="utf-8"))


def demo_cases() -> list[dict]:
    return [
        {"id": "D1", "ingredients": ["두부"]},
        {"id": "D2", "ingredients": ["김치", "밥", "간장", "소금"]},
    ]


def cook_now_count(catalog: Catalog, ingredients: list[str]) -> int:
    """Catalog dishes the user lacks at most one key ingredient of (staples count as owned)."""
    owned = catalog.owned(ingredients)
    return sum(len(catalog.match(d, owned).missing) <= 1 for d in catalog.all())


def nearest_rank(values: list[int], q: float) -> int:
    ordered = sorted(values)
    rank = max(1, -(-len(ordered) * q // 1))  # ceil(q * n), at least 1
    return ordered[int(rank) - 1]


def limit_values(catalog: Catalog, cases: list[dict]) -> dict[str, int]:
    counts = [cook_now_count(catalog, c["ingredients"]) for c in cases]
    mid, high = nearest_rank(counts, 0.5), nearest_rank(counts, 0.9)
    if high == mid:
        high = max(counts)
    return {"K_mid": mid, "K_high": high, "counts": counts}


def body(
    catalog: Catalog,
    vocab: list[str],
    ingredients: list[str],
    k: int | None,
    in_schema: bool = True,
    max_tokens: int = formats.MAX_TOKENS,
):
    """The server's request body (app.dishes.llm.DishLLM), optionally limited to k dishes."""
    names = [d.name for d in catalog.all()]
    choices = suggest_choices(ingredients, names, vocab, catalog.staples)
    req = suggest_request(choices)
    system, schema = req.system, json.loads(json.dumps(req.schema))
    if k is not None:
        system += CAP_SENTENCE.format(k=k)
        if in_schema:  # rejected with HTTP 400 on this route (amendment of criteria_round5.json)
            schema["properties"]["dishes"]["maxItems"] = k
    payload = {
        "model": formats.MODEL,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": req.user}],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": req.name, "strict": True, "schema": schema},
        },
        "provider": {"require_parameters": True},
        "max_tokens": max_tokens,
        "temperature": 0,
    }
    return choices, payload


def token_room(k: int, served_rows: list[dict]) -> int:
    """ceil(k x the 95th percentile of output tokens per returned dish) (amendment 2)."""
    per = sorted(r["output_tokens"] / r["raw_count"] for r in served_rows if r["raw_count"])
    p95 = per[min(len(per) - 1, round(0.95 * (len(per) - 1)))]
    return math.ceil(k * p95)
