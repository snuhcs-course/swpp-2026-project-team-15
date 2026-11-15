# AI-assisted with Codex, 2026-11-14 to 2026-11-15; reviewed by Soohyun An.
# CSV status preservation assisted by Codex, 2026-11-15; reviewed by Soohyun An
"""Validate saved acquisitions offline and expose originals for subsequent review."""

import copy
import csv
import io
import json
import warnings

from PIL import Image

from .config import CATEGORIES, validate_output_dir
from .storage import IntegrityError, RunStorage

REVIEW_NOTICE = (
    "Counts are unique source IDs, not substantively distinct dishes. Semantic duplicate "
    "review is pending and required before production adoption. Preserve all originals; "
    "collection does not establish production readiness or permission for redistribution."
)


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def essential_failure(record):
    """Return the first essential content failure without supplementing source fields."""
    if not _text(record.get("title")):
        return "missing_title"
    if not any(_text(row.get("name_raw")) for row in record.get("ingredients", [])):
        return "missing_ingredients"
    if not any(_text(row.get("instruction")) for row in record.get("steps", [])):
        return "missing_steps"
    return None


def _verify_image(storage, entry, policy):
    """Check original bytes and actual decoding, rather than trusting a saved status."""
    if entry["state"] != "image_validated":
        raise IntegrityError("Thumbnail is not validated")
    body = storage.verify(entry)
    if len(body) > policy.get("max_bytes", 10 * 1024 * 1024):
        raise IntegrityError("Thumbnail exceeds byte limit")
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(body)) as image:
            width, height = image.size
            image_format = image.format
            if width * height > policy.get("max_pixels", 20_000_000):
                raise IntegrityError("Thumbnail exceeds pixel limit")
            image.verify()
        with Image.open(io.BytesIO(body)) as image:
            image.load()
    if (entry["width"], entry["height"], entry["format"]) != (width, height, image_format):
        raise IntegrityError("Thumbnail metadata differs from decoded bytes")
    if entry.get("byte_count", len(body)) != len(body):
        raise IntegrityError("Thumbnail byte count differs from saved bytes")


def validate_run(root):
    """Read a run without writes/network; return explicit completeness and review evidence.

    Missing/corrupt selected artifacts are reported as incomplete rather than repaired.
    Malformed run metadata raises a normal input error. Findings never rewrite source
    records or apply recipe suitability or semantic duplicate filters.
    """
    storage = RunStorage(validate_output_dir(root))
    metadata = storage.read_json("run.json")
    manifest = storage.read_json("manifest.json")
    errors, findings, records = [], [], {}

    def error(code, source_id=None, **extra):
        errors.append(dict(code=code, source_id=source_id, **extra))

    if storage.path("failure.pending.json").exists():
        error(
            "pending_checkpoint",
            message="Resume to recover the pending checkpoint before validation.",
        )
    if manifest["run_id"] != metadata["run_id"]:
        error("run_identity_mismatch")
    expected = [(code, quota) for _, code, quota in CATEGORIES]
    plan = metadata["plan"]
    if plan["total"] != 500 or [(r["cat4"], r["quota"]) for r in plan["categories"]] != expected:
        error("plan_mismatch")
    # Response/list checks retain failure evidence even when it did not enter the quota.
    for entry in manifest.get("responses", []) + manifest.get("lists", []):
        try:
            storage.verify(entry)
        except (OSError, ValueError, KeyError):
            error("invalid_source_artifact", path=entry.get("path"))

    for source_id, detail in manifest.get("details", {}).items():
        if "record" not in detail:
            continue
        try:
            record = json.loads(storage.verify(detail["record"]))
            records[source_id] = record
            raw_path = detail.get("raw", {}).get("path")
            image_path = manifest.get("images", {}).get(source_id, {}).get("path")
            base = dict(
                source_id=source_id,
                source_url=record["source"]["url"],
                raw_path=raw_path,
                record_path=detail["record"]["path"],
                image_path=image_path,
            )
            values = copy.deepcopy(record.get("findings", []))
            if record.get("listed_tools") is None:
                values.append(dict(code="tools_not_listed", field="listed_tools"))
            for finding in values:
                findings.append(
                    dict(base, **finding, status="review_pending")
                    if "status" not in finding
                    else dict(base, **finding)
                )
        except (OSError, ValueError, KeyError, TypeError):
            error("invalid_record", source_id, path=detail["record"].get("path"))

    allocations = manifest.get("allocations", [])
    counts = {code: 0 for code, _ in expected}
    seen, successful = set(), set()
    for allocation in allocations:
        source_id, category = allocation.get("source_id"), allocation.get("category_code")
        if source_id in seen:
            error("duplicate_allocation", source_id)
            continue
        seen.add(source_id)
        if category not in counts:
            error("unknown_category", source_id, category_code=category)
            continue
        observations = [
            r
            for r in manifest.get("candidates", [])
            if r["source_id"] == source_id and r["category_code"] == category
        ]
        if not observations:
            error("category_not_observed", source_id, category_code=category)
            continue
        try:
            detail = manifest["details"][source_id]
            storage.verify(detail["raw"])
            record = records[source_id]
            source = record["source"]
            url = f"https://www.10000recipe.com/recipe/{source_id}"
            if (source["namespace"], source["id"], source["url"]) != (
                "10000recipe",
                source_id,
                url,
            ):
                raise IntegrityError("Record source identity differs from allocation")
            if detail["state"] != "parsed" or essential_failure(record):
                raise IntegrityError("Missing essential detail content")
            image = manifest["images"][source_id]
            if image.get("source_id") != source_id or image.get("recipe_source_url") != url:
                raise IntegrityError("Thumbnail belongs to another recipe")
            if not any(
                r.get("thumbnail_url") == image.get("source_url")
                for r in manifest["candidates"]
                if r["source_id"] == source_id
            ):
                raise IntegrityError("Thumbnail URL was not observed")
            _verify_image(storage, image, metadata.get("image_policy", {}))
        except (
            OSError,
            ValueError,
            KeyError,
            TypeError,
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
        ):
            error("invalid_selected_artifact", source_id)
            continue
        counts[category] += 1
        successful.add(source_id)

    categories = [
        dict(
            category_code=code,
            name=name,
            target=quota,
            selected=counts[code],
            deficit=max(0, quota - counts[code]),
        )
        for name, code, quota in CATEGORIES
    ]
    for category in categories:
        if category["selected"] != category["target"]:
            error("quota_mismatch", category_code=category["category_code"])
    if len(successful) != 500 or len(allocations) != 500:
        error("total_mismatch")
    if manifest.get("state") in ("blocked", "deferred", "failed") or manifest.get(
        "operator_review_required"
    ):
        error("collection_stopped", state=manifest.get("state"), reason=manifest.get("reason"))
    complete = not errors
    return dict(
        run_id=metadata["run_id"],
        status="complete" if complete else "incomplete",
        acquisition_complete=complete,
        target=500,
        unique_success_count=len(successful),
        categories=categories,
        errors=errors,
        findings=findings,
        failures=copy.deepcopy(manifest.get("failures", [])),
        replacements=copy.deepcopy(manifest.get("replacements", [])),
        category_outcomes=copy.deepcopy(manifest.get("category_outcomes", [])),
        collection_state=manifest.get("state"),
        collection_reason=manifest.get("reason"),
        operator_review_required=manifest.get("operator_review_required", False),
        operator_notice=copy.deepcopy(manifest.get("operator_notice")),
        retry_not_before=manifest.get("retry_not_before"),
        network_failure_streak=copy.deepcopy(manifest.get("network_failure_streak", [])),
        review_status="review_pending",
        count_basis="source_id",
        semantic_duplicate_review=dict(status="pending", required_before_production=True),
        semantic_uniqueness_guaranteed=False,
        review_notice=REVIEW_NOTICE,
    )


def write_report(root):
    """Atomically publish deterministic JSON and UTF-8 CSV; leave originals untouched."""
    report = validate_run(root)
    storage = RunStorage(validate_output_dir(root))
    columns = [
        "source_id",
        "source_url",
        "code",
        "status",
        "field",
        "order",
        "category_code",
        "reason",
        "raw_path",
        "record_path",
        "image_path",
        "observations",
    ]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for finding in report["findings"]:
        row = dict(finding)
        row["observations"] = json.dumps(row.get("observations", []), ensure_ascii=False)
        writer.writerow(row)
    for failure in report["failures"]:
        writer.writerow(dict(failure, code="acquisition_failed"))
    storage.write("review.csv", stream.getvalue().encode("utf-8-sig"))
    storage.write_json("report.json", report)
    return report
