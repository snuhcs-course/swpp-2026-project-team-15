"""Convert manually downloaded originals into app-sized WebP assets."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

SIZES = {"thumb": (300, 75), "list": (600, 78), "detail": (1200, 80)}
FIELDS = ("recipe_id", "pixabay_id", "user", "user_id", "page_url", "tags")

def load_selections(files: list[Path]) -> dict[int, dict[str, str]]:
    selected: dict[int, dict[str, str]] = {}
    for path in files:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                try:
                    selected[int(row["recipe_id"])] = row
                except (KeyError, TypeError, ValueError) as exc:
                    raise ValueError(f"Invalid selection row in {path}: {exc}") from exc
    return selected

def process(files: list[Path], root: Path, force: bool = False) -> dict[str, Any]:
    selections = load_selections(files)
    out = root / "output" / "images"
    out.mkdir(parents=True, exist_ok=True)
    missing: list[int] = []
    processed: set[int] = set()
    skipped = 0
    attribution: dict[str, Any] = {}
    placeholders: dict[str, str] = {}
    for recipe_id, row in selections.items():
        originals = [root / "downloads" / f"{recipe_id}.{ext}" for ext in ("jpg", "jpeg", "png", "webp")]
        source = next((p for p in originals if p.is_file()), None)
        if source is None:
            missing.append(recipe_id)
            continue
        with Image.open(source) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")
            for name, (width, quality) in SIZES.items():
                target = out / f"{recipe_id}_{name}.webp"
                if target.exists() and target.stat().st_mtime >= source.stat().st_mtime and not force:
                    skipped += 1
                    continue
                resized = image.copy()
                if resized.width > width:
                    height = max(1, round(resized.height * width / resized.width))
                    resized = resized.resize((width, height), Image.Resampling.LANCZOS)
                resized.save(target, "WEBP", quality=quality)
            processed.add(recipe_id)
        attribution[str(recipe_id)] = {"pixabay_id": int(row.get("pixabay_id") or 0),
            "user": row.get("user", ""), "user_id": int(row.get("user_id") or 0),
            "page_url": row.get("page_url", ""), "source": "Pixabay"}
        try:
            from blurhash import encode
            placeholders[str(recipe_id)] = encode(image, x_components=4, y_components=3)
        except ImportError:
            pass
    base = root / "output"
    base.mkdir(exist_ok=True)
    attr_path = base / "attribution.json"
    try:
        old = json.loads(attr_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        old = {}
    old.update(attribution)
    attr_path.write_text(json.dumps(old, ensure_ascii=False, indent=2), encoding="utf-8")
    if placeholders:
        p_path = base / "placeholders.json"
        try:
            old_hashes = json.loads(p_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            old_hashes = {}
        old_hashes.update(placeholders)
        p_path.write_text(json.dumps(old_hashes, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"processed": len(processed), "skipped": skipped, "missing": missing,
            "bytes": sum(p.stat().st_size for p in out.glob("*.webp"))}
