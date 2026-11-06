# AI-generated initial implementation with Codex (GPT-6 Luna Medium),
# 2026-11-05; reviewed by Ahyoon Choi.

"""Command line interface for candidate search, review sheets, processing, and status."""

from __future__ import annotations

import csv
from pathlib import Path

import typer
from assets import generate_url_mapping, write_recipe_csv
from config import TOOLS_ROOT, load_config
from models import load_recipes
from process import process as run_process
from search import search_recipe
from sheet import build_sheet

app = typer.Typer(no_args_is_help=True)


def _configured_path(path: Path | None, fallback: Path) -> Path:
    if path is None:
        return fallback
    return path if path.is_absolute() else (TOOLS_ROOT / path).resolve()


def _selection_files(selection: list[Path] | None, directory: Path) -> list[Path]:
    paths = selection if selection else sorted(directory.glob("*.csv"))
    return [path if path.is_absolute() else (TOOLS_ROOT / path).resolve() for path in paths]


def _batch(recipes_path: Path, batch: int, size: int):
    if batch < 1 or size < 1:
        raise typer.BadParameter("batch and batch-size must be positive")
    recipes = load_recipes(recipes_path)
    start = (batch - 1) * size
    return recipes[start : start + size]


@app.command()
def search(
    batch: int = typer.Option(..., min=1),
    force: bool = False,
    batch_size: int = typer.Option(50, min=1),
    recipes_file: Path | None = typer.Option(None),
):
    config = load_config()
    recipes = _batch(_configured_path(recipes_file, config.recipes_file), batch, batch_size)
    failures = []
    for index, recipe in enumerate(recipes, 1):
        typer.echo(f"[{index}/{len(recipes)}] {recipe.name_ko} ...")
        try:
            if (
                force
                and (config.cache_dir / f"{recipe.id}.json").exists()
                and not typer.confirm("Refresh cache younger than 24 hours?", default=False)
            ):
                continue
            hits, cached = search_recipe(recipe, config.cache_dir, force, confirm_recent=force)
            typer.echo(f"  {len(hits)} candidates ({'cache' if cached else 'fetched'})")
        except (ValueError, RuntimeError, OSError) as exc:
            failures.append(recipe.id)
            typer.echo(f"  failed: {exc}")
    if failures:
        typer.echo("Failures: " + ", ".join(map(str, failures)))


@app.command()
def sheet(
    batch: int = typer.Option(..., min=1),
    batch_size: int = typer.Option(50, min=1),
    recipes_file: Path | None = typer.Option(None),
):
    config = load_config()
    path = config.sheets_dir / f"sheet_{batch:02}.html"
    build_sheet(
        batch,
        _batch(_configured_path(recipes_file, config.recipes_file), batch, batch_size),
        config.cache_dir,
        path,
    )
    typer.echo(f"Created {path}")


@app.command("process")
def process_command(selection: list[Path] = typer.Option(None, "--selection"), force: bool = False):
    config = load_config()
    files = _selection_files(selection, config.selections_dir)
    result = run_process(files, config.downloads_dir, config.images_dir, config.output_dir, force)
    typer.echo(
        f"Processed {result['processed']}, skipped {result['skipped']}, missing originals: {result['missing']}, output bytes: {result['bytes']}"
    )
    try:
        import blurhash  # noqa: F401
    except ImportError:
        typer.echo("Optional blurhash library is unavailable; placeholders were skipped.")


@app.command("map-urls")
def map_urls_command(selection: list[Path] = typer.Option(None, "--selection")):
    config = load_config()
    result = generate_url_mapping(
        _selection_files(selection, config.selections_dir),
        config.images_dir,
        config.mapping_file,
        public_prefix=config.image_url_prefix,
        variant=config.image_variant,
    )
    typer.echo(
        f"Mapped {result['mapped']}, missing {result['missing']}; wrote {result['mapping_file']}"
    )


@app.command("recipe-csv")
def recipe_csv_command():
    config = load_config()
    result = write_recipe_csv(
        config.mapping_file, config.source_recipe_csv, config.output_recipe_csv
    )
    typer.echo(
        f"Wrote {config.output_recipe_csv}: {result['updated']} image URLs for "
        f"{result['recipes']} recipes"
    )


@app.command()
def status(
    batch_size: int = typer.Option(50, min=1),
    recipes_file: Path | None = typer.Option(None),
):
    config = load_config()
    recipes = load_recipes(_configured_path(recipes_file, config.recipes_file))
    selected = {}
    for path in sorted(config.selections_dir.glob("*.csv")):
        try:
            with path.open(encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f):
                    selected[int(row["recipe_id"])] = row
        except (OSError, ValueError, KeyError):
            continue
    print("batch  searched  selected  downloaded  processed")
    no_original, no_candidates = [], []
    for index in range(0, len(recipes), batch_size):
        chunk = recipes[index : index + batch_size]
        searched = sum((config.cache_dir / f"{r.id}.json").is_file() for r in chunk)
        chosen = [r.id for r in chunk if r.id in selected]
        downloaded = [
            rid
            for rid in chosen
            if any(
                (config.downloads_dir / f"{rid}.{ext}").is_file()
                for ext in ("jpg", "jpeg", "png", "webp")
            )
        ]
        complete = [
            rid
            for rid in downloaded
            if all(
                (config.images_dir / f"{rid}_{name}.webp").is_file()
                for name in ("thumb", "list", "detail")
            )
        ]
        print(
            f"{index // batch_size + 1:02}     {searched}/{len(chunk)}       {len(chosen)}/{len(chunk)}      {len(downloaded)}/{len(chosen)}       {len(complete)}/{len(downloaded)}"
        )
        no_original.extend(rid for rid in chosen if rid not in downloaded)
        for r in chunk:
            try:
                import json

                if not json.loads(
                    (config.cache_dir / f"{r.id}.json").read_text(encoding="utf-8")
                ).get("hits"):
                    no_candidates.append(r.id)
            except (OSError, ValueError):
                pass
    print(f"Selected without originals: {no_original}")
    print(f"No candidates: {no_candidates}")


if __name__ == "__main__":
    app()
