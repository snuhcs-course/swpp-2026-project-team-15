# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""Suggest and adapt dishes. The model only chooses from the closed list; have/missing are
recomputed here, and every model answer is checked before it is returned."""

import json
import re

from app.dishes.catalog import Catalog, Match
from app.dishes.llm import DishLLM, DishLLMError
from app.dishes.schemas import (
    AdaptResponse,
    Substitution,
    SuggestedDish,
    SuggestResponse,
    Video,
)
from app.dishes.youtube import VideoCache, search_url

MAX_CANDIDATES = 40
MAX_REASON = 60
_DIGITS = re.compile(r"\d")

SUGGEST_SYSTEM = (
    "You help a Korean student living alone decide what to cook from the ingredients they have. "
    "Choose ONLY from the candidate dishes (use their ids exactly). Prefer dishes that use most "
    "of the owned ingredients and are realistic for one person. Give a short Korean reason "
    "(under 40 characters) and up to 3 YouTube search keyword variants that each contain the "
    "dish name. Never invent dishes, ingredients or quantities."
)
ADAPT_SYSTEM = (
    "A student wants to cook a dish but lacks some ingredients. For each missing ingredient, "
    "propose a short Korean substitute using ONLY ingredients from the owned list or the listed "
    "basic seasonings, or say it can be skipped. No quantities, no cooking steps. "
    "Keep each suggestion under 40 characters."
)

SUGGEST_SCHEMA = {
    "type": "object",
    "properties": {
        "dishes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "reason": {"type": "string"},
                    "keywords": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["id", "reason", "keywords"],
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
                    "suggestion": {"type": "string"},
                    "uses": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["missing", "suggestion", "uses"],
                "additionalProperties": False,
            },
        },
        "skip_ok": {"type": "array", "items": {"type": "string"}},
        "note": {"type": "string"},
    },
    "required": ["substitutions", "skip_ok", "note"],
    "additionalProperties": False,
}


class DishService:
    def __init__(
        self, catalog: Catalog, llm: DishLLM | None = None, cache: VideoCache | None = None
    ):
        self.catalog = catalog
        self.llm = llm
        self.cache = cache or VideoCache(None)

    # -- suggest -----------------------------------------------------------------------------
    def suggest(self, ingredients: list[str], limit: int) -> SuggestResponse:
        ranked = self.catalog.rank(ingredients)
        picked: list[tuple[Match, str, list[str]]] = []
        source = "rules"
        if self.llm is not None and ranked:
            try:
                picked = self._ask_suggest(ingredients, ranked[:MAX_CANDIDATES], limit)
            except DishLLMError:
                picked = []
            if picked:
                source = "llm"
        seen = {m.dish.id for m, _, _ in picked}
        for match in ranked:  # top up (or fully replace) with the deterministic ranking
            if len(picked) >= limit:
                break
            if match.dish.id not in seen:
                picked.append((match, self._rules_reason(match), []))
        return SuggestResponse(
            source=source, dishes=[self._dish(m, r, k) for m, r, k in picked[:limit]]
        )

    def _ask_suggest(self, ingredients, candidates: list[Match], limit: int):
        by_id = {m.dish.id: m for m in candidates}
        listing = [
            {"id": m.dish.id, "name": m.dish.name, "ingredients": list(m.dish.key_ingredients)}
            for m in candidates
        ]
        user = json.dumps(
            {"owned": ingredients, "limit": limit, "candidates": listing}, ensure_ascii=False
        )
        data = self.llm.complete(SUGGEST_SYSTEM, user, "dish_choice", SUGGEST_SCHEMA)
        out, seen = [], set()
        for item in data.get("dishes", []) if isinstance(data.get("dishes"), list) else []:
            if not isinstance(item, dict):
                continue
            match = by_id.get(item.get("id"))
            if match is None or match.dish.id in seen:
                continue
            seen.add(match.dish.id)
            reason = str(item.get("reason", "")).strip()[:MAX_REASON]
            out.append((match, reason or self._rules_reason(match), self._keywords(match, item)))
        return out

    @staticmethod
    def _keywords(match: Match, item: dict) -> list[str]:
        names = (match.dish.name, *match.dish.aliases)
        raw = item.get("keywords", [])
        words = [w.strip() for w in raw if isinstance(w, str)] if isinstance(raw, list) else []
        good = []
        for word in words:
            if word and len(word) <= 40 and any(n in word for n in names) and word not in good:
                good.append(word)
        return good[:3]

    @staticmethod
    def _rules_reason(match: Match) -> str:
        total = len(match.have) + len(match.missing)
        return f"필요한 재료 {total}개 중 {len(match.have)}개 보유"

    def _dish(self, match: Match, reason: str, keywords: list[str]) -> SuggestedDish:
        dish = match.dish
        videos = [Video(**v) for v in self.cache.get(dish.id) if self._valid_video(v)]
        return SuggestedDish(
            id=dish.id,
            name=dish.name,
            category=dish.category,
            have=list(match.have),
            missing=list(match.missing),
            reason=reason,
            keywords=keywords or [f"{dish.name} 레시피"],
            videos=videos,
            search_url=search_url(dish.name),
        )

    @staticmethod
    def _valid_video(video: object) -> bool:
        return (
            isinstance(video, dict)
            and isinstance(video.get("video_id"), str)
            and isinstance(video.get("title"), str)
            and isinstance(video.get("thumbnail_url"), str)
        )

    # -- adapt -------------------------------------------------------------------------------
    def adapt(self, dish_id: str, ingredients: list[str]) -> AdaptResponse | None:
        """None when the dish is unknown. Raises DishLLMError when the model call fails."""
        dish = self.catalog.get(dish_id)
        if dish is None:
            return None
        owned = self.catalog.owned(ingredients)
        match = self.catalog.match(dish, owned)
        if not match.missing:
            return AdaptResponse(
                dish_id=dish_id,
                substitutions=[],
                skip_ok=[],
                source="rules",
                note="부족한 재료가 없어요.",
            )
        if self.llm is None:
            return self._adapt_rules(dish_id, match, owned)
        user = json.dumps(
            {
                "dish": dish.name,
                "missing": list(match.missing),
                "owned": sorted({n.strip() for n in ingredients if n.strip()}),
                "basic_seasonings": sorted(self.catalog.staples),
            },
            ensure_ascii=False,
        )
        data = self.llm.complete(ADAPT_SYSTEM, user, "dish_adapt", ADAPT_SCHEMA)
        return self._check_adapt(dish_id, match, owned, data)

    def _check_adapt(self, dish_id: str, match: Match, owned: set[str], data: dict):
        subs: list[Substitution] = []
        used: set[str] = set()
        for item in (
            data.get("substitutions", []) if isinstance(data.get("substitutions"), list) else []
        ):
            if not isinstance(item, dict):
                continue
            missing, text, uses = item.get("missing"), item.get("suggestion"), item.get("uses")
            if missing not in match.missing or missing in used:
                continue
            if not isinstance(text, str) or not text.strip() or _DIGITS.search(text):
                continue
            if not isinstance(uses, list) or not uses or not all(isinstance(u, str) for u in uses):
                continue
            if not all(self.catalog.usable(u, owned) for u in uses):
                continue
            used.add(missing)
            subs.append(Substitution(missing=missing, suggestion=text.strip()[:60], uses=uses))
        raw_skip = data.get("skip_ok", [])
        skip = [
            m
            for m in match.missing
            if isinstance(raw_skip, list) and m in raw_skip and m not in used
        ]
        note = data.get("note", "")
        note = note.strip()[:80] if isinstance(note, str) and not _DIGITS.search(note) else ""
        return AdaptResponse(
            dish_id=dish_id, substitutions=subs, skip_ok=skip, note=note, source="llm"
        )

    def _adapt_rules(self, dish_id: str, match: Match, owned: set[str]) -> AdaptResponse:
        subs, skip = [], []
        for missing in match.missing:
            options = [
                s
                for s in self.catalog.substitutes.get(missing, ())
                if self.catalog.usable(s, owned)
            ]
            if options:
                subs.append(
                    Substitution(
                        missing=missing,
                        suggestion=f"{options[0]}(으)로 대신해요",
                        uses=[options[0]],
                    )
                )
            elif missing in match.dish.optional:
                skip.append(missing)
        return AdaptResponse(
            dish_id=dish_id,
            substitutions=subs,
            skip_ok=skip,
            note="" if subs or skip else "대신할 수 있는 재료를 찾지 못했어요.",
            source="rules",
        )
