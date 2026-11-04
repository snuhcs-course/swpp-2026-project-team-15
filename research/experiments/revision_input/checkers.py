# AI-generated with Claude Code (Sonnet 5.5), 2026-11-03; reviewed by Jaehyuk Choi.
"""Independent checkers for revision outputs.

They do not share code with the production post-check in ``recipe_revision.compact``: they decide
from ingredient ids, names found in the prose and the recipe structure, so a delivered answer can be
judged without trusting the check that already let it through. All functions are pure; they take
the parsed model result and source records. Known-answer tests: tests/experiments/revision_input.
"""

from __future__ import annotations

import re
from collections import defaultdict

WATER_ID = 204
TYPE = {"3060001": "main", "3060002": "secondary", "3060003": "seasoning"}
PRIORITY = {"main": 0, "secondary": 1, "seasoning": 2}


# ---------------------------------------------------------------- source structure
def resolved_types(recipe) -> dict[int, str | None]:
    """ingredient_id -> main/secondary/seasoning by the server rule (main first)."""
    labels: dict[int, set[str]] = defaultdict(set)
    for row in recipe.ingredients:
        t = TYPE.get(row.ingredient_type_code)
        if t:
            labels[row.ingredient_id].add(t)
        else:
            labels[row.ingredient_id]
    return {
        i: (min(s, key=PRIORITY.__getitem__) if s else None) for i, s in labels.items()
    }


def source_ids(recipe) -> set[int]:
    return {r.ingredient_id for r in recipe.ingredients}


def allowed_ids(
    recipe, inventory_ids, policy: str, assumed_ids=frozenset()
) -> set[int]:
    """Ingredient ids a revision may contain.

    strict  : inventory (+ water)
    staples : strict + the recipe's own seasoning-labelled ingredients
    list    : strict + the assumed seasonings (``assumed_ids``, from the seasoning list) that the
              recipe itself contains; this is what the server's ``list`` mode makes available
    """
    allowed = set(inventory_ids) | {WATER_ID}
    if policy == "strict":
        return allowed
    if policy == "staples":
        types = resolved_types(recipe)
        return allowed | {i for i, t in types.items() if t == "seasoning"}
    if policy == "list":
        return allowed | (set(assumed_ids) & source_ids(recipe))
    raise ValueError(policy)


# ---------------------------------------------------------------- expected verdict
def name_defining_ids(recipe) -> set[int]:
    """Ingredients whose normalized or as-written name (>= 2 chars) occurs in the dish name."""
    out = set()
    for row in recipe.ingredients:
        for term in (row.name, row.original_name):
            if term and len(term) >= 2 and term in recipe.name:
                out.add(row.ingredient_id)
    return out


def expected_verdict(recipe, allowed: set[int]) -> tuple[str, dict]:
    """Rule-based expectation from recipe structure only.

    refuse    : an ingredient named in the dish name is unavailable (identity lost)
    ambiguous : no name-defining ingredient missing, but a main-labelled one is
    revise    : only secondary/seasoning ingredients (or nothing) are missing
    Water is never counted. Limits: lexical name test; source labels are noisy.
    """
    types = resolved_types(recipe)
    missing = {i for i in source_ids(recipe) if i not in allowed and i != WATER_ID}
    ident = name_defining_ids(recipe) & missing
    main = {i for i in missing if types.get(i) == "main"}
    info = {
        "missing": sorted(missing),
        "name_defining_missing": sorted(ident),
        "main_missing": sorted(main),
    }
    if ident:
        return "refuse", info
    if main:
        return "ambiguous", info
    return "revise", info


# ---------------------------------------------------------------- name-level matching
class NameIndex:
    """Alias table: catalog names, as-written names from the DB, and exact synonym groups.

    ``resolve(text)`` returns [(term, ids)] using longest-match-first, non-overlapping spans.
    Terms shorter than 2 characters are ignored (too many collisions: 물, 무, 파, 김, 밥).
    """

    SYNONYMS = (
        frozenset({"계란", "달걀"}),
        frozenset({"참치", "참치캔", "참치통조림"}),
        frozenset({"김치", "배추김치"}),
        frozenset({"후추", "후춧가루"}),
        frozenset({"소고기", "쇠고기"}),
    )
    # Generic cooking words that are also catalog names but are not an ingredient claim here.
    STOP = frozenset({"양념", "양념장", "국물", "기름"})

    def __init__(self, names: dict[int, str], recipes=None, stop=None):
        self.alias: dict[str, set[int]] = defaultdict(set)
        for i, n in names.items():
            self.alias[n].add(i)
        if recipes:
            for rec in recipes.values():
                for r in rec.ingredients:
                    if r.original_name:
                        self.alias[r.original_name].add(r.ingredient_id)
        for group in self.SYNONYMS:
            ids = set().union(*(self.alias.get(g, set()) for g in group))
            for g in group:
                self.alias[g] |= ids
        stop = self.STOP if stop is None else stop
        self.terms = sorted(
            (t for t in self.alias if len(t) >= 2 and t not in stop),
            key=lambda t: (-len(t), t),
        )
        self._re = (
            re.compile("|".join(re.escape(t) for t in self.terms))
            if self.terms
            else None
        )

    def resolve(self, text: str) -> list[tuple[str, frozenset[int]]]:
        if not text or not self._re:
            return []
        return [
            (m.group(), frozenset(self.alias[m.group()]))
            for m in self._re.finditer(text)
        ]


def _step_text(result) -> str:
    rec = result.get("revised_recipe") or {}
    parts = []
    for s in rec.get("steps", []):
        parts.append(s.get("instruction") or "")
        if s.get("tip"):
            parts.append(s["tip"])
    return "\n".join(parts)


def source_text(recipe) -> str:
    parts = [s.instruction for s in recipe.steps] + [
        s.tip for s in recipe.steps if s.tip
    ]
    return "\n".join(parts)


def id_level(result, allowed: set[int], names: dict[int, str]) -> dict:
    """Ingredient-list checks on a parsed *revised* result."""
    rec = result.get("revised_recipe")
    if not result.get("can_revise") or not rec:
        return {"applicable": False}
    ids = [i["ingredient_id"] for i in rec["ingredients"]]
    bad = sorted({i for i in ids if i not in allowed})
    unknown = sorted({i for i in ids if i not in names})
    name_mismatch = sorted(
        {
            i["ingredient_id"]
            for i in rec["ingredients"]
            if i["ingredient_id"] in names
            and i["name"].strip() != names[i["ingredient_id"]]
        }
    )
    return {
        "applicable": True,
        "violating_ids": bad,
        "unknown_ids": unknown,
        "name_mismatch_ids": name_mismatch,
        "duplicate_ids": len(ids) - len(set(ids)),
    }


def step_level(result, recipe, allowed: set[int], index: NameIndex) -> dict:
    """Name-level check of revised step/tip text.

    stale_missing : a source ingredient that is unavailable under the policy is still mentioned
                    (precise: restricted to the recipe's own ingredient rows).
    novel         : an unavailable ingredient that neither the source ingredient rows nor the source
                    step text mention, i.e. an ingredient the model introduced in prose.
    Mentions of unavailable ingredients that the *source* text already contains but does not list
    (generic words like 채소/소스, or unlisted seasonings) are not counted: in unmodified source
    recipes that pattern occurs in 79% of recipes, so counting it would be noise, not model error.
    """
    if not result.get("can_revise") or not result.get("revised_recipe"):
        return {"applicable": False}
    src_ids = source_ids(recipe)
    missing = {i for i in src_ids if i not in allowed and i != WATER_ID}
    src_mentioned = set(src_ids)
    for _, ids in index.resolve(source_text(recipe)):
        src_mentioned |= ids
    stale, novel = set(), set()
    for term, ids in index.resolve(_step_text(result)):
        if ids & allowed:
            continue
        if ids & missing:
            stale.add(term)
        elif not (ids & src_mentioned):
            novel.add(term)
    return {
        "applicable": True,
        "stale_missing_terms": sorted(stale),
        "novel_terms": sorted(novel),
    }


# ---------------------------------------------------------------- structure / consistency
def structure(result, recipe) -> dict:
    """Consistency of verdict, recipe and changes beyond what the wire schema enforces."""
    out = {"issues": []}
    if result is None:
        return out
    row_ids = {r.recipe_ingredient_id: r.ingredient_id for r in recipe.ingredients}
    step_ids = {s.step_id for s in recipe.steps}
    bad_ref = [
        c
        for c in result["changes"]
        if any(x not in row_ids for x in c["source_ingredient_row_ids"])
        or any(x not in step_ids for x in c["source_step_ids"])
    ]
    if bad_ref:
        out["issues"].append("invalid_reference")
    if not result["can_revise"]:
        return out
    rec = result["revised_recipe"]
    src = source_ids(recipe)
    new = {i["ingredient_id"] for i in rec["ingredients"]}
    removed = src - new
    added = new - src
    referenced = {
        row_ids[x]
        for c in result["changes"]
        for x in c["source_ingredient_row_ids"]
        if x in row_ids
    }
    kinds = [c["kind"] for c in result["changes"]]
    if removed - referenced:
        out["issues"].append("undeclared_removal")
    if added and "substitution" not in kinds:
        out["issues"].append("addition_without_substitution")
    same_steps = [s["instruction"] for s in rec["steps"]] == [
        s.instruction for s in recipe.steps
    ]
    if (removed or added) and "step" not in kinds and same_steps:
        out["issues"].append("ingredient_change_without_step_change")
    nums = [s["step_number"] for s in rec["steps"]]
    if nums != list(range(1, len(nums) + 1)):
        out["issues"].append("step_numbers_not_sequential")
    if not result["changes"] and (removed or added):
        out["issues"].append("changes_empty_but_recipe_differs")
    out.update(removed=sorted(removed), added=sorted(added))
    return out


# ---------------------------------------------------------------- safety
RAW_RISK = (
    "돼지고기",
    "닭",
    "소고기",
    "쇠고기",
    "다진고기",
    "계란",
    "달걀",
    "삼겹살",
    "햄버그",
    "갈비",
    "불고기",
    "오리",
    "소시지",
    "베이컨",
)
HEAT = (
    "익",
    "끓",
    "볶",
    "굽",
    "구운",
    "구워",
    "구이",
    "삶",
    "튀",
    "찌",
    "찐",
    "데치",
    "데친",
    "가열",
    "부치",
    "부친",
    "부쳐",
    "지지",
    "지진",
    "졸",
    "조리",
    "오븐",
    "프라이팬",
    "노릇",
    "반숙",
    "지단",
    "달군",
    "달구",
)
DONENESS = (
    "반숙",
    "완전히 익",
    "속까지",
    "충분히 익",
    "잘 익",
    "푹 익",
    "익을 때까지",
    "익혀",
    "투명해",
)


def raw_risk_ids(recipe, names) -> set[int]:
    return {
        r.ingredient_id
        for r in recipe.ingredients
        if any(k in names.get(r.ingredient_id, "") for k in RAW_RISK)
    }


def safety(result, recipe, names) -> dict:
    """Heat-step retention for revised recipes that still contain raw meat/poultry/egg.

    retained = the revised steps contain a heat-treatment term (required only if the source steps
    do) AND, when the source steps contain a doneness cue, at least one doneness cue remains.
    Deliberately lenient (lexical); it detects removal of cooking steps, not subtle undercooking
    advice.
    """
    if not result.get("can_revise") or not result.get("revised_recipe"):
        return {"applicable": False}
    rec = result["revised_recipe"]
    risk = raw_risk_ids(recipe, names) & {
        i["ingredient_id"] for i in rec["ingredients"]
    }
    if not risk:
        return {"applicable": False}
    text = _step_text(result)
    heat_needed = any(k in source_text(recipe) for k in HEAT)
    heat = (not heat_needed) or any(k in text for k in HEAT)
    src_cue = any(k in source_text(recipe) for k in DONENESS)
    cue = (not src_cue) or any(k in text for k in DONENESS)
    return {
        "applicable": True,
        "heat": heat,
        "cue_needed": src_cue,
        "cue": cue,
        "retained": heat and cue,
    }
