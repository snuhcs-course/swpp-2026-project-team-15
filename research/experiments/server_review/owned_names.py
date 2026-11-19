# AI-generated with Claude Code (Opus 5.5), 2026-11-19; not yet reviewed.
"""Finding 4: for one fridge name, which key ingredients each server rule counts as owned.

card: the closed choices of a suggestion (choices.py); addition: the addition suggestions and
the dish list's match (catalog.py); recipe: the recipe view and revision (recipe_names.py).
Korean names only. Run from server/.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "server"))

from app.dishes.catalog import Catalog  # noqa: E402
from app.dishes.choices import ingredient_vocabulary, owned_vocabulary  # noqa: E402
from app.dishes.recipe_names import RecipeNames  # noqa: E402

PRESETS = ["양파", "대파", "당근", "계란", "밥", "두부", "감자", "김치",
           "소금", "설탕", "간장", "식용유", "참기름", "후추", "다진마늘", "고춧가루", "깨소금",
           "식초", "고추장", "된장"]  # fmt: skip
STORE_NAMES = ["햇반", "즉석밥", "찬밥", "현미밥", "삼겹살", "목살", "대패삼겹살", "닭가슴살",
               "불고기감", "차돌박이", "스팸", "비엔나소시지", "런천미트", "청양고추", "풋고추",
               "슬라이스치즈", "모짜렐라치즈", "배추김치", "묵은지", "달걀", "쪽파", "깐마늘",
               "참치", "참치통조림", "소면", "신라면", "팽이버섯", "파스타", "캔옥수수", "튀김가루"]  # fmt: skip


def main():
    names = RecipeNames.load()
    # As the running server builds it; argv "before" gives the dish list's own equivalents.
    catalog = Catalog.load() if sys.argv[1:] == ["before"] else Catalog.load(names=names)
    rule = None if sys.argv[1:] == ["before"] else names
    vocabulary = ingredient_vocabulary(catalog.all())
    # Seasonings assumed at home are left out: no rule lists them as missing.
    vocabulary = [
        v
        for v in vocabulary
        if names.status(v, set()) != "assumed" and catalog.status(v, set()) != "assumed"
    ]
    rows, counts = (
        [],
        {"names": 0, "card_vs_addition": 0, "card_vs_recipe": 0, "addition_vs_recipe": 0},
    )
    for name in PRESETS + STORE_NAMES:
        card = owned_vocabulary([name], vocabulary, rule)
        held = catalog.owned([name])
        addition = {v for v in vocabulary if catalog.status(v, held) == "owned"}
        owned = names.owned([name])
        recipe = {v for v in vocabulary if names.status(v, owned) == "owned"}
        counts["names"] += 1
        for a, b, k in (
            (card, addition, "card_vs_addition"),
            (card, recipe, "card_vs_recipe"),
            (addition, recipe, "addition_vs_recipe"),
        ):
            counts[k] += a != b
        if not (card == addition == recipe):
            rows.append(
                {
                    "name": name,
                    "card": sorted(card),
                    "addition": sorted(addition),
                    "recipe": sorted(recipe),
                }
            )
    print(json.dumps({"counts": counts, "disagreements": rows}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
