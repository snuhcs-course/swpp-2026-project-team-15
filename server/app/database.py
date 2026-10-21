# AI-generated with Claude Code (Opus 5.5), 2026-10-11; reviewed by Jaehyuk Choi.
from pathlib import Path

from sqlalchemy import Engine
from sqlmodel import create_engine


def recipe_engine(database_url: str, db_path: Path) -> Engine:
    if not database_url:
        return read_only_sqlite_engine(db_path)
    if not database_url.startswith("postgresql+psycopg://"):
        raise ValueError("DATABASE_URL must use postgresql+psycopg://")
    return create_engine(
        database_url,
        pool_pre_ping=True,
        isolation_level="REPEATABLE READ",
        connect_args={"connect_timeout": 5, "options": "-c default_transaction_read_only=on"},
    )


def read_only_sqlite_engine(db_path: Path) -> Engine:
    if not db_path.is_file():
        raise FileNotFoundError(f"Recipe database not found: {db_path}")
    return create_engine(f"sqlite:///file:{db_path}?mode=ro&uri=true")
