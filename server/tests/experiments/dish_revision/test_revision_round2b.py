# AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
import pytest
from experiments.dish_revision import run_round2b

from app.dishes import prompts


def test_keep_variant_adds_one_sentence_after_rule_2_and_is_what_is_served():
    text = run_round2b.keep_variant(run_round2b.OLD)
    assert text.count(run_round2b.KEEP_SENTENCE.strip()) == 1
    assert text == prompts.REVISE_SYSTEM
    assert run_round2b.KEEP_SENTENCE.strip() not in run_round2b.OLD


def test_keep_variant_refuses_an_unknown_prompt():
    with pytest.raises(ValueError):
        run_round2b.keep_variant("no anchor here")


def test_dry_run_makes_no_call(capsys):
    assert run_round2b.main([]) == 0
    assert "dry run" in capsys.readouterr().out


def test_real_cases_hold_only_main_ingredients_and_are_seeded():
    from app.dishes.recipes import RecipeStore, SourceRecipe

    def recipe(dish_id):
        return SourceRecipe.model_validate(
            {
                "dish_id": dish_id,
                "video": None,
                "source": "ai_structured_from_video",
                "generated_at": "2026-11-19T00:00:00Z",
                "servings": None,
                "ingredients": [
                    {"name": "밥", "amount": None, "role": "main"},
                    {"name": "대파", "amount": None, "role": "secondary"},
                ],
                "steps": [{"n": 1, "text": "볶는다"}, {"n": 2, "text": "담는다"}],
                "tips": [],
                "uncertain": [],
                "caption_gaps": False,
            }
        )

    store = RecipeStore({d: recipe(d) for d in ("a", "b", "c")})
    first = run_round2b.real_cases(store, ["a", "b", "c"], 2)
    assert first == run_round2b.real_cases(store, ["c", "b", "a"], 2)
    assert all(c["ingredients"] == ["밥"] for c in first) and len(first) == 2
