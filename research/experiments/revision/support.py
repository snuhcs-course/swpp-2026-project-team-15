"""Deterministic source and model fixtures, never recipes judged by an AI."""
# AI-generated initial importer with Codex (GPT-6.1 Sol)
# 2026-10-14 to 2026-10-17; reviewed by Soohyun An

from contextlib import closing
import json
from pathlib import Path
import sqlite3
import shutil
from uuid import uuid4
import unittest
from unittest.mock import patch

from server.recipe_revision import InventoryIngredient, SourceIngredient, SourceRecipe, SourceStep
from experiments.revision.cases import ALL_RECIPES, INVENTORIES

ROOT = Path(__file__).resolve().parents[3]


def temporary_workspace():
    """Place isolated fixtures in the ignored workspace data tree for sandbox access."""
    parent = ROOT / "data/recipes/revision-test-tmp"
    parent.mkdir(parents=True, exist_ok=True)
    return WorkspaceTemporaryDirectory(parent)


class WorkspaceTemporaryDirectory:
    """Use inherited ACLs; Python's mode-700 temp directories block Windows sandbox tokens."""

    def __init__(self, parent: Path):
        self.parent = parent.resolve()
        self.path = self.parent / uuid4().hex
        self.path.mkdir()
        self.name = str(self.path)

    def cleanup(self):
        resolved = self.path.resolve()
        if resolved.parent != self.parent or self.path.is_symlink():
            raise ValueError("Temporary cleanup target escaped its workspace parent")
        if self.path.exists():
            shutil.rmtree(resolved)


class OfflineTestCase(unittest.TestCase):
    """Make an accidental real HTTP request fail in every revision test."""

    def setUp(self):
        super().setUp()
        guard = patch("urllib.request.OpenerDirector.open", side_effect=AssertionError("Network forbidden in tests"))
        guard.start()
        self.addCleanup(guard.stop)


def sample_recipe() -> SourceRecipe:
    """Plain source input with repeated IDs, nullable text and original context."""
    return SourceRecipe(9, "오므라이스", None, "한식", None, "20분", None, "4인분", None,
                        (SourceIngredient(1, 32, "계란", "2개", "3060001", "주재료", "달걀"),
                         SourceIngredient(2, 32, "계란", "약간", "3060003", "양념", "[양념]계란")),
                        (SourceStep(1, 1, "계란을 충분히 익힌다.", "조리 팁"),))


def inventory() -> tuple[InventoryIngredient, ...]:
    return tuple(InventoryIngredient(*pair) for pair in INVENTORIES["AI-E0"])


def feasible(ingredient_id: int = 32) -> dict:
    """A shape-valid sample; tests can deliberately choose an unavailable ID."""
    return {"can_revise": True, "reason": "테스트용 판단", "changes": [{
        "kind": "quantity", "reason": "테스트용 수량 조정", "source_ingredient_row_ids": [1],
        "source_step_ids": [1],
    }], "revised_recipe": {"name": "오므라이스", "servings": "4인분",
                            "ingredients": [{"ingredient_id": ingredient_id, "name": "계란",
                                             "quantity_text": "2개"}],
                            "steps": [{"step_number": 1, "instruction": "계란을 충분히 익힌다.", "tip": None}]}}


def raw(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False)


def model_raw(value: dict) -> str:
    """Encode an outcome in the version-3 wire envelope used by model fixtures."""
    return raw({"result": value})


def create_database(path: Path) -> None:
    """Populate the real importer schema with all fixed IDs and source edge cases."""
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.executescript((ROOT / "server/db/schema.sql").read_text(encoding="utf-8"))
        ingredients = dict(pair for pairs in INVENTORIES.values() for pair in pairs)
        connection.executemany("INSERT INTO ingredient VALUES (?, ?)", ingredients.items())
        for index, (recipe_id, name) in enumerate(ALL_RECIPES):
            connection.execute("INSERT INTO recipe(recipe_id,name,servings) VALUES (?,?,?)",
                               (recipe_id, name, "4인분"))
            for offset, (quantity, label, original) in enumerate((
                ("2개", "주재료", "달걀"), ("약간", "양념", "[양념]계란"), (None, None, None),
            )):
                connection.execute("INSERT INTO recipe_ingredient VALUES (?,?,?,?,?,?,?)",
                                   (index * 3 + offset + 1, recipe_id, 32, quantity,
                                    "3060001" if offset == 0 else "3060003", label, original))
            for offset in (1, 0):
                connection.execute("INSERT INTO recipe_step(step_id,recipe_id,step_number,instruction,tip) "
                                   "VALUES (?,?,?,?,?)",
                                   (index * 2 + offset + 1, recipe_id, 1, "충분히 익힌다.",
                                    "조리 팁" if offset else None))
