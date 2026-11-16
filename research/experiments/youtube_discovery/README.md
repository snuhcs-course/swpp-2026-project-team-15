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

Results are added after the runs.
