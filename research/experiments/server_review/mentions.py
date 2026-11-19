# AI-generated with Claude Code (Opus 5.5), 2026-11-19; not yet reviewed.
"""Finding 1: steps or tips that still name a removed ingredient, current check vs a candidate.

Replays every model answer recorded in revision round 3 through the server's check at HEAD and
through a candidate mention test; no model call. Run from server/:
    uv run python -m experiments.server_review.mentions  (with research/ on the path)
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "server"))

from app.dishes.recipe_names import RecipeNames  # noqa: E402
from app.dishes.revision_check import (  # noqa: E402
    RefusalNeeded,
    Violation,
    check,
    check_main_kept,
    check_short_mentions,
)
from app.dishes.schemas import SourceRecipe  # noqa: E402
from app.dishes.synonyms import with_synonyms  # noqa: E402

DATA = Path.home() / "PRJ/MyLittleChef/artifacts/dish-recipes"
RUN_DIR = ROOT / "data/dish-revision"
# Each run with the recipe file it was made from: N3/N3a and the first N1 run before the
# vertical-video rebuild, the second N1 run after it (before the 참치샐러드 row rename).
RUNS = [
    (RUN_DIR / "round3-N3-N3a-20261119T021247Z.json", DATA / "recipes.pre-shorts.json"),
    (RUN_DIR / "round3-N1-20261119T032459Z.json", DATA / "recipes.pre-shorts.json"),
    (RUN_DIR / "round3-N1-20261119T032656Z.json", DATA / "recipes.pre-salad-row.json"),
]
# Particles and endings that may follow a noun in a recipe step (longest first).
PARTICLES = ("으로", "이랑", "에서", "까지", "부터", "하고", "처럼", "보다", "에다",
             "을", "를", "이", "가", "은", "는", "과", "와", "도", "에", "만", "의", "로", "랑")


def key(text: str) -> str:
    return text.strip().replace(" ", "")


def mask(text: str, kept: list[str]) -> str:
    """The text with every kept name blanked out, longest first, so 고추장 hides its 고추."""
    out = text
    for name in sorted(kept, key=len, reverse=True):
        if len(name) >= 2:
            out = out.replace(name, "□" * len(name))
    return out


def names_in(text: str, form: str) -> bool:
    """A form of two or more characters anywhere; one character as a word of its own, optionally
    followed by a particle."""
    if len(form) >= 2:
        return form in text
    tail = "|".join(PARTICLES)
    return re.search(rf"(?<![가-힣]){re.escape(form)}(?:{tail})?(?![가-힣])", text) is not None


def candidate_hits(gone: list[str], kept: list[str], texts: list[str]) -> list[tuple[str, str, str]]:
    hits = []
    kept_forms = sorted({f for k in kept for f in with_synonyms([k])}, key=len, reverse=True)
    for name in gone:
        for form in sorted(with_synonyms([name])):
            for t in texts:
                if names_in(mask(t, kept_forms), form):
                    hits.append((name, form, t))
                    break
            else:
                continue
            break
    return hits


def kind(name: str, form: str, kept: list[str]) -> str:
    if form != name:
        return "synonym"
    if len(name) == 1:
        return "one_character"
    if any(name in k for k in kept):
        return "inside_kept_name"
    return "plain"


def main() -> None:
    names = RecipeNames.load()
    totals: Counter = Counter()
    examples = []
    for path, recipe_file in RUNS:
        raw = json.loads(recipe_file.read_text())["recipes"]
        recipes = {k: SourceRecipe.model_validate(v) for k, v in raw.items()}
        data = json.loads(Path(path).read_text())
        for variant, cases in data.items():
            if not isinstance(cases, list):
                continue
            for case in cases:
                recipe = recipes.get(case["dish_id"])
                for answer in case.get("answers") or []:
                    if recipe is None or not isinstance(answer, dict) or answer.get("can_revise") is False:
                        continue
                    totals["answers"] += 1
                    owned = names.owned(case["ingredients"])
                    status = [names.status(r.name, owned) for r in recipe.ingredients]
                    try:
                        revised, changes = check(answer, recipe, status, names, case["ingredients"])
                        check_main_kept(recipe, status, revised, changes)
                        check_short_mentions(recipe, status, revised)
                        verdict = "pass"
                    except RefusalNeeded:
                        verdict = "refusal"
                    except Violation as v:
                        verdict = v.code
                    except Exception as exc:  # noqa: BLE001 - finding 5 shows up here
                        verdict = f"crash:{type(exc).__name__}"
                    totals[f"current:{verdict}"] += 1
                    if verdict != "pass":
                        continue
                    kept = [key(r.name) for r in revised.ingredients]
                    gone = [key(r.name) for r, s in zip(recipe.ingredients, status) if s == "unavailable"
                            and not (with_synonyms([key(r.name)]) & set(kept))]
                    texts = [s.text for s in revised.steps] + revised.tips
                    hits = candidate_hits(gone, kept, texts)
                    if hits:
                        totals["candidate_flags_a_passed_answer"] += 1
                        for name, form, text in hits:
                            k = kind(name, form, kept)
                            totals[f"kind:{k}"] += 1
                            examples.append({"file": Path(path).name, "variant": variant,
                                             "dish_id": case["dish_id"], "removed": name, "form": form,
                                             "kind": k, "text": text})
    out = {"answers_replayed": totals.pop("answers"), "counts": dict(sorted(totals.items())),
           "examples": examples}
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
