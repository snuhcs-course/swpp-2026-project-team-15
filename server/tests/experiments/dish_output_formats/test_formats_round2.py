# AI-generated with Claude Code (Sonnet 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
import json

from experiments.dish_output_formats import formats, round2, run_round2
from experiments.dish_tokens.calls import Call

from app.dishes.catalog import Catalog
from app.dishes.service import DishService

CATALOG = Catalog.load()
NAMES = formats.dish_names(CATALOG)
VOCAB = formats.ingredient_vocabulary(CATALOG)


def test_matching_by_spelling_and_synonym_group_only():
    assert round2.vocab_match("달걀", VOCAB) == "계란"
    assert round2.vocab_match("참치 통조림", VOCAB) == "참치캔"
    assert round2.vocab_match("배추김치", VOCAB) == "김치"
    assert round2.vocab_match("다진마늘", VOCAB) is None  # prepared form, not a synonym group
    assert round2.vocab_match("쪽파", VOCAB) is None  # catalog equivalent, not matched here
    assert round2.unmatched_items(["달걀", "다진마늘", "다진 마늘", "egg"], VOCAB) == [
        "다진마늘",
        "egg",
    ]
    assert round2.x_names(["a", "b"]) == {"X1": "a", "X2": "b"}


def test_per_request_missing_enum_excludes_owned_vocabulary():
    enum = round2.missing_enum(["달걀", "밥", "깐마늘"], VOCAB)
    assert "계란" not in enum and "밥" not in enum and "마늘" in enum
    assert len(enum) == len(VOCAB) - 2
    schema = round2.answer_schema("R1", NAMES, ["달걀", "밥"], VOCAB, [])
    item = schema["properties"]["dishes"]["items"]["properties"]
    assert item["missing"]["items"]["enum"] == round2.missing_enum(["달걀", "밥"], VOCAB)
    assert item["have"]["items"]["enum"] == ["달걀", "밥"]


def test_r0_keeps_the_whole_vocabulary_and_r2_adds_mapping_first():
    r0 = round2.answer_schema("R0", NAMES, ["밥"], VOCAB, [])
    assert r0["properties"]["dishes"]["items"]["properties"]["missing"]["items"]["enum"] == VOCAB
    r2 = round2.answer_schema("R2", NAMES, ["밥", "다진마늘"], VOCAB, ["다진마늘"])
    assert list(r2["properties"]) == ["mapping", "dishes"]
    mapping = r2["properties"]["mapping"]["items"]["properties"]
    assert mapping["item"]["enum"] == ["X1"]
    assert mapping["same_as"]["enum"] == [*VOCAB, "none"]
    # no unmatched item: R2 is exactly R1
    assert round2.answer_schema("R2", NAMES, ["밥"], VOCAB, []) == round2.answer_schema(
        "R1", NAMES, ["밥"], VOCAB, []
    )


def test_payload_and_messages():
    body = round2.payload("R2", ["밥", "다진마늘"], NAMES, VOCAB)
    user = json.loads(body["messages"][1]["content"])
    assert user["unmatched"] == {"X1": "다진마늘"} and user["owned"] == ["밥", "다진마늘"]
    assert "mapping" in body["messages"][0]["content"]
    assert body["response_format"]["json_schema"]["strict"] is True
    assert body["max_tokens"] == 4096 and body["temperature"] == 0
    plain = round2.payload("R1", ["밥", "다진마늘"], NAMES, VOCAB)
    assert "unmatched" not in json.loads(plain["messages"][1]["content"])
    assert plain["messages"][0]["content"] == round2.criteria()["prompts"]["R0_R1"]


def test_read_mapping_and_removal_step():
    data = {
        "mapping": [
            {"item": "X1", "same_as": "마늘"},
            {"item": "X2", "same_as": "none"},
            {"item": "X9", "same_as": "마늘"},
            {"item": "X1", "same_as": "none"},
        ],
        "dishes": [
            {"name": "A", "have": ["다진마늘"], "missing": ["마늘", "대파"]},
            {"name": "B", "have": [], "missing": ["대파"]},
        ],
    }
    mapping = round2.read_mapping(data, ["다진마늘", "쪽파"], VOCAB)
    assert mapping == {"다진마늘": "마늘", "쪽파": "none"}
    cleaned, count, removed = round2.remove_mapped(data, mapping)
    assert count == 1 and removed == [("A", "마늘")]
    assert cleaned["dishes"][0]["missing"] == ["대파"]
    assert data["dishes"][0]["missing"] == ["마늘", "대파"]  # input not changed
    same, zero, _ = round2.remove_mapped(data, {"쪽파": "none"})
    assert same is data and zero == 0


def test_violations_cover_request_enum_and_mapping():
    ingredients = ["달걀", "다진마늘"]
    enum = round2.missing_enum(ingredients, VOCAB)
    data = {
        "mapping": [{"item": "X1", "same_as": "없는것"}, {"item": "X7", "same_as": "마늘"}],
        "dishes": [{"name": NAMES[0], "have": ["달걀", "x"], "missing": ["계란", "마늘", "zz"]}],
    }
    v = round2.count_violations(data, ingredients, NAMES, VOCAB, enum, ["다진마늘"])
    assert v["have_outside_owned"] == 1
    assert v["missing_outside"] == 1
    assert v["missing_outside_request_enum"] == 2  # 계란 (owned) and zz
    assert v["mapping_outside_enum"] == 2


def test_mapping_set_agrees_with_the_matching_rule():
    lists = round2.mapping_set()
    assert len(lists) == 40
    assert len({case["id"] for case in lists}) == 40
    for case in lists:
        assert 3 <= len(case["ingredients"]) <= 6
        unmatched = round2.unmatched_items(case["ingredients"], VOCAB)
        assert set(unmatched) == set(case["expected"]), case["id"]
        for label in case["expected"].values():
            assert label == "none" or label in VOCAB
        assert set(case["ambiguous"]) <= set(case["expected"])
    items = [v for case in lists for v in case["expected"].values()]
    assert len(items) == 43 and items.count("none") == 16


def test_scoring_of_a_mapping_and_owned_listed_as_missing():
    case = {
        "ingredients": ["깐마늘", "쪽파", "쌀", "양파"],
        "expected": {"깐마늘": "마늘", "쪽파": "none", "쌀": "밥"},
        "ambiguous": ["쌀"],
    }
    good = round2.score_mapping(case, {"깐마늘": "마늘", "쪽파": "none", "쌀": "none"})
    assert good == {
        "items": 2,
        "correct": 2,
        "false_merge": 0,
        "missed_merge": 0,
        "wrong_target": 0,
        "ambiguous": 1,
    }
    bad = round2.score_mapping(case, {"쪽파": "대파", "깐마늘": "양파"})
    assert (bad["false_merge"], bad["wrong_target"], bad["missed_merge"]) == (1, 1, 0)
    omitted = round2.score_mapping(case, {})
    assert omitted["missed_merge"] == 1 and omitted["correct"] == 1
    truly = round2.expected_owned_vocab(case, VOCAB)
    assert truly == {"양파", "마늘"}  # the ambiguous 쌀 is not counted
    dishes = [{"missing": ["마늘", "대파"]}, {"missing": ["대파"]}]
    assert round2.owned_listed_as_missing(dishes, truly) == 1
    assert round2.wrongly_hidden([("A", "대파"), ("A", "마늘")], truly) == 1


def test_bootstrap_is_reproducible_and_brackets_the_mean():
    diffs = [0.0, 1.0, -1.0, 2.0, 0.5, 0.5]
    a, b = run_round2.paired_bootstrap(diffs), run_round2.paired_bootstrap(diffs)
    assert a == b and a["n"] == 6
    assert a["low"] <= a["mean"] <= a["high"]
    assert run_round2.paired_bootstrap([]) == {"n": 0, "mean": None, "low": None, "high": None}


def test_plan_matches_the_frozen_call_plan():
    criteria = round2.criteria()
    steps = run_round2.plan(criteria, formats.frozen_cases(), round2.mapping_set())
    assert sum(len(c) for _, _, c in steps) == criteria["call_plan"]["planned_calls"] == 151
    assert criteria["call_plan"]["planned_calls"] <= criteria["call_plan"]["call_cap"] == 160
    assert "decision_rule" not in criteria  # no thresholds: the plan is descriptive


def test_run_set_with_a_fake_sender_counts_removals_and_mapping():
    case = {
        "id": "T1",
        "ingredients": ["밥", "다진마늘", "쪽파"],
        "expected": {"다진마늘": "마늘", "쪽파": "none"},
        "ambiguous": [],
    }
    answer = {
        "mapping": [{"item": "X1", "same_as": "마늘"}, {"item": "X2", "same_as": "none"}],
        "dishes": [{"name": NAMES[0], "have": ["밥"], "missing": ["마늘", "대파"]}],
    }

    def send(payload, key):
        call = Call(True, 200, 0.1, prompt_tokens=100, completion_tokens=50)
        call.data = answer
        return formats.Answer(call, "fake", json.dumps(answer))

    ctx = (CATALOG, DishService(CATALOG), NAMES, VOCAB)
    budget = run_round2.Budget(5)
    run = run_round2.run_set(
        "R2", "mapping", [case], ctx, "k", budget, sleep=lambda s: None, send=send
    )
    assert budget.used == 1
    tally = run["tally"]
    assert (tally["removals"], tally["items"], tally["correct"], tally["false_merge"]) == (
        1,
        2,
        2,
        0,
    )
    assert tally["dishes"] == 1 and tally["owned_as_missing"] == 0
    assert run["rows"][0]["returned"][0]["missing"] == ["대파"]
    table = run_round2.mapping_table(run, [case])
    assert [(t["item"], t["label"], t["model"]) for t in table] == [
        ("다진마늘", "마늘", "마늘"),
        ("쪽파", "none", "none"),
    ]
