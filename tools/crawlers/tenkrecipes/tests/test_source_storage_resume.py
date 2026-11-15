# AI-assisted with Codex, 2026-11-11; reviewed by Soohyun An
# Regression coverage assisted by Codex, 2026-11-12; reviewed by Soohyun An
# Test reorganization assisted by Codex, 2026-11-15; reviewed by Soohyun An
"""Immutable source snapshots, publication failures and local recovery."""

import copy
import hashlib
import json
import os
from pathlib import Path

import pytest

from crawlers.tenkrecipes.tests.support_http import (
    DETAIL_URL,
    FIXTURES,
    LIST_URL,
    FakeResponse,
    fixture_response,
)
from crawlers.tenkrecipes.tests.support_runs import make_run


def test_run_records_plan_versions_and_network_policy(tmp_path):
    _, run, options, _, _ = make_run(tmp_path)
    metadata = json.loads((Path(options["plan"]["output_dir"]) / "run.json").read_text("utf-8"))
    assert metadata["parser_version"] == "test-parser-v1"
    assert metadata["schema_version"] == "test-schema-v1"
    assert metadata["plan"]["total"] == 500
    assert sum(row["quota"] for row in metadata["plan"]["categories"]) == 500
    assert metadata["started_at"]
    assert metadata["run_id"]
    policy = run.snapshot()["network_policy"]
    assert policy["min_interval"] == 2
    assert tuple(policy["timeout"]) == (10, 30)
    assert policy["max_attempts"] == 3
    assert policy["max_wait"] == 60 and policy["run_budget"] == 120


def test_saved_lists_keep_bytes_hash_urls_times_and_ordered_candidate_observations(tmp_path):
    response = fixture_response("list.html", url=LIST_URL + "&observed=1")
    _, run, options, _, clock = make_run(tmp_path, response)
    run.fetch_list("52", 1)
    snapshot = run.snapshot()
    entry = snapshot["lists"][0]
    root = Path(options["plan"]["output_dir"])
    assert not Path(entry["path"]).is_absolute()
    assert (root / entry["path"]).resolve().is_relative_to(root.resolve())
    assert (root / entry["path"]).read_bytes() == response.content
    assert entry["sha256"] == hashlib.sha256(response.content).hexdigest()
    assert entry["source_url"] == LIST_URL
    assert entry["final_url"] == response.url
    assert entry["fetched_at"] == clock.utcnow().isoformat()
    observations = snapshot["candidates"]
    assert [row["source_id"] for row in observations] == ["900001", "900002"]
    assert [row["position"] for row in observations] == [1, 2]
    assert all(row["category_code"] == "52" and row["page"] == 1 for row in observations)


def test_detail_bytes_and_parsed_record_are_saved_without_fetching_images(tmp_path):
    response = fixture_response("detail.html")
    _, run, options, transport, _ = make_run(tmp_path, response)
    result = run.fetch_detail("900001")
    root = Path(options["plan"]["output_dir"])
    assert result["status"] == "parsed"
    assert (root / "details/900001.html").read_bytes() == response.content
    record = json.loads((root / "recipes/900001.json").read_text("utf-8"))
    assert record["source"]["id"] == "900001"
    assert len(record["ingredients"]) == 4 and len(record["steps"]) == 3
    assert [call["url"] for call in transport.calls] == [DETAIL_URL]
    assert not (root / "images").exists() or not list((root / "images").iterdir())


def test_repeated_list_access_reuses_original_snapshot_without_fetching(tmp_path):
    _, run, options, transport, _ = make_run(tmp_path, fixture_response("list.html"))
    run.fetch_list("52", 1)
    root = Path(options["plan"]["output_dir"])
    before = {path: path.read_bytes() for path in root.rglob("*.html")}
    run.fetch_list("52", 1)
    assert len(transport.calls) == 1
    assert {path: path.read_bytes() for path in before} == before
    assert len(run.snapshot()["candidates"]) == 2


@pytest.mark.parametrize("target", ["manifest.json", "details/900001.html", "recipes/900001.json"])
def test_failed_publication_retains_last_valid_checkpoint(tmp_path, monkeypatch, target):
    _, run, options, _, _ = make_run(
        tmp_path, fixture_response("list.html"), fixture_response("detail.html")
    )
    run.fetch_list("52", 1)
    manifest = Path(options["plan"]["output_dir"]) / "manifest.json"
    interrupted_path = Path(options["plan"]["output_dir"]) / target
    previous = manifest.read_bytes()
    replace = os.replace

    def interrupt_manifest(source, destination, *args, **kwargs):
        if Path(destination).resolve() == interrupted_path.resolve():
            raise OSError("synthetic interruption before artifact replacement")
        return replace(source, destination, *args, **kwargs)

    monkeypatch.setattr(os, "replace", interrupt_manifest)
    with pytest.raises(OSError):
        run.fetch_detail("900001")
    assert manifest.read_bytes() == previous
    assert json.loads(manifest.read_text("utf-8"))["candidates"]
    if target != "manifest.json":
        assert not interrupted_path.exists()


def test_resume_uses_pending_candidates_and_complete_details_before_new_pages(tmp_path):
    module, run, options, transport, clock = make_run(
        tmp_path, fixture_response("list.html"), fixture_response("detail.html")
    )
    run.fetch_list("52", 1)
    run.fetch_detail("900001")
    first_page_time = run.snapshot()["lists"][0]["fetched_at"]
    clock.sleep(10)
    transport.outcomes.extend([fixture_response("detail.html"), fixture_response("list.html")])
    resumed = module.CollectionRun.resume(**options)
    assert len(transport.calls) == 2
    resumed.resume_pending()
    assert [call["url"] for call in transport.calls] == [
        LIST_URL,
        DETAIL_URL,
        DETAIL_URL.replace("900001", "900002"),
    ]
    resumed.fetch_list("52", 2)
    assert transport.calls[-1]["url"] == LIST_URL.replace("page=1", "page=2")
    entries = resumed.snapshot()["lists"]
    assert entries[0]["fetched_at"] == first_page_time
    assert entries[1]["fetched_at"] != first_page_time
    assert len(resumed.snapshot()["attempts"]) == 4


def test_resume_recovers_missing_parsed_output_from_saved_raw_without_refetch(tmp_path):
    module, run, options, transport, _ = make_run(
        tmp_path, fixture_response("list.html"), fixture_response("detail.html")
    )
    run.fetch_list("52", 1)
    run.fetch_detail("900001")
    root = Path(options["plan"]["output_dir"])
    raw_before = (root / "details/900001.html").read_bytes()
    (root / "recipes/900001.json").unlink()
    transport.outcomes.append(fixture_response("detail.html"))
    resumed = module.CollectionRun.resume(**options)
    resumed.resume_pending()
    restored = json.loads((root / "recipes/900001.json").read_text("utf-8"))
    assert restored["source"]["id"] == "900001"
    assert (root / "details/900001.html").read_bytes() == raw_before
    assert [call["url"] for call in transport.calls] == [
        LIST_URL,
        DETAIL_URL,
        DETAIL_URL.replace("900001", "900002"),
    ]


@pytest.mark.parametrize("changed", ["plan", "parser_version", "schema_version"])
def test_resume_refuses_configuration_or_version_drift_without_io(tmp_path, changed):
    module, _, options, transport, _ = make_run(tmp_path)
    changed_options = dict(options)
    root = Path(options["plan"]["output_dir"])
    before = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
    if changed == "plan":
        plan = copy.deepcopy(json.loads(json.dumps(dict(options["plan"]), default=dict)))
        plan["categories"][0]["quota"] += 1
        changed_options["plan"] = plan
    else:
        changed_options[changed] = "different-version"
    with pytest.raises(module.ResumeMismatch):
        module.CollectionRun.resume(**changed_options)
    assert transport.calls == []
    assert {path: path.read_bytes() for path in root.rglob("*") if path.is_file()} == before


def test_resume_detects_corrupt_saved_source_without_silent_overwrite(tmp_path):
    module, run, options, transport, _ = make_run(tmp_path, fixture_response("list.html"))
    run.fetch_list("52", 1)
    entry = run.snapshot()["lists"][0]
    path = Path(options["plan"]["output_dir"]) / entry["path"]
    path.write_bytes(b"synthetic damaged snapshot")
    with pytest.raises(module.IntegrityError):
        module.CollectionRun.resume(**options)
    assert len(transport.calls) == 1
    assert path.read_bytes() == b"synthetic damaged snapshot"


@pytest.mark.parametrize("failure", ["denied", "challenge", "filter", "structure", "wait"])
def test_source_failure_preserves_previous_work_and_distinguishes_causes(tmp_path, failure):
    responses = {
        "denied": FakeResponse(403),
        "challenge": FakeResponse(body=b'<form id="challenge-form"></form>'),
        "filter": FakeResponse(
            body=(FIXTURES / "list.html")
            .read_bytes()
            .replace(b'name="cat2" value="18"', b'name="cat2" value="19"')
        ),
        "structure": FakeResponse(body=b"<html>not a recipe list</html>"),
        "wait": FakeResponse(429, headers={"Retry-After": "999"}),
    }
    _, run, options, transport, _ = make_run(
        tmp_path, fixture_response("list.html"), responses[failure]
    )
    run.fetch_list("52", 1)
    old = run.snapshot()["lists"][0]
    path = Path(options["plan"]["output_dir"]) / old["path"]
    original = path.read_bytes()
    result = run.fetch_list("52", 2)
    assert result["status"] == ("deferred" if failure == "wait" else "blocked")
    expected = dict(
        denied="access_denied",
        challenge="challenge",
        filter="structure_mismatch",
        structure="structure_mismatch",
        wait="wait_budget_exceeded",
    )
    assert result["reason"] == expected[failure]
    assert run.snapshot()["state"] == result["status"]
    assert path.read_bytes() == original
    assert run.snapshot()["candidates"][:2]
    assert len(transport.calls) == 2
    assert len(run.snapshot()["attempts"]) == 2
    assert len(list((Path(options["plan"]["output_dir"]) / "lists").rglob("*.html"))) == 2


def test_resume_recovers_list_published_before_interrupted_manifest(tmp_path, monkeypatch):
    """Regression: a published list must not disappear from pending work on resume."""
    module, run, options, transport, _ = make_run(tmp_path, fixture_response("list.html"))
    manifest = Path(options["plan"]["output_dir"]) / "manifest.json"
    replace = os.replace

    def interrupt(source, destination):
        if Path(destination).resolve() == manifest.resolve():
            raise OSError("synthetic checkpoint interruption")
        return replace(source, destination)

    with monkeypatch.context() as patch:
        patch.setattr(os, "replace", interrupt)
        with pytest.raises(OSError):
            run.fetch_list("52", 1)
    transport.outcomes.extend([fixture_response("detail.html"), fixture_response("detail.html")])
    resumed = module.CollectionRun.resume(**options)
    resumed.resume_pending()
    assert [call["url"] for call in transport.calls] == [
        LIST_URL,
        DETAIL_URL,
        DETAIL_URL.replace("900001", "900002"),
    ]
    assert len(resumed.snapshot()["lists"]) == 1


def test_resume_retains_retry_after_deadline_without_early_transport_access(tmp_path):
    """Regression: restarting a deferred run must not bypass Retry-After."""
    module, run, options, transport, _ = make_run(
        tmp_path, FakeResponse(429, headers={"Retry-After": "999"})
    )
    assert run.fetch_list("52", 1)["status"] == "deferred"
    transport.outcomes.append(fixture_response("list.html"))
    resumed = module.CollectionRun.resume(**options)
    assert resumed.fetch_list("52", 1)["status"] == "deferred"
    assert len(transport.calls) == 1


def test_retry_after_on_last_attempt_is_retained_across_resume(tmp_path):
    """Exhausting attempts must not allow resume to bypass the last rate-limit deadline."""
    module, run, options, transport, _ = make_run(
        tmp_path,
        FakeResponse(429, headers={"Retry-After": "2"}),
        FakeResponse(429, headers={"Retry-After": "2"}),
        FakeResponse(429, headers={"Retry-After": "999"}),
    )
    assert run.fetch_list("52", 1)["status"] == "failed"
    transport.outcomes.append(fixture_response("list.html"))
    resumed = module.CollectionRun.resume(**options)
    assert resumed.fetch_list("52", 1)["status"] == "deferred"
    assert len(transport.calls) == 3
