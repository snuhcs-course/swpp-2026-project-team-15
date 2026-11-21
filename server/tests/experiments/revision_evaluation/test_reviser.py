# AI-assisted with Codex, 2026-11-21; human review pending.
"""Behavioral parity of traced and untraced production Revision checks."""

from copy import deepcopy

import pytest
from experiments.revision_evaluation.reviser import TracedReviser
from experiments.revision_evaluation.tracing import LogicalModelCallRecorder

from app.dishes.catalog import Catalog
from app.dishes.recipes import RecipeStore
from app.dishes.revision import Reviser
from app.dishes.schemas import SourceRecipe
from tests.dishes.test_dishes import STAPLES, FakeLLM
from tests.dishes.test_revision import GOOD, RECIPE


@pytest.mark.parametrize(
    "ingredients,answers,expected_status,expected_checks",
    [
        (["밥", "김치", "대파", "달걀"], [], "revised", []),
        (["밥"], [], "refused", []),
        (["밥", "김치"], [GOOD], "revised", [("initial", "passed", None)]),
        (
            ["밥", "김치"],
            [{**GOOD, "changes": []}, GOOD],
            "revised",
            [("initial", "violation", "unexplained_change"), ("final", "passed", None)],
        ),
        (
            ["밥", "김치"],
            [{**GOOD, "changes": []}] * 2,
            "failed",
            [
                ("initial", "violation", "unexplained_change"),
                ("final", "violation", "unexplained_change"),
            ],
        ),
        (
            ["밥", "김치"],
            [{"can_revise": False, "refusal_reason": "안전한 조리가 어려워요."}],
            "refused",
            [("initial", "not_run", None)],
        ),
        (
            ["밥", "김치"],
            [{"can_revise": False, "refusal_reason": " "}] * 2,
            "failed",
            [("initial", "violation", "incomplete"), ("final", "violation", "incomplete")],
        ),
    ],
)
def test_traced_checks_preserve_production_response_and_requests(
    ingredients,
    answers,
    expected_status,
    expected_checks,
):
    catalog = Catalog.load(staples=STAPLES)
    store = RecipeStore({RECIPE["dish_id"]: SourceRecipe.model_validate(RECIPE)})
    original_answers = deepcopy(answers)
    plain_model, traced_model = FakeLLM(*deepcopy(answers)), FakeLLM(*deepcopy(answers))
    recorder = LogicalModelCallRecorder(traced_model)
    plain = Reviser(catalog, catalog, plain_model, store, clock=lambda: 0)
    traced = TracedReviser(catalog, catalog, recorder, store, clock=lambda: 0)

    expected = plain.revise(RECIPE["dish_id"], ingredients)
    actual = traced.revise(RECIPE["dish_id"], ingredients)

    assert actual == expected and actual.status == expected_status
    assert plain_model.calls == traced_model.calls
    assert len(recorder.calls) == len(answers)
    assert [(event.phase, event.result, event.code) for event in traced.checks] == expected_checks
    assert answers == original_answers


def test_check_owned_refusal_is_distinct_from_model_refusal():
    catalog = Catalog.load(staples=STAPLES)
    recipe = SourceRecipe.model_validate({**RECIPE, "dish_id": "omurice"})
    answer = deepcopy(GOOD)
    # omurice bypasses the name-based prescreen for missing kimchi, allowing the
    # unchanged production main-ingredient check to produce RefusalNeeded.
    answer["ingredients"] = [GOOD["ingredients"][0], GOOD["ingredients"][2]]
    answer["steps"] = ["기름에 밥을 볶는다."]
    answer["changes"].append(
        {"kind": "omission", "reason": "김치가 없어요.", "ingredient_refs": [2], "step_refs": []}
    )
    store = RecipeStore({"omurice": recipe})
    plain = Reviser(catalog, catalog, FakeLLM(deepcopy(answer)), store)
    traced = TracedReviser(catalog, catalog, FakeLLM(deepcopy(answer)), store)

    expected = plain.revise("omurice", ["밥"])
    actual = traced.revise("omurice", ["밥"])

    assert actual == expected and actual.status == "refused"
    assert traced.checks[0].result == "refusal_needed"
    assert traced.checks[0].message == actual.refusal_reason


def test_reusing_reviser_does_not_retain_previous_check_events():
    catalog = Catalog.load(staples=STAPLES)
    store = RecipeStore({RECIPE["dish_id"]: SourceRecipe.model_validate(RECIPE)})
    traced = TracedReviser(catalog, catalog, FakeLLM(deepcopy(GOOD)), store)
    traced.revise(RECIPE["dish_id"], ["밥", "김치"])
    assert len(traced.checks) == 1
    traced.revise(RECIPE["dish_id"], ["밥", "김치", "대파", "달걀"])
    assert traced.checks == []
