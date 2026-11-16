# Dish suggestion and substitution evaluation

Question: for a short list of ingredients, does the dish service show dishes a home cook can actually make, and when it proposes a substitute for a missing ingredient, is the substitute one the server's own table allows?

Scope: the AI-backed endpoints `POST /dishes/suggest` and `POST /dishes/adapt` of the dish-list server (no recipe database; a closed list of 130 student dishes with key ingredients, equivalents, a substitution table and combinations). The model only chooses dishes from candidates the server computed and words substitutions the server allowed; `have` and `missing` are computed by the server.

## Files

| File | Purpose |
| --- | --- |
| `cases.json` | The frozen evaluation set: 48 cases (31 suggest, 17 adapt). |
| `thresholds.json` | Pass thresholds with a plain-language reason each; committed together with the cases, before any run. |
| `run_eval.py` | Runner. Dry run by default; `--provider rules` (no model) and `--provider llm` (real model, needs `--allow-live-api`). |
| `scoring.py` | Pure scoring functions and the threshold comparison. |
| `../../../server/tests/experiments/dish_eval/` | Offline tests with fake service outputs (no network, no model). |

## Set design

Suggest cases (31): 27 valid inputs and 4 invalid ones.

- Valid: lists of one to eight Korean ingredient names for one person, including a single ingredient (두부, 고구마), aliases (달걀 for 계란, 쌀 for 밥, 참치 for 참치캔), duplicates, a blank entry, an unknown item, only basic seasonings (the right answer is an empty list), a list that completes exactly one dish (고구마 → 군고구마; 스파게티면, 마늘, 올리브유, 고추 → 알리오올리오), and a list of eight items.
- Invalid (HTTP 422 expected): empty list, `limit` 0, `limit` 9, 61 entries.

Per valid case: `acceptable_dish_ids` = all dishes that can be made with at most one missing key ingredient (computed from the dish list and table with the server's rules for basic seasonings and equivalents, then written down; a test re-derives it); `must_not_include` = up to six dishes that share an ingredient with the input but need three or more other key ingredients (only for inputs where many better dishes exist).

Adapt cases (17): 15 valid, 2 invalid. Each valid case names a dish, the owned ingredients and an outcome class:

| Class | Meaning |
| --- | --- |
| `allowed_substitution` | at least one missing key or optional ingredient has a table option the user can make; expected (missing → uses) pairs are listed |
| `allowed+skip` | as above, plus other missing items that are optional and have no option (to be skipped) |
| `skip_ok_only` | only optional items are missing and none has an option |
| `empty_with_note` | a required item is missing and the table has no option: empty list and the standard note |
| `nothing_missing` | nothing is missing: empty list and the standard note |

Invalid adapt cases: an unknown dish id and an empty ingredient list.

## Labelling method and limits

- The labels were written from the dish data and the table rules before any model output or baseline output existed. One person-equivalent labeller (an AI assistant); the set is a **one-reviewer draft** until the team reads it.
- The dish list and the substitution table were written by the same author as the cases. The evaluation therefore checks that the service is consistent with **our own table**, not that a dish or a substitution is good cooking.
- Suggest cases only test that acceptable dishes appear and bad ones do not; the order inside the top five and the wording of the reason text are not judged.
- 48 cases are small: a threshold of 85% on 27 cases moves by about 4 points per case.
- Cases may be added later; existing cases are not edited after the first results (label errors are noted in Results, not corrected in place).

## Thresholds

See `thresholds.json` for the values and the reason for each. In short:

| Part | Metric | Threshold |
| --- | --- | --- |
| suggest | answers with the expected fields; dish ids from the list | 100% |
| suggest | `have` / `missing` consistent with key ingredients | 100% |
| suggest | at least one acceptable dish in the top 5 | ≥ 85% |
| suggest | share of shown dishes with ≤ 2 missing key ingredients | ≥ 80% |
| suggest | forbidden dishes shown | 0 |
| suggest | invalid inputs refused; valid answer with a failing model (marked `rules`) | 100% |
| adapt | substitutions inside the table; no quantities or steps; `empty_with_note` cases correct | 100% |
| adapt | outcome matches the labelled class | ≥ 90% |
| adapt | unknown dish / empty list refused | 100% |
| adapt | median latency (live runs only) | ≤ 5 s |

Not thresholds, but reported: cost per request, model calls, the rules-only baseline next to the model result, and the share of suggest answers marked `llm` versus `rules`.

A suggestion is judged "invented quantity or step" if its text has a digit, a unit word (술, 컵, g, 인분 …) or a cooking-step word (먼저, 볶아, 끓이 …), see `scoring.QUANTITY_OR_STEP`. Matching never relies on exact text alone: ids and sets are compared, and note text is compared only for the two fixed notes.

## Reproduce

From the repository root:

```sh
uv sync --project server --locked
# plan only: case count, model calls, estimated cost (no call)
PYTHONPATH=server:research uv run --project server --locked python -m experiments.dish_eval.run_eval
# deterministic baseline, no model
PYTHONPATH=server:research uv run --project server --locked python -m experiments.dish_eval.run_eval --provider rules
# real model (billed): one call at most per valid case
PYTHONPATH=server:research uv run --project server --locked python -m experiments.dish_eval.run_eval --provider llm --allow-live-api
```

The live run reads `OPENROUTER_API_KEY` from the environment or `~/.config/mylittlechef/openrouter.env`, never prints it, and uses `google/gemini-2.5-flash-lite` at temperature 0 through the service's own client. It calls the service code in process (no HTTP). Summaries go to the ignored `data/dish-eval/`.

Offline tests: `cd server && uv run --locked pytest tests/experiments/dish_eval`.

Settings recorded in every summary: date, provider, model, temperature, max tokens, commit and whether the tree was dirty, SHA-256 of `cases.json`, `thresholds.json` and the dish list, SHA-256 of the prompts and response schemas, Python version, the exact command, token counts, calls and cost (default price 0.10 / 0.40 USD per million input / output tokens).

## Results

Not run yet.
