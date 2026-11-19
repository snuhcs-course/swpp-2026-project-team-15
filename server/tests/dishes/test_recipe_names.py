# AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""Recipe rows written from videos against the names a user types (phone check, 2026-11-19)."""

import json

import pytest

from app.dishes.recipe_names import NAMES_FILE, RecipeNames


@pytest.fixture(scope="module")
def names() -> RecipeNames:
    return RecipeNames.load()


def status(names: RecipeNames, row: str, fridge: list[str]) -> str:
    return names.status(row, names.owned(fridge))


@pytest.mark.parametrize(
    "row", ["꽃소금", "고운 소금", "진간장", "후춧가루", "통깨", "간 마늘", "찬물"]
)
def test_grades_and_forms_of_staples_are_assumed(names, row):
    assert status(names, row, []) == "assumed"


@pytest.mark.parametrize(
    ("row", "fridge"),
    [
        ("삶은 달걀", ["계란"]),
        ("김치 국물", ["김치"]),
        ("흰 쌀밥", ["밥"]),
        ("돼지 앞다리살", ["돼지고기"]),
        ("국수 (중면)", ["국수"]),
        ("고추", ["청양고추"]),
        ("모둠버섯(표고, 느타리, 새송이버섯)", ["버섯"]),
    ],
)
def test_same_ingredient_or_general_name_is_owned(names, row, fridge):
    assert status(names, row, fridge) == "owned"


@pytest.mark.parametrize(
    ("row", "fridge"),
    [
        ("쪽파", ["대파"]),  # a stand-in, not the same thing: the revision replaces it
        ("대파", ["쪽파"]),
        ("청양고추", ["고추"]),  # a general name does not cover a specific kind
        ("국간장", []),  # another kind of soy sauce
        ("맛소금", []),
    ],
)
def test_stand_ins_and_other_kinds_are_unavailable(names, row, fridge):
    assert status(names, row, fridge) == "unavailable"


@pytest.mark.parametrize(
    ("row", "fridge"),
    [
        ("스팸", ["햄"]),
        ("쌀", ["밥"]),
        ("열무김치", ["김치"]),
        ("불고기", ["소고기"]),
        ("파마산 치즈", ["치즈"]),
        ("고다치즈 슬라이스", ["치즈"]),
        ("모짜렐라 치즈 가래떡", ["떡"]),
        ("모닝빵", ["식빵"]),
        ("비엔나 살라미", ["햄"]),
    ],
)
def test_related_kinds_chosen_by_the_user_are_owned(names, row, fridge):
    # The user's choice (2026-11-19): a related kind used as a dish's main counts as the
    # general name typed in the fridge, so these recipes are not refused for it.
    assert status(names, row, fridge) == "owned"


def test_table_maps_to_plain_names_only():
    data = json.loads(NAMES_FILE.read_text(encoding="utf-8"))
    for key, value in data["same"].items():
        assert " " not in key and "(" not in key and key != value
        assert value not in data["same"], f"{key} -> {value} is a chain"
