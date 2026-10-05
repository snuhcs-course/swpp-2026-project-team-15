# Recipe CSV import (SQLite prototype)

`import_recipes.py` creates a new local SQLite database from the eight entity CSV files. It uses only Python's standard library. The source CSV files are read without modification.

From the repository root, put the eight CSV files in `data/recipes/` and run:

```powershell
python server/db/import_recipes.py
```

Alternatively, keep the CSVs elsewhere and pass their directory:

```powershell
python server/db/import_recipes.py --csv-dir "C:\path\to\recipes"
```

The default output is `data/recipes/recipes.sqlite3`. To choose another file, add `--db "C:\path\to\recipes.sqlite3"`. The script refuses to overwrite an existing database. Delete or rename a *generated test database* before rebuilding it; do not point the script at an existing database containing work you need to keep.

All eight CSV headers are checked before any database is created. Blank or whitespace-only CSV cells become SQL `NULL`. IDs and step numbers must be positive integers. Foreign keys are enforced, and a failed import removes only the new database file it created. The current files yield 537 `recipe` rows and 2,870 `recipe_step` rows; the other six files contain headers only.

`schema.sql` is a first SQLite schema for validating CSV import and raw SQL queries. It is not yet a SQLAlchemy model or an Alembic migration. The SQL table names use `snake_case`; column names match the CSV headers. `recipe_step.step_id` is the primary key because two `(recipe_id, step_number)` pairs repeat in the current source data.

The repository currently ignores `data/`, so the CSVs and generated SQLite file stay local. Record the CSV source and sharing terms before adding data to the public repository.
