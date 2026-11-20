# AI-generated with Claude Code (Sonnet 5.5), 2026-11-18; reviewed by Jaehyuk Choi.
"""Paths, key reading and small helpers shared by the dish-recipe data tools."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data" / "dish-recipes"  # untracked: third-party content is never committed
VIDEOS_FILE = DATA_DIR / "dish-videos.json"
INPUTS_DIR = DATA_DIR / "inputs"
MISSING_FILE = INPUTS_DIR / "_missing.json"
COVERAGE_FILE = DATA_DIR / "coverage.json"
CONFIG_DIR = Path.home() / ".config" / "mylittlechef"


def read_key(env_name: str, file_name: str) -> str:
    """Key from the environment, else from a 0600 file in the user's config directory."""
    key = os.environ.get(env_name, "").strip()
    path = CONFIG_DIR / file_name
    if not key and path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith(env_name + "="):
                key = line.split("=", 1)[1].strip().strip("\"'")
    return key


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def load_json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)
