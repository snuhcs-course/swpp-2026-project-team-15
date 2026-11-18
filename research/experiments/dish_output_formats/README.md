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

One run per variant at temperature 0, one model, 27 inputs (12 and 6 for the library and probe variants); enum support depends on the provider that serves the request; the reference is rule-made. Results are recorded below after the run.
