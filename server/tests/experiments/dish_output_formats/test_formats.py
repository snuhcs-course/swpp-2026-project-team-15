# AI-generated with Claude Code (Sonnet 5.5), 2026-11-18; reviewed by Jaehyuk Choi.
import json
from pathlib import Path

import httpx
from experiments.dish_output_formats import formats, run_formats
from experiments.dish_tokens.calls import Call

from app.dishes.catalog import Catalog

FROZEN = (
    Path(__file__).resolve().parents[4] / "research/experiments/dish_eval/catalog_at_freeze.json"
)
CATALOG = Catalog.load(FROZEN)  # the catalog of the study (130 dishes)
NAMES = formats.dish_names(CATALOG)
VOCAB = formats.ingredient_vocabulary(CATALOG)


def test_vocabulary_has_one_spelling_per_synonym_group():
    assert len(NAMES) == 130
    assert "계란" in VOCAB and "달걀" not in VOCAB
    assert "참치캔" in VOCAB and "참치" not in VOCAB and "참치통조림" not in VOCAB
    assert "김치" in VOCAB and "배추김치" not in VOCAB
    assert VOCAB == sorted(set(VOCAB))


def test_schemas_carry_the_enums():
    s1 = formats.schema_for("S1", NAMES, ["김치"], VOCAB)
    assert s1["properties"]["dishes"]["items"]["enum"] == NAMES
    s2 = formats.schema_for("S2", NAMES, ["김치", "밥"], VOCAB)
    item = s2["properties"]["dishes"]["items"]
    assert item["properties"]["name"]["enum"] == NAMES
    assert item["properties"]["have"]["items"]["enum"] == ["김치", "밥"]
    assert item["properties"]["missing"]["items"]["enum"] == VOCAB
    assert item["required"] == ["have", "missing", "name"]
    s3 = formats.schema_for("S3", NAMES, ["김치"], VOCAB)
    assert "have" not in s3["properties"]["dishes"]["items"]["properties"]


def test_owned_enum_trims_and_dedupes():
    assert formats.owned_enum([" 김치", "김치", "", "밥 "]) == ["김치", "밥"]


def test_payload_routes():
    rf = formats.response_format_payload("S2", ["김치"], NAMES, VOCAB)
    assert rf["response_format"]["json_schema"]["strict"] is True
    assert rf["provider"] == {"require_parameters": True} and "tools" not in rf
    assert (
        formats.response_format_payload("S2n", ["김치"], NAMES, VOCAB)["response_format"][
            "json_schema"
        ]["strict"]
        is False
    )
    assert "provider" not in formats.response_format_payload("S2r", ["김치"], NAMES, VOCAB)
    tools = formats.tools_payload("S4", ["김치"], NAMES, VOCAB)
    assert tools["tool_choice"]["function"]["name"] == formats.FUNCTION_NAME
    assert tools["tools"][0]["function"]["strict"] is True and "response_format" not in tools
    assert tools["messages"][0]["content"] == formats.prompts()["S2"]


def test_prompts_are_the_frozen_texts():
    given = formats.load_criteria()["prompts"]
    p = formats.prompts()
    assert p["S1"] == given["S1"] and p["S2"] == given["S2"] and p["S3"] == given["S3"]
    assert p["S0"].startswith("You help a Korean student")


def test_violations_count_each_kind_exactly():
    data = {
        "dishes": [
            {"name": "김치볶음밥", "have": ["김치", "참치"], "missing": ["대파", "달걀"]},
            {"name": "없는요리", "have": ["밥"], "missing": []},
            {"name": "김치볶음밥", "have": [], "missing": []},
        ]
    }
    v = formats.count_violations("S2", data, ["김치", "밥"], NAMES, VOCAB)
    assert v["names"] == 3 and v["names_outside_list"] == 1 and v["repeated"] == 1
    assert v["have"] == 3 and v["have_outside_owned"] == 1
    assert v["missing"] == 2 and v["missing_outside"] == 1


def test_names_only_answer_is_read_as_dishes_without_fields():
    data = formats.service_data("S1", {"dishes": ["김치볶음밥", "김치찌개"]})
    assert [d["name"] for d in data["dishes"]] == ["김치볶음밥", "김치찌개"]
    assert data["dishes"][0]["have"] == [] and data["dishes"][0]["missing"] == []
    assert formats.service_data("S1", None) == {"dishes": []}
    assert formats.service_data("S1", {"dishes": "x"}) == {"dishes": []}


def test_rules_assisted_computes_have_and_missing_from_key_ingredients():
    out = formats.rules_assisted(
        CATALOG, {"dishes": ["김치볶음밥", "김치볶음밥", "없는요리"]}, ["김치", "밥"]
    )
    assert len(out) == 1 and out[0]["id"] == "kimchi-fried-rice"
    assert set(out[0]["have"]) == {"밥", "김치"} and "김치" not in out[0]["missing"]


def test_client_code_lines_are_counted_for_both_routes():
    lines = formats.client_code_lines()
    assert set(lines) == {"raw_response_format", "raw_tools", "langchain"}
    assert all(n > 5 for n in lines.values())


def fake_post(transport_body, status=200):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=transport_body)

    return handler


def test_post_chat_reads_a_tool_call_and_a_message(monkeypatch):
    usage = {"prompt_tokens": 100, "completion_tokens": 20, "cost": 0.0001}
    tool = {
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "tool_calls": [{"function": {"arguments": json.dumps({"dishes": []})}}]
                },
            }
        ],
        "usage": usage,
        "provider": "SomeProvider",
    }
    msg = {
        "choices": [{"finish_reason": "stop", "message": {"content": '{"dishes": ["a"]}'}}],
        "usage": usage,
    }
    cut = {"choices": [{"finish_reason": "length", "message": {"content": '{"dishes": ['}}]}
    real = httpx.post
    for body, ok, provider in ((tool, True, "SomeProvider"), (msg, True, None), (cut, False, None)):
        transport = httpx.MockTransport(fake_post(body))
        monkeypatch.setattr(
            formats.httpx,
            "post",
            lambda url, transport=transport, **kw: httpx.Client(transport=transport).post(
                url, json=kw["json"], headers=kw["headers"]
            ),
        )
        answer = formats.post_chat({"x": 1}, "key")
        assert answer.call.ok is ok and answer.provider == provider
        if ok:
            assert answer.call.data is not None and answer.call.prompt_tokens == 100
        else:
            assert answer.call.finish_reason == "length"
    monkeypatch.setattr(formats.httpx, "post", real)


def test_token_cost_matches_the_price_table():
    assert abs(formats.token_cost(1_000_000, 1_000_000) - 0.50) < 1e-9


def answer(status=200, ok=True):
    return formats.Answer(Call(ok, status))


def test_with_retry_repeats_a_429_twice_and_counts_every_attempt():
    sent, waits = [], []

    def send():
        sent.append(1)
        return answer(429, False)

    budget = run_formats.Budget(10)
    out = run_formats.with_retry(send, budget, waits.append)
    assert len(sent) == 3 and out.attempts == 3 and budget.used == 3 and waits == [5, 15]
    ok = run_formats.with_retry(lambda: answer(), run_formats.Budget(10), waits.append)
    assert ok.attempts == 1


def test_budget_stops_at_the_cap():
    budget = run_formats.Budget(2)
    budget.take()
    budget.take()
    try:
        budget.take()
    except run_formats.CapReached:
        return
    raise AssertionError("the cap was not enforced")


def summary(truncated=0, failed=0, cost=0.0005, recall=0.5, precision=0.4, **violations):
    base = dict.fromkeys(("names_outside_list", "have_outside_owned", "missing_outside"), 0)
    return {
        "metrics": {"reference_recall": recall, "reference_precision": precision},
        "violations": base | violations,
        "truncated": truncated,
        "failed": failed,
        "mean_cost_usd": cost,
    }


def test_rule_picks_the_cheapest_qualifier_and_names_the_failures():
    per = {
        "S0": summary(recall=0.5, precision=0.4, have_outside_owned=3),
        "S1": summary(cost=0.0003, recall=0.45),
        "S2": summary(cost=0.0006),
        "S3": summary(cost=0.0004, truncated=1),
        "S4": summary(cost=0.0007, missing_outside=1),
    }
    out = run_formats.decide(per)
    assert out["chosen"] == "S2" and out["qualifying"] == ["S2"]
    assert out["verdicts"]["S1"]["checks"]["recall>=S0-0.02"] is False
    assert out["verdicts"]["S3"]["checks"]["zero_truncated"] is False
    assert out["verdicts"]["S4"]["checks"]["zero_violations"] is False


def test_rule_has_no_winner_when_nobody_qualifies_and_breaks_near_ties_by_code_length():
    per = {"S0": summary(), "S1": summary(failed=1)}
    assert run_formats.decide(per)["chosen"] is None
    per = {
        "S0": summary(),
        "S2": summary(cost=0.000500),
        "S4": summary(cost=0.000505),
    }
    lines = {"raw_response_format": 30, "raw_tools": 20}
    assert run_formats.decide(per, lines)["chosen"] == "S4"
    assert run_formats.decide(per, {"raw_response_format": 20, "raw_tools": 30})["chosen"] == "S2"


def test_plan_follows_the_frozen_criteria_and_stays_in_the_cap():
    criteria = formats.load_criteria()
    cases = formats.frozen_cases()
    assert len(cases) == 27
    plan = {v: len(run_formats.inputs_for(v, cases, criteria)) for v in criteria["run_order"]}
    assert plan["S0"] == 27 and plan["S4"] == 27 and plan["S5a"] == 12 and plan["S2r"] == 6
    assert sum(plan.values()) == criteria["planned_calls"] <= criteria["call_cap"]
    assert [c["id"] for c in run_formats.inputs_for("S5a", cases, criteria)][-1] == "S12"


def test_dry_run_makes_no_call(capsys):
    assert run_formats.main([]) == 0
    assert "dry run" in capsys.readouterr().out
