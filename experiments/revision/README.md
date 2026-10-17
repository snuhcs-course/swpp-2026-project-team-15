# AI Recipe Revision Experiment

This experiment evaluates whether an LLM can adapt a recipe to available refrigerator
ingredients while preserving the original dish's identity. It saves feasibility
decisions, reasons, revised ingredients, quantities and cooking steps for human review.
Recipes are loaded from local SQLite; filtering rules do not reselect the experiment cases.

- Preserve original recipes while allowing ingredient omission/substitution, serving
  and quantity adjustments, and corresponding cooking-step changes.
- Instruct the model to use only the supplied inventory and refuse when the dish's
  identity or basic food safety cannot be maintained.
- Validate response structure automatically; assess ingredient compliance, dish
  identity and cookability through human review.
- Exclude allergy functionality and actual cooking trials.

## 1. Experiment conditions

Compare 16 fixed recipes under two inventories, producing 32 cases in total.
Each CLI invocation selects either E0 or E1.

| Condition | Available ingredients (normalized ingredient IDs in parentheses) |
| --- | --- |
| AI-E0 | 김치(70), 밥(223), 계란(32), 소금(284), 설탕(282), 식용유(313), 후추(554) |
| AI-E1 | E0 + 양파(345), 간장(9), 두부(147) |

All listed ingredients, including seasonings, are considered available. Owned
quantities are unknown. Recipe and ingredient names below match the Korean DB records.

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

## 2. Setup

Use Python 3.11 or later. Run all commands in **Bash or Git Bash from the project root**.
The local database `data/recipes/recipes.sqlite3` must exist; the runner opens it read-only.

```bash
python -m pip install -r server/requirements.txt
```

For live API calls, prepare the environment file. This command preserves an existing file.

```bash
cp -n server/.env.example server/.env
```

Set the following values in `server/.env`. Replace the example endpoint and model
with values supported by your provider.

| Environment variable | Value |
| --- | --- |
| `REVISION_LLM_ENDPOINT` | Chat Completions-compatible HTTPS API URL |
| `REVISION_LLM_MODEL` | Model supporting Structured Outputs |
| `REVISION_LLM_API_KEY` | API authentication key |

The runner loads `server/.env` automatically; existing environment variables take
precedence. `.env` is ignored by Git. Mock runs need neither `.env` nor an API key.

## 3. Running experiments

### Mock runs

Defaults: **Mock / E0 / recipe 9**.

```bash
python -m experiments.revision.run_experiment
```

The default Mock returns a canned refusal labeled `MOCK ONLY` to exercise the
execution pipeline. Its responses do not measure feasibility or model quality.

```bash
# Run recipe 421 under E1
python -m experiments.revision.run_experiment --experiment-num 1 --recipe-id 421

# Run all 16 recipes under E0
python -m experiments.revision.run_experiment --experiment-num 0 --all
```

### Live API runs for E0 and E1

Each command makes up to 16 paid API calls, sending original recipes and the inventory
to the configured API. Each invocation creates a separate result directory.

```bash
# E0: 16 cases
python -m experiments.revision.run_experiment \
  --provider chat-completions \
  --allow-live-api \
  --experiment-num 0 \
  --all

# E1: 16 cases
python -m experiments.revision.run_experiment \
  --provider chat-completions \
  --allow-live-api \
  --experiment-num 1 \
  --all
```

For a single recipe, replace `--all` with an option such as `--recipe-id 9`.

| Main option | Default / description |
| --- | --- |
| `--experiment-num` | `0` (E0) by default; `1` selects E1 |
| `--recipe-id` | `9` by default; selects one recipe from the fixed list |
| `--all`, `-all` | All 16 recipes under the selected condition; mutually exclusive with `--recipe-id` |
| `--provider` | `mock` (default) or `chat-completions` |
| `--allow-live-api` | Required for live API calls |
| `--model` | Overrides the model configured through the environment |
| `--db` | `data/recipes/recipes.sqlite3` |
| `--output-dir` | `data/recipes/revision-experiments/` |

See help for additional options such as `--timeout`, `--temperature`,
`--max-completion-tokens` and `--mock-responses`.

```bash
python -m experiments.revision.run_experiment --help
```

## 4. Results and human evaluation

After completion or an error stop, inspect the directory printed to the console.
Case IDs use `AI-E<condition>-<recipe-id>`. All files from one run share a directory.

```text
data/recipes/revision-experiments/<run-id>/
  metadata.json
  AI-E0-9.json
  AI-E0-18.json
  ...
  results.csv
  evaluation.csv
```

| File | Contents |
| --- | --- |
| `metadata.json` | Planned cases, model/prompt configuration, DB identity, completion and stopping reason |
| `<case-id>.json` | Original recipe, inventory, request, raw/parsed AI response or error |
| `results.csv` | Feasibility decisions, reasons and case JSON filenames |
| `evaluation.csv` | Blank human evaluation fields, reviewer and notes |

Fill in `evaluation.csv` after the run finishes or stops. CSV files use UTF-8 with BOM.

| Outcome | Decision validity | Ingredient compliance | Source fidelity | Cookability |
| --- | --- | --- | --- | --- |
| `revised` - feasible | O/X | O/X | 1-3 | 1-3 |
| `refused` - infeasible | O/X | N/A | N/A | N/A |
| Operational error | N/A | N/A | N/A | N/A |

Check ingredient compliance in both the ingredient list and cooking instructions.
Assess cookability from the text without an actual cooking trial. Successful parsing
does not establish recipe correctness or food safety.

### Failure policy

- Save valid `refused` judgments as normal results and continue to the next case.
- On the first `api_error`, `response_format_error` or `revision_error`, save prior results and the
  failure reason, then stop the entire run.
- Record unattempted cases only in metadata; do not fabricate evaluation rows.
- Automatic retries, response repair and resuming stopped runs are unsupported.
  A new invocation writes to a new directory.

## 5. Error diagnostics and tests

Use the same runner for a single-case API check. Defaults are Mock / E0 / recipe 9;
live calls require both API options shown below.

```bash
python -m experiments.revision.run_experiment \
  --provider chat-completions \
  --allow-live-api \
  --experiment-num 0 \
  --recipe-id 9
```

Successful live or Mock outcomes, including valid refusals, save ordinary experiment
results without diagnostics or compatibility flags. Inputs, requests, responses and
available usage metadata are still retained. No separate diagnostic mode is needed.

On an error, the case JSON includes `diagnostics.stage` and a sanitized
`diagnostics.reason`. Request failures use `api_request`, provider decoding/envelope
failures use `provider_response`, and model JSON/schema failures use `response_parsing`.
Unexpected revision failures are stored as `revision_error` with stage `revision`
and stop the run too. All three error statuses are unscored operational errors.

Preflight or configuration failures occur before a case attempt: diagnostics are
saved in `metadata.json` when possible, without case or evaluation rows. Persistence
failures are recorded there when it remains writable; otherwise the CLI exits with
a sanitized error. API keys, authorization headers and raw provider error bodies
are excluded. Existing historical outputs are preserved.

Offline tests use Mock responses and temporary SQLite databases without real API calls.

```bash
python -m unittest discover -s experiments/revision -p 'test_*.py' -v
```

Reusable revision logic lives in [server/recipe_revision](../../server/recipe_revision/).
See [cases.py](cases.py) for fixed inputs, and [run_experiment.py](run_experiment.py)
and [reports.py](reports.py) for execution and result persistence.
