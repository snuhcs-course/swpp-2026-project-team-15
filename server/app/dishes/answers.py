# AI-generated with Claude Code (Sonnet 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""Check what the model answered before the user sees it. No model call, no network.

The model's order is kept. Only what the closed lists can decide is decided here: a dish name must
be in the dish list, ``have`` and ``missing`` must be within the request's choices (choices.py),
and a substitute must be something the user owns. The re-check matters when a provider does not
enforce the answer format.
"""

import json
import re
from urllib.parse import quote_plus

from app.dishes.choices import SuggestChoices
from app.dishes.korean import attach
from app.dishes.roles import DishCatalog, RecipeBook
from app.dishes.schemas import Substitution, SuggestedDish


def search_url(dish_name: str) -> str:
    return f"https://www.youtube.com/results?search_query={quote_plus(dish_name + ' 레시피')}"


def strings(value: object, *, unique: bool = True) -> list[str]:
    """The non-empty trimmed strings of a list; anything else is an empty list."""
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = item.strip() if isinstance(item, str) else ""
        if text and not (unique and text in out):
            out.append(text)
    return out


def _within(values: list[str], allowed: list[str] | None) -> list[str]:
    if allowed is None:
        return values
    allowed_set = set(allowed)
    return [v for v in values if v in allowed_set]


def check_suggest(
    data: dict,
    catalog: DishCatalog,
    recipes: RecipeBook | None,
    choices: SuggestChoices | None = None,
) -> list[SuggestedDish]:
    """Keep the model's order; drop names outside the list and repeated names. With the request's
    choices, also drop ``have``/``missing`` entries outside them, so an owned ingredient never
    comes back as missing."""
    have_ok = choices.have if choices else None
    missing_ok = choices.missing if choices else None
    out: list[SuggestedDish] = []
    seen: set[str] = set()
    items = data.get("dishes")
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        dish = catalog.by_name(name.strip()) if isinstance(name, str) else None
        if dish is None or dish.id in seen:
            continue
        seen.add(dish.id)
        out.append(
            SuggestedDish(
                id=dish.id,
                name=dish.name,
                category=dish.category,
                have=_within(strings(item.get("have")), have_ok),
                missing=_within(strings(item.get("missing")), missing_ok),
                search_url=search_url(dish.name),
                has_recipe=recipes is not None and dish.id in recipes,
            )
        )
    return out


def fewest_missing_first(dishes: list[SuggestedDish]) -> list[SuggestedDish]:
    """Dishes the model says need fewer missing ingredients come first; ties keep its order.

    The model is asked for best-first order but walks the dish list in its given order (round 3 of
    research/experiments/dish_output_formats), so the server orders by the model's own `missing`.
    Nothing is dropped and no count is imposed."""
    return sorted(dishes, key=lambda d: len(d.missing))


def check_adapt(data: dict, missing: list[str], owned: list[str]) -> list[Substitution]:
    subs: list[Substitution] = []
    used: set[str] = set()
    items = data.get("substitutions")
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        gap, sub = item.get("missing"), item.get("substitute")
        if gap not in missing or gap in used or not isinstance(sub, str):
            continue
        sub = sub.strip()
        if sub not in owned:
            continue
        used.add(gap)
        subs.append(
            Substitution(missing=gap, suggestion=f"{attach(sub, '으로')} 대신해요", uses=[sub])
        )
    return subs


_LIST_START = re.compile(r'\s*\{\s*"(\w+)"\s*:\s*\[')


def salvage_list(text: str) -> dict | None:
    """The complete items of a cut-off ``{"key": [ {...}, {...`` answer, or None if there are none.

    A cut only loses the dishes after the last complete one; the server orders what is kept."""
    start = _LIST_START.match(text)
    if not start:
        return None
    decoder, pos, items = json.JSONDecoder(), start.end(), []
    while True:
        while pos < len(text) and text[pos] in " \n\r\t,":
            pos += 1
        try:
            item, pos = decoder.raw_decode(text, pos)
        except ValueError:
            break
        items.append(item)
    return {start.group(1): items} if items else None
