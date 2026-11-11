# AI-assisted with Codex, 2026-11-11; reviewed by Soohyun An
"""Preview collection plans; source fetching is not implemented in stage 1."""

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


if __name__ == "__main__":
    app()
