"""Command line interface for candidate search, review sheets, processing, and status."""
from __future__ import annotations

import csv
from pathlib import Path

import typer

from .models import load_recipes
from .process import process as run_process
from .search import search_recipe
from .sheet import build_sheet

app = typer.Typer(no_args_is_help=True)
ROOT = Path(__file__).resolve().parents[2]

def _batch(recipes_path: Path, batch: int, size: int):
    if batch < 1 or size < 1:
        raise typer.BadParameter("batch and batch-size must be positive")
    recipes = load_recipes(recipes_path)
    start = (batch - 1) * size
    return recipes[start:start + size]

@app.command()
def search(batch: int = typer.Option(..., min=1), force: bool = False,
           batch_size: int = typer.Option(50, min=1), recipes_file: Path = typer.Option(ROOT / "recipes.json")):
    recipes = _batch(recipes_file, batch, batch_size)
    failures = []
    for index, recipe in enumerate(recipes, 1):
        typer.echo(f"[{index}/{len(recipes)}] {recipe.name_ko} ...")
        try:
            if (force and (ROOT / "cache" / f"{recipe.id}.json").exists()
                    and not typer.confirm("Refresh cache younger than 24 hours?", default=False)):
                continue
            hits, cached = search_recipe(recipe, ROOT / "cache", force, confirm_recent=force)
            typer.echo(f"  {len(hits)} candidates ({'cache' if cached else 'fetched'})")
        except (ValueError, RuntimeError, OSError) as exc:
            failures.append(recipe.id)
            typer.echo(f"  failed: {exc}")
    if failures:
        typer.echo("Failures: " + ", ".join(map(str, failures)))

@app.command()
def sheet(batch: int = typer.Option(..., min=1), batch_size: int = typer.Option(50, min=1),
          recipes_file: Path = typer.Option(ROOT / "recipes.json")):
    path = ROOT / "sheets" / f"sheet_{batch:02}.html"
    build_sheet(batch, _batch(recipes_file, batch, batch_size), ROOT / "cache", path)
    typer.echo(f"Created {path}")

@app.command("process")
def process_command(selection: list[Path] = typer.Option(None, "--selection"), force: bool = False):
    files = selection or sorted((ROOT / "selections").glob("*.csv"))
    result = run_process(files, ROOT, force)
    typer.echo(f"Processed {result['processed']}, skipped {result['skipped']}, missing originals: {result['missing']}, output bytes: {result['bytes']}")
    try:
        import blurhash  # noqa: F401
    except ImportError:
        typer.echo("Optional blurhash library is unavailable; placeholders were skipped.")

@app.command()
def status(batch_size: int = typer.Option(50, min=1), recipes_file: Path = typer.Option(ROOT / "recipes.json")):
    recipes = load_recipes(recipes_file)
    selected = {}
    for path in sorted((ROOT / "selections").glob("*.csv")):
        try:
            with path.open(encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f):
                    selected[int(row["recipe_id"])] = row
        except (OSError, ValueError, KeyError):
            continue
    print("batch  searched  selected  downloaded  processed")
    no_original, no_candidates = [], []
    for index in range(0, len(recipes), batch_size):
        chunk = recipes[index:index + batch_size]
        searched = sum((ROOT / "cache" / f"{r.id}.json").is_file() for r in chunk)
        chosen = [r.id for r in chunk if r.id in selected]
        downloaded = [rid for rid in chosen if any((ROOT / "downloads" / f"{rid}.{ext}").is_file() for ext in ("jpg", "jpeg", "png", "webp"))]
        complete = [rid for rid in downloaded if all((ROOT / "output/images" / f"{rid}_{name}.webp").is_file() for name in ("thumb", "list", "detail"))]
        print(f"{index // batch_size + 1:02}     {searched}/{len(chunk)}       {len(chosen)}/{len(chunk)}      {len(downloaded)}/{len(chosen)}       {len(complete)}/{len(downloaded)}")
        no_original.extend(rid for rid in chosen if rid not in downloaded)
        for r in chunk:
            try:
                import json
                if not json.loads((ROOT / "cache" / f"{r.id}.json").read_text(encoding="utf-8")).get("hits"):
                    no_candidates.append(r.id)
            except (OSError, ValueError):
                pass
    print(f"Selected without originals: {no_original}")
    print(f"No candidates: {no_candidates}")

if __name__ == "__main__":
    app()
