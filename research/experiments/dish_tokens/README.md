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

## Round 2: output size (criteria frozen 2026-11-16, before any call)

Question: with the prompt chosen in `../dish_naive/` round 2, does asking for less output lower the cost per call? Variants O0 to O3, the rule and the cap are in `criteria_round2.json`. Results are added below after the runs.

### Round 2 results (2026-11-16)

Base prompt: the production prompt, because the prompt study of `../dish_naive/` (round 2) adopted no variant. Same 12 inputs, `max_tokens` 4096, temperature 0, `run_output.py` (commit `8c9995f`), criteria frozen in `0fac1ca`. O0 is not a new call: it is the production-prompt answers of the prompt study on these 12 inputs (they are identical to baseline B of round 1 of this study: same input tokens, output tokens, cost and metrics, which shows that temperature 0 repeats exactly here). The 36 fresh calls took 40 attempts (4 retries after HTTP 429) and about $0.02. **No variant qualifies and none is adopted.**

| Variant | Failed (cut off) | Input tok | Output tok | Cost per call | Median latency | Names in list | `have` all owned | `missing` none owned | Recall | Precision | ≤2 missing |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| O0 full answer (baseline) | 0 | 981 | 882 | $0.000451 | 2.5 s | 99.6% | 99.1% | 100% | 44.0% | 38.8% | 81.9% |
| O1 names and `missing` only (not adoptable) | 2 | 981 | 1,008 | $0.000501 | 1.9 s | 100% | n/a | 97.0% | 34.5% | 42.1% | 87.2% |
| O2 "stop when the next dish is a poor fit" | 1 | 1,011 | 1,094 | $0.000539 | 2.4 s | 99.0% | 98.9% | 99.5% | 31.5% | 33.5% | 76.6% |
| O3 `missing` as one comma-joined string | 1 | 1,001 | 1,189 | $0.000576 | 2.7 s | 99.6% | 100% | 92.3% | 50.0% | 40.3% | 80.2% |

- **Every reduction made the call more expensive, not cheaper.** The qualitative stop instruction (O2) did not shorten the list: the model still enumerated and one answer ran to the 4,096-token limit. Dropping `have` (O1) lowered the latency but the model listed more dishes, so the output grew by 14%. Writing `missing` as a string (O3) saved no tokens and the answers got longer by 35%; its `missing` field named owned ingredients more often (92.3% disjoint).
- **Why no saving appears:** the cost is set by how many dishes the model lists, not by the size of each entry. With no count in the instruction the model chooses the length, and an instruction that only changes the format or the stopping words does not change that.
- **The failures are cut-off answers** (O1: S07 and S26; O2: S07; O3: S11), the same kind as in the prompt study.
- Against the rule: O2 fails recall (31.5% against 44.0% minus 2 points), a cut-off answer and a higher cost; O3 fails `missing` disjointness (92.3% against 100%) and a cut-off answer, and is more expensive; O1 fails recall and a cut-off answer, and cannot be adopted because the app needs `have`.

### Limits (round 2)

12 inputs, one run per variant; a difference below about 2 points or $0.00003 is noise, but the differences in cost here are larger than that. The recall figures include cut-off answers as empty. Quality is consistency with a reference made by rule from the same dish list, not human judgement.
