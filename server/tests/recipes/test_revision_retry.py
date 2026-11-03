# AI-generated with Claude Code (Sonnet 5.5), 2026-11-03; reviewed by Jaehyuk Choi.
"""One optional retry with feedback after a rejected revision."""

import json

from recipe_revision.core import LLMResponse
from recipe_revision.models import InventoryIngredient, SourceIngredient, SourceRecipe, SourceStep
from recipe_revision.pipeline import Steps, revise_with_steps

MAIN, SECONDARY, SEASONING = "3060001", "3060002", "3060003"
LABEL = {MAIN: "주재료", SECONDARY: "부재료", SEASONING: "양념"}


def row(row_id, ingredient_id, name, code):
    return SourceIngredient(row_id, ingredient_id, name, "1개", code, LABEL[code], name)


def make_recipe():
    rows = (
        row(1, 345, "양파", MAIN),
        row(2, 147, "두부", SECONDARY),
        row(3, 284, "소금", SEASONING),
    )
    steps = (SourceStep(11, 1, "양파를 썬다.", None),)
    return SourceRecipe(7, "양파전", None, None, None, None, None, "2인분", None, rows, steps)


def inventory(*pairs):
    return tuple(InventoryIngredient(i, n) for i, n in (*pairs, (204, "물")))


def success(ingredient_rows, steps):
    return {
        "can_revise": True,
        "reason": "ok",
        "changes": [],
        "revised_recipe": {
            "name": "양파전",
            "servings": "2인분",
            "ingredients": [
                {"ingredient_id": i, "name": n, "quantity_text": None} for i, n in ingredient_rows
            ],
            "steps": [
                {"step_number": k, "instruction": text, "tip": None}
                for k, text in enumerate(steps, 1)
            ],
        },
    }


class ScriptedLLM:
    """Returns the given results in order and records the requests."""

    def __init__(self, *results):
        self.results, self.requests = list(results), []

    def generate(self, request):
        self.requests.append(request)
        usage = {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110}
        return LLMResponse(json.dumps({"result": self.results.pop(0)}), {"usage": usage})


BAD = success([(345, "양파"), (9999, "설탕")], ["양파를 썬다."])
GOOD = success([(345, "양파")], ["양파를 썬다."])


def test_a_rejected_answer_is_not_retried_by_default():
    llm = ScriptedLLM(BAD)
    outcome = revise_with_steps(make_recipe(), inventory((345, "양파")), llm, Steps())
    assert outcome.status == "check_failed" and len(llm.requests) == 1


def test_pipeline_retry_sends_feedback_once_and_sums_usage():
    llm = ScriptedLLM(BAD, GOOD)
    outcome = revise_with_steps(
        make_recipe(), inventory((345, "양파")), llm, Steps(retry=True, prescreen=False)
    )
    assert outcome.status == "revised" and len(llm.requests) == 2
    feedback = json.loads(llm.requests[1].user)["feedback"]
    assert feedback["unavailable_in_ingredient_list"] == ["설탕"]
    assert "feedback" not in json.loads(llm.requests[0].user)
    assert outcome.provider_metadata["model_calls"] == 2
    assert outcome.provider_metadata["usage"]["prompt_tokens"] == 200


def test_pipeline_retry_that_fails_again_stays_rejected_and_calls_only_twice():
    llm = ScriptedLLM(BAD, BAD)
    outcome = revise_with_steps(
        make_recipe(), inventory((345, "양파")), llm, Steps(retry=True, prescreen=False)
    )
    assert outcome.status == "check_failed" and len(llm.requests) == 2
