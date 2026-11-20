# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""Offline tests of the round-2 payloads and the frozen adoption rule."""

from experiments.dish_naive.run_round2 import ADOPTABLE, decide, payload_for, prompts, schema_for

NAMES = ["김치비빔밥", "계란말이"]


def _item(schema):
    return schema["properties"]["dishes"]["items"]


def test_prompts_differ_only_where_the_variant_claims():
    p = prompts()
    assert p["P1"] == p["P2"] and p["P1"] != p["P0"]
    assert "ONLY ingredients that appear in the user's owned list" in p["P1"]
    assert "do not list the ingredients the user owns" in p["P3"]


def test_schema_enum_and_minimal():
    assert "enum" not in _item(schema_for("P1", ["김치"]))["properties"]["have"]["items"]
    p2 = _item(schema_for("P2", [" 김치 ", "밥", "김치"]))["properties"]["have"]["items"]
    assert p2["enum"] == ["김치", "밥"]
    p3 = _item(schema_for("P3", ["김치"]))
    assert set(p3["properties"]) == {"name", "missing"} and p3["required"] == ["name", "missing"]


def test_payload_is_bounded_and_deterministic():
    p = payload_for("P2", ["김치"], NAMES)
    assert p["max_tokens"] == 4096 and p["temperature"] == 0
    assert p["response_format"]["json_schema"]["strict"] is True


def _variant(have=1.0, names=1.0, nonempty=0.9, recall=0.4, precision=0.4, cost=0.0004, bad=0):
    return {
        "metrics": {
            "have_subset_share": have,
            "valid_names_share": names,
            "nonempty_when_possible": nonempty,
            "reference_recall": recall,
            "reference_precision": precision,
        },
        "truncated": bad,
        "failed": 0,
        "mean_cost_usd": cost,
    }


def test_adoption_rule_picks_cheapest_variant_that_holds_everything():
    base = _variant(have=0.95)
    result = decide({"P0": base, "P1": _variant(cost=0.0005), "P2": _variant(cost=0.0004)})
    assert result["adopted"] == "P2"
    weak = decide({"P0": base, "P1": _variant(have=0.98), "P2": _variant(recall=0.2)})
    assert weak["adopted"] is None
    assert decide({"P0": base, "P1": _variant(names=0.99)})["adopted"] is None
    assert decide({"P0": base, "P1": _variant(bad=1)})["adopted"] is None
    assert ADOPTABLE == ("P1", "P2")


def test_retry_repeats_only_rate_limited_calls(monkeypatch):
    from experiments.dish_naive import run_round2 as r
    from experiments.dish_tokens.calls import Call

    monkeypatch.setattr(r.time, "sleep", lambda s: None)
    answers = iter([Call(False, 429), Call(False, 429), Call(True, 200)])
    monkeypatch.setattr(r, "chat", lambda payload, key: next(answers))
    r.CALLS_MADE["n"] = 0
    call, attempts = r.chat_with_retry({}, "k", cap=10)
    assert call.ok and attempts == 3 and r.CALLS_MADE["n"] == 3
    monkeypatch.setattr(r, "chat", lambda payload, key: Call(False, 500))
    call, attempts = r.chat_with_retry({}, "k", cap=10)
    assert not call.ok and attempts == 1
