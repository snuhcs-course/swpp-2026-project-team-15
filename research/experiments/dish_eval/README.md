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

Date 2026-11-16. Code, cases and thresholds as of commit `e5ddfab` (the frozen set; unchanged since). One run each, one model call at most per valid case, temperature 0, `google/gemini-2.5-flash-lite`. No repeats were made, so run-to-run variation is unknown.

| Metric | Threshold | Rules only (no model) | Model |
| --- | --- | --- | --- |
| suggest: expected fields | 100% | 100% pass | 100% pass |
| suggest: ids from the list | 100% | 100% pass | 100% pass |
| suggest: `have`/`missing` consistent | 100% | 100% pass | 100% pass |
| suggest: ≥1 acceptable dish in top 5 | ≥ 85% | 100% pass | 100% pass |
| suggest: shown dishes with ≤ 2 missing | ≥ 80% | 100% pass | 99.2% pass |
| suggest: forbidden dishes shown | 0 | 0 pass | **1 fail** |
| suggest: invalid inputs refused | 100% | 100% pass | 100% pass |
| suggest: valid answer with a failing model | 100% | 100% pass | 100% pass |
| adapt: pairs inside the table | 100% | 100% pass | 100% pass |
| adapt: no invented quantities or steps | 100% | 100% pass | **93.3% fail** (1 of 15) |
| adapt: empty-with-note cases | 100% | 100% pass | 100% pass |
| adapt: outcome matches label | ≥ 90% | 100% pass | 100% pass |
| adapt: unknown dish / empty list refused | 100% | 100% pass | 100% pass |
| median latency | ≤ 5 s | not measured | 1.3 s pass (max 3.1 s) |

Model run: 35 model calls (26 suggest cases with candidates, 9 adapt cases that have a table option; the server answers the other cases without the model), 37,299 input and 9,038 output tokens, about $0.0074 in total (about $0.0002 per call). Suggest answers marked `llm`: 23, marked `rules`: 4 (S09 had no candidates; for S02, S18 and S30 the model's answer was not usable and the server fell back to its ranking; the reason was not inspected). The rules run made no call.

Failure analysis:

- **Forbidden dish (S05, input: 두부 only).** The model's five dishes were 두부조림 and 두부부침 (the two acceptable ones), 두부국, 두부덮밥 (missing 밥, 양파, 대파) and 김치국. Only two dishes need at most one more item for this input, so three slots go to dishes needing more; the model chose 두부덮밥, which is on the forbidden list. The service did not prevent it because the closed-list guard only checks that the id exists. This is a real, small ranking weakness for single-ingredient input; it was not fixed here.
- **Step word (A08, 김치전 with flour and onion).** The suggestion text was "밀가루와 소금을 섞어 사용하세요." The scorer's step-word pattern matches "섞어". The text invents no quantity and no step order, so this is arguably a scorer that is stricter than intended; but the threshold was fixed before the run and the case counts as a failure. Neither the pattern nor the threshold was changed.
- The rules-only baseline passes every threshold, which is expected: the labels were derived with the same matching rules the baseline ranks by. What the comparison shows is that the model adds wording and some reordering without breaking the guards (ids, have/missing, table pairs, empty-note cases), at the cost of the two issues above. It does not show that the model's order is better for users.

Label notes (not corrected in place): none found so far. S09 (only seasonings) has an empty acceptable set by design.

## Run 2: no fixed card count (settings changed)

Date 2026-11-16. This run is **not comparable one to one with Run 1**: the system under test changed (commit `618ea63`, evaluated at `696657c`, clean tree; `cases.json` and `thresholds.json` byte-identical to the frozen commit; scorer patterns untouched).

What changed in the system: `/dishes/suggest` no longer takes a count. The model is told to choose every dish that can reasonably be made, best first, and to return fewer or none instead of filling up; it now sees every dish sharing a key ingredient with the input (no 40-candidate cut). The server still drops unknown or duplicate ids and recomputes `have`/`missing`, but truncates nothing and applies no missing-count cutoff. The rules fallback returns every dish sharing a key ingredient (fewest missing, then name). An empty model answer is an empty list marked `llm`.

What changed in the harness (not in cases, thresholds or scoring patterns): the response-length check against `limit` was removed, and "acceptable dish in top 5" is computed over the **first five of the returned list**; an empty list counts as a miss when acceptable dishes exist. The `limit` field in the frozen cases is still sent but ignored by the server.

Same model and decoding as Run 1 (`google/gemini-2.5-flash-lite`, temperature 0, max tokens 1024). One run each. 37 model calls ($0.0122, 64,708 input and 14,246 output tokens); the rules run made none. About two more calls were spent on a diagnosis afterwards (below), so about 39 in total.

| Metric | Threshold | Run 1 model | Run 2 rules only | Run 2 model |
| --- | --- | --- | --- | --- |
| suggest: expected fields | 100% | 100% pass | 100% pass | 100% pass |
| suggest: ids from the list | 100% | 100% pass | 100% pass | 100% pass |
| suggest: `have`/`missing` consistent | 100% | 100% pass | 100% pass | 100% pass |
| suggest: ≥1 acceptable dish in first 5 | ≥ 85% | 100% pass | 100% pass | 100% pass |
| suggest: shown dishes with ≤ 2 missing (first 5) | ≥ 80% | 99.2% pass | 100% pass | 97.9% pass |
| suggest: forbidden dishes shown (first 5) | 0 | 1 fail | 0 pass | **1 fail** |
| suggest: invalid inputs refused | 100% | 100% pass | **50% fail** | **50% fail** |
| suggest: valid answer with a failing model | 100% | 100% pass | 100% pass | 100% pass |
| adapt: pairs inside the table | 100% | 100% pass | 100% pass | 100% pass |
| adapt: no invented quantities or steps | 100% | 93.3% fail | 100% pass | 93.3% fail |
| adapt: empty-with-note cases | 100% | 100% pass | 100% pass | 100% pass |
| adapt: outcome matches label | ≥ 90% | 100% pass | 100% pass | 100% pass |
| adapt: unknown dish / empty list refused | 100% | 100% pass | 100% pass | 100% pass |
| median latency | ≤ 5 s | 1.3 s pass | n/a | 1.5 s pass (max 3.6 s) |

Suggest answers marked `llm`: 19, marked `rules`: 8 (S09 has no candidates, as before). The returned lists had 1 to 10 dishes when the model answered (S05, 두부 only: 3), and 67 to 114 dishes when the rules fallback answered.

Failure analysis:

- **Invalid inputs refused (new failure, both runs).** Cases S28 (`limit` 0) and S29 (`limit` 9) expect HTTP 422 because Run 1 had a 1..8 range. With no count, `limit` is ignored and the requests succeed. The two cases are frozen and now describe a rule that was removed on purpose; they are kept and the failure is reported, not hidden. Empty list and 61 entries are still refused.
- **Forbidden dish (S05, 두부 only), unchanged.** The model returned 두부부침, 두부국, 두부덮밥. Without padding it returned three dishes instead of five, but still chose 두부덮밥 (forbidden: needs 밥, 양파, 대파). 두부조림, an acceptable dish, was left out. Not fixed.
- **Step word (A08), unchanged.** Same "섞어" pattern case as Run 1; the scorer was not changed.
- **Fallback on large candidate lists (found by inspection, not scored).** In 7 of the 26 model-backed suggest cases (S02, S07, S11, S17, S18, S24, S26; inputs with 67 to 114 matching dishes) the model call ended as "incomplete answer" and the server fell back to the unranked-by-model list. Re-running S02 and S07 once each gave the same error. The likely cause is the 1,024-token output ceiling, which is too small for a long answer when the model may return many dishes (not confirmed: the finish reason was not logged). These cases still pass the metrics because the fallback is a valid answer, so the table hides the loss. This run does not measure the model's behaviour on those inputs.
- The rules baseline passes everything except the removed-range cases, again because the labels follow the same matching rules.

Limits: one run, one model; the first-five metrics say nothing about the quality of the dishes beyond the fifth; 7 of 26 model-backed cases did not reach the model's choice (above).
