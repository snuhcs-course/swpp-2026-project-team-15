# AI Recipe Revision Experiment

Evaluate whether an LLM can revise ingredients, quantities and cooking steps using
only the supplied inventory while preserving the original dish. Recipes come from
local SQLite without filtering-based reselection. Responses are checked for structure;
people assess their quality. Allergy functionality and actual cooking are excluded.

## Experiment conditions

E0/E1 compare the 16 recipes below (32 cases). E2/E3 compare garlic preparation
using the same four recipes under both inventories (8 additional cases).
Each CLI invocation selects one condition.

| Condition | Available ingredients (normalized ingredient IDs in parentheses) |
| --- | --- |
| AI-E0 | 김치(70), 밥(223), 계란(32), 소금(284), 설탕(282), 식용유(313), 후추(554) |
| AI-E1 | E0 + 양파(345), 간장(9), 두부(147) |
| AI-E2 (whole) | E1 + 바게트(214), 어묵(349), 밀가루(213), 마늘(169) |
| AI-E3 (minced) | E1 + 바게트(214), 어묵(349), 밀가루(213), 다진마늘(103) |

All listed ingredients, including seasonings, are considered available. Owned
quantities are unknown. Recipe and ingredient names below match the Korean DB records.

### E0/E1 recipes

| Recipe ID | Recipe name |
| --- | --- |
| 9 | 오므라이스 |
| 18 | 두부국 |
| 97 | 계란말이 |
| 112 | 김치적 |
| 114 | 두부김치 |
| 115 | 오믈렛 |
| 118 | 중국식볶음밥 |
| 130 | 두부양념조림 |
| 192 | 김치채소쌈 |
| 194 | 계란말이주먹밥 |
| 216 | 두부오믈렛 |
| 238 | 김치주먹밥 |
| 291 | 김치쌈밥 |
| 299 | 열무비빔밥 |
| 320 | 김치볶음밥 |
| 421 | 양파전 |

### E2/E3 recipes (execution order)

| Recipe ID | Recipe name |
| --- | --- |
| 335 | 마늘빵 |
| 395 | 어묵볶음 |
| 97 | 계란말이 |
| 421 | 양파전 |

E2 and E3 differ only in garlic ID; all other inventory items are identical.
Observe whether the model adapts preparation steps appropriately, using the
existing prompt and human evaluation criteria.

## Setup

Use Python 3.11+ with dependencies from `server/requirements.txt` installed.
The database must exist at `data/recipes/recipes.sqlite3`; it is opened read-only.
Run the commands below in **Bash or Git Bash from the project root**.

For live calls, create `server/.env` using `server/.env.example` as a template and set:

| Variable | Value |
| --- | --- |
| `REVISION_LLM_ENDPOINT` | Chat Completions-compatible HTTPS API URL |
| `REVISION_LLM_MODEL` | Model supporting Structured Outputs |
| `REVISION_LLM_API_KEY` | API authentication key |

The runner loads this file without overwriting existing environment variables.
`.env` is ignored by Git. Mock runs require no API key.

## Run

### Mock: one recipe

```bash
python -m experiments.revision.run_experiment --recipe-id 9
```

### Mock: all recipes in the selected condition

```bash
python -m experiments.revision.run_experiment --all
```

Mock runs check the execution pipeline without network calls. The default response
is a canned `MOCK ONLY` refusal, not an assessment of recipe feasibility.

### API: one recipe

```bash
python -m experiments.revision.run_experiment \
  --provider chat-completions --allow-live-api --recipe-id 9
```

### API: all recipes in the selected condition

```bash
python -m experiments.revision.run_experiment \
  --provider chat-completions --allow-live-api --all
```

API runs send recipes and inventory to the configured provider and may incur costs.
The examples use E0. Select E1, E2 or E3 with `--experiment-num 1`, `2` or `3`.
For E2/E3 single-case runs, choose a recipe from their four-recipe list.

### Options

| Option | Description |
| --- | --- |
| `--experiment-num` | `0` (E0, default), `1` (E1), `2` (E2, whole garlic), `3` (E3, minced garlic) |
| `--recipe-id` | One recipe in the selected condition; default `9` for E0/E1, `335` for E2/E3 |
| `--all`, `-all` | All 16 recipes for E0/E1 or all 4 for E2/E3; mutually exclusive with `--recipe-id` |
| `--provider` | `mock` (default) or `chat-completions` |
| `--allow-live-api` | Required to enable live calls |
| `--model` | Override `REVISION_LLM_MODEL` |
| `--db` | Override the default SQLite path |
| `--output-dir` | Parent directory for new runs; default `data/recipes/revision-experiments/` |
| `--mock-responses` | JSON fixtures for selected cases, original 32 E0/E1 cases or all 40 cases; Mock only |
| `--timeout` | Positive request timeout in seconds; default `60` |
| `--temperature` | Optional live sampling setting; must be supported by the model |
| `--max-completion-tokens` | Optional live output token limit |
| `--help` | Show CLI help |

## Outputs and human evaluation

Each invocation creates an independent `<run-id>/` directory under the output
location. Metadata, case JSONs and CSVs are saved directly inside it.

| File | Contents |
| --- | --- |
| `metadata.json` | Plan, configuration, DB identity, completion and stopping reason |
| `<case_id>.json` | Original recipe, inventory, request, raw/parsed response or error |
| `results.csv` | `run_id`, `case_id`, `recipe_name`, `status`, `reason`, `artifact` |
| `evaluation.csv` | `run_id`, `case_id`, `recipe_name`, four scores below, `reviewer`, `rubric_version`, `notes` |

`recipe_name` is the original name. Case IDs follow `AI-E<condition>-<recipe-id>`.
Join CSVs by `case_id` within one run or `(run_id, case_id)` across runs.
`artifact` is relative to the run directory; CSVs use UTF-8 with BOM.
Historical files are not rewritten.

Fill in `evaluation.csv` after execution finishes or stops:

| Outcome | `decision_validity` | `ingredient_compliance` | `source_fidelity` | `cookability` |
| --- | --- | --- | --- | --- |
| `revised` | O/X | O/X | 1-3 | 1-3 |
| `refused` | O/X | N/A | N/A | N/A |
| Operational error | N/A | N/A | N/A | N/A |

Review ingredient use in both ingredients and steps; judge cookability from text.
Record the reviewer, rubric version and any notes. Parsing success is not a quality score.

Valid refusals continue execution. The first `api_error`, `response_format_error`
or `revision_error` saves prior results and the failure, then stops the run.
Unattempted cases appear only in metadata. No retries, repair or resume are supported.
Sanitized diagnostics are saved only on errors, in the case JSON or in metadata
for failures before an attempt. Credentials are excluded from saved artifacts.

See [cases.py](cases.py) for fixed inputs, [reports.py](reports.py) for CSV generation,
and [server/recipe_revision](../../server/recipe_revision/) for reusable revision logic.
