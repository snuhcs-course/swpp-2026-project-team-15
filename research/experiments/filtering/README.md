# Recipe filtering development runner

Read-only SQLite adapter and comparative diagnostics for server/recipe_filtering. FastAPI uses the shared core directly; this CLI and its unchanged regression tests in server/tests/experiments/filtering are development tools excluded from the runtime archive.

From repository root:

```sh
uv sync --project server --locked
uv run --project server --locked python research/experiments/filtering/run_experiment.py --db data/recipes-iter2/recipes.sqlite3 --fridge-ids 70 32 223 345
```

Use the matching560-item catalog; old701-item IDs are incompatible. The original default DB location remains unchanged for compatibility, so pass --db explicitly. --help lists thresholds, exclusions, human annotation and output options. Generated CSV/metadata stay under ignored data/. Labels and threshold comparisons are experimental choices, not measured precision/recall or validated semantic corrections.

## Experiment Configurations (E0, E1, E2)

Three experimental configurations are used to compare filtering behavior under different refrigerator inventories and matching policies.

| Experiment | Refrigerator Ingredients (Name and ID)                                    | Excluded Match Ingredients                   | Purpose                                                                     |
| ---------- | ------------------------------------------------------------------------- | -------------------------------------------- | --------------------------------------------------------------------------- |
| E0         | 김치(70), 계란(32), 밥(223), 소금(284), 설탕(282), 식용유(313), 후추(554) | None                                         | Evaluate filtering with a minimal refrigerator inventory.                   |
| E1         | E0 + 양파(345), 간장(9), 두부(147)                                        | None                                         | Observe how additional available ingredients affect candidate selection.    |
| E2         | Same as E1                                                                | 소금(284), 설탕(282), 식용유(313), 후추(554) | Evaluate filtering when basic seasonings do not contribute to match counts. |

E2 uses the same physical refrigerator inventory as E1. The four excluded ingredients remain available but do not contribute to match numerators. Ingredient counts, coverage denominators, and matched/missing ingredient displays remain unchanged.

All three configurations use the same filtering rules and default D-rule thresholds (`0.25`, `0.5`, `0.75`).


## Rules

- **Baseline:** total matches >= 2 AND main matches >= 1.
- **A:** total matches >= 1.
- **B:** general matches >= 1.
- **C:** general matches >= 2 OR main matches >= 1.
- **D(t):** general ingredient coverage >= `t`.

General ingredients are main and secondary ingredients, excluding seasonings. Ingredient IDs are deduplicated within each recipe. For conflicting type rows on the same recipe and normalized ingredient ID, metrics use the existing experiment's priority: main > secondary > seasoning. Unknown types contribute to total counts and coverage only. Coverage with a zero denominator is `null`; D therefore rejects recipes with no classified general ingredients.

All listed rules and the type-priority policy are experiment choices for comparison, not finalized service behavior.
