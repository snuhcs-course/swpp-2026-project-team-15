# Local Filtering Experiment

This standalone runner compares deterministic filtering rules over the imported SQLite recipe database. The reusable logic is in `server/recipe_filtering`; it imports only the Python standard library and has no Django, database, or filesystem dependency. The runner adapts SQLite rows into those plain Python data structures.

The runner opens SQLite in read-only mode. It does not change the database, CSVs, or importer.

## Run

From the repository root, provide the refrigerator's normalized ingredient IDs:

```powershell
python experiments/filtering/run_experiment.py --fridge-ids 70 223 32 284 282 313 554 345 9 147
```

- Note: The ingredient IDs represent the following normalized ingredients: 김치(70), 밥(223), 계란(32), 소금(284), 설탕(282), 식용유(313), 후추(554), 양파(345), 간장(9), 두부(147).

The default database is `data/recipes/recipes.sqlite3`. D-rule thresholds default to `0.25`, `0.5`, and `0.75`; these are experiment parameters, not selected product rules. Override them and choose a separate output directory as needed:

```powershell
python experiments/filtering/run_experiment.py `
  --db data/recipes/recipes.sqlite3 `
  --fridge-ids 70 223 32 345 `
  --d-thresholds 0.4 0.6 `
  --output-dir data/recipes/filtering-experiments/run-01
```

The default output directory is `data/recipes/filtering-experiments/`, which is covered by the repository's existing `data/` ignore rule.

## Experiment Configurations (E0, E1, E2)

Three experimental configurations are used to compare filtering behavior under different refrigerator inventories and matching policies.

| Experiment | Refrigerator Ingredients (Name and ID)                                    | Excluded Match Ingredients                   | Purpose                                                                     |
| ---------- | ------------------------------------------------------------------------- | -------------------------------------------- | --------------------------------------------------------------------------- |
| E0         | 김치(70), 계란(32), 밥(223), 소금(284), 설탕(282), 식용유(313), 후추(554) | None                                         | Evaluate filtering with a minimal refrigerator inventory.                   |
| E1         | E0 + 양파(345), 간장(9), 두부(147)                                        | None                                         | Observe how additional available ingredients affect candidate selection.    |
| E2         | Same as E1                                                                | 소금(284), 설탕(282), 식용유(313), 후추(554) | Evaluate filtering when basic seasonings do not contribute to match counts. |

E2 uses the same physical refrigerator inventory as E1. The four excluded ingredients remain available but do not contribute to match numerators. Ingredient counts, coverage denominators, and matched/missing ingredient displays remain unchanged.

All three configurations use the same filtering rules and default D-rule thresholds (`0.25`, `0.5`, `0.75`).

### Running the Experiments

Run each configuration from the repository root.

**E0: Minimal refrigerator**

```powershell
python experiments/filtering/run_experiment.py --fridge-ids 70 32 223 284 282 313 554 --output-dir data/recipes/filtering-experiments-e0
```

**E1: Expanded refrigerator**

```powershell
python experiments/filtering/run_experiment.py --fridge-ids 70 32 223 284 282 313 554 345 9 147 --output-dir data/recipes/filtering-experiments-e1
```

**E2: Expanded refrigerator with basic seasoning exclusions**

```powershell
python experiments/filtering/run_experiment.py --fridge-ids 70 32 223 284 282 313 554 345 9 147 --excluded-match-ids 284 282 313 554 --output-dir data/recipes/filtering-experiments-e2
```

Each configuration writes its results to a separate output directory to prevent overwriting results from other experiments.

## Rules

- **Baseline:** total matches >= 2 AND main matches >= 1.
- **A:** total matches >= 1.
- **B:** general matches >= 1.
- **C:** general matches >= 2 OR main matches >= 1.
- **D(t):** general ingredient coverage >= `t`.

General ingredients are main and secondary ingredients, excluding seasonings. Ingredient IDs are deduplicated within each recipe. For conflicting type rows on the same recipe and normalized ingredient ID, metrics use the existing experiment's priority: main > secondary > seasoning. Unknown types contribute to total counts and coverage only. Coverage with a zero denominator is `null`; D therefore rejects recipes with no classified general ingredients.

All listed rules and the type-priority policy are experiment choices for comparison, not finalized service behavior.

## Classification diagnostics

The runner does not infer semantic errors from ingredient names or source types.

- `type_conflicts.csv` lists multiple source types for the same `(recipe_id, ingredient_id)` pair. Main/seasoning conflicts are flagged separately.
- `type_variations_across_recipes.csv` lists normalized ingredients assigned different types in different recipes; this is distinct from a within-recipe conflict.
- `type_conflict_sensitivity.csv` shows a counterfactual where main/seasoning conflicts are treated as seasoning. It is a sensitivity view, not a claim that the source's main label is wrong.
- `semantic_reviews.csv` and `semantic_review_impact.csv` are populated only if a human-reviewed annotation CSV is provided. No semantic correction is assumed by default.

Annotation CSV format:

```csv
ingredient_id,semantic_type,reason
123,양념,Manually reviewed against the ingredient definition
```

Supported `semantic_type` values are `주재료`, `부재료`, `양념` (or `main`, `secondary`, `seasoning`). An annotation explicitly supplies the reviewed type and a reason. The impact file compares decisions after applying all supplied annotations together.

## Outputs

- `candidate_summary.csv`: candidate counts/fractions and candidate-only mean/median total, general, and main coverage.
- `recipe_metrics.csv`: counts, rates, rule decisions, and decision explanations for every recipe.
- `rule_differences.csv`: every recipe with different outcomes for each pair of rules, including both rules' reasons and matching metrics.
- `type_conflicts.csv`, `type_variations_across_recipes.csv`: source classification diagnostics.
- `type_conflict_sensitivity.csv`: decision changes in the explicit conflict counterfactual.
- `semantic_reviews.csv`, `semantic_review_impact.csv`: only explicit, manually reviewed semantic annotations and their impact.
- `metadata.json`: database path, refrigerator IDs, thresholds, and counting policies.

No precision or recall is calculated because no labeled set of revision-feasible recipes has been supplied.

## E2: numerator-only exclusion of basic seasonings

Use E1's ten inventory IDs and omit sugar, salt, oil, and pepper from match
numerators, including their general/main contributions when classified that
way in the recipe. Denominators and rule definitions stay the same. This is an
experimental switch; default runs use no exclusions.

```powershell
python experiments/filtering/run_experiment.py --fridge-ids 9 32 70 147 223 282 284 313 345 554 --excluded-match-ids 282 284 313 554 --d-thresholds 0.25 0.5 0.75 --output-dir data/recipes/filtering-experiments-e2
```

The ingredient display in `rule_differences.csv` still reflects the physical
inventory: excluded seasonings remain in matched lists and are not marked as
missing. Thus list lengths can exceed match counts in E2. Metadata records
`excluded_match_ids` and the exclusion policy. All sensitivity calculations
use the same exclusions.

Run the focused regression tests from the repository root:

```powershell
python -m unittest discover -s experiments/filtering -p "test_*.py" -v
```

## Current integrated environment

The current reproducible Python environment is server/pyproject.toml plus server/uv.lock. From repository root, run `uv sync --project server --locked` and invoke the experiment with `uv run --project server --locked python ...`. server/requirements.txt alone is not the full server/experiment environment. The historical data/recipes defaults remain unchanged; for the integrated 560-item catalog explicitly pass `--db data/recipes-iter2/recipes.sqlite3`. Never mix the old 701-item IDs with the new catalog.
