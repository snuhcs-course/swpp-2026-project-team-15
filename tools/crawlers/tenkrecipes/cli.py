# AI-assisted with Codex, 2026-11-11; reviewed by Soohyun An
"""Preview plans and parse saved source HTML without fetching source content."""

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


if __name__ == "__main__":
    app()
