# Revision request efficiency and reliability

Compares how the recipe-revision request is built and what happens around the model call, on a fixed case set. It measures input size, model calls per request and how often a delivered answer breaks a rule. Recipe quality is not judged here.

Hypothesis: a compact request, a refusal decided in code before the call, a deterministic post-check and an optional retry reduce input tokens and model calls without delivering more rule-breaking answers.

**Depends on** the recipe-revision pipeline in `server/recipe_revision/{compact,pipeline,prescreen,seasoning,changes}.py` and the assumed-seasoning list in `server/app/recipes/seasonings.py`. Merge after the change that adds them; the tests in `server/tests/experiments/revision_input/` are skipped until then.

## Contents

| File | Purpose |
| --- | --- |
| `cases/test.json`, `cases/heldout.json` | 72 and 60 cases as ids only (recipe id, pantry ids, stratum). No recipe text. |
| `thresholds.json` | Pass criteria, fixed before the final runs. |
| `run_experiment.py` | Runs the arms over a set; mock by default. |
| `checkers.py`, `scoring.py` | Checkers independent of the production post-check; one scored row per call. |
| `criteria.py` | Applies `thresholds.json` with case-level bootstrap intervals. |
| `cases.py` | Loads the manifests; regenerates a set from a local database. |
| `offline_llm.py` | Labelled mock model for plumbing checks. Its numbers are not results. |

## Input needs

The recipe database is private and not in the repository. Pass a local copy with `--db` (read-only). Cases name recipes by id, so the database must be the one the ids come from. A live run needs the server's `REVISION_LLM_*` variables.

## Arms

Same request model and settings for every arm; the first is the baseline.

| Arm | What it does |
| --- | --- |
| `original` | Full-row request, no post-check. |
| `check-only` | Compact request and post-check. |
| `default` | Adds a refusal in code when an ingredient named in the dish name is unavailable (no model call) and a completed change list. These are the shipped defaults. |
| `retry` | `default` plus one retry with feedback after a rejected answer (off by default in the server). |

## Run

From the repository root. The default mode makes no network call.

```sh
uv sync --project server --locked
PYTHONPATH=server:research uv run --project server --locked python -m experiments.revision_input.run_experiment --db data/recipes/recipes.sqlite3 --set test
```

`--set heldout` runs the second set, `--limit N` the first N cases, `--arms` a subset that includes `original`. A live run adds `--provider chat-completions --allow-live-api`; it makes about arms × cases × repeats model calls (default 4 × 72 × 2), so check the model price first (`--price-in`/`--price-out`, USD per million tokens, are used for the cost estimate). Run each set once per final code version and keep the output directory; results land under `data/` (ignored).

Tests, with no network: `cd server && uv run --locked pytest tests/experiments/revision_input`. One test regenerates `cases/test.json` from the database when it is available at `data/recipes-iter2/recipes.sqlite3`.

## Criteria

Candidate arm against `original`, per set, 95% bootstrap intervals over cases (`thresholds.json`):

1. Median input tokens ratio, upper end ≤ 0.60.
2. Revised answers with an unavailable or unknown ingredient id: upper end of the difference ≤ +5 points.
3. Format errors and change-list inconsistencies: upper end of each difference ≤ +3 points.
4. False refusals and false acceptances against the rule-based expectation: upper end of each difference ≤ +5 points.
5. Quality judged by a second model: not evaluated.
6. Heat-treatment steps kept when raw meat or egg remains: lower end of the difference ≥ −2 points.
7. Rejected attempts ≤ 10%.
8. Median latency and cost ratios ≤ 1.

The expected verdict is rule-based: refuse when an ingredient named in the dish name is unavailable, otherwise revise. The `default` arm applies the same rule in code, so its false acceptances are zero by construction; that is not independent evidence.

## Results as measured

Model `google/gemini-2.5-flash-lite`, temperature 0, two repeats per case. Pantry availability follows the `list` seasoning mode with the ten-entry list in use at the time (pepper as `후추` only). Per request, `check-only` / `default` / `retry`:

| | Test (72 cases) | Held-out (60 cases) |
| --- | --- | --- |
| Model calls | 1.00 / 0.62 / 0.72 | 1.00 / 0.72 / 0.83 |
| Input tokens | 1,326 / 843 / 966 | 1,349 / 968 / 1,156 |
| Cost (USD) | 0.00038 / 0.00028 / 0.00031 | 0.00042 / 0.00031 / 0.00036 |
| Rejected attempts | 17.8% / 17.1% / 5.3% | 17.1% / 17.8% / 8.6% |
| False refusals | 5.0% / 5.0% / 8.8% | 8.1% / 8.1% / 13.5% |
| False acceptances | 11.1% / 0% / 0% | 23.5% / 0% / 0% |
| Inconsistent change lists (revised) | 13.5% / 14.7% / 13.9% | 14.7% / 16.7% / 15.6% |
| Delivered rule violations (revised) | 0% / 0% / 0% | 2.9% / 3.3% / 3.1% |

Against `original`, input tokens are 0.65× (test) and 0.67× (held-out) for `default`.

| Criterion | `default` test / held-out | `retry` test / held-out |
| --- | --- | --- |
| 1 Input tokens ≤ 0.60 | fail / fail | fail / fail |
| 2 Unavailable ids | pass / pass | pass / pass |
| 3 Format and consistency | fail / fail | fail / fail |
| 4 False refusals and acceptances | fail / fail | fail / fail |
| 6 Heat steps kept | pass / pass | pass / pass |
| 7 Rejected attempts ≤ 10% | fail / fail | pass / pass |
| 8 Latency and cost | pass / pass | pass / pass |

Re-scoring the stored runs with this module reproduces these values.

## Limits

- Cases are synthetic, one model, no human review of answers. Criterion 5 was not run.
- Cases are drawn from recipe structure, and the expected verdict is a lexical rule on the dish name.
- The sets were used repeatedly during development; the held-out set is the least reused.
- The seasoning list now also contains `통후추` and `흰후추`. The results above predate that and have not been re-run.
- One failure is not caught by the post-check: an ingredient that appears only in the steps and in neither the recipe nor the pantry.
- Latency is measured under concurrent calls.
