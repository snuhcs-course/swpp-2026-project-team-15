# Recipe CSV import (SQLite prototype)

`import_recipes.py` creates a local SQLite database from eight entity CSV files. It uses Python's standard library and leaves the source files unchanged.

## Source data

Put the eight prepared entity CSVs in `data/recipes/`. The current dataset contains:

| CSV file | SQLite table | Rows |
| --- | --- | ---: |
| `Recipe.csv` | `recipe` | 537 |
| `Ingredient.csv` | `ingredient` | 560 |
| `RecipeStep.csv` | `recipe_step` | 2,870 |
| `RecipeIngredient.csv` | `recipe_ingredient` | 5,933 |
| `CookingTool.csv` | `cooking_tool` | 0 |
| `Allergen.csv` | `allergen` | 0 |
| `RecipeCookingTool.csv` | `recipe_cooking_tool` | 0 |
| `IngredientAllergen.csv` | `ingredient_allergen` | 0 |

All eight files are required, including files containing only headers. Counts may change when the source data is updated.

`Ingredient.csv` is the normalized ingredient catalog. `RecipeIngredient.original_name` preserves the source ingredient text, including labels such as `[양념장]`. The importer preserves the supplied IDs and names; it does not normalize synonyms or preparation forms.

`RecipeIngredient.csv` contains 5,933 rows covering all 537 recipes in `Recipe.csv`. Each row has its own `recipe_ingredient_id`, so the same ingredient can appear more than once in a recipe with different quantities. Use distinct `ingredient_id` values for ingredient matching; display quantities from the individual rows. `quantity_text` keeps amounts as written, such as `200g` or `약간`. Eight rows have no amount and import as SQL `NULL`.

`ingredient_type_code` and `ingredient_type` classify each row as `3060001` / `주재료`, `3060002` / `부재료`, or `3060003` / `양념`. They do not identify which cooking step uses the ingredient.

## Build the local database

From the repository root, run:

```bash
python -m server.db.import_recipes
```

To keep the CSVs elsewhere, pass `--csv-dir /path/to/recipes`. The default database path is `data/recipes/recipes.sqlite3`; pass `--db /path/to/recipes.sqlite3` to choose another path. The importer refuses to overwrite an existing database. Choose a new path when rebuilding.

All eight CSV headers are checked before database creation. Blank or whitespace-only cells become SQL `NULL`. IDs and step numbers must be positive integers. Foreign keys are enforced, and a failed import removes only the new database file it created.

## Schema and existing databases

[`schema.sql`](schema.sql) defines the tables and constraints. The recipe and step CSV headers are:

- `Recipe.csv`: `recipe_id,name,description,cuisine_type,category,cooking_time,calories,servings,difficulty`
- `RecipeStep.csv`: `step_id,recipe_id,step_number,instruction,tip`

`recipe.main_image_url`, `recipe.source_url` and `recipe_step.image_url` are no longer part of the schema. Older CSVs containing these columns must use the headers above before import. Recipe metadata, ingredient IDs, quantities and step tips are retained. `recipe_step.step_id` is the primary key; `step_number` gives the order within a recipe.

An existing database already using this schema needs no rebuild. The importer
never migrates or deletes an existing database. The Revision loader ignores
unused URL columns in legacy databases; if physical removal is needed, prepare
and verify a separate database before switching paths. Historical experiment
JSON files retain their original snapshots and are not rewritten.
