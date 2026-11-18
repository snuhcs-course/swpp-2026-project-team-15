# Constrained answer formats for dish selection

Question: if the model's answer is limited to the closed vocabularies of the service through structured-output features, which format is the cheapest and the most reliable, and does a helper library (LangChain) change the behaviour or only add code?

Background. The service gives the model the 130 dish names and the user's ingredients and takes back `{name, have, missing}` per dish. The earlier rounds (`../dish_naive/`, `../dish_tokens/`) found that the model sometimes writes names outside the list, `have` items the user did not enter, and answers long enough to be cut off. A *structured output* asks the provider to make the answer follow a JSON schema; an *enum* in that schema lists the only values a field may take, so a conforming answer cannot contain anything else, if the provider enforces it. This study measures whether it does.

## Vocabularies

- Dish names: the 130 names of `server/app/dishes/dishes.json`.
- Ingredient vocabulary for `missing`: the 63 distinct key ingredients of that list, one spelling per synonym group (e.g. 계란, not 달걀).
- `have`: a per-request enum made of the user's own ingredients.

## Formats (details and exact prompts in `criteria.json`)

| Id | Answer | Route |
| --- | --- | --- |
| S0 | `name`, `have`, `missing` as free strings (today's service) | `response_format` json_schema |
| S1 | names only, enum of the 130 names | `response_format` |
| S2 | name enum, `have` enum (user's items), `missing` enum (vocabulary) | `response_format` |
| S3 | name enum, `missing` enum | `response_format` |
| S4 | as S2 | forced function call (`tools` + `tool_choice`) |
| S5a, S5b | as S2 | LangChain `with_structured_output`, `json_schema` and `function_calling` (first 12 inputs) |
| S2n, S2r | as S2 | probes: `strict` false; without `provider.require_parameters` (first 6 inputs) |
| S6 | names of S1; `have`/`missing` computed by the server from the key ingredients | comparison point, no extra call |

## Frozen before running

`criteria.json` (committed before any model call): inputs (the 27 well-formed inputs of the naive study, same scorer and rule-made reference set), prompts, call cap (200; 171 planned), cost cap ($0.30), the definition of a constraint violation and the decision rule: a candidate among S1–S4 qualifies with zero violations, zero cut-off answers, zero failed calls and recall and precision within 2 points of S0 run the same day; the cheapest qualifier wins (near ties go to the shorter client code). S5, the probes and S6 never enter the rule.

**Ground truth is not human-labelled.** The reference set is made by rule from the dish list the system uses, so recall and precision measure agreement with that rule, not how good a dish is for a person.

## Reproduce

```sh
# dry run, no call
PYTHONPATH=server:research uv run --project server --locked python -m experiments.dish_output_formats.run_formats
# live (key in ~/.config/mylittlechef/openrouter.env); LangChain runs in a temporary environment, nothing is installed globally
PYTHONPATH=server:research uv run --project server --locked --with langchain-openai --with langchain-core \
    python -m experiments.dish_output_formats.run_formats --allow-live-api
```

Offline tests: `cd server && uv run --locked pytest tests/experiments/dish_output_formats`.

## Limits

One run per variant at temperature 0, one model, 27 inputs (12 and 6 for the library and probe variants); enum support depends on the provider that serves the request; the reference is rule-made.

## Results (2026-11-18)

Run on commit `c3fd8d9` (criteria and runner frozen in it), `google/gemini-2.5-flash-lite`, temperature 0, `max_tokens` 4096, the 27 inputs. 171 planned calls, every one answered at the first attempt (no HTTP 429), plus two diagnostic calls (recorded as an amendment before they were made, excluded from the tables): 173 of 200. Cost of the run about $0.07. Raw answers are in the ignored `data/dish-formats/`. All requests were served by one provider (Google AI Studio).

**Rule outcome: no candidate qualifies.** S1, S2 and S3 each fail the zero-truncation condition (1, 2 and 1 inputs ran to the 4,096-token limit); S3 also fails precision (0.290 against S0's 0.347 − 0.02); S4 fails the zero-failed-calls condition (5 failed calls) and both recall and precision. No candidate is chosen.

| | S0 free text | S1 names, enum | S2 name+have+missing, enums | S3 name+missing, enums | S4 = S2 as function call |
| --- | --- | --- | --- | --- | --- |
| Names outside the 130 | 24 of 566 | **0** of 455 | **0** of 331 | **0** of 623 | **0** of 553 |
| `have` outside the user's list | 25 of 650 | n/a | **0** of 601 | n/a | **0** of 757 |
| `missing` outside the vocabulary | 84 of 509 | n/a | **0** of 267 | **0** of 670 | **0** of 982 |
| Cut off / failed calls | 2 / 0 | 1 / 0 | 2 / 0 | 1 / 0 | 0 / 5 |
| Input / output tokens (mean) | 981 / 1,248 | 911 / 273 | 988 / 789 | 964 / 706 | 2,211 / 748 |
| Cost per call (from tokens) | $0.000597 | $0.000200 | $0.000414 | $0.000379 | $0.000520 |
| Latency median / p95 | 2.3 / 8.6 s | 0.9 / 2.3 s | 1.9 / 8.5 s | 1.6 / 7.7 s | 1.6 / 8.4 s |
| Recall / precision (reference) | 45.7% / 34.7% | 44.3% / 37.0% | 44.6% / 51.6% | 44.6% / 29.0% | 29.4% / 19.3% (5 failed count as empty) |
| Non-empty when possible | 92.3% | 100% | 96.2% | 96.2% | 84.6% |
| `missing` items none owned | 99.2% | n/a | 91.7% | 91.7% | 95.8% |
| Dishes returned (min / median / max) | 1 / 18 / 44 | 1 / 13.5 / 122 | 1 / 13 / 28 | 1 / 18.5 / 125 | 1 / 7.5 / 130 |
| Repeated names | 81 | 22 | 19 | 67 | 5 |

Vocabulary: 63 ingredient names (the 130 dishes use 63 distinct key ingredients after synonym reduction). Provider-reported cost, where present, is 91–100% of the token-based figure in the full runs.

### What the data say

- **The enum is enforced.** Across S1–S4 and the two probes, more than 5,000 constrained items there was not a single value outside the vocabulary; S0, without enums, had 24 invented dish names, 25 `have` items the user did not enter and 84 `missing` items outside the vocabulary (16.5% of its `missing` items, most often short forms and synonyms such as 파, 빵, 참치, or ingredients outside the key ingredients of the list such as 멸치육수, 국간장, 다진마늘, 물). Enforcement held with `strict` false (S2n) and without `provider.require_parameters` (S2r): on inputs S01–S06 both returned answers identical to S2, so on this provider and model neither flag changed anything. Whether another provider would silently drop the enums is not tested; `require_parameters` is kept because it makes a provider that cannot enforce the schema fail instead of ignoring it.
- **Enums shorten the answer and make it cheaper.** Names only (S1) costs a third of S0 per call ($0.00020) and answers in 0.9 s; with `have` and `missing` (S2) the cost falls by 31% and the median number of dishes drops from 18 to 13. Part of this is that the model lists fewer dishes, so the saving is not purely the format.
- **Enums do not fix the logic.** The vocabulary constrains spelling, not meaning: S2 and S3 name an ingredient as `missing` that the user owns in 8.3% of dishes (S0: 0.8%), because 계란 is a valid vocabulary word whether or not the user has it. Repeated dish names stay (S3: 67 of 623; S1: 22 of 455), since a JSON schema enum cannot say "each value once".
- **Two kinds of cut-off answers.** S1 (S09) and S3 (S24) are repetition loops: one answer repeats `김치국`/`김치찌개` 37 times (33 distinct names in 494 items), the other writes `오징어볶음` 97 times. S2 (S09, S16) and S0 (S04, S15) are long lists of 82–112 distinct dishes that reach the limit. Both happen on inputs with no good match (seasonings only, an unknown ingredient) or very common ones (달걀, 쌀).
- **The function-call route is worse here.** S4 sends the same schema as a forced tool call. Five of 27 calls came back empty with `finish_reason: error`; a diagnostic call on one of them shows the model's native reason `MALFORMED_FUNCTION_CALL`. Input tokens are 2.2 times higher (2,211 against 988). Recall and precision are lower mostly because those five count as empty.
- **S6 (rules-assisted, comparison only, no call):** names of S1 with `have` and `missing` computed from the dish list: `have` all owned 99.1%, `missing` none owned 100%, recall 44.3%, precision 37.0%, dishes with at most two missing 75.1%; but it needs key ingredients per dish, which the naive design avoids.

### LangChain against the raw route

Same schema as S2 on the first 12 inputs (`langchain-openai` and `langchain-core` in a temporary environment, 38 packages installed by uv, nothing global).

| | Raw S2 (first 12) | S5a LangChain `json_schema` | S5b LangChain `function_calling` |
| --- | --- | --- | --- |
| Failed calls | 1 (S09, cut off) | 4 (S01, S04, S05, S09: `LengthFinishReasonError`) | 12 of 12 (HTTP 404) |
| Constraint violations | 0 | 0 | n/a |
| Recall / precision | 50.0% / 52.7% | 50.7% / 43.4% | none |
| Client code (statements) | 36 | 30 (+ the library) | 30 |

- With `method="function_calling"` every call returned 404 "No endpoints found that can handle the requested parameters". The request carries `provider.require_parameters: true`; the likely cause is a parameter that LangChain adds in this mode and the provider does not list, but that was not tested.
- With `method="json_schema"` the answers differ from the raw route with the same schema: on the 8 inputs that succeeded in both, only 1 gives the same dish set, and 4 inputs ran to the limit where the raw call did not for 3 of them. The two routes differ at least in property order of the schema (the raw schema lists `missing` before `have`, the library's model the other way round) and in how the library rewrites the schema; which of them causes the difference was not tested. So the helper changes the behaviour as well as the amount of code (6 fewer statements, one more dependency, and the library raises on a cut-off answer instead of returning the part that is complete).

### Decision

No variant is adopted under the frozen rule. For the next step, S2 is the format to carry forward: it is the only one that returns `have` (the app shows it), has zero vocabulary violations, and is 31% cheaper than the free-text format; its two failures are long lists that the server's existing salvage of complete items after a cut-off already handles. The names-only S1 is the cost floor ($0.0002 per call) but cannot show `have` or `missing`. Raw `response_format` is the recommended route; LangChain and the function-call route are not worth it on this provider and model. The `missing`-owned error of S2 (8.3%) and the repetitions need a server check or a different prompt, which this study did not test.

### Limits and what is not verified

- One run per variant at temperature 0, one model, one serving provider, 27 inputs (12 for S5a/S5b, 6 for the probes): one input moves a share by about 3 points (8 points for 12 inputs).
- The reference is rule-made from the dish list, not by people; recall and precision measure agreement with that rule.
- The causes of the S5a and S5b differences, of S4's malformed calls and of the repetition loops were not tested. Behaviour on a provider other than Google AI Studio is not known.
- A `maxItems` limit would stop the loops but is a fixed count, which the service avoids; it was not tried.

## Round 2: per-request enums and mapping of unmatched ingredients (2026-11-19)

Design fixed in `criteria_round2.json` and `mapping_set.json` (commit `812b830`) before any call. Round 2 has **no thresholds and no adoption rule**: every number is reported and the recommendation below is a judgement.

- **Problem from round 1.** With `missing` limited to the whole vocabulary (S2), the model named an ingredient the user owns as missing in 8.3% of dishes.
- **R0** = S2 again (same day). **R1** = S2 with a per-request `missing` enum: the vocabulary minus the names the server matches to the user's items (exact spelling or a synonym group). **R2** = R1 plus, for user items with no vocabulary match, a numbered list (`X1: 다진마늘`) that the model maps first (`mapping`: a vocabulary name or `none`); the server then removes mapped names from `missing`.
- **Mapping set.** 40 invented lists (3–6 items) with 43 unmatched items: 27 should map (다진마늘 → 마늘, egg → 계란, 두뷰 → 두부), 16 are traps that should stay `none` (쪽파 is not 대파, 두유 is not 두부), 3 are ambiguous (쌀, 파스타면, 컵라면). One labeller's draft. R2 ran on all 40, R0 and R1 on the first 15 (call cap).
- **Reproduce:** `cd server && PYTHONPATH=.:../research uv run --locked python -m experiments.dish_output_formats.run_round2 [--allow-live-api]`.
- 160 attempts (151 calls and 9 retries after HTTP 429), $0.080, all served by Google AI Studio, `google/gemini-2.5-flash-lite`, temperature 0.

### Frozen 27 inputs

| | R0 (whole vocabulary) | R1 (per-request `missing`) | R2 (R1 + mapping) |
| --- | --- | --- | --- |
| Dishes with an owned ingredient listed as missing | 8.3% | **0%** | **0%** |
| Constraint violations (names, `have`, `missing`, mapping) | 0 | 0 | 0 |
| Repeated dish names in raw answers | 19 | 0 | 0 |
| Cut-off answers | 2 (S09, S16) | 4 (S01, S08, S09, S16) | 4 (S01, S04, S08, S09) |
| Nonempty when a dish is possible | 96.2% | 88.5% | 88.5% |
| Reference recall / precision | 44.6% / 51.6% | 46.5% / 53.7% | 46.3% / 52.0% |
| Dishes per input (median, max) | 13, 28 | 14, 39 | 14, 39 |
| Output tokens (mean) | 789 | 1,061 | 1,082 |
| Cost per call | $0.00041 | $0.00052 | $0.00053 |
| Latency median / p95 | 1.9 / 9.3 s | 2.1 / 8.9 s | 1.9 / 9.4 s |

Paired per input (mean difference, bootstrap 95% interval, inputs both answered):

| | owned listed as missing (share of dishes) | recall | precision | latency |
| --- | --- | --- | --- | --- |
| R1 − R0 (n = 23) | −12.2 points (−23.3 to −3.4) | +2.0 (−2.3 to +7.1) | −2.2 (−6.2 to +1.5) | +1.0 s (+0.1 to +2.2) |
| R2 − R0 (n = 22) | −12.8 points (−25.5 to −3.7) | +2.1 (−2.5 to +7.6) | −2.2 (−6.3 to +1.9) | +0.6 s (−0.3 to +1.6) |
| R2 − R1 (n = 22) | 0 | 0 | 0 | −0.4 s (−1.6 to +0.6) |

Most frozen inputs have no unmatched item, so R2 sends exactly R1's request there; at temperature 0 their answers were identical on all 22 inputs both completed.

### Mapping set

| | R0 (first 15) | R1 (first 15) | R2 (all 40) |
| --- | --- | --- | --- |
| Dishes with an owned ingredient listed as missing (by the labels) | 25 of 237 (10.6%) | 2 of 200 (1.0%) | 0 of 530 |
| Repeated dish names | 39 | 0 | 1 |
| Cut-off answers | 2 | 3 | 4 |
| Cost per call | $0.00062 | $0.00064 | $0.00054 |

Paired on the first 15 lists: R1 − R0 −13.4 points (−29.5 to −1.5, n = 11); R2 − R1 −2.8 points (−7.9 to 0, n = 9).

R2's mapping of the 40 non-ambiguous unmatched items:

| Outcome | Items | Examples |
| --- | --- | --- |
| Right | 21 | 다진마늘 → 마늘, egg → 계란, 두뷰 → 두부, 비비고 만두 → 만두, 청경채 → none |
| **False merge** (label `none`, model named a vocabulary entry) | **14** | 쪽파 → 대파 (3 lists), 적양배추 → 양배추 (2), 두유 → 두부, 들기름 → 참기름, 미나리 → 미역, 부추 → 부침가루, 브로콜리 → 가지, 올리고당 → 올리브유 |
| Missed merge | 5 | 4 lost to cut-off answers (깐마늘, 삼겹살, 표고버섯, 스팸), cheese → none |
| Wrong target | 0 | |

The three ambiguous items were mapped 쌀 → 밥, 파스타면 → 스파게티면, 컵라면 → 라면. Of the 16 traps only 2 stayed `none` (생크림, 청경채).

The removal step made 7 removals: 2 were right (청양고추 → 고추 in two dishes) and **5 were harmful**: after 두유 → 두부, 두부 disappeared from the missing list of 두부김치, 두부부침, 두부조림, 두부국 and 두부덮밥, so the app would say the user has tofu.

### What the numbers show

- **The per-request enum removes the original problem.** On the frozen inputs R1 cut owned-as-missing from 8.3% to 0%; the paired interval excludes zero. On the mapping set the remaining error was 1% of dishes, coming from forms the server cannot match (치즈 for 슬라이스치즈, 고추 for 청양고추). Recall and precision did not change measurably (intervals include zero).
- **Repeated dish names disappeared with the narrower enum** (19 and 39 for R0, 0 for R1). The cause was not tested.
- **The cost is a longer answer.** R1 wrote about a third more output tokens, cost $0.0001 more per call, took about 1 s longer in the paired median and was cut off twice more often (4 against 2 of 27). On a single run the cut-off difference may be noise; it lowers "nonempty" from 96% to 89% because cut answers are scored as empty here (the service keeps the complete part).
- **The model's own mapping is not safe with this model.** It merged 14 of 16 traps into a similar-sounding or similar-looking vocabulary name, including nonsense (부추 → 부침가루, 브로콜리 → 가지) and a harmful one (두유 → 두부) whose removal step then told the user they own tofu. The prompt rule ("only the same ingredient; 쪽파 is not 대파") was ignored for exactly the example it named. The gain of R2 over R1 on the problem it targets was small (−2.8 points, interval reaching zero).

### What they cannot show

One run of one model on one provider; 27 frozen inputs and 40 lists written and labelled by one person; R0 and R1 saw only 15 lists. The traps are my judgement of "only a substitute". Cut-off answers are scored as empty although the service salvages their complete part. Whether a stronger model maps safely was not tested.

### Recommendation (judgement)

Use **R1** in the service: dish names, `have` and `missing` limited to closed lists, with `missing` built per request from the vocabulary minus what the user owns. It removes the owned-as-missing error by construction, keeps the names valid, and costs about $0.0001 more per call. Do **not** use the model mapping of R2 with this model: it cannot be trusted to say "none". Unmatched user items (다진마늘, egg) stay in `have` under the user's wording; the remaining risk is that their vocabulary form can still be listed as missing (1% of dishes here). Watch the cut-off rate on the deployed server.

## Round 3: list length under closed choices (2026-11-19)

Two live requests on the demo server returned 102 and 94 dishes (about 8 s) after the closed choices were deployed. Design fixed before any call in `criteria_round3.json` (commit `9afc16a`): the 27 frozen inputs, the current 128-dish list, the server's request body, five variants, no pass/fail threshold. 140 attempts (135 planned + 5 retries after HTTP 429), $0.10.

| | P0 served (round-2 wording) | PA "only what you can cook now, or after a small purchase" | PB "best first, stop when the rest mostly lacks ingredients" | PC per-dish `fit` field | PD earlier free text |
|---|---|---|---|---|---|
| Dishes returned: median / mean / max | 17.5 / 25.7 / 116 | 16 / 24.6 / 96 | 17.5 / 30.8 / 115 | 79 / 63.7 / 126 | 18 / 19.3 / 52 |
| Cut at 4,096 tokens (salvaged) / failed | 5 / 1 | 4 / 0 | 10 / 1 | 14 / 0 | 3 / 0 |
| Missing per dish by the rules: 0 / 1 / 2 / 3+ | 9 / 20 / 30 / 42% | 10 / 23 / 33 / 35% | 9 / 21 / 30 / 40% | 4 / 15 / 25 / 56% | 13 / 23 / 32 / 32% |
| Missing per dish as the model wrote it: 0 / 1 / 2 / 3+ | 24 / 35 / 25 / 17% | 23 / 42 / 22 / 13% | 22 / 40 / 30 / 8% | 12 / 36 / 35 / 17% | 54 / 28 / 8 / 10% |
| Owned ingredient listed as missing (dishes) | 0 | 0 | 0 | 0 | 34 |
| Reference recall / precision | 0.48 / 0.25 | 0.53 / 0.28 | 0.60 / 0.26 | 0.74 / 0.15 | 0.52 / 0.35 |
| Latency p50 / p95, output tokens, cost per call | 2.1 / 8.8 s, 1,293, $0.00061 | 1.9 / 7.9 s, 1,133, $0.00055 | 2.4 / 8.7 s, 1,815, $0.00082 | 8.1 / 9.0 s, 2,699, $0.00115 | 2.2 / 7.6 s, 1,213, $0.00058 |

Answers cut at the limit keep only their complete dishes, so their counts above are lower bounds of what the model was writing. Among answers that were not cut: P0 median 16.5 (max 36, n = 22), PA 16 (54, 23), PB 15 (31, 17), PC 19 (118, 13), PD 18 (48, 24).

Paired against P0 per input (mean difference, bootstrap 95% interval, n = 25–26): PA dishes −0.5 (−15.7 to +14.7), rules-missing per dish −0.09 (−0.27 to +0.09), recall +0.08 (−0.02 to +0.19), precision +0.04 (−0.06 to +0.13); PC dishes +36.5 (+17.5 to +56.0), rules-missing +0.60 (+0.30 to +0.92), precision −0.18 (−0.31 to −0.06).

**What the numbers show.**
- The median list is short in every closed variant (16–18); the long lists are a tail. In each variant a few inputs run away to 90–126 dishes, and not always the same inputs: P0 on 두부 (102), on salt, soy sauce and sugar only (102) and on 밥+계란+an unknown item (116); PA on 김치+밥 (96). The two live requests were such tails.
- In the runaway answers the model walks the dish list in the order it was given (95–96% of consecutive pairs in list order for P0 on 두부 and on 밥+계란; 100% even for a 28-dish answer). So "best first" is not followed: the order is the list's order, and the dishes the user can cook now are not at the top.
- Wording PA moves every average in the intended direction (shorter, fewer 3+-missing dishes, higher recall and precision, cheaper, fewer cut answers), but every paired interval includes zero, and it still runs away on one input. PB cuts more answers. The `fit` field (PC) makes lists much longer and its labels do not separate dishes (rules-missing mean 1.5 for "now", 2.9 for "small purchase", 2.9 for "mostly missing"). Free text (PD) brings back owned ingredients listed as missing (34 dishes).
- Offline, on the stored answers: ordering each list by the model's own `missing` count (ties in the model's order) raises the share of dishes with at most one missing ingredient among the first five from 0.55 to 0.64 (P0) and from 0.53 to 0.62 (PA); the rules-missing mean of the first five falls from 1.3 to 1.1.

**Check on the redeployed demo server (same day, after adoption).** [두부] returned 7 dishes and [김치, 밥, 간장, 소금] 13, both cut at 4,096 output tokens (8.5 s and 7.9 s); the 7 and 13 are what survived the cut, not short answers. The kept lists were in non-decreasing order of `missing` and no owned ingredient was listed as missing. The salvaged `missing` lists also name seasonings such as 간장, 설탕 and 참기름, which are key ingredients of some dishes and therefore allowed choices, although the wording says basic seasonings are not listed; this lengthens every item. So the length and latency problem is not solved: the answers still run to the limit on common inputs.

**Adopted (judgement, not a rule outcome).** The PA wording, and the server orders the checked list by the model's own `missing` count, keeping the model's order for ties; nothing is dropped and no count is imposed. The list length is not solved: wording alone did not stop answers that run to the output limit (the two live requests above), and a cap would be a fixed count. The evidence for PA over P0 is weak (all paired intervals include zero); the ordering is the part that the stored answers support. Not tried: shuffling or regrouping the dish list sent to the model (the walk follows its order), and keeping seasonings out of the `missing` choices.

**Limits.** One run per variant, one model and provider, 27 inputs; the reference sets and the rules' missing counts come from the catalog's key ingredients, not from people; the offline ordering check reuses the same answers.

## Round 4: bounding the answer by structure (2026-11-19)

After round 3 both demo requests still ran into the 4,096-token output limit (about 8 s). Design fixed before any call in `criteria_round4.json` (commit `aee797b`): the 27 frozen inputs plus the two demo inputs (D1 = 두부, D2 = 김치, 밥, 간장, 소금); the split variants and the names-only reference ran on the two demo inputs plus six inputs drawn with a fixed seed (8 inputs). No pass/fail threshold. 383 calls, $0.10, no HTTP 429 (also not in the 18 concurrent calls per split request).

| | S_now (served) | S_noseason | S_shuffle | S_names (cost reference) | S_split | S_split_noseason |
|---|---|---|---|---|---|---|
| Inputs / requests | 29 / 29 | 29 / 29 | 29 / 29 | 8 / 8 | 8 / 144 | 8 / 144 |
| Inputs with a cut answer | 6 | 2 | 9 | 0 | 0 | 0 |
| Dishes returned: median / mean / max | 16 / 23.6 / 96 | 16 / 19.9 / 114 | 16 / 32.4 / 108 | 18 / 14.0 / 25 | 66 / 67.8 / 86 | 70 / 71.0 / 90 |
| Missing per dish by the rules: 0 / 1 / 2 / 3+ | 9 / 22 / 33 / 35% | 11 / 21 / 33 / 36% | 7 / 16 / 28 / 49% | 20 / 28 / 40 / 13% | 5 / 20 / 26 / 49% | 5 / 18 / 27 / 50% |
| First five with at most one missing (mean share) | 0.60 | 0.59 | 0.54 | 0.55 | 0.58 | 0.63 |
| Staples among the missing items | 8.4% | 0% | 5.7% | — | 8.1% | 0% |
| Owned ingredient listed as missing | 0 | 0 | 0 | 0 | 0 | 0 |
| Reference recall / precision | 0.53 / 0.28 | 0.48 / 0.29 | 0.52 / 0.20 | 0.46 / 0.47 | 0.87 / 0.19 | 0.84 / 0.17 |
| Wall time p50 / p95 | 2.1 / 8.9 s | 2.1 / 8.5 s | 2.0 / 9.3 s | 0.9 / 1.0 s | 1.9 / 5.0 s | 1.9 / 2.8 s |
| Output tokens per input, cost per input | 1,334, $0.00063 | 983, $0.00048 | 1,698, $0.00078 | 99, $0.00013 | 3,853, $0.00199 | 3,713, $0.00193 |

Demo inputs: S_now cut both (7 and 13 dishes kept, 8.1 and 8.2 s); S_noseason answered both in full (11 dishes in 1.7 s, 13 in 3.0 s); the split variants returned 62–69 dishes in 1.6–1.9 s.

Paired against S_now per input (mean difference, bootstrap 95% interval): S_noseason dishes −3.7 (−16.3 to +7.9), recall −0.08 (−0.16 to −0.01), precision −0.02 (−0.06 to +0.02), cost −$0.00014 (−0.00041 to +0.00011); S_split_noseason (n = 8) dishes +53 (+43 to +63), rules-missing mean +0.72 (+0.48 to +0.99), recall +0.23 (+0.12 to +0.34), precision −0.21 (−0.31 to −0.13), wall −1.8 s (−4.0 to +0.05), cost +$0.0012 (+0.0007 to +0.0015); S_shuffle precision −0.09 (−0.19 to −0.01), rules-missing mean +0.24 (−0.03 to +0.53).

**What the numbers show.**
- Taking the staples out of the `missing` choices shortens every answer (output tokens −26%, cost −23%) and cut answers drop from 6 to 2 of 29; both demo inputs are answered in full and fast. It does not stop every runaway: 밥 + 계란 + an unknown item still returned 114 dishes (cut). Recall falls a little (the interval just excludes zero) while precision and the first-five share do not move.
- Splitting by the catalog's categories removes the cut answers and the slow tail (p95 2.8–5.0 s, no 429 with 18 concurrent calls), but each category answer lists most of its own dishes: 62–90 dishes per input, half of them missing three or more ingredients, three times the cost. That is the opposite of the promise "what you can cook now", and the server's ordering keeps the first five about as good as before, not better.
- Shuffling the dish list makes lists longer and less precise; the walk in list order is not what decides which dishes appear, so changing the order does not help.
- Names only is the cost floor (about a fifth of S_now, under a second) but the cards would have no missing list.

**Adopted (judgement, not a rule outcome).** S_noseason: the server leaves the staples it assumes at home (staples.json plus water, with their synonym spellings) out of the `missing` choices; the wording and the ordering are unchanged. The split is not adopted: it fixes the cut answers by making every list three to four times longer. What remains: an occasional runaway answer on very common inputs (2 of 29 here), which the server still salvages and orders.

**Limits.** One run per variant, one model and provider; the split variants and names-only on 8 inputs; reference sets and rule-based missing counts come from the catalog, not from people.
