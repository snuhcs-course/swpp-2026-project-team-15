# YouTube video discovery for the dish list

Question: which way of finding YouTube cooking videos for a dish gives the most relevant, embeddable and popular videos per dish at an acceptable cost, without using the YouTube search quota?

Scope: YouTube only. The dish list is the 130 dishes in `server/app/dishes/dishes.json`.

## Methods

| Method | How |
| --- | --- |
| A (current) | `search.list` (relevance order, 25 results, query "<dish> 레시피"), then `videos.list`; keep embeddable public videos whose title contains the dish name; top 3 by views. |
| B | The model `google/gemini-2.5-flash-lite:online` (OpenRouter web-search plugin) is asked for YouTube watch URLs for "<dish> 레시피". Ids come from the answer and the URL citations. One batched `videos.list` call checks that they exist, are public and embeddable, and gives titles and views. Then the same filter and ranking as A. |
| C | B plus a second query "<dish> 만들기" to the same model; ids merged before the single `videos.list` call. |

## Criteria (fixed before any call, see `criteria.json`)

- Test set: 40 dishes. 10 are already cached for method A; 30 are drawn per category with seed 20261116 (`sampling.py`; the ids are listed in `criteria.json` and a test re-derives them).
- Quota plan for A: the 10 cached dishes reuse the stored videos (no search call); at most 20 more dishes are searched, with at most 25 extra `search.list` calls today (100 units each, own daily bucket of about 100 calls). The other dishes are reported as pending. B and C run on all 40 dishes (at most 90 model calls, 0.80 USD).
- Metrics per method: strict relevance (title contains the dish name, spaces and punctuation ignored) and a looser rate (any alias); share of verified videos that are embeddable and public; existence rate of the ids the model produced; coverage (dishes with 3 kept videos); median views of kept videos; cost in USD and YouTube quota units; latency.
- Relevance is a title match, not a human judgement (no human check in this study).
- Decision rule: prefer B or C over A only if all hold: strict relevance at least A − 0.05, coverage at least A − 0.05, kept videos 100% embeddable and public, existence rate at least 0.95, cost at most 0.02 USD per dish. If both pass, choose B. Otherwise keep A. Relevance and the rule use the dishes where A ran live (paired); for the 10 cached dishes the stored 3 videos are a filled list, so only coverage and views are comparable.

## Files

| File | Purpose |
| --- | --- |
| `criteria.json` | Frozen sample, metrics and decision rule. |
| `sampling.py`, `scoring.py` | Seeded sampler; pure scoring (name match, id extraction, summary, decision). |
| `run_study.py` | Runner. Dry run by default; `--allow-live-api` makes real calls; raw output goes to the ignored `data/youtube-discovery/`. |
| `../../../server/tests/experiments/youtube_discovery/` | Offline tests (no network). |

```sh
cd server
PYTHONPATH=.:../research uv run python -m experiments.youtube_discovery.run_study                 # plan only
PYTHONPATH=.:../research uv run python -m experiments.youtube_discovery.run_study --allow-live-api --max-search 20
```

## Results (run on 2026-11-16)

Criteria commit `232d99e` precedes every call. A ran on 30 dishes (10 cached, 20 live); B and C on all 40. "Paired" means the 20 dishes where A ran live.

| Measure | A | B | C |
| --- | --- | --- | --- |
| Strict relevance, paired (title names the dish) | 0.542 | 0.607 | 0.526 |
| Looser relevance (any alias), paired | 0.553 | 0.623 | 0.546 |
| Coverage (3 kept videos), paired (20 dishes) | 0.80 | 0.35 | 0.40 |
| Coverage, all dishes with a result | 0.83 (30) | 0.33 (40) | 0.43 (40) |
| Verified videos that are embeddable and public (before the filter) | 1.00 | 0.89 | 0.91 |
| Existence rate of model ids | n/a | 0.993 (all 40) | 0.981 (all 40) |
| Median views of kept videos, paired | 2.67 M | 1.07 M | 1.65 M |
| Cost per dish (OpenRouter) | 0 | 0.0071 USD | 0.0145 USD |
| YouTube quota units, whole run | 2,020 (20 `search.list` + 20 `videos.list`) | 38 | 40 |
| Median latency of one discovery call | 0.71 s (search + details) | 2.9 s | 2.9 s |

Totals: 2,098 quota units, 20 `search.list` calls (cap 25), 80 model calls (cap 90), about 0.58 USD (cap 0.80), 98 `videos.list` requests. Two model calls returned HTTP 429 (`ramyeon-egg`, B and C), so that dish has no model result.

Decision rule on the paired dishes: B passes relevance, kept-embeddable, existence and cost but fails coverage (0.35 against 0.80 − 0.05); C fails coverage too (0.40). **Decision: keep A.**

### Failure analysis

- The model returns 3 to 7 ids per dish (3.6 for B on average), while A inspects 25 candidates. After the title filter fewer than 3 remain for most dishes, so coverage is limited by candidate count, not by existence: almost every id is real (B 0.993).
- The second query (C) adds candidates and coverage (0.33 to 0.43) but dilutes relevance (0.58 to 0.50 on the 30 A dishes), and doubles the cost.
- 8 to 11% of verified model ids are not embeddable; the filter removes them, which lowers the number kept.
- B is not worse on relevance (0.607 against 0.542 on the same dishes); A's low strict relevance comes from the 25-candidate pool holding many videos that do not name the dish (for example `sausage-stir` and `hotdog-pan` kept none).
- Model videos are less viewed (median 1.07 M against 2.67 M), consistent with the model picking whatever its web search surfaced.

### Limits

- Relevance is a title match, not a human judgement.
- 20 paired dishes, one run per method; the model web search is not deterministic, so numbers can differ between runs. No confidence interval was computed.
- The 10 cached dishes are all fried-rice dishes and their stored videos are a filled list: they contribute to coverage and views only, not to relevance.
- 10 of the 30 extra dishes have no A result yet (`search.list` cap); the rule used the paired 20 only.
- Prices and the model's search behaviour are those of 2026-11-16.

### Completing A

Pending dishes: `tuna-gimbap`, `tofu-soup`, `potato-stir`, `spam-bean-sprout`, `pork-bowl`, `cream-pasta`, `egg-boiled`, `dumpling-stew`, `doenjang-stew`, `bibimbap` (the last 10 of `extra`). On a later day, with the local results file kept, run `run_study.py --allow-live-api --methods a --max-search 10`; finished entries are skipped.
