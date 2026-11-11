# AI-assisted with Codex, 2026-11-11; reviewed by Soohyun An
"""Build immutable collection plans without accessing services or loading credentials."""

from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[3]
LIST_URL = "https://www.10000recipe.com/recipe/list.html"
CATEGORIES = (
    ("밑반찬", "63", 100),
    ("메인반찬", "56", 90),
    ("국/탕", "54", 60),
    ("찌개", "55", 30),
    ("면/만두", "53", 60),
    ("밥/죽/떡", "52", 100),
    ("퓨전", "61", 20),
    ("양식", "65", 20),
    ("샐러드", "64", 20),
)
PROTECTED_DIRECTORIES = (
    "server",
    "android",
    "data/recipes",
    "tools",
    "research",
    "scripts",
    "deploy",
    "docs",
    "openspec",
    ".git",
    ".agents",
    ".codex",
    ".aws",
    ".github",
)


def validate_output_dir(output_dir: Path) -> Path:
    """Resolve a destination and reject overlaps with existing source/data roots.

    Ancestors are rejected too, so choosing the repository root cannot later
    allow a collector to write into production directories. Resolution handles
    symlink aliases before checking boundaries. This function creates no files.
    """
    output = output_dir.expanduser().resolve()
    for name in PROTECTED_DIRECTORIES:
        protected = (REPO_ROOT / name).resolve()
        if output == protected or protected in output.parents or output in protected.parents:
            raise ValueError(f"output directory overlaps a protected project path: {output}")
    for ancestor in (output, *output.parents):
        if ancestor.exists() and not ancestor.is_dir():
            raise ValueError(f"output directory or its parent is an existing file: {ancestor}")
    return output


def build_plan(output_dir: Path | None = None) -> Mapping[str, object]:
    """Return an independent, deeply immutable plan for the approved 500 source IDs.

    Relative output paths use the caller's working directory. With no override,
    choose a unique run path under ignored project data. No directory is created,
    no environment file is loaded, and no network or server modules are accessed.
    """
    destination = validate_output_dir(
        output_dir
        if output_dir is not None
        else REPO_ROOT / "data" / "tenkrecipes" / "runs" / uuid4().hex
    )
    categories = tuple(
        MappingProxyType(
            {
                "name": name,
                "cat4": code,
                "quota": quota,
                "list_url": f"{LIST_URL}?cat2=18&cat4={code}&order=reco&page=1",
            }
        )
        for name, code, quota in CATEGORIES
    )
    return MappingProxyType(
        {
            "total": sum(quota for _, _, quota in CATEGORIES),
            "output_dir": str(destination),
            "categories": categories,
        }
    )
