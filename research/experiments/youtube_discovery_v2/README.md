# YouTube video discovery, study v2

Question: for each dish of the app, which way of finding YouTube cooking videos returns the most relevant, popular, embeddable videos?

This study replaces [study v1](../youtube_discovery/README.md). Two weaknesses of v1: it kept only videos whose title contains the dish name (this drops famous videos with other titles and English-titled videos), and it scored relevance with the same title rule, so a filter graded itself. v2 splits the problem into three stages that are measured separately.

## Design (fixed in `criteria.json` before any v2 call)

| Stage | Question | Options |
| --- | --- | --- |
| 1. Candidates | Where do the candidate videos come from? | **A1** YouTube search, relevance order, 25 results (the current production query); **B** a model with web search asked for the most popular, best-regarded recipe videos (any language, up to 8); **B2** the same, asked to prefer the most viewed; **U** the union of A1, B and B2. **A2** (search ordered by views) is not run: the 20 search calls allowed today are spent on A1; it is pending. |
| 2. Relevance | Which candidates are really recipe videos of this dish? | **J0** the old rule (title contains the dish name); **J1** a language model reading title, channel, duration, description and tags (`gemini-2.5-flash-lite`, one call per dish); **E** a second, stronger model (`gemini-2.5-flash`) used only to score the results, so a selector is not graded by itself. |
| 3. Ranking | Which three of the relevant candidates are shown? | most views; like ratio (likes/views, at least 1,000 views); newest; most views with at most one video per channel. |

Every candidate is enriched by one `videos.list` call per dish (title, channel, description, tags, duration, views, likes, embeddable and public flags). A video that is not public and embeddable is never chosen. No page is scraped.

**Dishes.** The 40 dishes of v1. The dishes that failed in v1 (`pork-kimchi-fried-rice`, `sausage-stir`, `pork-lettuce`, `hotdog-pan`) are already among them, so none was added. The 20 dishes that get a live search (the first 20 of `extra`) are the *paired set*: all 32 combinations (4 candidate sources x 2 selectors x 4 rankings) are compared there. The 10 cached dishes keep no candidate pool, so A1 does not exist for them. B and B2 are also reported on all 40.

**Judge validation.** 60 candidate videos are drawn with a seed (20 Korean titles naming the dish, 15 Korean titles not naming it, 15 titles without Hangul, 10 videos of 60 s or less). The assistant labels them from the same fields the judges see, before any judge call; the labels (one labeler, a draft, ids only) are committed in `labels.json` before the judges run. A judge counts as trusted with Cohen's kappa >= 0.6 against the labels. If E is not trusted, no decision is made; if J1 is not trusted, J1 combinations are excluded. J0 is also compared with the labels, which measures how often the old rule was wrong, especially on English and nameless titles.

**Metrics** (per combination, scored by E): `p3` = chosen videos that E calls relevant / 3, averaged over dishes (an empty slot is a miss); precision among chosen videos; coverage = share of dishes with 3 chosen videos; dishes with no relevant chosen video; median views; relevant English-titled videos chosen; cost per dish; search calls per dish.

**Decision rule.** Among trusted combinations with coverage >= 0.9 x the best coverage, take the highest `p3` (ties: lower cost, then fewer search calls). Report the paired per-dish difference to the baseline (A1 + J0 + views) with a 95% bootstrap interval (10,000 resamples of dishes); the result is inconclusive when the interval contains 0.

**Budget.** At most 200 model calls (planned 162), 1.50 USD, 20 `search.list` calls, 800 units of other YouTube quota.

## Files

| File | Purpose |
| --- | --- |
| `criteria.json` | Frozen design, metrics, rule, budget. |
| `scoring.py` | Pure functions: candidate features, ranking, selection, judge-answer parsing, kappa, bootstrap, the rule. |
| `run.py` | Runner (`plan`, `collect`, `sample`, `judge-validate`, `judge`, `analyze`); dry run unless `--allow-live-api`. Raw data go to the ignored `data/youtube-discovery-v2/`. |
| `analyze.py` | Offline analysis of the stored data. |
| `labels.json` | Labels of the 60 validation videos (added before the judges run). |
| `../../../server/tests/experiments/youtube_discovery_v2/` | Offline tests. |

```sh
cd server
PYTHONPATH=.:../research uv run python -m experiments.youtube_discovery_v2.run plan
PYTHONPATH=.:../research uv run python -m experiments.youtube_discovery_v2.run collect --allow-live-api --max-search 20
```

## Results

Added after the run (see the commit history: criteria, then labels, then results).
