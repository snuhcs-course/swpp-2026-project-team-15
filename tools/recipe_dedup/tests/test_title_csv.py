# AI-assisted with Codex, 2026-11-15; reviewed by Soohyun An
"""Stage-one CLI contracts for a user-authored title worksheet, using local fixtures."""

import codecs
import csv
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2]
GUARDED_CLI = """
import runpy
import sys
def guard(event, args):
    if event in ('socket.connect', 'socket.getaddrinfo'):
        raise AssertionError('NETWORK_FORBIDDEN')
    if event == 'import' and args[0].startswith(('crawlers.tenkrecipes', 'app.')):
        raise AssertionError('COLLECTOR_OR_SERVER_IMPORT_FORBIDDEN')
sys.addaudithook(guard)
sys.argv = ['recipe_dedup.cli', *sys.argv[1:]]
runpy.run_module('recipe_dedup.cli', run_name='__main__')
"""


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def files_under(root):
    """Capture source bytes to detect any writes, including unexpected new artifacts."""
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


@pytest.fixture
def source_run(tmp_path):
    """Build a two-selection run with an unrelated, unreadable attempt record."""
    root = tmp_path / "source"
    rows = [("900002", '  달걀, "볶음밥"\n원본 제목  '), ("000123", "♥[신혼밥상] 오이 무침")]
    manifest = dict(run_id="fixture-run", allocations=[], details={}, images={})
    for source_id, title in rows:
        record_path = f"recipes/{source_id}.json"
        write_json(
            root / record_path,
            dict(
                source=dict(id=source_id, url=f"https://example.invalid/{source_id}"), title=title
            ),
        )
        image = root / f"images/{source_id}.jpg"
        image.parent.mkdir(exist_ok=True)
        image.write_bytes(b"source image bytes are not decoded by title export")
        manifest["allocations"].append(dict(source_id=source_id, category_code="63"))
        manifest["details"][source_id] = dict(record=dict(path=record_path))
        manifest["images"][source_id] = dict(path=f"images/{source_id}.jpg")
    manifest["details"]["999999"] = dict(record=dict(path="recipes/999999.json"))
    (root / "recipes/999999.json").write_text("unselected and not JSON", encoding="utf-8")
    write_json(root / "manifest.json", manifest)
    return root, manifest, rows


def invoke_titles(root, output):
    """Exercise the documented CLI without collector imports or network access."""
    return subprocess.run(
        [
            sys.executable,
            "-c",
            GUARDED_CLI,
            "titles",
            "--source-run",
            str(root),
            "--output",
            str(output),
        ],
        cwd=TOOLS,
        env=dict(os.environ, PYTHONPATH=str(TOOLS), PYTHONIOENCODING="utf-8"),
        capture_output=True,
        encoding="utf-8",
        timeout=30,
    )


def test_titles_preserve_selected_order_original_text_and_blank_user_titles(source_run, tmp_path):
    root, _, rows = source_run
    before = files_under(root)
    output = tmp_path / "worksheet" / "titles.csv"

    result = invoke_titles(root, output)

    assert result.returncode == 0, result.stderr
    content = output.read_bytes()
    assert content.startswith(codecs.BOM_UTF8)
    for encoding, body in (("utf-8-sig", content), ("utf-8", content[len(codecs.BOM_UTF8) :])):
        reader = csv.DictReader(io.StringIO(body.decode(encoding), newline=""))
        assert reader.fieldnames == ["source_id", "original_title", "normalized_title"]
        assert list(reader) == [
            dict(source_id=source_id, original_title=title, normalized_title="")
            for source_id, title in rows
        ]
    assert files_under(root) == before


def test_identical_original_titles_keep_both_source_ids(source_run, tmp_path):
    root, _, rows = source_run
    for source_id, _ in rows:
        path = root / f"recipes/{source_id}.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        record["title"] = "콩나물무침"
        write_json(path, record)
    output = tmp_path / "titles.csv"

    result = invoke_titles(root, output)

    assert result.returncode == 0, result.stderr
    with output.open(encoding="utf-8-sig", newline="") as handle:
        assert [r["source_id"] for r in csv.DictReader(handle)] == [r[0] for r in rows]


def test_existing_user_worksheet_is_not_overwritten(source_run, tmp_path):
    root, _, _ = source_run
    output = tmp_path / "titles.csv"
    original = "source_id,original_title,normalized_title\n900002,原題,사용자 제목\n".encode()
    output.write_bytes(original)
    before = files_under(root)

    result = invoke_titles(root, output)

    assert result.returncode != 0
    assert "exist" in result.stderr.lower()
    assert output.read_bytes() == original
    assert files_under(root) == before


def test_output_inside_source_run_is_rejected(source_run):
    root, _, _ = source_run
    before = files_under(root)

    result = invoke_titles(root, root / "worksheet" / "titles.csv")

    assert result.returncode != 0
    assert "source" in result.stderr.lower()
    assert files_under(root) == before
    assert not (root / "worksheet").exists()


@pytest.mark.parametrize(
    "defect",
    ["missing_record", "corrupt_record", "wrong_id", "duplicate_id", "missing_detail", "escape"],
)
def test_invalid_selected_input_reports_id_before_creating_output(source_run, tmp_path, defect):
    root, manifest, _ = source_run
    source_id = "000123"
    path = root / "recipes" / f"{source_id}.json"
    if defect == "missing_record":
        path.unlink()
    elif defect == "corrupt_record":
        path.write_text("not JSON", encoding="utf-8")
    elif defect == "wrong_id":
        record = json.loads(path.read_text(encoding="utf-8"))
        record["source"]["id"] = "different"
        write_json(path, record)
    elif defect == "duplicate_id":
        manifest["allocations"].append(manifest["allocations"][-1])
    elif defect == "missing_detail":
        del manifest["details"][source_id]
    else:
        outside = tmp_path / "outside.json"
        outside.write_bytes(path.read_bytes())
        manifest["details"][source_id]["record"]["path"] = "../outside.json"
    write_json(root / "manifest.json", manifest)
    before = files_under(root)
    output = tmp_path / "not-created" / "titles.csv"

    result = invoke_titles(root, output)

    assert result.returncode != 0
    assert source_id in result.stderr
    assert not output.parent.exists()
    assert files_under(root) == before
