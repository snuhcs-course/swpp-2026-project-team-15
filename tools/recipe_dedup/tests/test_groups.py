# AI-assisted with Codex, 2026-11-15; reviewed by Soohyun An
"""Offline contracts for exact-title candidates and explicit duplicate decisions."""

import codecs
import csv
import json
import os
import subprocess
import sys

import pytest
from test_title_csv import GUARDED_CLI, TOOLS, files_under, write_json

TITLE_COLUMNS = ["source_id", "original_title", "normalized_title"]
DECISION_COLUMNS = ["source_id", "decision", "duplicate_of", "reason"]


def write_csv(path, rows, columns=TITLE_COLUMNS, encoding="utf-8-sig"):
    with path.open("w", encoding=encoding, newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def review_input(tmp_path):
    """Supply cross-category variants, a distinct dish and an unfinished title."""
    root = tmp_path / "source"
    manifest = dict(run_id="review-fixture", allocations=[], details={}, images={})
    records, rows = [], []
    for index, (source_id, name) in enumerate(
        [("0001", "Egg rice"), ("2002", "Egg rice"), ("3003", "Other rice"), ("4004", " \t")]
    ):
        record = dict(
            source=dict(id=source_id, url=f"https://example.invalid/{source_id}"),
            title=f' Original, "{source_id}"\n title ',
            ingredients=[dict(name_raw="egg", quantity_text="2", source_material_id="1470")],
            steps=[dict(order=1, instruction="Cook", tips=["Low heat"])],
        )
        records.append(record)
        write_json(root / f"recipes/{source_id}.json", record)
        manifest["allocations"].append(dict(source_id=source_id, category_code=str(index)))
        manifest["details"][source_id] = dict(record=dict(path=f"recipes/{source_id}.json"))
        manifest["images"][source_id] = dict(path=f"images/{source_id}.jpg")
        rows.append(
            dict(source_id=source_id, original_title=record["title"], normalized_title=name)
        )
    write_json(root / "manifest.json", manifest)
    write_json(root / "recipes/9999.json", dict(title="Unselected"))
    worksheet = tmp_path / "titles.csv"
    write_csv(worksheet, list(reversed(rows)))
    return root, worksheet, rows, records


def invoke_groups(root, worksheet, output):
    return subprocess.run(
        [
            sys.executable,
            "-c",
            GUARDED_CLI,
            "groups",
            "--source-run",
            str(root),
            "--titles",
            str(worksheet),
            "--output",
            str(output),
        ],
        cwd=TOOLS,
        env=dict(os.environ, PYTHONPATH=str(TOOLS), PYTHONIOENCODING="utf-8"),
        capture_output=True,
        encoding="utf-8",
        timeout=30,
    )


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig"])
def test_groups_include_comparison_content_and_pending_rows(review_input, tmp_path, encoding):
    root, worksheet, rows, records = review_input
    # Editors may change whitespace in original-title cells; stored source stays intact.
    edited = [dict(r, original_title="".join(r["original_title"].split())) for r in rows]
    edited[0]["original_title"] = "\t " + rows[0]["original_title"].replace("\n", "\r\n") + " "
    write_csv(worksheet, list(reversed(edited)), encoding=encoding)
    before, worksheet_before = files_under(root), worksheet.read_bytes()
    output = tmp_path / "review"

    result = invoke_groups(root, worksheet, output)

    assert result.returncode == 0, result.stderr
    report = json.loads((output / "groups.json").read_text(encoding="utf-8"))
    assert report["source_run_id"] == "review-fixture"
    assert report["title_normalization_complete"] is False
    assert report["unfinished_ids"] == ["4004"]
    assert report["groups"] == [
        dict(
            normalized_title="Egg rice",
            recipes=[
                dict(
                    source_id=r["source"]["id"],
                    original_title=r["title"],
                    normalized_title="Egg rice",
                    source_url=r["source"]["url"],
                    ingredients=r["ingredients"],
                    steps=r["steps"],
                    thumbnail_path=f"images/{r['source']['id']}.jpg",
                )
                for r in records[:2]
            ],
        )
    ]
    decision_path = output / "decisions.csv"
    assert decision_path.read_bytes().startswith(codecs.BOM_UTF8)
    with decision_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == DECISION_COLUMNS
        assert list(reader) == [
            dict(source_id=r["source_id"], decision="pending", duplicate_of="", reason="")
            for r in rows
        ]
    assert files_under(root) == before
    assert worksheet.read_bytes() == worksheet_before


@pytest.mark.parametrize("other", ["Egg  rice", " Egg rice", "Egg rice!", "\u00e9", "e\u0301"])
def test_normalized_titles_are_not_rewritten_or_merged(review_input, tmp_path, other):
    root, worksheet, rows, _ = review_input
    rows[1]["normalized_title"] = other
    rows[2]["normalized_title"] = other
    write_csv(worksheet, rows)
    output = tmp_path / "review"
    result = invoke_groups(root, worksheet, output)
    assert result.returncode == 0, result.stderr
    report = json.loads((output / "groups.json").read_text(encoding="utf-8"))
    assert [
        (g["normalized_title"], [r["source_id"] for r in g["recipes"]]) for g in report["groups"]
    ] == [(other, ["2002", "3003"])]


def test_unicode_equivalents_remain_separate(review_input, tmp_path):
    root, worksheet, rows, _ = review_input
    rows[0]["normalized_title"] = "\u00e9"
    rows[1]["normalized_title"] = "e\u0301"
    rows[2]["normalized_title"] = "Unique"
    rows[3]["normalized_title"] = "Another"
    write_csv(worksheet, rows)
    output = tmp_path / "review"
    result = invoke_groups(root, worksheet, output)
    assert result.returncode == 0, result.stderr
    report = json.loads((output / "groups.json").read_text(encoding="utf-8"))
    assert report["groups"] == []
    assert report["unfinished_ids"] == []
    assert report["title_normalization_complete"] is True


@pytest.mark.parametrize("defect", ["duplicate", "missing", "unknown", "original_title"])
def test_invalid_mapping_reports_id_without_outputs(review_input, tmp_path, defect):
    root, worksheet, rows, _ = review_input
    if defect == "duplicate":
        rows.append(rows[1])
    elif defect == "missing":
        rows.pop(1)
    elif defect == "unknown":
        rows[1] = dict(rows[1], source_id="unknown")
    else:
        rows[1]["original_title"] += "!"
    write_csv(worksheet, rows)
    before = files_under(root)
    output = tmp_path / "absent" / "review"
    result = invoke_groups(root, worksheet, output)
    assert result.returncode != 0
    assert ("unknown" if defect == "unknown" else "2002") in result.stderr
    assert not output.parent.exists()
    assert files_under(root) == before


def test_existing_work_and_source_run_cannot_be_output(review_input, tmp_path):
    root, worksheet, _, _ = review_input
    output = tmp_path / "review"
    output.mkdir()
    decisions = output / "decisions.csv"
    decisions.write_text("manual work", encoding="utf-8")
    before = files_under(root)
    for destination, diagnostic in [(output, "exist"), (root / "new-review", "source")]:
        result = invoke_groups(root, worksheet, destination)
        assert result.returncode != 0
        assert diagnostic in result.stderr.lower()
    assert decisions.read_text(encoding="utf-8") == "manual work"
    assert files_under(root) == before


def test_duplicate_decisions_allow_variants_and_cross_title_exclusion(review_input, tmp_path):
    from recipe_dedup.review import read_decisions

    _, _, rows, _ = review_input
    path = tmp_path / "decisions.csv"
    decisions = [
        dict(source_id=r["source_id"], decision="keep", duplicate_of="", reason="") for r in rows
    ]
    decisions[2].update(
        decision="exclude", duplicate_of="0001", reason="Same dish, different title"
    )
    decisions[3].update(decision="pending", reason="Ingredient identity needs manual review")
    write_csv(path, list(reversed(decisions)), DECISION_COLUMNS)
    before = path.read_bytes()
    assert read_decisions(path, [r["source_id"] for r in rows]) == decisions
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "defect",
    [
        "reason",
        "representative",
        "self",
        "unknown_target",
        "chain",
        "cycle",
        "pending_target",
        "missing_row",
        "duplicate_row",
        "unknown_id",
        "invalid_decision",
        "keep_reference",
        "pending_reference",
    ],
)
def test_invalid_decisions_are_rejected_without_repair(review_input, tmp_path, defect):
    from recipe_dedup.review import read_decisions

    _, _, source_rows, _ = review_input
    rows = [
        dict(source_id=r["source_id"], decision="keep", duplicate_of="", reason="")
        for r in source_rows
    ]
    rows[1].update(decision="exclude", duplicate_of="0001", reason="Duplicate")
    if defect == "reason":
        rows[1]["reason"] = " \t"
    elif defect == "representative":
        rows[1]["duplicate_of"] = ""
    elif defect == "self":
        rows[1]["duplicate_of"] = "2002"
    elif defect == "unknown_target":
        rows[1]["duplicate_of"] = "9999"
    elif defect == "chain":
        rows[0].update(decision="exclude", duplicate_of="3003", reason="Dup")
    elif defect == "cycle":
        rows[0].update(decision="exclude", duplicate_of="2002", reason="Dup")
    elif defect == "pending_target":
        rows[0]["decision"] = "pending"
    elif defect == "missing_row":
        rows.pop(1)
    elif defect == "duplicate_row":
        rows.append(rows[1])
    elif defect == "unknown_id":
        rows[1]["source_id"] = "9999"
    elif defect == "invalid_decision":
        rows[1]["decision"] = "delete"
    elif defect == "keep_reference":
        rows[1]["decision"] = "keep"
    else:
        rows[1]["decision"] = "pending"
    path = tmp_path / "decisions.csv"
    write_csv(path, rows, DECISION_COLUMNS)
    before = path.read_bytes()
    with pytest.raises(ValueError, match="2002|0001|9999"):
        read_decisions(path, [r["source_id"] for r in source_rows])
    assert path.read_bytes() == before
