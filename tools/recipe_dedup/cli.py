# AI-assisted with Codex, 2026-11-15; reviewed by Soohyun An
"""Local recipe preparation commands independent of the source collector."""

from pathlib import Path

import typer

from .review import export_groups
from .selection import export_selection
from .titles import export_titles

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)


@app.callback()
def main() -> None:
    """Prepare local recipe data without network calls or server configuration."""


@app.command()
def titles(
    source_run: Path = typer.Option(..., help="Supplied collection run containing manifest.json."),
    output: Path = typer.Option(..., help="New title CSV outside the source run."),
) -> None:
    """Create a title worksheet for the user to normalize manually."""
    try:
        count = export_titles(source_run, output)
    except (OSError, ValueError) as exc:
        typer.echo(f"Title export error: {exc}", err=True)
        raise typer.Exit(1) from exc
    typer.echo(f"Wrote {count} title rows to {output}")


@app.command()
def groups(
    source_run: Path = typer.Option(..., help="Supplied collection run containing manifest.json."),
    titles: Path = typer.Option(..., help="User-authored title mapping CSV."),
    output: Path = typer.Option(..., help="New review directory outside the source run."),
) -> None:
    """Group exact user titles and create an all-pending duplicate decision worksheet."""
    try:
        report = export_groups(source_run, titles, output)
    except (OSError, ValueError) as exc:
        typer.echo(f"Group export error: {exc}", err=True)
        raise typer.Exit(1) from exc
    typer.echo(
        f"Wrote {len(report['groups'])} candidate groups to {output}; "
        f"unfinished titles: {len(report['unfinished_ids'])}. Duplicate review is pending."
    )


@app.command(name="select")
def select_recipes(
    source_run: Path = typer.Option(..., help="Supplied collection run containing manifest.json."),
    titles: Path = typer.Option(..., help="Completed user-authored title mapping CSV."),
    decisions: Path = typer.Option(..., help="Completed duplicate decision CSV; no pending rows."),
    output: Path = typer.Option(..., help="New selection directory outside the source run."),
) -> None:
    """Export kept recipe copies after validating all titles and duplicate decisions."""
    try:
        report = export_selection(source_run, titles, decisions, output)
    except (OSError, ValueError) as exc:
        typer.echo(f"Selection export error: {exc}", err=True)
        raise typer.Exit(1) from exc
    typer.echo(
        f"Wrote {report['kept_count']} kept recipes; "
        f"excluded {report['excluded_count']} to {output}. "
        "Service suitability is not assessed."
    )


if __name__ == "__main__":
    app()
