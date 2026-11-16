# From a recipe database to a closed dish list and on-request videos

Why this version of the app has no recipe database, how dishes and videos are chosen, and what each choice rests on. Each row links to the study that holds the data, criteria and limits.

## Decision chain

| Step | Decision | Evidence | Study |
| --- | --- | --- | --- |
| 1 | No recipe database: recipe sites could not be used for a store release. The server keeps a closed list of 130 student-cooking dish names (`server/app/dishes/dishes.json`) and shows YouTube videos instead of recipe text. | Constraint, not measurement | - |
| 2 | First design (hybrid): the server computes have/missing from key ingredients and a substitution table; the model only ranks. | 48 frozen cases (31 suggestion, 17 substitution), 14 thresholds fixed before the run: 12 met, 2 not (one off-list dish for a one-ingredient input; a wording check on a substitute sentence). Run 2 without a fixed card count: output was cut for 7 inputs at 1,024 tokens. | [dish_eval](../experiments/dish_eval/README.md) |
| 3 | Naive design: the model gets only the dish names and the user's ingredients and returns dishes with have/missing; the server checks names and nothing else. No rules fallback (502 instead). | 9 thresholds, 3 met: names in the list 99.7%, `have` all from the user's list 94.6%, recall/precision against a rules-built reference 33% / 32%. The reference is not human-labelled and favours the rules design. Chosen for simplicity and because it keeps the closed list as the only shared data. | [dish_naive](../experiments/dish_naive/README.md) |
| 4 | Output cap 4096 tokens, retry in the app on a cut answer. A prompt that defines `have` as "only what the user listed" removes false `have` entries (100% vs 95.8%) but was not adopted: it did not meet the pre-set rule (cut answers counted as empty). | Cost per call is about $0.0005 and 80% of it is output; compact formats, no `have`, or "stop at poor fits" were not cheaper. 2 of 27 inputs still hit 8,192 tokens because the model may list the whole dish list. | [dish_tokens](../experiments/dish_tokens/README.md), [dish_naive](../experiments/dish_naive/README.md) |
| 5 | Videos are found when the user opens a dish: one web-search model call proposes links, one batched YouTube lookup keeps those that exist, are public and embeddable, in the model's order. | No pipeline variant met the pre-set rule (links for 90% of dishes within 6 s); one call per dish was the closest (83%), batching several dishes in one call gave links for 15% of dishes. Asking for ids alone returned invented ids; titles with ids worked. On-request loading was chosen to pay the search cost only for dishes the user opens (about $0.008 each). | [dish_pipeline](../experiments/dish_pipeline/README.md) |
| 6 | No title filter and no ranking by views. | The first discovery study kept the search API with a title filter and was superseded: its relevance metric was the same string rule. With 60 hand-labelled videos the title rule found 57% of relevant videos and none of the 19 with English or nameless titles. Model judges (kappa 0.61) rated 76% of the embeddable model-provided links as relevant. | [youtube_discovery](../experiments/youtube_discovery/README.md) (superseded), [youtube_discovery_v2](../experiments/youtube_discovery_v2/README.md), [dish_pipeline](../experiments/dish_pipeline/README.md) |
| 7 | Request wording D0: "videos to follow along and cook the dish". Adding "for someone cooking alone", simple-tools conditions, or exclusions did not help. | 27 dishes, two judges: relevant share 82.4% (D0) vs 75.7–77.7% (D1, D2) and 75.9% (D3, which also lowered links per dish); differences are within the bootstrap interval. The word 자취생 did not act as a search keyword. | [dish_pipeline](../experiments/dish_pipeline/README.md) (round 3) |

## Limits that apply to all rows

- One labeller (an AI) made the answer keys and the 60 video labels; no human labels exist. Judge agreement with those labels is 0.61 (kappa), just above the pre-set 0.6.
- One model family and one run per variant; web search results change from day to day.
- The 27 dishes of the video studies contain many fried-rice dishes.
- "Easy for a person living alone" is not measured by any metric.
- The frozen cases, thresholds and criteria were committed before their results; later changes are recorded as dated amendments in each study's `criteria` file and README.
