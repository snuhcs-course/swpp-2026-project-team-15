# AI-generated with Claude Code (Sonnet 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""Check what the model answered before the user sees it. No model call, no network.

The model's order is kept. Only what the closed lists can decide is decided here: a dish name must
be in the dish list, ``have`` and ``missing`` must be within the request's choices (choices.py),
and a substitute must be something the user owns. The re-check matters when a provider does not
enforce the answer format.
"""

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
    choices, also drop ``missing`` entries outside them, so an owned ingredient never comes back as
    missing, and decide ``have`` here: the user's items that are this dish's own ingredients. A
    dish that uses none of them is dropped (the served model listed 35 egg dishes with
    ``have: [초콜릿]`` for a fridge of only 초콜릿; research/experiments/e2e_followups, item 1)."""
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
        if choices is not None:
            have = [i for i in choices.have if catalog.uses(dish, i)]
            if not have:
                continue
        else:
            have = strings(item.get("have"))
        seen.add(dish.id)
        out.append(
            SuggestedDish(
                id=dish.id,
                name=dish.name,
                category=dish.category,
                have=have,
                missing=_within(strings(item.get("missing")), missing_ok),
                search_url=search_url(dish.name),
                has_recipe=recipes is not None and dish.id in recipes,
            )
        )
    return out


# The longest list a suggestion returns. Chosen in round 5 of research/experiments/
# dish_output_formats: the 90th percentile, over 29 inputs, of how many dishes the dish list says
# the user can cook missing at most one key ingredient. Ordinary answers are shorter and are not
# cut; only runaway answers that walk the whole dish list (계란 + 밥 gave 118) are.
SUGGEST_LIMIT = 36


def fewest_missing_first(dishes: list[SuggestedDish]) -> list[SuggestedDish]:
    """Dishes the model says need fewer missing ingredients come first; ties keep its order; at
    most SUGGEST_LIMIT are kept.

    The model is asked for best-first order but walks the dish list in its given order (round 3 of
    research/experiments/dish_output_formats), so the server orders by the model's own `missing`
    and then keeps the first SUGGEST_LIMIT."""
    return sorted(dishes, key=lambda d: len(d.missing))[:SUGGEST_LIMIT]


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
