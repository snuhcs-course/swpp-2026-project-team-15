# Token cost of the naive dish-selection call

Question: how cheaply can the naive selection call (dish names + owned ingredients in, dishes with have/missing out) run without losing answer quality? Variants, the quality baseline and the decision rule are fixed in `criteria.json`, committed before any call of this study (together with `../dish_pipeline/criteria.json`). Same 12 inputs as the pipeline study (seeded sample of the frozen naive inputs).

Image resolution was reduced earlier for recognition; here the corresponding levers are the output budget, the answer schema, the prompt layout, the reasoning setting and prefix caching.

Results are added below after the runs.

## Results (2026-11-16)

Commit of the runner: `769edb3`; criteria: `969dea5`. 96 model calls (8 variants x 12 inputs), about $0.049 in total. Numbers are means over the 12 inputs; one run each at temperature 0. Quality metrics follow `../dish_naive/` (reference set made by rule, not human-labelled).

| Variant | Failed/truncated | Input tok | Output tok | Cached tok | Cost per call | Median latency | have ok | missing ok | Recall | Precision | ≤2 missing |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B (ceiling 8192) | 0 | 981 | 882 | 0 | $0.000451 | 2.2 s | 99.1% | 100% | 44.0% | 38.8% | 81.9% |
| V0 (2048, as shipped) | 1 | 981 | 882 | 0 | $0.000451 | 2.4 s | 98.9% | 100% | 28.0% | 30.1% | 80.6% |
| V1a (1024) | 4 | 981 | 672 | 217 | $0.000347 | 2.3 s | 100% | 100% | 11.5% | 25.0% | 83.7% |
| V1b (4096) | 0 | 981 | 882 | 144 | $0.000438 | 2.2 s | 99.1% | 100% | 44.0% | 38.8% | 81.9% |
| V2 compact text | 0 | 859 | 943 | 0 | $0.000463 | 2.5 s | 100% | 100% | 52.5% | 42.9% | 83.3% |
| V3 reasoning off | 0 | 981 | 882 | 145 | $0.000438 | 2.3 s | 99.1% | 100% | 44.0% | 38.8% | 81.9% |
| V4 names + missing only | 1 | 981 | 1,376 | 0 | $0.000648 | 1.6 s | n/a | 98.3% | 42.0% | 28.6% | 71.8% |
| V5 dish list first | 1 | 981 | 1,877 | 289 | $0.000823 | 2.6 s | 78.4% | 100% | 50.5% | 28.4% | 64.0% |

Recall/precision/≤2-missing for failed calls count the failed input as empty, so V0 and V1a lose recall because of truncation.

**Rule outcome.** B, V1b, V2 and V3 qualify (zero truncation, every metric within 2 points of B or better); the rule picks V3 by the lowest mean cost. This is a weak result: V3 returns the same answers as B and V1b. The model does not reason by default (0 reasoning tokens everywhere), so the reasoning switch changes nothing, and the cost differences between B, V1b and V3 ($0.000451 vs $0.000438) come from provider-side implicit caching of the repeated prompt prefix (cached tokens 0 vs about 145), not from the variant. The only measured levers are:

- **Output budget.** The shipped `max_tokens` 2048 truncated one answer in 12 (2,013 tokens) and 1024 truncated four. The longest complete answer was 2,015 tokens; the smallest tested setting with no truncation is **4096** (V1b). The shipped value is raised to 4096 in the commit after this study.
- **Output length is the cost.** Output tokens (882 on average) cost four times as much per token as input and are about 80% of a call's cost. With no fixed count the model lists 14–44 dishes, and the answer grows with the list. Any other lever is small next to that: the whole selection call costs about $0.0005.
- **V2** (compact text) saves 122 input tokens (12%) but the model wrote 61 more output tokens, so it does not cost less; its higher recall (52.5%) is within what one run at temperature 0 can vary, not a finding.
- **V4 and V5 are worse, not cheaper**: each had one answer that ran to the 8,192-token ceiling (a repeating list), which shows the runaway risk of free-length output; V5 also invented `have` items more often (78.4% ok). V4 removes `have` but the model then wrote longer lists.
- **Caching.** Cached tokens appear on some variants (144–289 of 981 input tokens) without any change in prompt layout, so they depend on call timing and not on the V5 ordering; the saving is below $0.00002 per call.

### Limits

12 inputs and one run per variant: differences below about 2 points or $0.00003 are noise. Latency varies by call. Quality is consistency with the rule-made reference. A `max_tokens` of 4096 was chosen from the longest answers of 12 inputs; a longer input list could need more.
