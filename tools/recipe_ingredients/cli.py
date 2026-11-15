# AI-generated offline publication CLI with Codex, 2026-11-15; reviewed by Soohyun An
"""Run reviewed ingredient normalization using explicitly supplied local paths."""

from pathlib import Path

import typer

from recipe_ingredients.publication import PublicationError, publish

app = typer.Typer(add_completion=False)


@app.command()
def main(
    selected: Path = typer.Option(..., help="Selected recipe JSON."),
    decisions: Path = typer.Option(..., help="Reviewed ingredient-decision JSON."),
    catalog_dir: Path = typer.Option(..., help="Directory containing the four original CSVs."),
    output: Path = typer.Option(..., help="New destination for the three result JSON files."),
) -> None:
    """Preserve four CSV snapshots and publish the validated ingredient catalog."""
    try:
        report = publish(selected, decisions, catalog_dir, output)
    except PublicationError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from error
    typer.echo(f"Published {report['catalog_count']} ingredients; results: {output.resolve()}")


if __name__ == "__main__":
    app()
