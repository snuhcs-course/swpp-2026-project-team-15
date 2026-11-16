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

MAX_REASON = 60
_DIGITS = re.compile(r"\d")

SUGGEST_SYSTEM = (
    "You help a Korean student living alone decide what to cook from the ingredients they have. "
    "Choose ONLY from the candidate dishes (use their ids exactly). Choose every dish that can "
    "reasonably be made from the owned ingredients, best first. If only a few fit, return only "
    "those; if none fit, return an empty list. Never add dishes just to fill the list. Prefer "
    "dishes that use most of the owned ingredients and are realistic for one person. Give a "
    "short Korean reason "
    "(under 40 characters) and up to 3 YouTube search keyword variants that each contain the "
    "dish name. Never invent dishes, ingredients or quantities."
)
NO_SUBSTITUTE = "냉장고 재료로는 마땅한 대체를 찾지 못했어요."
ADAPT_SYSTEM = (
    "A student wants to cook a dish but lacks some ingredients. For each missing ingredient, "
    "choose ONE of its allowed_uses (copy the ingredient names exactly into 'uses') and write a "
    "short Korean suggestion for it (under 40 characters). Never use anything that is not in "
    "allowed_uses. No quantities, no cooking steps. Leave skip_ok empty."
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
    def suggest(self, ingredients: list[str]) -> SuggestResponse:
        ranked = self.catalog.rank(ingredients)
        if self.llm is not None and ranked:
            try:
                picked = self._ask_suggest(ingredients, ranked)
            except DishLLMError:
                picked = None
            if picked is not None:  # an empty answer is an answer: nothing fits
                return SuggestResponse(
                    source="llm", dishes=[self._dish(m, r, k) for m, r, k in picked]
                )
        return SuggestResponse(
            source="rules",
            dishes=[self._dish(m, self._rules_reason(m), []) for m in ranked],
        )

    def _ask_suggest(self, ingredients, candidates: list[Match]):
        by_id = {m.dish.id: m for m in candidates}
        listing = [
            {"id": m.dish.id, "name": m.dish.name, "ingredients": list(m.dish.key_ingredients)}
            for m in candidates
        ]
        user = json.dumps({"owned": ingredients, "candidates": listing}, ensure_ascii=False)
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
        """None when the dish is unknown. Raises DishLLMError when the model call fails.

        Only substitutions the server's table allows (and the user can make with what they own)
        are ever returned; the model only chooses among them and words the suggestion."""
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
        options = {m: o for m in match.missing if (o := self.catalog.options(m, owned))}
        if self.llm is None or not options:
            return self._adapt_rules(dish_id, match, options)
        user = json.dumps(
            {
                "dish": dish.name,
                "missing": [
                    {"name": m, "allowed_uses": [list(o) for o in opts]}
                    for m, opts in options.items()
                ],
            },
            ensure_ascii=False,
        )
        data = self.llm.complete(ADAPT_SYSTEM, user, "dish_adapt", ADAPT_SCHEMA)
        return self._check_adapt(dish_id, match, owned, options, data)

    def _check_adapt(self, dish_id, match: Match, owned, options, data: dict) -> AdaptResponse:
        subs: list[Substitution] = []
        used: set[str] = set()
        for item in (
            data.get("substitutions", []) if isinstance(data.get("substitutions"), list) else []
        ):
            if not isinstance(item, dict):
                continue
            missing, text, uses = item.get("missing"), item.get("suggestion"), item.get("uses")
            if missing not in options or missing in used:
                continue
            if not isinstance(text, str) or not text.strip() or _DIGITS.search(text):
                continue
            if not isinstance(uses, list) or not uses or not all(isinstance(u, str) for u in uses):
                continue
            if not self.catalog.accepts(missing, uses, owned):
                continue
            used.add(missing)
            subs.append(Substitution(missing=missing, suggestion=text.strip()[:60], uses=uses))
        for missing, opts in options.items():  # an approved option the model skipped is still true
            if missing not in used:
                subs.append(self._rule_substitution(missing, opts[0]))
        skip = [m for m in match.missing if m in match.dish.optional and m not in options]
        note = data.get("note", "")
        note = note.strip()[:80] if isinstance(note, str) and not _DIGITS.search(note) else ""
        if not subs and not skip:
            note = NO_SUBSTITUTE
        return AdaptResponse(
            dish_id=dish_id, substitutions=subs, skip_ok=skip, note=note, source="llm"
        )

    @staticmethod
    def _rule_substitution(missing: str, option: tuple[str, ...]) -> Substitution:
        return Substitution(
            missing=missing, suggestion=f"{'+'.join(option)}(으)로 대신해요", uses=list(option)
        )

    def _adapt_rules(self, dish_id: str, match: Match, options) -> AdaptResponse:
        subs = [self._rule_substitution(m, opts[0]) for m, opts in options.items()]
        skip = [m for m in match.missing if m in match.dish.optional and m not in options]
        return AdaptResponse(
            dish_id=dish_id,
            substitutions=subs,
            skip_ok=skip,
            note="" if subs or skip else NO_SUBSTITUTE,
            source="rules",
        )
