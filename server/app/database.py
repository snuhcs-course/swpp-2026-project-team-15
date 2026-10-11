# AI-generated with Claude Code (Opus 5.5), 2026-10-11; reviewed by Jaehyuk Choi.
from pathlib import Path

from sqlalchemy import Engine
from sqlmodel import create_engine


def read_only_sqlite_engine(db_path: Path) -> Engine:
    if not db_path.is_file():
        raise FileNotFoundError(f"Recipe database not found: {db_path}")
    return create_engine(f"sqlite:///file:{db_path}?mode=ro&uri=true")
