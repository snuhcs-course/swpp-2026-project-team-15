"""Validate an eight-CSV dataset ZIP, then initialize or replace recipe tables atomically."""

import argparse
import json
import os
import sqlite3
import tempfile
import zipfile
from pathlib import Path

import psycopg
from psycopg import sql

from db.import_recipes import TABLES, create_database, read_rows

MAX_BYTES = 64 * 1024 * 1024


def import_zip(url: str, archive: Path, *, replace: bool = False) -> dict[str, int]:
    if not url.startswith("postgresql+psycopg://"):
        raise ValueError("DATABASE_URL must use postgresql+psycopg://")
    if archive.stat().st_size > MAX_BYTES // 2:
        raise ValueError("ZIP exceeds 32 MiB")
    expected = {spec.filename for spec in TABLES}
    with tempfile.TemporaryDirectory() as directory:
        target = Path(directory)
        with zipfile.ZipFile(archive) as source:
            members = [i for i in source.infolist() if not i.is_dir()]
            if len(members) != len(expected) or {i.filename for i in members} != expected:
                raise ValueError("ZIP must contain exactly the eight CSV files at its root")
            if sum(i.file_size for i in members) > MAX_BYTES:
                raise ValueError("Expanded ZIP exceeds 64 MiB")
            for info in members:
                with source.open(info) as handle:
                    data = handle.read(MAX_BYTES + 1)
                if len(data) > MAX_BYTES:
                    raise ValueError("CSV exceeds size limit")
                (target / info.filename).write_bytes(data)
        counts = create_database(target, target / "validated.sqlite3")
        with sqlite3.connect(target / "validated.sqlite3") as check:
            water = check.execute("SELECT name FROM ingredient WHERE ingredient_id=204").fetchone()
            if water not in (("물",), ("Water",)):
                raise ValueError("Dataset must identify water as ingredient 204")
            incomplete = check.execute("""
                SELECT recipe_id FROM recipe r WHERE
                NOT EXISTS (SELECT 1 FROM recipe_step s WHERE s.recipe_id=r.recipe_id) OR
                NOT EXISTS (SELECT 1 FROM recipe_ingredient i WHERE i.recipe_id=r.recipe_id)
                LIMIT 1
            """).fetchone()
            if not counts['recipe'] or incomplete:
                raise ValueError("Dataset contains empty or incomplete recipe sources")
        rows = [(spec, read_rows(target, spec)) for spec in TABLES]
        with psycopg.connect(url.replace("postgresql+psycopg://", "postgresql://", 1)) as conn:
            conn.execute("SET LOCAL lock_timeout = '15s'")
            conn.execute("SELECT pg_advisory_xact_lock(151503)")
            exists = conn.execute("SELECT to_regclass('public.recipe')").fetchone()[0]
            if exists and not replace:
                raise ValueError("Database initialized; use reset explicitly")
            if not exists:
                conn.execute(Path(__file__).with_name('schema.sql').read_text(), prepare=False)
            else:
                # DELETE preserves MVCC snapshots; never drop schema or application data.
                for spec in reversed(TABLES):
                    conn.execute(sql.SQL('DELETE FROM {}').format(sql.Identifier(spec.table)))
            for spec, records in rows:
                statement = sql.SQL('COPY {} ({}) FROM STDIN').format(
                    sql.Identifier(spec.table), sql.SQL(', ').join(map(sql.Identifier, spec.columns)),
                )
                with conn.cursor().copy(statement) as copy:
                    for _, values in records:
                        copy.write_row(values)
        return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--replace', action='store_true')
    args = parser.parse_args()
    try:
        counts = import_zip(os.environ.get('DATABASE_URL', ''), args.archive, replace=args.replace)
    except Exception as exc:
        raise SystemExit(f'Import failed ({type(exc).__name__}); transaction rolled back') from None
    print(json.dumps(counts, sort_keys=True))


if __name__ == '__main__':
    main()
