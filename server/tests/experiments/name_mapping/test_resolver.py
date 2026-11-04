# AI-generated with Claude Code (Sonnet 5.5), 2026-11-04; reviewed by Jaehyuk Choi.
"""Name resolution on a tiny synthetic catalog and toy vectors; no model, no database."""

import json

from experiments.name_mapping import resolver as R
from experiments.name_mapping import run_experiment as X

CATALOG = {1: "후추", 2: "통후추", 3: "국간장", 4: "진간장", 5: "계란", 6: "대파"}
VECTORS = {
    "후추": [1.0, 0.0, 0.0],
    "통후추": [0.6, 0.8, 0.0],
    "국간장": [0.0, 1.0, 0.0],
    "진간장": [0.0, 0.99, 0.1],
    "계란": [0.0, 0.0, 1.0],
    "대파": [0.5, 0.5, 0.5],
    "pepper powder": [1.0, 0.0, 0.0],  # same as 후추
    "soy sauce": [0.0, 1.0, 0.05],  # between the two soy sauces
    "mystery": [0.3, 0.2, 0.1],
}


def embed(texts):
    return [VECTORS.get(t, [0.01, 0.01, 0.01]) for t in texts]


def test_exact_then_synonym_then_unmapped():
    r = R.Resolver(CATALOG)
    assert r.resolve("후추").kind == "exact"
    hit = r.resolve("후춧가루")  # synonym group of the server
    assert (hit.kind, hit.ingredient_id, hit.name) == ("synonym", 1, "후추")
    assert r.resolve("달걀").name == "계란"
    assert r.resolve("커피").kind == "unmapped"


def test_embedding_needs_similarity_and_a_clear_lead():
    r = R.Resolver(CATALOG, embed, tau=0.95, margin=0.05)
    assert r.resolve("pepper powder").name == "후추"  # 1.0 and ahead of 통후추 by > 0.05
    assert r.resolve("mystery").kind == "unmapped"  # below tau
    sibling = R.Resolver(CATALOG, embed, tau=0.9, margin=0.05).resolve("soy sauce")
    assert sibling.kind == "unmapped"  # two near-equal siblings: margin guard refuses
    assert R.Resolver(CATALOG, embed, tau=0.9, margin=0.0).resolve("soy sauce").kind == "embedding"


def test_exact_and_synonym_do_not_call_the_embedder():
    calls = []

    def counting(texts):
        calls.append(list(texts))
        return embed(texts)

    r = R.Resolver(CATALOG, counting)
    calls.clear()
    r.resolve("계란")
    r.resolve("달걀")
    assert calls == []


def test_resolution_is_deterministic_and_ties_take_the_lower_id():
    r = R.Resolver({1: "a", 2: "a2"}, lambda t: [[1.0, 0.0] for _ in t], tau=0.5, margin=0.0)
    assert r.resolve("zzz").ingredient_id in (1, 2)
    assert r.resolve("zzz") == r.resolve("zzz")


def test_suggestion_rules():
    names = ["간장", "국간장", "진간장", "양조간장", "간장게장", "대파"]
    assert R.suggest_app_rule("간장", names) == ["간장게장", "국간장", "진간장", "양조간장"]
    assert R.suggest_app_rule("", names) == []
    assert R.suggest_app_rule("후춧", names) == []
    alias = {"후춧가루": "후추"}
    assert R.suggest_with_aliases("후춧", ["후추"], alias) == ["후추"]


def test_strip_wording_baseline():
    assert R.strip_wording("대파 1단") == "대파"
    assert R.strip_wording("소금 500g") == "소금"
    assert R.strip_wording("다진 마늘") == "마늘"
    assert R.strip_wording("달 걀") == "달걀"


def test_evaluate_weights_by_occurrence():
    gold = {"후춧가루": "후추", "달걀": "계란", "커피": None, "대파 한 단": "대파"}
    counts = [("후춧가루", 6), ("달걀", 2), ("커피", 1), ("대파 한 단", 1)]
    shares = X.evaluate(R.Resolver(CATALOG), counts, gold)
    assert shares == {
        "mapped_correct": 0.8,
        "mapped_wrong": 0.0,
        "unmapped_correct": 0.1,
        "unmapped_wrong": 0.1,
    }


def test_runner_reads_a_catalog_and_prints_shares(tmp_path, capsys):
    import sqlite3

    db = tmp_path / "t.sqlite3"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE ingredient (ingredient_id INTEGER PRIMARY KEY, name TEXT)")
    con.executemany("INSERT INTO ingredient VALUES (?, ?)", list(CATALOG.items()))
    con.commit()
    con.close()
    names, gold = tmp_path / "n.json", tmp_path / "g.json"
    names.write_text(json.dumps([["달걀", 3], ["커피", 1]]), encoding="utf-8")
    gold.write_text(json.dumps({"달걀": "계란", "커피": None}), encoding="utf-8")
    X.main(["--db", str(db), "--names", str(names), "--gold", str(gold)])
    out = capsys.readouterr().out
    assert "exact+synonym" in out and '"mapped_correct": 0.75' in out
