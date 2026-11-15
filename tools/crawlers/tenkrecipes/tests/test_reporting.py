# AI-assisted with Codex, 2026-11-12; reviewed by Soohyun An
# Test reorganization assisted by Codex, 2026-11-15; reviewed by Soohyun An
"""Offline completeness, immutable evidence and review exports."""

import csv
import importlib
import json

import pytest

from crawlers.tenkrecipes.storage import digest
from crawlers.tenkrecipes.tests.support_runs import saved_collection


def reporting():
    """Import report behavior at execution, keeping all cases discoverable."""
    return importlib.import_module("crawlers.tenkrecipes.reporting")


def test_exact_500_and_nine_quotas_are_complete_but_review_is_pending(tmp_path):
    storage, manifest = saved_collection(tmp_path)
    ids = [row["source_id"] for row in manifest["allocations"][:2]]
    paths = [manifest["details"][i]["raw"]["path"] for i in ids]
    paths += [manifest["details"][i]["record"]["path"] for i in ids]
    paths += [manifest["images"][i]["path"] for i in ids]
    before = {path: storage.path(path).read_bytes() for path in paths}
    assert before[paths[0]] == before[paths[1]]
    assert before[paths[4]] == before[paths[5]]
    report = reporting().write_report(storage.root)
    assert report["status"] == "complete" and report["acquisition_complete"] is True
    assert report["target"] == report["unique_success_count"] == 500
    assert [
        (r["category_code"], r["target"], r["selected"], r["deficit"]) for r in report["categories"]
    ] == [
        ("63", 100, 100, 0),
        ("56", 90, 90, 0),
        ("54", 60, 60, 0),
        ("55", 30, 30, 0),
        ("53", 60, 60, 0),
        ("52", 100, 100, 0),
        ("61", 20, 20, 0),
        ("65", 20, 20, 0),
        ("64", 20, 20, 0),
    ]
    assert report["review_status"] == "review_pending"
    assert report["semantic_duplicate_review"] == dict(
        status="pending", required_before_production=True
    )
    assert report["count_basis"] == "source_id"
    assert report.get("production_ready") is not True
    assert {path: storage.path(path).read_bytes() for path in paths} == before
    for source_id in ids:
        record = storage.read_json(manifest["details"][source_id]["record"]["path"])
        assert record["source"]["id"] == source_id
        assert record["source"]["url"].endswith("/" + source_id)


@pytest.mark.parametrize(
    "defect",
    [
        "499",
        "duplicate_id",
        "wrong_category",
        "missing_image",
        "corrupt_image",
        "missing_record",
        "missing_raw",
        "empty_title",
        "empty_ingredients",
        "empty_steps",
    ],
)
def test_false_completeness_is_rejected_offline(tmp_path, defect):
    storage, manifest = saved_collection(tmp_path)
    source_id = manifest["allocations"][0]["source_id"]
    detail = manifest["details"][source_id]
    if defect == "499":
        manifest["allocations"].pop()
    elif defect == "duplicate_id":
        manifest["allocations"][-1]["source_id"] = source_id
    elif defect == "wrong_category":
        manifest["allocations"][0]["category_code"] = "56"
    elif defect.startswith("empty_"):
        entry = detail["record"]
        record = storage.read_json(entry["path"])
        field = defect.removeprefix("empty_")
        record[field] = " " if field == "title" else []
        storage.write_json(entry["path"], record)
        entry["sha256"] = digest(storage.path(entry["path"]).read_bytes())
    else:
        entry = (
            manifest["images"][source_id]
            if "image" in defect
            else detail["record" if defect == "missing_record" else "raw"]
        )
        if defect == "corrupt_image":
            storage.path(entry["path"]).write_bytes(b"not an image")
            # Even matching hashes cannot turn invalid image bytes into an asset.
            entry["sha256"] = digest(b"not an image")
        else:
            storage.path(entry["path"]).unlink()
    storage.write_json("manifest.json", manifest)
    report = reporting().validate_run(storage.root)
    assert report["status"] == "incomplete" and report["acquisition_complete"] is False
    assert report["errors"]
    if defect == "499":
        assert report["unique_success_count"] == 499
        assert next(r for r in report["categories"] if r["category_code"] == "64")["deficit"] == 1


def test_findings_remain_reviewable_without_rewriting_or_disqualifying_records(tmp_path):
    storage, manifest = saved_collection(tmp_path)
    source_id = manifest["allocations"][0]["source_id"]
    entry = manifest["details"][source_id]["record"]
    record = storage.read_json(entry["path"])
    observations = [
        dict(representation=kind, value=value, source_url=record["source"]["url"])
        for kind, value in [("dom", record["title"]), ("jsonld", "Different title")]
    ]
    record["findings"].append(
        dict(
            code="source_mismatch",
            field="title",
            status="review_pending",
            observations=observations,
        )
    )
    storage.write_json(entry["path"], record)
    entry["sha256"] = digest(storage.path(entry["path"]).read_bytes())
    storage.write_json("manifest.json", manifest)
    before = {p: p.read_bytes() for p in storage.root.rglob("*") if p.is_file()}
    report = reporting().write_report(storage.root)
    assert report["acquisition_complete"] is True
    assert all(path.read_bytes() == body for path, body in before.items())
    assert storage.read_json(entry["path"]) == record
    assert record["ingredients"][-1]["quantity_text"] is None
    findings = [r for r in report["findings"] if r["source_id"] == source_id]
    assert {"missing_quantity", "tools_not_listed", "source_mismatch"} <= {
        r["code"] for r in findings
    }
    assert (
        next(r for r in findings if r["code"] == "source_mismatch")["observations"] == observations
    )
    assert all(r["status"] == "review_pending" for r in findings)
    with storage.path("review.csv").open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    mismatch = next(
        r for r in rows if r["source_id"] == source_id and r["code"] == "source_mismatch"
    )
    assert json.loads(mismatch["observations"]) == observations
    assert mismatch["source_url"] == record["source"]["url"]
    assert mismatch["raw_path"] == manifest["details"][source_id]["raw"]["path"]
    assert mismatch["record_path"] == entry["path"]
    assert mismatch["image_path"] == manifest["images"][source_id]["path"]
    assert storage.read_json("report.json") == report


def test_validate_is_read_only_and_report_is_repeatable(tmp_path):
    storage, _ = saved_collection(tmp_path)
    before = {p: p.read_bytes() for p in storage.root.rglob("*") if p.is_file()}
    reporting().validate_run(storage.root)
    assert {p: p.read_bytes() for p in storage.root.rglob("*") if p.is_file()} == before
    first = reporting().write_report(storage.root)
    csv_before = storage.path("review.csv").read_bytes()
    second = reporting().write_report(storage.root)
    assert second == first and storage.path("review.csv").read_bytes() == csv_before


@pytest.mark.parametrize("command", ["validate", "report"])
def test_offline_cli_reports_incomplete_run_without_live_flag(tmp_path, run_tool, command):
    storage, manifest = saved_collection(tmp_path)
    manifest["allocations"].pop()
    storage.write_json("manifest.json", manifest)
    result = run_tool(command, "--output-dir", str(storage.root))
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["acquisition_complete"] is False
    assert payload["unique_success_count"] == 499
    assert "FORBIDDEN_IO" not in result.stderr
    assert storage.path("report.json").exists() == (command == "report")
