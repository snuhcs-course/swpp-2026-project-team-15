# AI-assisted with Codex, 2026-11-15; human review pending.
"""Local recipe preparation commands independent of the source collector."""

from pathlib import Path

import typer

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


if __name__ == "__main__":
    app()
