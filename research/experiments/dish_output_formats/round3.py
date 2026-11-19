# AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""Round 3 of the answer-format study: how long the suggestion list is under the closed choices.

Pure builders and scorers (no network). P0 is the request the server sends today; PA and PB change
only the wording; PC adds a per-dish ``fit`` field; PD is the earlier free-text request. See
``criteria_round3.json``.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.dishes.answers import check_suggest
from app.dishes.catalog import Catalog
from app.dishes.choices import SuggestChoices, owned_vocabulary, suggest_choices
from app.dishes.prompts import (
    suggest_schema,
    suggest_user_message,
)
from experiments.legacy_prompts import SUGGEST_CLOSED_SYSTEM_ROUND2, SUGGEST_SCHEMA, SUGGEST_SYSTEM

from . import formats

HERE = Path(__file__).resolve().parent
VARIANTS = ("P0", "PA", "PB", "PC", "PD")


def criteria() -> dict:
    return json.loads((HERE / "criteria_round3.json").read_text(encoding="utf-8"))


def system_prompt(variant: str) -> str:
    if variant == "P0":
        return SUGGEST_CLOSED_SYSTEM_ROUND2
    if variant == "PD":
        return SUGGEST_SYSTEM
    return criteria()["prompts"][variant]


def fit_schema(choices: SuggestChoices, fits: list[str]) -> dict:
    """P0's schema with ``fit`` written before ``have`` and ``missing``."""
    schema = suggest_schema(choices)
    dish = schema["properties"]["dishes"]["items"]
    props = dish["properties"]
    dish["properties"] = {
        "name": props["name"],
        "fit": {"type": "string", "enum": fits},
        "have": props["have"],
        "missing": props["missing"],
    }
    dish["required"] = ["name", "fit", "have", "missing"]
    return schema


def answer_schema(variant: str, choices: SuggestChoices) -> dict:
    if variant == "PD":
        return SUGGEST_SCHEMA
    if variant == "PC":
        return fit_schema(choices, criteria()["pc_fit_values"])
    return suggest_schema(choices)


def payload(variant: str, choices: SuggestChoices) -> dict:
    """The same request body the server's model client sends, with this variant's text/schema."""
    return {
        "model": formats.MODEL,
        "messages": [
            {"role": "system", "content": system_prompt(variant)},
            {"role": "user", "content": suggest_user_message(choices.have, choices.names)},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "dish_choice",
                "strict": True,
                "schema": answer_schema(variant, choices),
            },
        },
        "provider": {"require_parameters": True},
        "max_tokens": formats.MAX_TOKENS,
        "temperature": 0,
    }


def choices_for(catalog: Catalog, vocab: list[str], ingredients: list[str]) -> SuggestChoices:
    return suggest_choices(ingredients, [d.name for d in catalog.all()], vocab)


def checked(variant: str, data: dict | None, catalog: Catalog, choices: SuggestChoices) -> list:
    """What the server would return: names in the list, no repeats, values within the choices."""
    if not data:
        return []
    return check_suggest(data, catalog, None, None if variant == "PD" else choices)


def fits_by_id(data: dict | None, catalog: Catalog) -> dict[str, str]:
    out: dict[str, str] = {}
    items = (data or {}).get("dishes")
    for item in items if isinstance(items, list) else []:
        dish = catalog.by_name(item.get("name", "")) if isinstance(item, dict) else None
        if dish is not None and dish.id not in out and isinstance(item.get("fit"), str):
            out[dish.id] = item["fit"]
    return out


def rules_missing(catalog: Catalog, ingredients: list[str]) -> dict[str, int]:
    owned = catalog.owned(ingredients)
    return {d.id: len(catalog.match(d, owned).missing) for d in catalog.all()}


def owned_listed_as_missing(dishes: list, ingredients: list[str], vocab: list[str]) -> int:
    owned = owned_vocabulary(list(ingredients), vocab)
    return sum(1 for d in dishes if owned & set(d.missing))


def bucket(n: int) -> str:
    return str(n) if n < 3 else "3+"
