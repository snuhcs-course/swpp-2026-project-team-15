# AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""Offline checks of round 3 (list length): request builders, the fit schema and the scorer."""

import json

from experiments.dish_output_formats import round3, run_round3
from experiments.dish_output_formats.formats import Answer
from experiments.dish_output_formats.run_formats import Budget
from experiments.dish_tokens.calls import Call

from app.dishes.catalog import Catalog
from app.dishes.choices import ingredient_vocabulary
from app.dishes.prompts import SUGGEST_CLOSED_SYSTEM_ROUND2


def _ctx():
    catalog = Catalog.load()
    return catalog, ingredient_vocabulary(catalog.all())


def test_production_variant_sends_the_server_request():
    catalog, vocab = _ctx()
    choices = round3.choices_for(catalog, vocab, ["두부"])
    body = round3.payload("P0", choices)
    assert body["messages"][0]["content"] == SUGGEST_CLOSED_SYSTEM_ROUND2
    assert body["max_tokens"] == 4096 and body["temperature"] == 0
    dish = body["response_format"]["json_schema"]["schema"]["properties"]["dishes"]["items"]
    assert "두부" not in dish["properties"]["missing"]["items"]["enum"]


def test_fit_field_comes_before_have_and_missing():
    catalog, vocab = _ctx()
    choices = round3.choices_for(catalog, vocab, ["김치", "밥"])
    dish = round3.answer_schema("PC", choices)["properties"]["dishes"]["items"]
    assert list(dish["properties"]) == ["name", "fit", "have", "missing"]
    assert dish["properties"]["fit"]["enum"] == ["now", "small_purchase", "mostly_missing"]


def test_one_case_salvages_a_cut_answer_and_counts_rules_missing():
    catalog, vocab = _ctx()
    raw = '{"dishes": [{"name": "김치볶음밥", "have": ["김치", "밥"], "missing": ["대파"]}, {"na'

    def send(_body, _key):
        return Answer(Call(False, 200, 1.0, 10, 20, finish_reason="length"), None, raw)

    row = run_round3.one_case(
        "P0", {"id": "T", "ingredients": ["김치", "밥"]}, (catalog, vocab), "k", Budget(5), send
    )
    assert row["truncated"] and row["answered"]
    assert [d["id"] for d in row["returned"]] == [catalog.by_name("김치볶음밥").id]
    assert row["returned"][0]["rules_missing"] >= 0
    assert row["owned_as_missing"] == 0
    json.dumps(row)


def test_buckets_and_shares():
    assert [round3.bucket(n) for n in (0, 1, 2, 3, 7)] == ["0", "1", "2", "3+", "3+"]
    assert run_round3.shares([0, 0, 1, 5]) == {"0": 0.5, "1": 0.25, "2": 0.0, "3+": 0.25}
