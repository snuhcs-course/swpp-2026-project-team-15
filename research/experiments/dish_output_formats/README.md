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
