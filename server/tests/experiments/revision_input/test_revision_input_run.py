# AI-generated with Claude Code (Sonnet 5.5), 2026-11-03; human review pending.
"""The runner end to end with the offline stand-in; no network, no recipe database."""

import json
import socket

import pytest
from experiments.revision_input import run_experiment as rx
from experiments.revision_input.offline_llm import OfflineLLM

from recipe_revision.models import SourceIngredient, SourceRecipe, SourceStep

NAMES = {32: "계란", 99: "대파", 284: "소금", 554: "후추", 345: "양파", 204: "물"}


def make_recipe(recipe_id, name):
    rows = (
        SourceIngredient(1, 32, "계란", "2개", "3060001", "주재료", "달걀"),
        SourceIngredient(2, 99, "대파", "1대", "3060002", "부재료", "대파"),
        SourceIngredient(3, 284, "소금", "약간", "3060003", "양념", "소금"),
    )
    steps = (SourceStep(10, 1, "계란을 풀고 대파를 썰어 넣어 익힌다.", None),)
    return SourceRecipe(recipe_id, name, None, None, None, None, None, "1인분", None, rows, steps)


CASES = [
    {"case_id": "X-1", "recipe_id": 1, "stratum": "S1", "inventory_ids": [32, 99, 284]},
    {"case_id": "X-2", "recipe_id": 1, "stratum": "S3", "inventory_ids": [32, 284]},
    {"case_id": "X-3", "recipe_id": 2, "stratum": "S4", "inventory_ids": [99, 284]},
]


@pytest.fixture
def patched(monkeypatch, tmp_path):
    recipes = {1: make_recipe(1, "계란말이"), 2: make_recipe(2, "계란국")}
    monkeypatch.setattr(rx, "load_catalog", lambda path: (recipes, NAMES))
    monkeypatch.setattr(rx, "load_cases", lambda name: CASES)
    db = tmp_path / "recipes.sqlite3"
    db.write_bytes(b"not a real database")  # only hashed, never opened
    return db


def forbid_network(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("network is forbidden in tests")

    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)


def test_mock_run_writes_calls_summary_and_labels_itself(patched, tmp_path, monkeypatch, capsys):
    forbid_network(monkeypatch)
    out_dir = tmp_path / "out"
    code = rx.main(["--db", str(patched), "--output-dir", str(out_dir), "--repeats", "1"])
    assert code == 0
    (run_dir,) = out_dir.iterdir()
    meta = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert meta["configuration"]["is_mock"] is True
    assert meta["arms"] == list(rx.ARMS) and meta["set"] == "test"
    assert len(list((run_dir / "calls").iterdir())) == len(rx.ARMS) * len(CASES)
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert set(summary["criteria_vs_original"]) == {"check-only", "default", "retry"}
    assert "MOCK" in capsys.readouterr().out


def test_default_arm_refuses_in_code_without_a_model_call(patched, tmp_path):
    rx.main(["--db", str(patched), "--output-dir", str(tmp_path / "out"), "--repeats", "1"])
    (run_dir,) = (tmp_path / "out").iterdir()
    refused = json.loads((run_dir / "calls" / "default__X-3__r1.json").read_text(encoding="utf-8"))
    assert refused["status"] == "refused" and refused["model_calls"] == 0
    original = json.loads(
        (run_dir / "calls" / "original__X-3__r1.json").read_text(encoding="utf-8")
    )
    assert original["model_calls"] == 1


def test_retry_arm_makes_a_second_call_after_a_rejection(patched, tmp_path):
    rx.main(["--db", str(patched), "--output-dir", str(tmp_path / "out"), "--repeats", "1"])
    (run_dir,) = (tmp_path / "out").iterdir()
    # X-2 lacks 대파, whose name stays in the unchanged steps: rejected, then retried once.
    call = json.loads((run_dir / "calls" / "retry__X-2__r1.json").read_text(encoding="utf-8"))
    assert call["status"] == "check_failed" and call["model_calls"] == 2


def test_live_provider_needs_the_explicit_flag(patched, tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        rx.main(["--db", str(patched), "--provider", "chat-completions"])
    assert exc.value.code == 2
    assert "--allow-live-api" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        rx.main(["--db", str(patched), "--allow-live-api"])  # live flag in mock mode


def test_offline_llm_answers_follow_the_stated_rules():
    llm = OfflineLLM()
    recipe = make_recipe(1, "계란말이")
    request = rx.revise.__globals__["build_request"](recipe, ())
    llm.prepare(recipe, {32, 284})
    revised = json.loads(llm.generate(request).text)["result"]
    assert revised["can_revise"] and [
        i["ingredient_id"] for i in revised["revised_recipe"]["ingredients"]
    ] == [32, 284]
    llm.prepare(recipe, {99, 284})  # 계란 is in the dish name and unavailable
    assert json.loads(llm.generate(request).text)["result"]["can_revise"] is False
    assert llm.calls == 2
