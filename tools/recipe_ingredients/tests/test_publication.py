# AI-generated catalog publication tests with Codex, 2026-11-15; reviewed by Soohyun An
"""Exercise catalog preservation and bounded publication using disposable inputs."""

import builtins
import csv
import hashlib
import io
import json
import socket
from pathlib import Path

import pytest
from test_mapping import prepare

CSV_NAMES = (
    "Ingredient.csv",
    "IngredientPresentation.csv",
    "IngredientAllergen.csv",
    "RecipeIngredient.csv",
)


def workspace(tmp_path):
    """Write independent inputs and four catalog files with deliberately varied bytes."""
    catalog_dir = tmp_path / "catalog"
    catalog_dir.mkdir()
    _, selected, reviewed = prepare(catalog_dir)
    for name in CSV_NAMES[1:]:
        (catalog_dir / name).write_bytes(b"\xef\xbb\xbfheader,value\r\n1,keep\r\n")
    selected_path, decisions_path = tmp_path / "selected.json", tmp_path / "decisions.json"
    selected_path.write_text(json.dumps(selected), encoding="utf-8")
    decisions_path.write_text(json.dumps(reviewed), encoding="utf-8")
    before = {name: (catalog_dir / name).read_bytes() for name in CSV_NAMES}
    return selected_path, decisions_path, catalog_dir, tmp_path / "output", before


def test_publication_preserves_four_snapshots_and_three_originals(tmp_path):
    from recipe_ingredients.publication import publish

    selected, decisions, directory, output, before = workspace(tmp_path)
    inputs = [selected.read_bytes(), decisions.read_bytes()]
    report = publish(selected, decisions, directory, output)
    assert [selected.read_bytes(), decisions.read_bytes()] == inputs
    for name in CSV_NAMES:
        backup = directory / f"{Path(name).stem}_old.csv"
        assert backup.read_bytes() == before[name]
        snapshot = report["csv_snapshots"][name]
        assert (
            snapshot["before_sha256"]
            == snapshot["backup_sha256"]
            == hashlib.sha256(before[name]).hexdigest()
        )
        assert (
            snapshot["after_sha256"] == hashlib.sha256((directory / name).read_bytes()).hexdigest()
        )
    assert all((directory / name).read_bytes() == before[name] for name in CSV_NAMES[1:])
    content = (directory / "Ingredient.csv").read_bytes()
    assert content.startswith(b"\xef\xbb\xbf")
    assert list(csv.reader(io.StringIO(content.decode("utf-8-sig")))) == [
        ["ingredient_id", "name"],
        ["7", "Salt"],
        ["2", "Water"],
        ["8", "Apple"],
        ["9", "Zebra"],
    ]
    assert set(p.name for p in output.iterdir()) == {
        "ingredient-mapping.json",
        "normalized-recipes.json",
        "validation-report.json",
    }
    assert json.loads((output / "validation-report.json").read_text(encoding="utf-8")) == report
    assert report["catalog_published"] is True
    assert report["service_suitability_assessed"] is False
    assert report["published_catalog"]["sha256"] == hashlib.sha256(content).hexdigest()
    for name, digest in report["output_hashes"].items():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == digest


@pytest.mark.parametrize("conflict", [*CSV_NAMES, "output", "missing", "invalid"])
def test_preflight_failure_never_changes_catalog_or_existing_destinations(tmp_path, conflict):
    from recipe_ingredients.publication import PublicationError, publish

    selected, decisions, directory, output, before = workspace(tmp_path)
    if conflict in CSV_NAMES:
        (directory / f"{Path(conflict).stem}_old.csv").write_bytes(b"Existing backup")
    elif conflict == "output":
        output.mkdir()
        (output / "manual.txt").write_text("Keep", encoding="utf-8")
    elif conflict == "missing":
        (directory / CSV_NAMES[1]).unlink()
    elif conflict == "invalid":
        decisions.write_text('{"decisions": []}', encoding="utf-8")
    snapshot = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    with pytest.raises(PublicationError):
        publish(selected, decisions, directory, output)
    assert {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == snapshot
    assert (directory / "Ingredient.csv").read_bytes() == before["Ingredient.csv"]


@pytest.mark.parametrize("change", ["selected", "decisions", "catalog", "invalid-reference"])
def test_input_changes_and_bad_generated_references_prevent_backups(tmp_path, monkeypatch, change):
    from recipe_ingredients import publication

    selected, decisions, directory, output, before = workspace(tmp_path)
    real_build = publication.build_documents

    def changed(*args):
        documents = real_build(*args)
        if change == "invalid-reference":
            documents["normalized-recipes.json"]["recipes"][0]["recipe"]["ingredients"][0][
                "ingredient_id"
            ] = 999
        else:
            path = {
                "selected": selected,
                "decisions": decisions,
                "catalog": directory / "Ingredient.csv",
            }[change]
            path.write_bytes(path.read_bytes() + b" ")
        return documents

    monkeypatch.setattr(publication, "build_documents", changed)
    with pytest.raises(publication.PublicationError):
        publication.publish(selected, decisions, directory, output)
    assert not list(directory.glob("*_old.csv"))
    assert not output.exists()
    if change != "catalog":
        assert (directory / "Ingredient.csv").read_bytes() == before["Ingredient.csv"]


@pytest.mark.parametrize("failure", ["backup", "replace", "report"])
def test_io_failure_reports_phase_and_preserves_recovery_files(tmp_path, monkeypatch, failure):
    from recipe_ingredients import publication

    selected, decisions, directory, output, before = workspace(tmp_path)
    real_open, real_replace = Path.open, publication.os.replace

    def failing_open(path, *args, **kwargs):
        if failure == "backup" and path.name == "IngredientPresentation_old.csv":
            raise OSError("Synthetic backup failure")
        if failure == "report" and path.name == ".validation-report.json.tmp":
            raise OSError("Synthetic report failure")
        return real_open(path, *args, **kwargs)

    def failing_replace(source, destination):
        if failure == "replace" and Path(destination).name == "Ingredient.csv":
            raise OSError("Synthetic replacement failure")
        return real_replace(source, destination)

    monkeypatch.setattr(Path, "open", failing_open)
    monkeypatch.setattr(publication.os, "replace", failing_replace)
    with pytest.raises(publication.PublicationError) as caught:
        publication.publish(selected, decisions, directory, output)
    error = str(caught.value)
    assert failure in error.lower()
    assert "remaining" in error.lower()
    assert (directory / "Ingredient_old.csv").read_bytes() == before["Ingredient.csv"]
    assert not (output / "validation-report.json").exists()
    assert all((directory / n).read_bytes() == before[n] for n in CSV_NAMES[1:])
    assert ((directory / "Ingredient.csv").read_bytes() == before["Ingredient.csv"]) is (
        failure != "report"
    )


def test_cli_uses_explicit_paths_and_refuses_rerun(tmp_path, monkeypatch):
    """Exercise publication without optional runtimes, environment files or networking."""
    from typer.testing import CliRunner

    real_import, real_open = builtins.__import__, io.open

    def offline_import(name, *args, **kwargs):
        if name.split(".")[0] in {
            "server",
            "app",
            "recipe_dedup",
            "crawlers",
            "tenkrecipes",
            "dotenv",
            "requests",
        }:
            raise AssertionError(f"Forbidden runtime import: {name}")
        return real_import(name, *args, **kwargs)

    def without_env(file, *args, **kwargs):
        if isinstance(file, (str, Path)) and Path(file).name.startswith(".env"):
            raise AssertionError("Environment file access is forbidden")
        return real_open(file, *args, **kwargs)

    def offline_connect(*args, **kwargs):
        raise AssertionError("Network access is forbidden")

    monkeypatch.setattr(builtins, "__import__", offline_import)
    monkeypatch.setattr(builtins, "open", without_env)
    monkeypatch.setattr(io, "open", without_env)
    monkeypatch.setattr(socket.socket, "connect", offline_connect)
    monkeypatch.delenv("PIXABAY_KEY", raising=False)
    from recipe_ingredients.cli import app

    selected, decisions, directory, output, _ = workspace(tmp_path)
    arguments = [
        "--selected",
        str(selected),
        "--decisions",
        str(decisions),
        "--catalog-dir",
        str(directory),
        "--output",
        str(output),
    ]
    runner = CliRunner()
    success = runner.invoke(app, arguments)
    assert success.exit_code == 0, success.output
    assert str(output) in success.output
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    refused = runner.invoke(app, arguments)
    assert refused.exit_code != 0
    assert "failed" in refused.output.lower()
    assert {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == before
