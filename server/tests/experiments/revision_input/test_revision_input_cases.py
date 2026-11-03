# AI-generated with Claude Code (Sonnet 5.5), 2026-11-03; reviewed by Jaehyuk Choi.
"""The committed case manifests: shape, counts, and that they hold ids only."""

import json
from collections import Counter
from pathlib import Path

import pytest
from experiments.revision_input import cases as K
from experiments.revision_input.catalog import load_catalog

ALLOWED_KEYS = {
    "case_id",
    "recipe_id",
    "stratum",
    "category",
    "inventory_ids",
    "designated_absent",
    "strict_missing",
}
DB = Path(__file__).resolve().parents[4] / "data" / "recipes-iter2" / "recipes.sqlite3"


@pytest.mark.parametrize("name,total", [("test", 72), ("heldout", 60)])
def test_manifest_counts_and_ids(name, total):
    manifest = json.loads((Path(K.__file__).parent / K.MANIFESTS[name]).read_text(encoding="utf-8"))
    cases = manifest["cases"]
    assert len(cases) == total == sum(manifest["strata"].values())
    assert Counter(c["stratum"] for c in cases) == Counter(manifest["strata"])
    assert len({c["case_id"] for c in cases}) == total
    assert len({c["recipe_id"] for c in cases}) == total  # one case per recipe
    for case in cases:
        assert set(case) == ALLOWED_KEYS  # ids and labels only; no recipe text
        assert all(isinstance(i, int) for i in case["inventory_ids"])
        assert 204 not in case["inventory_ids"]  # water is appended at run time
        assert len(set(case["inventory_ids"])) == len(case["inventory_ids"])


def test_sets_use_different_recipes():
    test = {c["recipe_id"] for c in K.load_cases("test")}
    heldout = {c["recipe_id"] for c in K.load_cases("heldout")}
    assert not test & heldout


def test_stratum_definitions_match_the_missing_lists():
    for name in ("test", "heldout"):
        for case in K.load_cases(name):
            if case["stratum"] == "S1":
                assert case["strict_missing"] == []
            if case["stratum"] in ("S4", "S5", "S3"):
                assert case["designated_absent"]
            assert set(case["designated_absent"]) <= set(case["strict_missing"])


@pytest.mark.skipif(not DB.exists(), reason="recipe database not available")
def test_generator_reproduces_the_committed_test_set():
    recipes, names = load_catalog(DB)
    assert K.regenerate_test_set(recipes, names) == K.load_cases("test")
