# AI-assisted with Codex, 2026-11-11; reviewed by Soohyun An
# Error-policy integration assisted by Codex, 2026-11-14; human review pending.
# Stage 5 commands assisted by Codex, 2026-11-14; human review pending.
# Category-scoped quota commands assisted by Codex, 2026-11-14; human review pending.
"""Offline plan/parse commands and explicit live source snapshot collection."""

import json
from pathlib import Path

import typer

from .config import build_plan

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)


@app.callback()
def main() -> None:
    """Prepare 10000recipe data independently of the application server."""


@app.command()
def plan(
    output_dir: Path | None = typer.Option(None, help="Destination for a future run."),
) -> None:
    """Print the offline collection plan as JSON without creating output files."""
    try:
        planned = build_plan(output_dir=output_dir)
    except (ValueError, OSError, RuntimeError) as exc:
        raise typer.BadParameter(str(exc), param_hint="--output-dir") from exc
    payload = {
        "total": planned["total"],
        "output_dir": planned["output_dir"],
        "categories": [dict(category) for category in planned["categories"]],
    }
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


@app.command()
def parse(
    input_path: Path = typer.Option(..., "--input", file_okay=True, dir_okay=False),
    source_url: str = typer.Option(..., help="Original recipe URL for source identity."),
) -> None:
    """Read local UTF-8 detail HTML and emit JSON without modifying any files."""
    # Keep Beautiful Soup out of imports/help/plan so planning stays lightweight.
    from .parsing import ParseError, parse_recipe

    try:
        html = input_path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        # Plain diagnostics preserve filenames even when Rich would wrap a long path.
        typer.echo(f"Input error: {input_path.name}\n{exc}", err=True)
        raise typer.Exit(2) from exc
    try:
        record = parse_recipe(html, source_url=source_url)
    except ParseError as exc:
        typer.echo(f"Parse error: {exc}", err=True)
        raise typer.Exit(1) from exc
    typer.echo(json.dumps(record, ensure_ascii=False, indent=2))


def _report_run(output_dir, *, publish):
    """Validate local artifacts without opening a live client or repairing files."""
    from .reporting import validate_run, write_report

    try:
        result = (write_report if publish else validate_run)(output_dir)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        typer.echo(f"Report input error: {exc}", err=True)
        raise typer.Exit(2) from exc
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["acquisition_complete"]:
        raise typer.Exit(1)


@app.command()
def validate(output_dir: Path = typer.Option(..., help="Existing run to validate offline.")):
    """Check quotas, originals and decoded thumbnails without changing the run."""
    _report_run(output_dir, publish=False)


@app.command()
def report(output_dir: Path = typer.Option(..., help="Existing run for JSON/CSV review reports.")):
    """Write report.json and review.csv without collecting or modifying originals."""
    _report_run(output_dir, publish=True)


def _source_run(
    output_dir,
    live,
    *,
    resume_run,
    category="63",
    page=1,
    max_wait=60.0,
    run_budget=120.0,
    acknowledge_stop=False,
    full=False,
    only_category=None,
):
    """Run a pilot, a single category quota, or the full approved traversal."""
    if not live:
        raise typer.BadParameter("Network access requires --live", param_hint="--live")
    from .fetching import HttpClient
    from .workflow import PARSER_VERSION, SCHEMA_VERSION, CollectionRun

    try:
        plan = build_plan(output_dir)
        codes = [row["cat4"] for row in plan["categories"]]
        if only_category is not None:
            if full:
                raise ValueError("--full and --only-category are mutually exclusive")
            if only_category not in codes:
                raise ValueError("Expected an approved --only-category code")
            if category != "63" or page != 1:
                raise ValueError("Do not combine --only-category with pilot --category/--page")
            if not resume_run and only_category != codes[0]:
                raise ValueError(f"Start with category {codes[0]}; resume the same run afterward")
        client = HttpClient(live=True, max_wait=max_wait, run_budget=run_budget)
        options = dict(
            plan=plan, client=client, parser_version=PARSER_VERSION, schema_version=SCHEMA_VERSION
        )
        if resume_run:
            run = CollectionRun.resume(**options)
            if acknowledge_stop:
                run.acknowledge_stop()
        else:
            if category not in {row["cat4"] for row in plan["categories"]} or page < 1:
                raise ValueError("Expected a configured category and positive page")
            if full and (category != "63" or page != 1):
                raise ValueError(
                    "--full follows the fixed plan; do not combine with --category/--page"
                )
            run = CollectionRun.create(**options)
            if not full and only_category is None:
                result = run.fetch_list(category, page)
                if result["status"] in ("blocked", "deferred", "failed"):
                    typer.echo(json.dumps(dict(output_dir=plan["output_dir"], **result)))
                    raise typer.Exit(1)
        quota_report = None
        scope = only_category
        if scope is None and not full:
            scope = run.snapshot().get("quota_category")
        if full or scope is not None or run.snapshot().get("collection_mode") == "quota":
            quota_report = run.collect_quotas(category_code=scope)
        else:
            run.resume_pending(include_images=True)
        snapshot = run.snapshot()
        typer.echo(
            json.dumps(
                dict(
                    output_dir=plan["output_dir"],
                    state=snapshot["state"],
                    reason=snapshot["reason"],
                    operator_review_required=snapshot.get("operator_review_required", False),
                    operator_notice=snapshot.get("operator_notice"),
                    network_failure_streak=snapshot.get("network_failure_streak", []),
                    failed_candidates=sum(
                        row["status"] == "failed"
                        for row in snapshot.get("candidate_outcomes", {}).values()
                    ),
                    parsed_details=sum(
                        row["state"] == "parsed" for row in snapshot["details"].values()
                    ),
                    validated_images=sum(
                        row["state"] == "image_validated" for row in snapshot["images"].values()
                    ),
                    selected_count=len(snapshot.get("allocations", [])),
                    categories=quota_report["categories"] if quota_report else [],
                    acquisition_complete=bool(
                        quota_report and quota_report["acquisition_complete"]
                    ),
                    requested_category=scope,
                    category_complete=bool(quota_report and quota_report.get("category_complete")),
                    review_status="review_pending",
                    report_path="report.json" if quota_report else None,
                    review_path="review.csv" if quota_report else None,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
        if snapshot["state"] in ("blocked", "deferred", "failed") or (
            snapshot["state"] == "incomplete"
            and not (quota_report and quota_report.get("category_complete"))
        ):
            raise typer.Exit(1)
    except (OSError, ValueError) as exc:
        typer.echo(f"Collection error: {exc}", err=True)
        raise typer.Exit(1) from exc


@app.command()
def collect(
    output_dir: Path | None = typer.Option(
        None, help="New run directory; existing runs are refused."
    ),
    live: bool = typer.Option(False, "--live", help="Explicitly enable source HTTP requests."),
    category: str = typer.Option("63", help="Approved cat4 code for one source page."),
    page: int = typer.Option(1, min=1),
    max_wait: float = typer.Option(60.0, help="Maximum individual wait in seconds."),
    run_budget: float = typer.Option(
        120.0, help="HTTP time budget in seconds for this invocation."
    ),
    full: bool = typer.Option(False, "--full", help="Fill the fixed nine-category 500-ID plan."),
    only_category: str | None = typer.Option(
        None, help="Fill only this category's quota, then stop; follow the fixed category order."
    ),
) -> None:
    """Collect a pilot, one category quota, or all quotas, with explicit live opt-in."""
    _source_run(
        output_dir,
        live,
        resume_run=False,
        category=category,
        page=page,
        max_wait=max_wait,
        run_budget=run_budget,
        full=full,
        only_category=only_category,
    )


@app.command()
def resume(
    output_dir: Path = typer.Option(..., help="Existing run directory."),
    live: bool = typer.Option(False, "--live", help="Explicitly enable pending source requests."),
    max_wait: float = typer.Option(60.0, help="Must match the saved network policy."),
    run_budget: float = typer.Option(120.0, help="Must match the saved network policy."),
    acknowledge_stop: bool = typer.Option(
        False, "--acknowledge-stop", help="Acknowledge a saved stop after operator review."
    ),
    full: bool = typer.Option(
        False, "--full", help="Continue a pilot toward the fixed 500-ID plan."
    ),
    only_category: str | None = typer.Option(
        None, help="Fill only this category's quota in the existing run, then stop."
    ),
) -> None:
    """Resume the saved scope; choose --only-category or --full to change scope."""
    _source_run(
        output_dir,
        live,
        resume_run=True,
        max_wait=max_wait,
        run_budget=run_budget,
        acknowledge_stop=acknowledge_stop,
        full=full,
        only_category=only_category,
    )


if __name__ == "__main__":
    app()
