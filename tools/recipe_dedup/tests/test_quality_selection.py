# AI-assisted with Codex, 2026-11-15; reviewed by Soohyun An
"""Contracts for explicit quality exclusions alongside duplicate decisions."""

import json
import os
import subprocess
import sys

import pytest
from test_groups import DECISION_COLUMNS, write_csv
from test_groups import review_input as review_input
from test_selection import selection_input as selection_input
from test_title_csv import GUARDED_CLI, TOOLS, files_under


def invoke_quality(root, titles, decisions, quality, output):
    return subprocess.run(
        [
            sys.executable,
            "-c",
            GUARDED_CLI,
            "select",
            "--source-run",
            str(root),
            "--titles",
            str(titles),
            "--decisions",
            str(decisions),
            "--quality-exclusions",
            str(quality),
            "--output",
            str(output),
        ],
        cwd=TOOLS,
        env=dict(os.environ, PYTHONPATH=str(TOOLS), PYTHONIOENCODING="utf-8"),
        capture_output=True,
        encoding="utf-8",
        timeout=30,
    )


def test_explicit_quality_exclusion_overrides_pending_and_keep(selection_input, tmp_path):
    root, titles, mapping, _, decisions, rows = selection_input
    rows[3]["decision"] = "pending"
    write_csv(decisions, rows, DECISION_COLUMNS)
    quality_rows = [
        dict(
            source_id=mapping[i]["source_id"],
            normalized_title=mapping[i]["normalized_title"],
            reason="User quality exclusion",
        )
        for i in (1, 3)
    ]
    quality = tmp_path / "quality.csv"
    write_csv(quality, quality_rows, ["source_id", "normalized_title", "reason"])
    before, csv_before = files_under(root), [p.read_bytes() for p in (titles, decisions, quality)]
    output = tmp_path / "selected"
    result = invoke_quality(root, titles, decisions, quality, output)
    assert result.returncode == 0, result.stderr
    data = json.loads((output / "selected-recipes.json").read_text(encoding="utf-8"))
    assert [r["source_id"] for r in data["recipes"]] == ["0001"]
    report = json.loads((output / "selection-report.json").read_text(encoding="utf-8"))
    assert (report["input_count"], report["kept_count"], report["excluded_count"]) == (4, 1, 3)
    assert report["excluded_ids"] == ["2002", "3003", "4004"]
    assert report["duplicate_excluded_ids"] == ["3003"]
    assert report["quality_exclusions"] == quality_rows
    assert report["decisions"] == rows
    assert report["selection_complete"] is True
    assert report["duplicate_review_complete"] is False
    assert report["service_suitability_assessed"] is False
    assert files_under(root) == before
    assert [p.read_bytes() for p in (titles, decisions, quality)] == csv_before


@pytest.mark.parametrize(
    "defect", ["unknown", "duplicate", "title", "reason", "representative", "other_pending"]
)
def test_invalid_quality_inputs_fail_before_output(selection_input, tmp_path, defect):
    root, titles, mapping, _, decisions, rows = selection_input
    index = 0 if defect == "representative" else 3
    quality_rows = [
        dict(
            source_id=mapping[index]["source_id"],
            normalized_title=mapping[index]["normalized_title"],
            reason="Quality issue",
        )
    ]
    if defect == "unknown":
        quality_rows[0]["source_id"] = "9999"
    elif defect == "duplicate":
        quality_rows.append(quality_rows[0])
    elif defect == "title":
        quality_rows[0]["normalized_title"] = "wrong title"
    elif defect == "reason":
        quality_rows[0]["reason"] = " \t"
    elif defect == "other_pending":
        rows[1]["decision"] = "pending"
        write_csv(decisions, rows, DECISION_COLUMNS)
    quality = tmp_path / "quality.csv"
    write_csv(quality, quality_rows, ["source_id", "normalized_title", "reason"])
    output = tmp_path / "absent" / "selected"
    result = invoke_quality(root, titles, decisions, quality, output)
    assert result.returncode != 0
    assert (
        "9999"
        if defect == "unknown"
        else "2002"
        if defect == "other_pending"
        else "0001"
        if defect == "representative"
        else "4004"
    ) in result.stderr
    assert not output.parent.exists()
