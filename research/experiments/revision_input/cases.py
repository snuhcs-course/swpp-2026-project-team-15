# AI-generated with Claude Code (Sonnet 5.5), 2026-11-03; human review pending.
"""Revision cases: (recipe, single-person pantry) pairs.

A case is a recipe id plus the ingredient ids in the pantry (water is appended at run time, as the
server does). The committed manifests ``cases/test.json`` and ``cases/heldout.json`` hold ids only.
``build`` regenerates a set of the same kind from a local recipe database:

  S1 complete   nothing missing
  S2 seasoning  1-3 seasoning-labelled ingredients missing, all else present
  S3 minor      1-2 non-seasoning, non-dish-name ingredients missing
  S4 identity   exactly one ingredient named in the dish name missing
  S5 multi      2-3 non-seasoning ingredients missing (half include a dish-name ingredient)

The pantry is the present source ingredients plus 3-6 unrelated fridge items. Seasonings are
present with probability 0.3 (S1: always, S2: all but the omitted ones). Every case passes the
server's filtering policy with seasonings ignored (``GENERATION_POLICY``).
"""

import json
import random
from pathlib import Path

from app.recipes.policy import RecommendationPolicy
from recipe_revision.seasoning import ASSUME_ALL

from . import checkers as ck

FRIDGE_POOL = {  # ingredient_id -> sampling weight (single-person Korean fridge)
    32: 4,
    345: 4,
    129: 4,
    147: 3,
    70: 3,
    334: 2,
    12: 2,
    122: 2,
    485: 2,
    349: 2,
    539: 2,
    443: 2,
    384: 2,
    98: 1,
    523: 1,
    518: 1,
    223: 3,
    169: 3,
    454: 1,
    141: 2,
    283: 1,
    368: 1,
    227: 1,
    307: 1,
    297: 1,
    198: 1,
    188: 1,
    286: 1,
    514: 1,
    495: 1,
    341: 1,
    262: 1,
    76: 1,
    236: 1,
    35: 1,
    232: 1,
    470: 1,
    233: 1,
    312: 1,
    213: 1,
    265: 1,
    370: 1,
    211: 1,
    432: 1,
    47: 1,
    144: 1,
}
CATEGORIES = [
    "밥",
    "나물/생채/샐러드",
    "만두/면류",
    "밑반찬/김치",
    "국",
    "볶음",
    "찌개/전골/스튜",
    "구이",
    "찜",
    "부침",
    "튀김/커틀릿",
    "조림",
]
STRATA_TEST = {"S1": 8, "S2": 16, "S3": 16, "S4": 20, "S5": 12}
STRATA_DEV = {"S1": 3, "S2": 6, "S3": 6, "S4": 9, "S5": 6}
STRATA_HELDOUT = {"S1": 6, "S2": 14, "S3": 14, "S4": 16, "S5": 10}
GENERATOR_VERSION = "1"
# The committed sets were drawn while every seasoning-labelled ingredient was ignored by the
# filtering counts; this policy reproduces that, independent of the current seasoning list.
GENERATION_POLICY = RecommendationPolicy(seasonings=ASSUME_ALL)
MANIFESTS = {"test": "cases/test.json", "heldout": "cases/heldout.json"}


def _groups(names):
    out = []
    for g in ck.NameIndex.SYNONYMS:
        ids = {i for i, n in names.items() if n in g}
        out.append(ids)
    return out


def build(seed: int, counts: dict, exclude: set, recipes, names, set_label: str) -> list[dict]:
    rng = random.Random(seed)
    syn_groups = _groups(names)
    by_cat = {
        c: sorted(i for i, r in recipes.items() if r.category == c and i not in exclude)
        for c in CATEGORIES
    }
    used = set(exclude)
    cases = []
    for stratum, n in counts.items():
        made = 0
        order = list(CATEGORIES)
        rng.shuffle(order)
        attempts = 0
        while made < n:
            attempts += 1
            if attempts > 4000:
                raise RuntimeError(f"cannot fill {stratum}")
            cat = order[(made + attempts // 60) % len(order)]
            pool = [i for i in by_cat[cat] if i not in used]
            if not pool:
                continue
            rid = rng.choice(pool)
            rec = recipes[rid]
            types = ck.resolved_types(rec)
            ids = [
                i
                for i in dict.fromkeys(r.ingredient_id for r in rec.ingredients)
                if i != ck.WATER_ID
            ]
            ident = sorted(ck.name_defining_ids(rec) - {ck.WATER_ID})
            seas = [i for i in ids if types[i] == "seasoning" and i not in ident]
            sec = [i for i in ids if types[i] in ("secondary", None) and i not in ident]
            main_ni = [i for i in ids if types[i] == "main" and i not in ident]
            nonseas_ni = [i for i in ids if types[i] != "seasoning" and i not in ident]
            absent: set[int] = set()
            season_p = 0.3
            if stratum == "S1":
                season_p = 1.0
            elif stratum == "S2":
                if len(seas) < 1:
                    continue
                k = min(len(seas), rng.choice([1, 2, 3]))
                absent = set(rng.sample(seas, k))
                season_p = 1.0  # the others are present: isolates the seasoning-only effect
            elif stratum == "S3":
                if rng.random() < 0.25 and main_ni and len(ids) > 3:
                    absent = {rng.choice(main_ni)}
                elif sec:
                    absent = set(rng.sample(sec, min(len(sec), rng.choice([1, 2]))))
                else:
                    continue
            elif stratum == "S4":
                if not ident:
                    continue
                absent = {rng.choice(ident)}
            elif stratum == "S5":
                if rng.random() < 0.5 and ident and nonseas_ni:
                    absent = {rng.choice(ident)} | set(
                        rng.sample(nonseas_ni, min(len(nonseas_ni), rng.choice([1, 2])))
                    )
                elif len(nonseas_ni) >= 3:
                    absent = set(rng.sample(nonseas_ni, rng.choice([2, 3])))
                else:
                    continue
            present = [
                i
                for i in ids
                if i not in absent
                and (types[i] != "seasoning" or i in ident or rng.random() < season_p)
            ]
            if stratum != "S2" and stratum != "S1":
                pass
            # seasonings that were dropped by chance (not designated) become "missing" too
            blocked = set(absent)
            for g in syn_groups:
                if g & absent:
                    blocked |= g
            extras = [i for i in FRIDGE_POOL if i not in ids and i not in blocked]
            weights = [FRIDGE_POOL[i] for i in extras]
            want = rng.randint(3, 6)
            chosen = []
            while len(chosen) < want and extras:
                pick = rng.choices(range(len(extras)), weights=weights)[0]
                chosen.append(extras.pop(pick))
                weights.pop(pick)
            inventory = present + chosen
            rng.shuffle(inventory)
            if not (inventory and ck.WATER_ID not in inventory):
                continue
            available = frozenset(inventory) | {ck.WATER_ID}
            metrics = GENERATION_POLICY.metrics(rec, available)
            if not GENERATION_POLICY.accepts(metrics):
                continue
            strict_missing = sorted(set(ids) - set(inventory))
            cases.append(
                {
                    "case_id": f"{set_label}-{len(cases) + 1:03d}",
                    "recipe_id": rid,
                    "stratum": stratum,
                    "category": rec.category,
                    "inventory_ids": inventory,
                    "designated_absent": sorted(absent),
                    "strict_missing": strict_missing,
                }
            )
            used.add(rid)
            made += 1
    return cases


def load_cases(name: str, root: Path | None = None) -> list[dict]:
    """Cases of a committed manifest (``test`` or ``heldout``)."""
    path = (root or Path(__file__).parent) / MANIFESTS[name]
    return json.loads(path.read_text(encoding="utf-8"))["cases"]


def regenerate_test_set(recipes, names) -> list[dict]:
    """Rebuild ``cases/test.json`` from a local database (for checking the generator).

    The test set excludes the recipes of the fixed revision matrix and of a small development set
    drawn with seed 11.
    """
    from experiments.revision.cases import ALL_RECIPES

    fixed = {rid for rid, _ in ALL_RECIPES}
    dev = build(11, STRATA_DEV, fixed, recipes, names, "DG")
    used = fixed | {c["recipe_id"] for c in dev}
    return build(20261102, STRATA_TEST, used, recipes, names, "T")
