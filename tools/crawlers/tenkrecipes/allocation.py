# AI-assisted with Codex, 2026-11-14; human review pending.
"""Deterministic source-ID allocation with recorded replacements and bounded traversal."""

from .reporting import write_report


def _selected(run, category):
    return sum(row["category_code"] == category for row in run._manifest["allocations"])


def _category_outcome(run, category, reason, page):
    """Update one category checkpoint without discarding earlier observations or failures."""
    manifest = run.snapshot()
    code = category["cat4"]
    row = dict(
        category_code=code,
        reason=reason,
        page=page,
        selected=_selected(run, code),
        deficit=max(0, category["quota"] - _selected(run, code)),
    )
    manifest["category_outcomes"] = [
        r for r in manifest["category_outcomes"] if r["category_code"] != code
    ]
    manifest["category_outcomes"].append(row)
    run._commit(manifest)


def _record_decision(run, candidate, result):
    """Allocate at most once, or retain a failure and link its next same-category success."""
    manifest = run.snapshot()
    source_id, code = candidate["source_id"], candidate["category_code"]
    if result["status"] == "image_validated":
        if not any(row["source_id"] == source_id for row in manifest["allocations"]):
            manifest["allocations"].append(dict(source_id=source_id, category_code=code))
        replaced = {
            r["failed_source_id"] for r in manifest["replacements"] if r["category_code"] == code
        }
        for failure in manifest["failures"]:
            if (
                failure["category_code"] == code
                and failure["source_id"] not in replaced
                and failure["source_id"] != source_id
                and failure["status"] == "failed"
                and run._manifest["candidate_outcomes"].get(failure["source_id"], {}).get("status")
                == "failed"
            ):
                manifest["replacements"].append(
                    dict(
                        failed_source_id=failure["source_id"],
                        replacement_source_id=source_id,
                        category_code=code,
                    )
                )
        for observation in manifest["candidates"]:
            if observation["source_id"] == source_id:
                observation["state"] = "selected"
    else:
        if not any(
            row["source_id"] == source_id and row["category_code"] == code
            for row in manifest["failures"]
        ):
            detail = manifest["details"].get(source_id, {})
            image = manifest["images"].get(source_id, {})
            manifest["failures"].append(
                dict(
                    source_id=source_id,
                    category_code=code,
                    reason=result.get("reason"),
                    status=result["status"],
                    source_url=candidate["source_url"],
                    page=candidate["page"],
                    position=candidate["position"],
                    raw_path=(detail.get("raw") or {}).get("path"),
                    record_path=detail.get("record", {}).get("path"),
                    image_path=image.get("path"),
                )
            )
    run._commit(manifest)


def _finish(run, *, stopped=False):
    """Keep stop causes visible; only validated exact quotas may claim completion."""
    manifest = run.snapshot()
    if not stopped:
        manifest.update(state="running", reason=None)
        run._commit(manifest)
    report = write_report(run.storage.root)
    if not stopped:
        manifest = run.snapshot()
        manifest.update(
            state=report["status"],
            reason=None if report["acquisition_complete"] else "quota_shortfall",
        )
        run._commit(manifest)
        # Publish against the final checkpoint, not the transient running state.
        report = write_report(run.storage.root)
    return dict(report, status=run._manifest["state"] if stopped else report["status"])


def collect_quotas(run):
    """Fill categories in plan order, reusing saved pages before expanding each traversal.

    Repeated IDs within a category do not cause extra detail/image requests.
    Different IDs remain distinct irrespective of content equality. Exhaustion
    never lends quota to another category or broadens the source filters.
    """
    manifest = run.snapshot()
    manifest["collection_mode"] = "quota"
    run._commit(manifest)
    if run._operator_status() or run._deferred():
        return _finish(run, stopped=True)
    # A finished/exhausted category must not hide a missing derived or image file.
    # Repair historical selections without resetting the newer failure streak.
    for selection in run._manifest["allocations"]:
        source_id = selection["source_id"]
        detail = run._manifest["details"][source_id]
        image = run._manifest["images"][source_id]
        if (
            run.storage.path(detail["record"]["path"]).exists()
            and run.storage.path(image["path"]).exists()
        ):
            continue
        result = run.fetch_detail(source_id)
        if result["status"] == "parsed":
            result = run.fetch_thumbnail(source_id)
        if result["status"] != "image_validated":
            return _finish(run, stopped=True)
        manifest = run.snapshot()
        for observation in manifest["candidates"]:
            if observation["source_id"] == source_id:
                observation["state"] = "selected"
        run._commit(manifest)
    allocated = {row["source_id"] for row in run._manifest["allocations"]}
    for category in run.metadata["plan"]["categories"]:
        code, quota = category["cat4"], category["quota"]
        previous = next(
            (r for r in run._manifest["category_outcomes"] if r["category_code"] == code), {}
        )
        if _selected(run, code) == quota:
            if previous.get("reason") != "quota_reached":
                last_page = max(
                    (r["page"] for r in run._manifest["lists"] if r["category_code"] == code),
                    default=1,
                )
                _category_outcome(run, category, "quota_reached", last_page)
            continue
        if previous.get("reason") == "exhausted" and _selected(run, code) < quota:
            continue
        page, observed = 1, set()
        while _selected(run, code) < quota:
            if run._operator_status() or run._deferred():
                _category_outcome(run, category, run._manifest["reason"], page)
                return _finish(run, stopped=True)
            result = run.fetch_list(code, page)
            if result["status"] not in ("ok", "empty"):
                _category_outcome(run, category, result["reason"], page)
                return _finish(run, stopped=True)
            ids = {row["source_id"] for row in result["items"]}
            if not ids:
                _category_outcome(run, category, "exhausted", page)
                break
            if not ids - observed:
                _category_outcome(run, category, "repeated_page", page)
                manifest = run.snapshot()
                manifest.update(state="blocked", reason="repeated_page")
                run._commit(manifest)
                return _finish(run, stopped=True)
            candidates = [
                r
                for r in run._manifest["candidates"]
                if r["category_code"] == code and r["page"] == page
            ]
            for candidate in candidates:
                source_id = candidate["source_id"]
                if source_id in allocated or source_id in observed:
                    continue
                # Per-page repeated cards must not inflate failures or allocations.
                observed.add(source_id)
                outcome = run._process_candidate(candidate)
                _record_decision(run, candidate, outcome)
                if (
                    run._operator_status()
                    or run._deferred()
                    or source_id not in run._manifest["candidate_outcomes"]
                ):
                    _category_outcome(run, category, run._manifest["reason"], page)
                    return _finish(run, stopped=True)
                if outcome["status"] == "image_validated":
                    allocated.add(source_id)
                if _selected(run, code) == quota:
                    break
            observed.update(ids)
            page += 1
        if _selected(run, code) == quota:
            _category_outcome(run, category, "quota_reached", page - 1)
    return _finish(run)
