# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""Suggest and adapt dishes the naive way: the model sees only the dish names and the user's
ingredients and answers with dishes plus what the user has and lacks. The server checks that the
names belong to the list and nothing else; there is no rules fallback."""

import json

from app.dishes.catalog import Catalog
from app.dishes.llm import DishLLM, DishLLMError
from app.dishes.schemas import (
    AdaptResponse,
    Substitution,
    SuggestedDish,
    SuggestResponse,
    Video,
)
from app.dishes.youtube import VideoCache, search_url

NO_SUBSTITUTE = "냉장고 재료로는 마땅한 대체를 찾지 못했어요."
NOT_CONFIGURED = "The model service is not configured"

SUGGEST_SYSTEM = (
    "You help a Korean student living alone decide what to cook from the ingredients they have. "
    "Return every dish from the given dish list that can reasonably be cooked with the owned "
    "ingredients, best first. Use the dish names exactly as written in the list. For each dish, "
    "'have' lists the main ingredients of the dish that the user owns (copy the user's wording) "
    "and 'missing' lists the main ingredients the user lacks. Basic seasonings and oil at home "
    "(salt, soy sauce, sugar, pepper, cooking oil, sesame oil, water) are not listed. If no dish "
    "fits, return an empty list. Never add dishes just to fill the list."
)
ADAPT_SYSTEM = (
    "A student wants to cook a dish but lacks some ingredients. For each missing ingredient, "
    "name ONE substitute that is in the owned ingredients list (copy it exactly), or an empty "
    "string if nothing owned can reasonably replace it. Never name anything that is not in the "
    "owned list."
)

SUGGEST_SCHEMA = {
    "type": "object",
    "properties": {
        "dishes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "have": {"type": "array", "items": {"type": "string"}},
                    "missing": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["name", "have", "missing"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["dishes"],
    "additionalProperties": False,
}
ADAPT_SCHEMA = {
    "type": "object",
    "properties": {
        "substitutions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "missing": {"type": "string"},
                    "substitute": {"type": "string"},
                },
                "required": ["missing", "substitute"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["substitutions"],
    "additionalProperties": False,
}


def suggest_user_message(ingredients: list[str], names: list[str]) -> str:
    return json.dumps({"owned": ingredients, "dishes": names}, ensure_ascii=False)


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = item.strip() if isinstance(item, str) else ""
        if text and text not in out:
            out.append(text)
    return out


class DishService:
    def __init__(
        self, catalog: Catalog, llm: DishLLM | None = None, cache: VideoCache | None = None
    ):
        self.catalog = catalog
        self.llm = llm
        self.cache = cache or VideoCache(None)
        self._by_name = {d.name: d for d in catalog.dishes.values()}

    def suggest(self, ingredients: list[str]) -> SuggestResponse:
        """Raises DishLLMError when the model is missing or fails."""
        if self.llm is None:
            raise DishLLMError(NOT_CONFIGURED)
        user = suggest_user_message(ingredients, list(self._by_name))
        data = self.llm.complete(SUGGEST_SYSTEM, user, "dish_choice", SUGGEST_SCHEMA)
        return SuggestResponse(source="llm", dishes=self.check_suggest(data))

    def check_suggest(self, data: dict) -> list[SuggestedDish]:
        """Keep the model's order; drop names outside the list and repeated names."""
        out: list[SuggestedDish] = []
        seen: set[str] = set()
        items = data.get("dishes")
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            dish = self._by_name.get(name.strip()) if isinstance(name, str) else None
            if dish is None or dish.id in seen:
                continue
            seen.add(dish.id)
            out.append(
                SuggestedDish(
                    id=dish.id,
                    name=dish.name,
                    category=dish.category,
                    have=_strings(item.get("have")),
                    missing=_strings(item.get("missing")),
                    videos=[Video(**v) for v in self.cache.get(dish.id) if _valid_video(v)],
                    search_url=search_url(dish.name),
                )
            )
        return out

    def adapt(
        self, dish_id: str, ingredients: list[str], missing: list[str]
    ) -> AdaptResponse | None:
        """None when the dish is unknown. Raises DishLLMError when the model call fails.

        The model names a substitute from the user's own ingredients (or null); the server only
        checks the JSON shape and that the substitute is one of those ingredients."""
        dish = self.catalog.get(dish_id)
        if dish is None:
            return None
        wanted = _strings(missing)
        if not wanted:
            return AdaptResponse(
                dish_id=dish_id,
                substitutions=[],
                skip_ok=[],
                source="llm",
                note="부족한 재료가 없어요.",
            )
        if self.llm is None:
            raise DishLLMError(NOT_CONFIGURED)
        owned = _strings(ingredients)
        user = json.dumps(
            {"dish": dish.name, "missing": wanted, "owned": owned}, ensure_ascii=False
        )
        data = self.llm.complete(ADAPT_SYSTEM, user, "dish_adapt", ADAPT_SCHEMA)
        subs = self.check_adapt(data, wanted, owned)
        return AdaptResponse(
            dish_id=dish_id,
            substitutions=subs,
            skip_ok=[],
            note="" if subs else NO_SUBSTITUTE,
            source="llm",
        )

    @staticmethod
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
            subs.append(Substitution(missing=gap, suggestion=f"{sub}(으)로 대신해요", uses=[sub]))
        return subs


def _valid_video(video: object) -> bool:
    return (
        isinstance(video, dict)
        and isinstance(video.get("video_id"), str)
        and isinstance(video.get("title"), str)
        and isinstance(video.get("thumbnail_url"), str)
    )
