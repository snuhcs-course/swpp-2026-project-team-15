# AI-assisted with Codex, 2026-11-15; reviewed by Soohyun An
"""Final selection contracts: explicit completion, source preservation and regeneration."""

import json
import os
import subprocess
import sys

import pytest
from test_groups import DECISION_COLUMNS, invoke_groups, write_csv
from test_groups import review_input as review_input
from test_title_csv import GUARDED_CLI, TOOLS, files_under, invoke_titles, write_json


@pytest.fixture
def selection_input(review_input, tmp_path):
    """Complete a synthetic worksheet, retaining quality notes on a kept recipe."""
    root, worksheet, rows, records = review_input
    rows[3]["normalized_title"] = "  Manual name, with spaces  "
    write_csv(worksheet, list(reversed(rows)))
    for record in records:
        record["extra_metadata"] = {"preserve": ["unknown", {"nested": True}]}
        write_json(root / f"recipes/{record['source']['id']}.json", record)
        image = root / f"images/{record['source']['id']}.jpg"
        image.parent.mkdir(exist_ok=True)
        image.write_bytes(b"original local image")
    (root / "page.html").write_text("original HTML", encoding="utf-8")
    (root / "report.json").write_text('{"original_report": true}', encoding="utf-8")
    decisions = [
        dict(source_id=r["source_id"], decision="keep", duplicate_of="", reason="") for r in rows
    ]
    decisions[2].update(decision="exclude", duplicate_of="0001", reason="Same dish, other title")
    decisions[3]["reason"] = "Data quality still needs manual review"
    path = tmp_path / "decisions.csv"
    write_csv(path, list(reversed(decisions)), DECISION_COLUMNS)
    return root, worksheet, rows, records, path, decisions


def invoke_select(root, worksheet, decisions, output):
    return subprocess.run(
        [
            sys.executable,
            "-c",
            GUARDED_CLI,
            "select",
            "--source-run",
            str(root),
            "--titles",
            str(worksheet),
            "--decisions",
            str(decisions),
            "--output",
            str(output),
        ],
        cwd=TOOLS,
        env=dict(os.environ, PYTHONPATH=str(TOOLS), PYTHONIOENCODING="utf-8"),
        capture_output=True,
        encoding="utf-8",
        timeout=30,
    )


def test_selection_preserves_source_content_order_and_quality_notes(selection_input, tmp_path):
    root, worksheet, rows, records, decisions, decision_rows = selection_input
    before = files_under(root)
    input_before = [worksheet.read_bytes(), decisions.read_bytes()]
    output = tmp_path / "selected"

    result = invoke_select(root, worksheet, decisions, output)

    assert result.returncode == 0, result.stderr
    selected = json.loads((output / "selected-recipes.json").read_text(encoding="utf-8"))
    assert selected == dict(
        source_run_id="review-fixture",
        recipes=[
            dict(
                source_id=records[i]["source"]["id"],
                original_title=records[i]["title"],
                thumbnail_path=f"images/{records[i]['source']['id']}.jpg",
                recipe=dict(records[i], title=rows[i]["normalized_title"]),
            )
            for i in (0, 1, 3)
        ],
    )
    report = json.loads((output / "selection-report.json").read_text(encoding="utf-8"))
    assert report["source_run_id"] == "review-fixture"
    assert (report["input_count"], report["kept_count"], report["excluded_count"]) == (4, 3, 1)
    assert report["kept_ids"] == ["0001", "2002", "4004"]
    assert report["excluded_ids"] == ["3003"]
    assert report["decisions"] == decision_rows
    assert report["title_normalization_complete"] is True
    assert report["duplicate_review_complete"] is True
    assert report["service_suitability_assessed"] is False
    assert report["remaining_work"] == [
        "ingredient_normalization",
        "entity_csv_conversion",
        "image_deployment",
        "database_import",
    ]
    assert sorted(p.name for p in output.iterdir()) == [
        "selected-recipes.json",
        "selection-report.json",
    ]
    assert files_under(root) == before
    assert [worksheet.read_bytes(), decisions.read_bytes()] == input_before


@pytest.mark.parametrize(
    "defect",
    [
        "blank_keep_title",
        "blank_excluded_title",
        "pending",
        "bad_representative",
        "missing_decision",
    ],
)
def test_incomplete_or_invalid_review_fails_before_output(selection_input, tmp_path, defect):
    root, worksheet, rows, _, decisions, decision_rows = selection_input
    offending_id = "3003"
    if defect.startswith("blank"):
        index = 0 if defect == "blank_keep_title" else 2
        offending_id = rows[index]["source_id"]
        rows[index]["normalized_title"] = " \t\r\n"
        write_csv(worksheet, rows)
    elif defect == "pending":
        decision_rows[3]["decision"] = "pending"
        offending_id = "4004"
    elif defect == "bad_representative":
        decision_rows[2]["duplicate_of"] = "4004"
        decision_rows[3].update(decision="exclude", duplicate_of="0001", reason="Duplicate")
    else:
        decision_rows.pop(2)
    write_csv(decisions, decision_rows, DECISION_COLUMNS)
    before = files_under(root)
    inputs_before = [worksheet.read_bytes(), decisions.read_bytes()]
    output = tmp_path / "absent" / "selected"

    result = invoke_select(root, worksheet, decisions, output)

    assert result.returncode != 0
    assert offending_id in result.stderr
    assert not output.parent.exists()
    assert files_under(root) == before
    assert [worksheet.read_bytes(), decisions.read_bytes()] == inputs_before


def test_repeated_and_revised_selection_uses_new_paths(selection_input, tmp_path):
    root, worksheet, rows, _, decisions, decision_rows = selection_input
    first, repeated, revised = [tmp_path / name for name in ("first", "repeated", "revised")]
    for path in (first, repeated):
        result = invoke_select(root, worksheet, decisions, path)
        assert result.returncode == 0, result.stderr
    original = files_under(first)
    assert files_under(repeated) == original
    rows[1]["normalized_title"] = "Revised name"
    decision_rows[0].update(decision="exclude", duplicate_of="2002", reason="Change representative")
    decision_rows[2]["duplicate_of"] = "2002"
    write_csv(worksheet, rows)
    write_csv(decisions, decision_rows, DECISION_COLUMNS)

    result = invoke_select(root, worksheet, decisions, revised)

    assert result.returncode == 0, result.stderr
    data = json.loads((revised / "selected-recipes.json").read_text(encoding="utf-8"))
    assert [r["source_id"] for r in data["recipes"]] == ["2002", "4004"]
    assert data["recipes"][0]["recipe"]["title"] == "Revised name"
    assert files_under(first) == original
    result = invoke_select(root, worksheet, decisions, first)
    assert result.returncode != 0
    assert "exist" in result.stderr.lower()
    assert files_under(first) == original


def test_final_output_cannot_modify_source_or_inputs(selection_input):
    root, worksheet, _, _, decisions, _ = selection_input
    before = files_under(root)
    inputs_before = [worksheet.read_bytes(), decisions.read_bytes()]
    for output in (root / "selected", worksheet, decisions):
        result = invoke_select(root, worksheet, decisions, output)
        assert result.returncode != 0
        assert "source" in result.stderr.lower() or "exist" in result.stderr.lower()
    assert files_under(root) == before
    assert [worksheet.read_bytes(), decisions.read_bytes()] == inputs_before


def test_documented_titles_groups_select_sequence(selection_input, tmp_path):
    root, worksheet, rows, _, _, _ = selection_input
    before = files_under(root)
    fresh = tmp_path / "fresh-titles.csv"
    result = invoke_titles(root, fresh)
    assert result.returncode == 0, result.stderr
    write_csv(fresh, rows)
    review = tmp_path / "review"
    result = invoke_groups(root, fresh, review)
    assert result.returncode == 0, result.stderr
    decisions = review / "decisions.csv"
    # This synthetic example keeps all variants, explicitly decided by the fixture.
    write_csv(
        decisions,
        [dict(source_id=r["source_id"], decision="keep", duplicate_of="", reason="") for r in rows],
        DECISION_COLUMNS,
    )
    selected = tmp_path / "selected"
    result = invoke_select(root, fresh, decisions, selected)
    assert result.returncode == 0, result.stderr
    report = json.loads((selected / "selection-report.json").read_text(encoding="utf-8"))
    assert report["kept_count"] == 4
    assert report["excluded_count"] == 0
    assert files_under(root) == before
