# AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""Round 4 of the answer-format study: bounding the suggestion answer by its structure.

Pure builders (no network). S_now is the request the server sends today; S_noseason takes the
assumed staples out of the ``missing`` choices; S_shuffle sends the dish list in a seeded random
order; S_names asks for names only (a cost reference); S_split and S_split_noseason send one
request per dish category of the catalog and merge. See ``criteria_round4.json``.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, replace
from pathlib import Path

from app.dishes.catalog import Catalog
from app.dishes.choices import SuggestChoices, suggest_choices
from app.dishes.prompts import SUGGEST_CLOSED_SYSTEM, suggest_schema, suggest_user_message
from app.dishes.synonyms import SYNONYM_GROUPS

from . import formats

HERE = Path(__file__).resolve().parent
SINGLE = ("S_now", "S_noseason", "S_shuffle", "S_names")
SPLIT = ("S_split", "S_split_noseason")
VARIANTS = SINGLE + SPLIT


def criteria() -> dict:
    return json.loads((HERE / "criteria_round4.json").read_text(encoding="utf-8"))


@dataclass(frozen=True)
class Request:
    """One model request of a variant: the group it covers and its closed choices."""

    group: str
    choices: SuggestChoices
    body: dict


def staple_forms(staples: frozenset[str]) -> set[str]:
    """The staples with every spelling of their synonym groups."""
    forms = set(staples)
    for group in SYNONYM_GROUPS:
        if forms & group:
            forms |= group
    return forms


def without_staples(choices: SuggestChoices, staples: frozenset[str]) -> SuggestChoices:
    forms = staple_forms(staples)
    return replace(choices, missing=[m for m in choices.missing if m not in forms])


def category_groups(catalog: Catalog) -> dict[str, list[str]]:
    """Dish names by the catalog's own category, categories in first-appearance order."""
    groups: dict[str, list[str]] = {}
    for dish in catalog.all():
        groups.setdefault(dish.category, []).append(dish.name)
    return groups


def shuffled(names: list[str], case_id: str, seed: int) -> list[str]:
    out = list(names)
    random.Random(f"{seed}:{case_id}").shuffle(out)
    return out


def names_schema(names: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {"dishes": {"type": "array", "items": {"type": "string", "enum": names}}},
        "required": ["dishes"],
        "additionalProperties": False,
    }


def body(system: str, choices: SuggestChoices, schema: dict) -> dict:
    """The same body the server's model client sends (app.dishes.llm.DishLLM)."""
    return {
        "model": formats.MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": suggest_user_message(choices.have, choices.names)},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "dish_choice", "strict": True, "schema": schema},
        },
        "provider": {"require_parameters": True},
        "max_tokens": formats.MAX_TOKENS,
        "temperature": 0,
    }


def requests_for(
    variant: str, case_id: str, ingredients: list[str], catalog: Catalog, vocab: list[str]
) -> list[Request]:
    crit = criteria()
    names = [d.name for d in catalog.all()]
    if variant in SPLIT:
        groups = category_groups(catalog)
    elif variant == "S_shuffle":
        groups = {"all": shuffled(names, case_id, crit["shuffle_seed"])}
    else:
        groups = {"all": names}
    out = []
    for group, group_names in groups.items():
        choices = suggest_choices(ingredients, group_names, vocab)
        if variant in ("S_noseason", "S_split_noseason"):
            choices = without_staples(choices, catalog.staples)
        if variant == "S_names":
            req = body(formats.prompts()["S1"], choices, names_schema(choices.names))
        else:
            req = body(SUGGEST_CLOSED_SYSTEM, choices, suggest_schema(choices))
        out.append(Request(group, choices, req))
    return out


def split_cases(cases: list[dict]) -> list[dict]:
    """The pre-registered subset the split variants run on: the demo inputs plus a seeded sample."""
    crit = criteria()
    rng = random.Random(crit["split_sample_seed"])
    sample = rng.sample(cases, crit["split_sample_size"])
    return demo_cases() + sample


def demo_cases() -> list[dict]:
    return [dict(c) for c in criteria()["demo_inputs"]]


def bucket(n: int) -> str:
    return str(n) if n < 3 else "3+"
