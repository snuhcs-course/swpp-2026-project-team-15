# AI-assisted with Codex, 2026-11-11; reviewed by Soohyun An
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


def _source_run(
    output_dir, live, *, resume_run, category="63", page=1, max_wait=60.0, run_budget=120.0
):
    """Execute one source page or drain saved candidates; never allocate quotas."""
    if not live:
        raise typer.BadParameter("Network access requires --live", param_hint="--live")
    from .fetching import HttpClient
    from .workflow import PARSER_VERSION, SCHEMA_VERSION, CollectionRun

    try:
        plan = build_plan(output_dir)
        client = HttpClient(live=True, max_wait=max_wait, run_budget=run_budget)
        options = dict(
            plan=plan, client=client, parser_version=PARSER_VERSION, schema_version=SCHEMA_VERSION
        )
        if resume_run:
            run = CollectionRun.resume(**options)
        else:
            if category not in {row["cat4"] for row in plan["categories"]} or page < 1:
                raise ValueError("Expected a configured category and positive page")
            run = CollectionRun.create(**options)
            result = run.fetch_list(category, page)
            if result["status"] in ("blocked", "deferred", "failed"):
                typer.echo(json.dumps(dict(output_dir=plan["output_dir"], **result)))
                raise typer.Exit(1)
        run.resume_pending(include_images=True)
        snapshot = run.snapshot()
        typer.echo(
            json.dumps(
                dict(
                    output_dir=plan["output_dir"],
                    state=snapshot["state"],
                    reason=snapshot["reason"],
                    parsed_details=sum(
                        row["state"] == "parsed" for row in snapshot["details"].values()
                    ),
                    validated_images=sum(
                        row["state"] == "image_validated" for row in snapshot["images"].values()
                    ),
                    acquisition_complete=False,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
        if snapshot["state"] in ("blocked", "deferred", "failed"):
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
) -> None:
    """Save one list page, candidate details and validated thumbnails; quotas come later."""
    _source_run(
        output_dir,
        live,
        resume_run=False,
        category=category,
        page=page,
        max_wait=max_wait,
        run_budget=run_budget,
    )


@app.command()
def resume(
    output_dir: Path = typer.Option(..., help="Existing run directory."),
    live: bool = typer.Option(False, "--live", help="Explicitly enable pending source requests."),
    max_wait: float = typer.Option(60.0, help="Must match the saved network policy."),
    run_budget: float = typer.Option(120.0, help="Must match the saved network policy."),
) -> None:
    """Verify a saved run and process its recorded candidates without fetching new pages."""
    _source_run(output_dir, live, resume_run=True, max_wait=max_wait, run_budget=run_budget)


if __name__ == "__main__":
    app()
