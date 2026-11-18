# AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""Offline checks of round 4 (structure): request builders, the split merge and the plan."""

import json

from experiments.dish_output_formats import formats, round4, run_round4
from experiments.dish_output_formats.formats import Answer
from experiments.dish_tokens.calls import Call

from app.dishes.catalog import Catalog
from app.dishes.choices import ingredient_vocabulary
from app.dishes.prompts import SUGGEST_CLOSED_SYSTEM


def _ctx():
    catalog = Catalog.load()
    return catalog, ingredient_vocabulary(catalog.all())


def _missing_enum(body: dict) -> list[str]:
    dish = body["response_format"]["json_schema"]["schema"]["properties"]["dishes"]["items"]
    return dish["properties"]["missing"]["items"]["enum"]


def test_production_variant_is_the_served_request():
    catalog, vocab = _ctx()
    [req] = round4.requests_for("S_now", "T", ["두부"], catalog, vocab)
    assert req.body["messages"][0]["content"] == SUGGEST_CLOSED_SYSTEM
    assert len(req.choices.names) == len(catalog)


def test_noseason_removes_staples_from_missing_choices():
    catalog, vocab = _ctx()
    [now] = round4.requests_for("S_now", "T", ["두부"], catalog, vocab)
    [noseason] = round4.requests_for("S_noseason", "T", ["두부"], catalog, vocab)
    assert "간장" in _missing_enum(now.body)
    assert not set(_missing_enum(noseason.body)) & round4.staple_forms(catalog.staples)


def test_split_sends_one_request_per_category_covering_every_dish():
    catalog, vocab = _ctx()
    reqs = round4.requests_for("S_split", "T", ["두부"], catalog, vocab)
    assert len(reqs) == len({d.category for d in catalog.all()})
    assert sum(len(r.choices.names) for r in reqs) == len(catalog)


def test_shuffle_is_seeded_and_keeps_every_name():
    catalog, vocab = _ctx()
    [a] = round4.requests_for("S_shuffle", "T", ["두부"], catalog, vocab)
    [b] = round4.requests_for("S_shuffle", "T", ["두부"], catalog, vocab)
    assert a.choices.names == b.choices.names
    assert sorted(a.choices.names) == sorted(d.name for d in catalog.all())


def test_split_case_merges_groups_orders_by_missing_and_counts_cut_calls():
    catalog, vocab = _ctx()
    cut = '{"dishes": [{"name": "김치볶음밥", "have": ["김치"], "missing": ["대파", "계란"]}, {"na'

    def send(body, _key):
        names = json.loads(body["messages"][1]["content"])["dishes"]
        if "김치볶음밥" in names:
            return Answer(Call(False, 200, 1.0, 10, 20, finish_reason="length"), None, cut)
        if "김치찌개" in names:
            data = {"dishes": [{"name": "김치찌개", "have": ["김치"], "missing": []}]}
            return Answer(Call(True, 200, 1.0, 10, 20, finish_reason="stop", data=data))
        return Answer(Call(True, 200, 1.0, 10, 5, finish_reason="stop", data={"dishes": []}))

    budget = run_round4.LockedBudget(100)
    row = run_round4.run_case(
        "S_split", {"id": "T", "ingredients": ["김치"]}, (catalog, vocab), "k", budget, send
    )
    assert row["requests"] == len({d.category for d in catalog.all()})
    assert row["truncated_calls"] == 1 and row["failed_calls"] == 0
    ids = [d["id"] for d in row["returned"]]
    assert ids == [catalog.by_name("김치찌개").id, catalog.by_name("김치볶음밥").id]
    assert row["owned_as_missing"] == 0


def test_plan_stays_within_the_registered_budget():
    catalog, _ = _ctx()
    crit = round4.criteria()
    runs = run_round4.plan(formats.frozen_cases())
    groups = len(round4.category_groups(catalog))
    planned = sum(len(c) * (groups if v in round4.SPLIT else 1) for v, c in runs.items())
    assert planned == crit["budget"]["planned_calls"] <= crit["budget"]["model_calls"]
    assert len(runs["S_split"]) == 2 + crit["split_sample_size"]
