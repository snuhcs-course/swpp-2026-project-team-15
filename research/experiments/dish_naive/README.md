# Naive dish selection: the model decides, the server checks names

Question: if the model gets only the dish names and the user's ingredients, and answers with the dishes plus what the user has and lacks, how often is that answer consistent with the user's input, compared with computing have/missing on the server from key ingredients?

This is the design the demo started from. It replaces the server-side key-ingredient calculation, the substitution table and the rules fallback. Video discovery and token cost are separate studies (`../dish_tokens/`).

## Design under test

- Prompt: the dish names (one list) and the user's ingredients. No key ingredients, no categories, no table.
- Answer (strict JSON): `{"dishes":[{"name","have":[...],"missing":[...]}]}`, best first, no fixed count, an empty list is allowed.
- The server drops names that are not in the list and duplicates, keeps the order, and returns `have`/`missing` as the model wrote them (trimmed).
- Model failure: HTTP 502, no fallback.
- Adapt: the model proposes for each missing ingredient a substitute taken from the user's own ingredients, or null. The server checks only the JSON shape and that substitutes come from that list.

## Frozen before running (`criteria.json`)

The 31 suggestion inputs of `../dish_eval/cases.json` (inputs only; the two `limit` cases are dropped), the metrics and the thresholds are fixed in `criteria.json`, committed before any model call of this study. The thresholds apply to the naive path. A model call cap of 80 applies.

Metrics per answer: share of returned names in the dish list; `have` items that are not among the user's ingredients; `missing` items that are among them; non-empty answers when the reference set is not empty; recall and precision against the reference set; share of dishes with at most two missing key ingredients; refusal of malformed input; latency; tokens and cost.

Reference set: dishes with at least one owned key ingredient and at most one missing key ingredient, computed from the dish list by the old rule. The stored answers of the earlier design (hybrid, run 2 of `../dish_eval/`) are scored against the same reference for comparison; they are not subject to thresholds here.

**Ground truth is not human-labelled.** The reference is made by rule from the same list the system uses, so it measures consistency with that list and not how good a dish is for a person. It is also conservative: a dish with two missing ingredients can be a good suggestion.

## Limits

One run at temperature 0, one model, 31 inputs (one case moves a share by about 3 points), one author for the criteria.

## Reproduce

```sh
PYTHONPATH=server:research uv run --project server --locked python -m experiments.dish_naive.run_naive                      # dry run, no call
PYTHONPATH=server:research uv run --project server --locked python -m experiments.dish_naive.run_naive --allow-live-api   # real model calls (key in ~/.config/mylittlechef/openrouter.env)
```

## Results — Run 1 (2026-11-16)

System under test: commit `4fbea49` (naive path, `google/gemini-2.5-flash-lite`, temperature 0, `max_tokens` 2048, one call per case, 27 model calls, about $0.014). Criteria frozen in `52e808f` before any call. Raw results are in the ignored `data/dish-naive/`.

| Metric (threshold) | Naive | Met |
| --- | --- | --- |
| Returned names in the dish list (100%) | 99.7% (1 of 383 names invented) | no |
| `have` items all owned (≥95%) | 94.6% | no (by 0.4 point) |
| `missing` items none owned (≥95%) | 99.2% | yes |
| Non-empty when the reference is not empty (≥90%) | 84.6% | no |
| Recall of the reference set (≥60%) | 33.0% (46.9% over the 22 answered cases) | no |
| Precision against the reference (≥60%) | 32.2% | no |
| Dishes with ≤2 missing by the reference (≥80%) | 73.2% | no |
| Malformed input refused (100%) | 100% | yes |
| Median latency (≤5 s) | 2.4 s | yes |
| Model failure is 502 | unit-tested | yes |

Reported only: input 26,477 and output 27,608 tokens (about 1,000 per call each), no reasoning tokens, no cached tokens. The earlier hybrid answers on the same 27 inputs score recall 66.8% and precision 37.4% against the same reference.

### What failed

- **Output too long: 5 of 27 calls were cut off** (`finish_reason: length` at 2,048 tokens: S04, S09, S15, S17, S18) and returned 502. With no fixed count the model lists 14–44 dishes with `have`/`missing` for most inputs (median 814 output tokens, up to 2,016). These five cases pull recall and the non-empty share down; excluding them the model's recall is 46.9%, still below the threshold. The setting that is wrong is the output budget, not the idea; the token study (`../dish_tokens/`) measures it.
- **Invented `have` items**: with `[두부]` the model returns `김치국` with `have: [김치, 두부]` (15 of 20 dishes claim an ingredient the user does not have), and with `[떡, 어묵, 고추장, 대파]` it returns `두부김치` with `두부, 김치` as owned. It treats "have" as "usually in the dish". The server cannot notice this: it does not know the dish's ingredients.
- **Breadth over fit**: for `[김치, 밥]` the model returns 14 dishes, including `김치찌개`, `김치국` and `김치파스타` that need other main ingredients; precision against the conservative reference is low. Whether a person would accept these dishes was not measured (no human labels).
- One invented name (S26) and 11 repeated names (S07) were dropped by the name check, as designed.

### Limits

Single run at temperature 0, 31 inputs, one model. The reference is rule-made from the same list and counts a dish with two missing ingredients as wrong. The hybrid comparison covers the 27 answered-or-failed inputs of its own run and was produced with another `max_tokens` (1,024) and another prompt.

## Round 2: prompt definition (criteria frozen 2026-11-16, before any call)

Round 1 found that the model reads `have` as "usually in this dish". Round 2 tests whether a prompt that defines `have` as the user's own items, with or without a schema that restricts `have` to those items, fixes this. Variants P0 to P3, the 27 inputs, the adoption rule and the call cap are in `criteria_round2.json`. P3 (no `have`) is measured but cannot be adopted because the app needs `have`. Results are added below after the runs.

### Round 2 results (2026-11-16)

Settings: `google/gemini-2.5-flash-lite`, temperature 0, `max_tokens` 4096, the 27 well-formed inputs, variants and rule of `criteria_round2.json` (frozen in `0fac1ca`, runner `run_round2.py`). **No variant is adopted; the production prompt stays.**

| Variant | Failed calls (of 27) | Input tok | Output tok | Cost per call | Names in list | `have` all owned | `missing` none owned | Non-empty | Recall | Precision | ≤2 missing |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P0 production prompt | 2 (2 cut off) | 981 | 1,248 | $0.000597 | 95.8% | 95.8% | 99.2% | 92.3% | 45.7% | 34.7% | 69.7% |
| P1 `have` defined in the prompt | 4 (4 cut off) | 1,005 | 1,105 | $0.000542 | 99.7% | **100%** | 98.0% | 84.6% | 33.5% | 39.4% | 80.1% |
| P2 P1 + schema enum for `have` | 5 (5 cut off) | 1,005 | 1,154 | $0.000562 | 98.0% | **100%** | 98.2% | 84.6% | 37.1% | 47.7% | 88.6% |
| P3 no `have` (not adoptable) | 3 (3 cut off) | 975 | 1,211 | $0.000582 | 99.9% | n/a | 97.6% | 92.3% | 48.8% | 25.3% | 58.3% |

This is run B. Run A (the same plan, 108 calls, commit `208f963`) lost 15 calls to HTTP 429 (provider rate limit: P0 8, P1 4, P2 3) and was repeated with a retry after 429 (amendment in `criteria_round2.json`, committed before the repeat). Run B needed 10 retried attempts (118 attempts for 108 calls); the first run and the repeat together used 226 attempts and about $0.114.

**Rule outcome.** P1 and P2 each fail four checks: (1) cut-off answers (4 and 5 inputs ran to the 4,096-token limit, against 2 for P0), (2) the share of raw names in the dish list is below 100% (99.7% and 98.0%; P0 95.8%), (3) non-empty answers fall more than 2 points below P0 (84.6% against 92.3%) and (4) so does recall (the cut-off answers count as empty, which dominates both). They pass the `have` check and the precision check. So the rule adopts nothing.

**What the data say anyway**
- **The prompt definition removes the invented `have` items:** all 100% of returned dishes list only owned ingredients with P1 and P2 (P0: 95.8%; run A: 95.2%). The enum in the schema (P2) adds nothing over the prompt definition on `have`, and it lowers the share of names in the list (98.0% against 99.7%).
- **The truncations are the open problem, not `have`.** Answers that fit are shorter with P1 and P2 (mean 597 and 498 output tokens over the answers that completed, against 1,025 for P0), but the inputs on which the model enumerates dozens of dishes still run to the 4,096-token limit: S04 and S15 with P0; S11, S17, S24, S30 with P1; S01, S07, S09, S11, S26 with P2; S09, S11, S21 with P3. The limit of 4,096, chosen earlier from 12 inputs, is too small for these 27 inputs; raising it would only move the cost because the answer length is set by how many dishes the model lists.
- **Run to run, at temperature 0, the answers do not change:** on the inputs that succeeded in both runs, the returned dish sets are identical (18 of 18 for P0, 19 of 19 for P1, 20 of 20 for P2, 24 of 24 for P3). Differences between variants are therefore differences of the prompt and not of chance on these inputs, but the inputs that fail to complete differ between variants.
- **Recall and precision change with the number of failures** because failed inputs count as empty answers; the comparison of recall between variants mostly measures how many answers were cut off.
- **P3** (no `have`) cannot be adopted (the app shows `have`), and it is not cheaper: its answers are longer (1,211 output tokens) because the model lists more dishes.

### Limits (round 2)

One run per variant (two for the plan above), 27 inputs, one model. The reference set is made by rule from the same dish list, not by people. A rate-limit failure is not a result of the variant, but the cut-off answers are. The enum schema depends on the provider enforcing it; it accepted every request.

## Round 2b: output cap 8192 (criteria frozen 2026-11-16, before any call)

Round 2 compared the production prompt (P0) with the prompt that defines `have` as the user's own items (P1) at an output cap of 4,096 tokens. 2 to 5 of the 27 inputs were cut off and counted as empty, so the comparison measured truncations more than prompts. Round 2b repeats P0 and P1 on the same 27 inputs with the cap raised to 8,192 for both. The adoption rule, the numbers recorded without thresholds (how many dishes the model returns, cost, latency) and the call cap are in `criteria_round2b.json`. Results are added below after the runs.

### Round 2b results (2026-11-16)

Settings: `google/gemini-2.5-flash-lite`, temperature 0, `max_tokens` 8192 for both prompts, the 27 well-formed inputs, rule of `criteria_round2b.json` (frozen in `e4191fb`, runner `run_round2b.py` in `d6ce049`; run on commit `d6ce049`). 54 calls, 60 attempts (6 retries after HTTP 429), about $0.039. **P1 is not adopted; the production prompt and the 4,096-token cap stay.**

| Variant | Failed calls (of 27) | Output tok (mean) | Cost per call | Names in list | `have` all owned | Non-empty | Recall | Precision | ≤2 missing | Dishes returned (min / median / max) | Latency median / max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P0 production prompt | 1 (1 cut off) | 1,457 | $0.000681 | 96.6% | 96.7% | 96.2% | 48.8% | 29.0% | 63.9% | 1 / 18 / 130 | 3.0 s / 20.3 s |
| P1 `have` defined in the prompt | 2 (2 cut off) | 1,618 | $0.000748 | **99.7%** | 98.0% | 92.3% | 57.1% | 37.3% | 74.1% | 1 / 16 / 128 | 2.6 s / 19.8 s |

**Rule outcome.** P1 passes four checks (names in the list ≥ P0, recall and precision ≥ P0 − 2 points, cost ≤ 1.15 × P0: $0.000748 against $0.000681) and fails three: (1) two answers (S24, S30) still ran to the 8,192-token limit, (2) `have` is 98.0%, below the 99% floor (the 100% of round 2 was measured on fewer, shorter answers), (3) non-empty answers are 92.3% against 96.2% (the two cut-off answers count as empty). Because P0 itself has a cut-off answer at 8,192 (S15), the "raise only the cap" branch of the rule does not apply either; the server stays as it is.

**What the data say anyway**
- **Raising the cap does not remove the truncations; the cause is the answer length.** Without a count limit the model sometimes lists nearly the whole dish list: 130 of 130 dishes for `달걀, 쌀` (P0, S04, 5,633 output tokens), 118 and 128 for P1 on S11 and S17. The cut-off answers are inputs where that listing did not finish within 8,192 tokens (P0: S15, which lists `김치, 김치, 밥, 밥`; P1: S24, S30). Three calls of the first-run list were 20 s or longer, close to the service's 30 s timeout for one model call.
- **Median answers are short in both prompts** (18 and 16 dishes); the distribution has a heavy tail, so the cost per call is set by a few inputs.
- **P1 improves the quality of what is returned** (names in the list 99.7% against 96.6%, `have` 98.0% against 96.7%, precision 37.3% against 29.0%) without raising the cost beyond the 15% allowance, but one run of 27 inputs cannot separate this from the cut-off answers, which count as empty and dominate recall and non-empty.
- Run-to-run variation was not repeated for 8,192; the 4,096 runs showed identical answers on repeated inputs.

### Limits (round 2b)

One run per variant at temperature 0, 27 inputs (one case moves a share by about 3 points), one model. The reference set is rule-made from the dish list, not by people. Retries after HTTP 429 are not a result of the variant. Two of the three truncations are in P1, one in P0, which is too few to rank the prompts on robustness.
