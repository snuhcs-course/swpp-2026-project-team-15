# Recipe revision development runner

Offline observation runner for the shared server recipe_revision core. FastAPI does not import it; it and its original regression tests in server/tests/experiments/revision are excluded from the runtime archive. Responses are structurally checked, while people assess recipe quality. No allergy/cooking-safety validation is implied.

The fixed E0–E3 inventories and recipe matrix are documented once in the [regression reference](../../../server/tests/experiments/revision/README.md), which the original tests validate against the runner configuration.

## Run from repository root

```sh
(cd server && uv sync --locked)
PYTHONPATH=research uv run --project server --locked python -m experiments.revision.run_experiment --db data/recipes-iter2/recipes.sqlite3 --recipe-id 9
```

Default provider is an explicitly labeled mock refusal. Add `--all` for the selected matrix or `--experiment-num 1`, `2`, `3` for another condition. Use `--help` for every argument. Only an explicitly authorized live run uses `--provider chat-completions --allow-live-api`, with the existing server environment-file settings. Credentials never enter results or client code.

The default DB path remains the original data/recipes location for compatibility; pass the matching560-item DB explicitly as above. IDs from the old701-item catalog are incompatible. The runner opens SQLite read-only and creates a separate output directory under ignored data/ for each invocation. It preserves prior results, stops on the first operational/schema error and does not retry/resume. Valid refusals continue.

Outputs contain source/request/outcome metadata, results.csv and an initially blank evaluation.csv. Human review records decision validity, ingredient compliance, source fidelity and cookability; parsing success alone is not quality. Existing fixtures/mock transports forbid accidental HTTP calls in tests. Source tests are collected by server/pyproject.toml.
