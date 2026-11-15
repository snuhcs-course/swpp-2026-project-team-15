# AI-generated with Codex, 2026-11-16; reviewed by Soohyun An
"""Verify durable local build completion and failures that could hide data damage."""

import hashlib
import importlib
import json
import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def arguments(case, output):
    normalized, catalog, review, existing = case[:4]
    return [
        "build",
        "--normalized-recipes",
        str(normalized),
        "--ingredient-catalog",
        str(catalog),
        "--review-dir",
        str(review),
        "--existing-csv",
        str(existing),
        "--output",
        str(output),
    ]


def snapshot(case):
    paths = [*case[:2], *case[2].iterdir(), *case[3].iterdir()]
    return {path: path.read_bytes() for path in paths}


def test_cli_creates_verified_db_offline_and_only_then_records_completion(append_case, tmp_path):
    output = tmp_path / "finished"
    before = snapshot(append_case)
    guard = tmp_path / "sitecustomize.py"
    guard.write_text(
        "import importlib.abc, socket, sys\n"
        "class Guard(importlib.abc.MetaPathFinder):\n"
        " def find_spec(self, fullname, path=None, target=None):\n"
        "  if fullname.split('.')[0] in "
        "{'app','server','crawlers','recipe_dedup','recipe_ingredients','dotenv'}:\n"
        "   raise AssertionError('Forbidden import: '+fullname)\n"
        "sys.meta_path.insert(0,Guard())\n"
        "def blocked(*a,**kw): raise AssertionError('Network forbidden')\n"
        "socket.socket=blocked\nsocket.create_connection=blocked\n",
        encoding="utf-8",
    )
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(tmp_path), str(ROOT / "tools")]))
    result = subprocess.run(
        [sys.executable, "-m", "recipe_entities.cli", *arguments(append_case, output)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads((output / "validation-report.json").read_bytes())
    assert report["status"] == "completed" and report["database_fields_match"] is True
    assert report["counts"]["Recipe.csv"] == {"existing": 1, "added": 2, "total": 3}
    assert report["counts"]["RecipeIngredient.csv"] == {"existing": 2, "added": 8, "total": 10}
    assert report["counts"]["RecipeStep.csv"] == {"existing": 2, "added": 4, "total": 6}
    assert report["service_suitability_assessed"] is False
    assert set(report["input_hashes"]) >= {
        "schema",
        "importer",
        "normalized_recipes",
        "ingredient_catalog",
    }
    for name, expected in report["output_hashes"].items():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == expected
    with closing(sqlite3.connect(output / "recipes.sqlite3")) as db:
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        assert db.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        assert db.execute("SELECT recipe_id FROM recipe ORDER BY recipe_id").fetchall() == [
            (1,),
            (6001,),
            (7001,),
        ]
        assert db.execute(
            "SELECT name,main_image_url FROM recipe WHERE recipe_id=1"
        ).fetchone() == ("기존 요리", "/old.jpg")
    assert all(path.read_bytes() == content for path, content in before.items())


def test_existing_output_db_is_not_overwritten(append_case, tmp_path):
    output = tmp_path / "existing-result"
    output.mkdir()
    marker = output / "recipes.sqlite3"
    marker.write_bytes(b"existing database must survive")
    build = importlib.import_module("recipe_entities.build")
    with pytest.raises(ValueError, match="exist"):
        build.build_entities(*append_case[:4], output)
    assert marker.read_bytes() == b"existing database must survive"
    assert list(output.iterdir()) == [marker]


@pytest.mark.parametrize("phase", ["write", "import", "verify"])
def test_cli_failure_keeps_inputs_and_reports_partial_result_without_success(
    append_case, tmp_path, monkeypatch, capsys, phase
):
    build = importlib.import_module("recipe_entities.build")
    cli = importlib.import_module("recipe_entities.cli")
    output = tmp_path / "partial"
    existing_db = append_case[3] / "existing.sqlite3"
    existing_db.write_bytes(b"do not overwrite")
    before = snapshot(append_case)
    if phase == "write":

        def failed_write(plan, target):
            (target / "partial.csv").write_text("partial", encoding="utf-8")
            raise OSError("synthetic disk failure")

        monkeypatch.setattr(build, "_write_files", failed_write)
    else:
        real_run = subprocess.run

        def run(command, **kwargs):
            if phase == "import":
                return subprocess.CompletedProcess(
                    command, 1, stdout="", stderr="synthetic import failure"
                )
            result = real_run(command, **kwargs)
            assert result.returncode == 0
            with closing(sqlite3.connect(output / "recipes.sqlite3")) as db:
                with db:
                    db.execute("UPDATE recipe SET name='damaged' WHERE recipe_id=6001")
            return result

        monkeypatch.setattr(build.subprocess, "run", run)
    monkeypatch.setattr(sys, "argv", ["recipe_entities", *arguments(append_case, output)])
    assert cli.main() == 1
    captured = capsys.readouterr()
    assert "completed" not in captured.out.lower()
    assert phase in captured.err and str(output) in captured.err
    report = json.loads((output / "validation-report.json").read_bytes())
    assert report["status"] == "failed" and report["phase"] == phase
    assert all(path.read_bytes() == content for path, content in before.items())
