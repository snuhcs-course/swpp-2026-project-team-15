# Recipe CSV import (SQLite prototype)

`import_recipes.py` creates a local SQLite database from eight entity CSV files. It uses Python's standard library and leaves the source files unchanged.

## Ingredient data

Put the eight prepared entity CSVs in `data/recipes/`. `Ingredient.csv` contains 701 distinct names. Bracketed preparation labels such as `[양념장]` were removed from `Ingredient.name` for matching, while the complete source text remains in `RecipeIngredient.original_name`. Synonyms and source typos have not yet been corrected.

`RecipeIngredient.csv` contains 5,933 rows covering all 537 recipes in `Recipe.csv`. Each row has its own `recipe_ingredient_id`, so the same ingredient can appear more than once in a recipe with different quantities. Use distinct `ingredient_id` values for ingredient matching; display quantities from the individual rows. `quantity_text` keeps amounts as written, such as `200g` or `약간`. Eight rows have no amount and import as SQL `NULL`.

`ingredient_type_code` and `ingredient_type` classify each row as `3060001` / `주재료`, `3060002` / `부재료`, or `3060003` / `양념`. They do not identify which cooking step uses the ingredient.

## Build the local database

From the repository root, run:

```powershell
python server/db/import_recipes.py
```

To keep the CSVs elsewhere, pass `--csv-dir "C:\path\to\recipes"`. The default database path is `data/recipes/recipes.sqlite3`; pass `--db "C:\path\to\recipes.sqlite3"` to choose another path. The importer refuses to overwrite an existing database. Choose a new path when rebuilding, or remove only a generated test database you no longer need.

All eight CSV headers are checked before database creation. Blank or whitespace-only cells become SQL `NULL`. IDs and step numbers must be positive integers. Foreign keys are enforced, and a failed import removes only the new database file it created.

The resulting tables contain 537 `recipe` rows, 2,870 `recipe_step` rows, 701 `ingredient` rows and 5,933 `recipe_ingredient` rows. The cooking-tool and allergen tables still contain headers only. `recipe_step.step_id` is the primary key.
