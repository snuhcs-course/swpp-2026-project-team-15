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

## What changed during the run (all recorded in `criteria.json` under `amendments`, committed before the step they affect)

1. The YouTube search quota for the day was already used up when the study started, so **A1 (YouTube search) has no candidates yet**. The paired comparison, the combinations that include A1 and U, and the decision rule are **deferred**. Today's results cover the model-discovery sources B and B2.
2. The first judge models failed validation (below). As the criteria allowed, stronger models were tried in a fixed order with the unchanged prompt; two reached the threshold.
3. The first collection did not request video duration; the runner was fixed and the candidates re-fetched before the sample was drawn and labelled.
4. Spending reached the guard (1.45 of 1.50 USD) after 27 of 40 dishes had both judgements; the analysis covers those 27.

## Results (2026-11-16)

Commits in order: criteria, quota amendment, labels (before any judge ran), judge amendments, results. Model calls 141 of 200, 1.46 USD of 1.50, `search.list` 0 of 20, `videos.list` 80 requests.

### Judge validation (60 labelled videos, one labeler)

Agreement with the labels. Labels: 44 relevant, 16 not. Kappa corrects for agreement by chance; 0.6 is the pre-set threshold.

| Judge | Agreement | Precision | Recall | Kappa | Trusted |
| --- | --- | --- | --- | --- | --- |
| J0 title rule (old) | 0.67 | 0.96 | **0.57** | 0.37 | rule, not a model |
| gemini-2.5-flash-lite | 0.73 | 0.73 | 1.00 | 0.00 (calls every video relevant) | no |
| gemini-2.5-flash | 0.77 | 0.78 | 0.95 | 0.26 | no |
| gemini-2.5-pro (evaluator E) | 0.87 | 0.86 | 0.98 | 0.61 | yes, barely |
| claude-haiku-4.5 (selector J1) | 0.85 | 0.89 | 0.91 | 0.61 | yes, barely |

The old title rule rarely accepts a wrong video (precision 0.96) but misses 43% of the relevant ones: on the 16 videos without Hangul in the title it found 0 of 12 relevant ones, and on the 18 Korean titles that do not name the dish it found 0 of 7. The three judge models that are not trusted accept almost everything; the trusted ones still accept some neighbours of the dish (for example a different stew with the same main ingredient). Kappa 0.61 is at the threshold on 60 videos from one labeler, so it carries wide uncertainty, and choosing the models on the same labels makes the figures optimistic.

### Source comparison on the 27 dishes judged (B against B2; A1 is pending)

Chosen videos are the top 3 of the candidates the selector accepts, ranked as shown; `p3` is scored by the evaluator (a different model from the selector J1); coverage is the share of dishes with 3 chosen videos.

| Source | Selector | Ranking | p3 | Precision of chosen | Coverage | Dishes with 0 relevant | Median views |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B | J0 title rule | views | 0.48 | 0.91 | 0.44 | 11 | 0.64 M |
| B | J1 | views | **0.78** | 0.93 | **0.74** | **1** | 1.37 M |
| B | J1 | like ratio | 0.78 | 0.93 | 0.74 | 1 | 0.77 M |
| B | J1 | newest | 0.78 | 0.93 | 0.74 | 1 | 0.63 M |
| B | J1 | views, one per channel | 0.77 | 0.91 | 0.74 | 1 | 1.37 M |
| B2 (asked for most viewed) | J0 | views | 0.42 | 0.90 | 0.26 | 10 | 0.35 M |
| B2 | J1 | views | 0.67 | 0.90 | 0.48 | 1 | 1.30 M |
| B2 | J1 | newest | 0.69 | 0.93 | 0.48 | 1 | 0.77 M |

- Replacing the title rule with a trusted judge raises coverage from 0.44 to 0.74 and p3 from 0.48 to 0.78 for B, with the same precision of what is chosen. English-titled relevant videos chosen: 0 under J0, 6 under J1.
- Asking the model to prefer the most viewed videos (B2) did **not** help: it returned fewer candidates (3.95 against 4.6 ids per dish) and the coverage fell to 0.48. Its median views of chosen videos are about the same as B's.
- Rankings differ little because each dish has only about 4 candidates; they mostly matter once A1 supplies 25.
- Among the 91 candidates the evaluator calls relevant, the old rule accepts 55: it accepts 55 of 81 Korean-titled and 0 of 10 non-Hangul-titled ones. Examples it dropped: a ham-and-cheese sandwich video with 114 M views, a French-toast video with 46 M views, and a 12 M-view video titled "달걀볶음밥" (an alias of the dish "계란볶음밥" that the old rule does not know).
- Ninety-two percent of verified candidates were public and embeddable (127 of 138).

### Decision

**None yet.** The rule needs A1, which does not exist until the next day with search quota. What the data already say: (1) the title filter was hiding relevant videos, so v1's conclusion is withdrawn; (2) among model-discovery sources B is better than B2; (3) a language-model selector is usable only with a validated model, and two of four candidates failed.

### Failure analysis

- Candidate count is the limit for B: 4.6 ids per dish means coverage cannot exceed what the model finds (0.74 at best here). A1 gives 25 candidates, so the pooled source U is the likely winner; this is untested.
- Selector and evaluator disagree on neighbouring dishes (for example sundubu stew for "tofu soup"; scallion pork stir-fry for "pork lettuce wraps"). The labels treat them as other dishes; the trusted models accept some of them, so precision is probably overstated.
- One selector call (`bacon-fried-rice`) returned an unusable answer after a retry; that dish is excluded.
- Shorts: 7 of the 91 relevant candidates are 60 s or shorter; the rule treats them like any other video.

### Limits

Single run; one labeler (the assistant) with 60 videos and a kappa at the threshold; the selector and the evaluator are language models, partly of one vendor family; relevance is judged from metadata, not from the video; 27 dishes with both judgements; the 16 planned combinations that use A1 or U have no data, and the 16 shown for B and B2 are computed on the 27 judged dishes, not on the planned paired set of 20; no confidence intervals could be computed without the paired set.

### To finish (next day with search quota)

```sh
cd server
PYTHONPATH=.:../research uv run python -m experiments.youtube_discovery_v2.run collect --allow-live-api --max-search 20
# label 30 videos drawn from A1 candidates (amendment 1), then judge the rest:
PYTHONPATH=.:../research uv run python -m experiments.youtube_discovery_v2.run judge --allow-live-api --selector anthropic/claude-haiku-4.5 --evaluator google/gemini-2.5-pro
PYTHONPATH=.:../research uv run python -m experiments.youtube_discovery_v2.run analyze --selector anthropic/claude-haiku-4.5 --evaluator google/gemini-2.5-pro
```

The judging step needs a new budget (about 0.6 USD for the evaluator on the 13 dishes still unjudged plus the A1 candidates). The raw data stay in the ignored `data/youtube-discovery-v2/` of this clone.
