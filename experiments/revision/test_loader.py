"""Read-only source/preflight checks against temporary importer-schema databases."""
# AI-generated initial importer with Codex (GPT-6.1 Sol)
# 2026-10-14 to 2026-10-17; reviewed by Soohyun An

from dataclasses import asdict
from contextlib import closing
import hashlib
from pathlib import Path
import sqlite3
from unittest.mock import patch

from experiments.revision.cases import INVENTORIES, RECIPES, matrix
from experiments.revision.mock_llm import MockLLM
from experiments.revision.run_experiment import run
from experiments.revision.sqlite_loader import PreflightError, load_inputs
from experiments.revision.support import OfflineTestCase, create_database, temporary_workspace


class LoaderTests(OfflineTestCase):
    """Preserve original row identities, nulls, types and deterministic ordering."""

    def setUp(self):
        super().setUp()
        temporary = temporary_workspace()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.database = self.directory / "recipes.sqlite3"
        create_database(self.database)

    def test_exact_fixed_matrix(self):
        cases = matrix()
        expected_ids = (9, 18, 97, 112, 114, 115, 118, 130, 192, 194, 216, 238, 291, 299, 320, 421)
        self.assertEqual(tuple(key for key, _ in RECIPES), expected_ids)
        self.assertEqual(len(cases), 32)
        self.assertEqual(len({case.case_id for case in cases}), 32)
        self.assertEqual([case.recipe_id for case in cases[:16]], list(expected_ids))
        self.assertTrue(all(case.experiment == "AI-E0" for case in cases[:16]))
        self.assertTrue(all(case.experiment == "AI-E1" for case in cases[16:]))
        self.assertEqual([key for key, _ in INVENTORIES["AI-E0"]], [70, 223, 32, 284, 282, 313, 554])
        self.assertEqual([key for key, _ in INVENTORIES["AI-E1"]], [70, 223, 32, 284, 282, 313, 554, 345, 9, 147])

    def test_full_snapshot_rows_nulls_order_and_source_unchanged(self):
        before = hashlib.sha256(self.database.read_bytes()).hexdigest()
        recipes, inventories = load_inputs(self.database)
        self.assertEqual(set(recipes), {key for key, _ in RECIPES})
        recipe = recipes[9]
        self.assertEqual([row.ingredient_id for row in recipe.ingredients], [32, 32, 32])
        self.assertEqual([row.recipe_ingredient_id for row in recipe.ingredients], [1, 2, 3])
        self.assertEqual([row.quantity_text for row in recipe.ingredients], ["2개", "약간", None])
        self.assertEqual(recipe.ingredients[1].original_name, "[양념]계란")
        self.assertEqual(recipe.ingredients[1].ingredient_type, "양념")
        self.assertEqual(recipe.ingredients[1].ingredient_type_code, "3060003")
        self.assertEqual([step.step_id for step in recipe.steps], [1, 2])
        self.assertEqual(recipe.steps[1].tip, "조리 팁")
        self.assertIsNone(recipe.steps[0].image_url)
        self.assertIsNone(recipe.description)
        self.assertEqual(recipe.source_url, "https://example.test/9")
        self.assertEqual(len(inventories["AI-E0"]), 7)
        self.assertEqual(len(inventories["AI-E1"]), 10)
        self.assertEqual(before, hashlib.sha256(self.database.read_bytes()).hexdigest())
        self.assertEqual(len(asdict(recipe)["ingredients"]), 3)

    def test_connections_are_read_only_and_closed(self):
        import experiments.revision.sqlite_loader as loader
        actual_connect = sqlite3.connect
        captured = []

        def connect(database_uri, **kwargs):
            self.assertTrue(database_uri.endswith("?mode=ro"))
            connection = actual_connect(database_uri, **kwargs)
            with self.assertRaises(sqlite3.OperationalError):
                connection.execute("DELETE FROM recipe")
            connection.rollback()
            captured.append(connection)
            return connection

        with patch.object(loader.sqlite3, "connect", side_effect=connect):
            load_inputs(self.database)
        with self.assertRaises(sqlite3.ProgrammingError):
            captured[0].execute("SELECT 1")

    def test_preflight_failure_saves_only_metadata_without_calling_llm(self):
        mutations = ("DELETE FROM recipe WHERE recipe_id=9",
                     "UPDATE recipe SET name='wrong' WHERE recipe_id=9",
                     "DELETE FROM recipe_ingredient WHERE recipe_id=9",
                     "DELETE FROM recipe_step WHERE recipe_id=9",
                     "UPDATE ingredient SET name='wrong' WHERE ingredient_id=70",
                     "DELETE FROM ingredient WHERE ingredient_id=32",
                     "DROP TABLE recipe_step")
        for index, statement in enumerate(mutations):
            database = self.directory / f"bad-{index}.sqlite3"
            create_database(database)
            with closing(sqlite3.connect(database)) as connection, connection:
                connection.execute(statement)
            llm = MockLLM()
            output = self.directory / f"out-{index}"
            with self.subTest(statement=statement), self.assertRaises(PreflightError):
                run(database, output, llm, llm.configuration())
            self.assertEqual(llm.calls, 0)
            import json
            directory = next(output.iterdir())
            self.assertEqual({path.name for path in directory.iterdir()}, {"metadata.json"})
            metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["diagnostics"]["stage"], "preflight")
            self.assertFalse(metadata["complete"])
            self.assertEqual(metadata["attempted_case_ids"], [])

    def test_missing_file_and_empty_schema_fail(self):
        for path in (self.directory / "missing.sqlite3", self.directory / "empty.sqlite3"):
            if path.name.startswith("empty"):
                path.touch()
            with self.subTest(path=path), self.assertRaises(PreflightError):
                load_inputs(path)

    def test_readme_matrix_matches_configuration(self):
        text = (Path(__file__).parent / "README.md").read_text(encoding="utf-8")
        for recipe_id, name in RECIPES:
            self.assertIn(f"| {recipe_id} | {name} |", text)
        for ingredient_id, name in INVENTORIES["AI-E1"]:
            self.assertIn(f"{name}({ingredient_id})", text)
