# AI-assisted with Codex, 2026-11-14; human review pending.
# Detail failure reclassification assisted by Codex, 2026-11-15; reviewed by Soohyun An.
# Simple candidate errors assisted by Codex, 2026-11-15; reviewed by Soohyun An .
"""Deterministic successful source-ID allocation and bounded traversal."""

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


def _allocate_candidate(run, candidate):
    """Record a successful ID once without coupling allocation to error history."""
    manifest = run.snapshot()
    source_id, code = candidate["source_id"], candidate["category_code"]
    if not any(row["source_id"] == source_id for row in manifest["allocations"]):
        manifest["allocations"].append(dict(source_id=source_id, category_code=code))
    for observation in manifest["candidates"]:
        if observation["source_id"] == source_id:
            observation["state"] = "selected"
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
    result = dict(report, status=run._manifest["state"] if stopped else report["status"])
    if code := run._manifest.get("quota_category"):
        category = next(row for row in report["categories"] if row["category_code"] == code)
        result.update(
            requested_category=code,
            category_complete=not stopped and category["selected"] == category["target"],
        )
    return result


def category_scope(categories, manifest, category_code):
    """Validate category priority without I/O, returning the requested traversal.

    Resume also calls this before publishing recovered checkpoints, so an
    invalid operator request cannot mutate an otherwise recoverable run.
    """
    if category_code is not None:
        codes = [row["cat4"] for row in categories]
        if category_code not in codes:
            raise ValueError("Expected an approved --only-category code")
        for previous in categories[: codes.index(category_code)]:
            exhausted = any(
                row["category_code"] == previous["cat4"] and row["reason"] == "exhausted"
                for row in manifest["category_outcomes"]
            )
            selected = sum(
                row["category_code"] == previous["cat4"] for row in manifest["allocations"]
            )
            if selected != previous["quota"] and not exhausted:
                raise ValueError(f"Finish earlier category {previous['cat4']} first")
        return [categories[codes.index(category_code)]]
    return categories


def collect_quotas(run, *, category_code=None):
    """Fill all quotas or one category, preserving source order and saved work.

    Repeated IDs never cause extra detail/image requests or quota inflation.
    A scoped request stops at that category; predecessors must have reached
    quota or exhausted their candidates. Exhaustion never broadens filters.
    """
    categories = category_scope(run.metadata["plan"]["categories"], run._manifest, category_code)
    manifest = run.snapshot()
    manifest["collection_mode"] = "quota"
    if category_code is None:
        manifest.pop("quota_category", None)
    else:
        manifest["quota_category"] = category_code
    run._commit(manifest)
    if run._operator_status() or run._deferred():
        return _finish(run, stopped=True)
    # A finished/exhausted category must not hide a missing derived or image file.
    # Repair historical selections without resetting the newer failure streak.
    for selection in run._manifest["allocations"]:
        if category_code is not None and selection["category_code"] != category_code:
            continue
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
    for category in categories:
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
                if outcome["status"] == "image_validated":
                    _allocate_candidate(run, candidate)
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
