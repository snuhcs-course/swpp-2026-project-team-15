# Model-call pipeline for dishes and YouTube links

Structure (fixed by the product decision): the phone sends its ingredients; the server gives the model the ingredient list and the dish-name list and gets dishes plus YouTube video-id candidates per dish; the server only checks with one batched `videos.list` call that each id exists and is embeddable; the phone shows cards. No title filter, no view sorting, no fixed card or link count.

Question: which arrangement of the model calls is cheapest while the cards appear fast and most dishes keep an embeddable video? Variants P1–P4, metrics, the judge and the decision rule are in `criteria.json`, committed before any call. The selection call uses the winner of `../dish_tokens/`.

Results are added below after the runs.

## Results (2026-11-16)

Runner commit `4597c17`, criteria `969dea5`; selection call = the token-study winner (V3, same answers as the baseline). 162 model calls in the run plus 2 diagnostic calls (cap 200), about $0.80 in total; YouTube `videos.list` only (no `search.list`). 12 seeded inputs (mean 18.9 selected dishes per input), one run, temperature 0. The relevance judge is an LLM given title, channel and description; it is **unvalidated** and not used by the rule.

| Variant | Dishes with ≥1 embeddable link | Links per dish | Existing ids | Judged relevant | Failed | Cost per request | Cards p50 / p95 | Videos p50 / p95 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P2 batched, ids, 3 links | 16.3% | 0.19 | 88.9% | 97.1% | 0% | $0.0083 | 2.5 / 4.1 s | 6.1 / 8.7 s |
| P2 batched, ids, 5 links | 15.4% | 0.17 | 88.1% | 96.8% | 0% | $0.0081 | 2.5 / 4.1 s | 5.8 / 7.8 s |
| P2 batched, ids + titles, 3 | 15.0% | 0.19 | 76.6% | 84.8% | 0% | $0.0083 | 2.5 / 4.1 s | 7.2 / 8.9 s |
| P3 single call, ids, 3 | 14.3% | 0.21 | 88.0% | 95.5% | 25% | $0.0090 | 6.2 / 19.3 s | 6.2 / 19.3 s |
| P3 single call, ids + titles, 3 | 8.8% | 0.13 | 70.8% | 100% (few links) | 25% | $0.0091 | 7.1 / 19.5 s | 7.1 / 19.5 s |
| P1 per dish, ids, 3 (modelled) | 0% | 0 | 0% | n/a | 33% | $0.140 | 2.5 / 4.1 s | 6.0 / 7.6 s |
| P1 per dish, ids, 5 (modelled) | 0% | 0 | 0% | n/a | 33% | $0.140 | 2.5 / 4.1 s | 6.3 / 7.9 s |
| P1 per dish, ids + titles, 3 (modelled) | 83.3% (10 of 12 dishes) | 1.75 | 84.6% | 90.5% | 8% | $0.146 | 2.5 / 4.1 s | 6.8 / 8.4 s |
| P4 lazy, ids + titles, 3: per opened card | 83.3% | 1.75 | 84.6% | 90.5% | 8% | selection $0.0005 + $0.0077 per opened card | cards 2.5 / 4.1 s | 6.8 s after the tap |

P1 and P4 rows come from 12 per-dish unit calls (one seeded dish per input); their request cost is modelled as selection cost plus the number of selected dishes times the mean unit cost (P4: plus 1 or 3 opened cards, $0.0081 and $0.0235 per request). "Cards" is when the dish list can be shown (the selection call; for P3 the single call); "videos" adds the discovery call (P1: the p95 unit call).

**Rule outcome: no variant qualifies.** The rule needs at least one embeddable link for 90% of dishes and p50 cards latency ≤ 6 s; the best variant (P1, per dish, ids + titles) reaches 83% and costs about $0.15 per request (about 300 times the selection call). P3 also misses the latency limit (p50 6.2–7.1 s, p95 about 19 s, one request in four fails).

### What the numbers show

- **The model does not reliably produce YouTube ids.** Asked for ids only, it often returns strings that are not video ids (UUID-like text) or nothing: in the per-dish ids-only runs 6 ids were returned for 12 dishes and none existed. With titles requested next to each id, the same call returned usable ids for 10 of 12 dishes. Whether titles make the model copy from search results rather than guess was not tested separately.
- **One batched call finds links for few dishes**: with 19 dishes per request, one web search covers about 1 in 6 dishes (0.19 links per dish). The ids that do come back are mostly real (about 89% exist) and relevant by the judge (97%), so the rule check removes few; the loss is coverage, not wrong links.
- **Cost is dominated by the web-search calls**: each web call costs about $0.008 whatever the output size (ids or titles; 3 or 5 links change cost by under 3%), while the selection call costs $0.0005. Output size (ids vs titles) matters for tokens (35 vs 860 output tokens per call) but not for the bill. The cheapest structure is therefore the one with the fewest web calls: P2 at about $0.008 per request but 16% coverage, or P4 lazy loading at $0.008 per opened card.
- **Content filter**: 4 of 12 ids-only unit calls ended with `content_filter` (for example for `김치죽`); this appears as a failure and is not understood.
- **Latency**: the cards appear after the selection call (p50 2.5 s, p95 4.1 s) in P1, P2 and P4; videos follow about 3.5–5 s later. P3 delays the cards to 6–7 s and has a long tail.

### Limits

12 inputs, one run, one discovery model and plugin (not Google grounding; a handful of search results per request); P1 and P4 are modelled from 12 unit calls, one dish per input, so their coverage rests on 12 dishes (10 hits); the judge is unvalidated; differences below about 10 points of coverage or $0.002 are within noise. Title-based relevance only. The structure with a model-found link was not compared with the search-API method here, so this result says nothing about which discovery method is better, only about the cost and coverage of model discovery inside this pipeline.

## Round 2: relevance of model-provided links (criteria frozen 2026-11-16, before the analysis)

No new call: the stored outputs of the second YouTube discovery study are analysed offline. What is counted, the judges used and the failure types are fixed in `criteria_round2.json`. Results are added below after the analysis.

### Round 2 results (2026-11-16, offline, no call)

Question: if the server only checks that a link exists and can be embedded, how many of the links a model with web search provides are recipe videos of the dish? Data: method B of the second YouTube discovery study (`../youtube_discovery_v2/`, now in this branch; it was first written in a separate `yt-discovery` branch), 27 dishes with both judgements. Relevance is the gemini-2.5-pro judgement (E); claude-haiku-4.5 (J1) is shown for comparison. Run: `PYTHONPATH=.:../research uv run python -m experiments.dish_pipeline.analyze_links` (from `server/`, after copying `candidates.json` and `judgements.json` to `data/youtube-discovery-v2/`).

| Per dish (mean over 27) / total | E | J1 |
| --- | --- | --- |
| Links the model provided | 4.5 / 122 | same |
| Links that exist | 4.1 / 110 (90%) | same |
| Links that exist and are public and embeddable | 3.9 / 104 (85% of provided) | same |
| Relevant links among those | 2.9 / 79 | 3.0 / 81 |
| **Share of embeddable links that are relevant** (pooled; mean over dishes) | **76% (73%)** | 78% (75%) |
| Dishes with 0, 1, 2, 3 or more relevant links | 1, 4, 5, 17 | 1, 4, 2, 20 |
| Dishes with at least one relevant link | 26 of 27 | 26 of 27 |
| First embeddable link (the model's first choice) is relevant | 93% of dishes | 96% |

- The two judges agree on 90% of the 104 links (kappa 0.73).
- **Old title rule on the same links** (the normalised title contains the dish name): it accepts 51 of the 104 (49%) and gives a relevant link for 17 of 27 dishes. It accepts 5 links that E rejects and rejects 33 that E accepts.
- Method B2 (the model asked for the most viewed videos): 109 links provided, 92 embeddable, 67 relevant (73%), 26 of 27 dishes with at least one.

**Why the 25 embeddable links that E rejects were rejected** (the judges did not store reasons; one reading of title, channel, description and length by the assistant, `failure_types_round2.json`):

| Type | Links | Example |
| --- | --- | --- |
| Neighbouring dish | 16 | kimchi fried rice for "kimchi tuna fried rice"; kimchi stew for "spam kimchi stew"; mushroom stir-fry for "mushroom fried rice" |
| Other dish | 3 | a different dish altogether (a pork-chop recipe for "pork lettuce wraps") |
| Short (60 s or less) | 3 | a 23-second microwave steamed-egg clip (also a correct dish) |
| Vlog or eating show | 1 | an idol vlog that makes the dish |
| Other | 2 | judged irrelevant although the title names the dish (shrimp fried rice from a recipe channel; a janchi noodle video): probably judge errors |

**Reading.** Without any relevance check, about three of four embeddable links are real recipe videos of the dish and 26 of 27 dishes get at least one. The first link is relevant for 93–96% of dishes, so ordering by the model's own choice is already good at the top. Most errors are a close neighbour of the dish (kimchi fried rice for a variant): these may be acceptable for a student who wants a similar recipe, and the judges and the labeller differ on them. The old title rule is worse than no filter on this data: it keeps only 49% of the embeddable links and leaves 10 dishes without any link it accepts.

### Limits

Relevance comes from two language models that agreed with one labeller's 60 labels at kappa 0.61, barely above the pre-set 0.6, and judge metadata, not the video. 27 dishes, mostly fried-rice dishes (first in the list), one run of the model discovery. Failure types are one person's reading. The link numbers include 12 ids (10%) that do not exist and 6 existing videos that are not embeddable.

## Round 3: wording of the discovery request (criteria frozen 2026-11-16, before any call)

Question: how should the request to a web-search model be worded so that the links that survive the embeddable/public check are cooking videos of exactly the requested dish? The structure is fixed: the server asks the model for links at request time and only checks that a video exists, is public and can be embedded, keeping the model's order (no title filter, no view sorting, no count cutoff).

| Variant | Request (the full texts are in `criteria_round3.json`) |
| --- | --- |
| OLD | the earlier request (popular, well-rated recipe videos); stored outputs, reference only |
| D0 | videos to follow along and cook the dish (how-to recipe videos), nothing else |
| D1 | D0 + "a young adult cooking alone for the first time, i.e. a 자취생" |
| D2 | D0 + observable conditions only: few ingredients, simple tools, easy-to-follow steps, short running time |
| D3 | D2 + "exactly this dish, no neighbours or variants" + "exclude shorts, vlogs, mukbang, reviews, ads" |

Same 27 dishes and the same two validated judges as the second YouTube discovery study (gemini-2.5-pro as primary, claude-haiku-4.5 as second; prompt and rubric unchanged). Rule: choose the highest relevant share among variants whose dishes-with-a-relevant-link and links per dish stay within 1 dish and 0.5 of D0; inconclusive (keep D0) when the paired 95% interval against D0 contains 0. Whether a video is "easy for a person living alone" is **not** measured by any judge; running time is only a weak proxy. Run: `PYTHONPATH=.:../research uv run python -m experiments.dish_pipeline.run_round3 plan|collect|judge|analyze` from `server/` (dry run unless `--allow-live-api`).

### Round 3 results (2026-11-16)

Setup as frozen in `criteria_round3.json` (commit `3aec6a1`, recorded as `9c8e63e` before the branch history was rewritten on 2026-11-19; same content, but the rewritten commit carries a later commit time than the results; one amendment, below). 27 dishes x 4 variants, one run, temperature 0. The usable links of a variant are the model's links that exist, are public and embeddable, in the model's order; relevance is the judgement of gemini-2.5-pro (E, primary) and claude-haiku-4.5 (J1). Calls: 118 discovery calls plus 3 attempts of one failed call (121 of 140), 52 judge calls, 27 `videos.list` requests, $0.81 for discovery and $0.47 for judging ($1.28 of 1.80).

| | OLD (stored) | D0 follow along | D1 + 자취생 | D2 + observable conditions | D3 + exact dish, excludes |
| --- | --- | --- | --- | --- | --- |
| Links provided / exist / usable | 122 / 110 / 104 | 118 / 111 / 102 | 114 / 111 / 103 | 114 / 110 / 103 | 112 / 89 / 83 |
| Usable links per dish | 3.85 | 3.78 | 3.81 | 3.81 | **3.07** |
| **Relevant share of usable links (E)** | 76.0% | **82.4%** | 75.7% | 77.7% | 75.9% |
| Relevant share (J1) | 77.9% | 77.5% | 75.7% | 75.7% | 75.9% |
| Dishes with at least one relevant link (E) | 26 | 26 | 26 | 26 | 25 |
| First usable link relevant (E) | 93% | 96% | 93% | 96% | 92% |
| Shorts (60 s or less) | 6.7% | 8.8% | 4.9% | 9.7% | 14.5% |
| Running time of usable links, quartiles (s) | 248 / 398 / 567 | 215 / 354 / 565 | 248 / 368 / 564 | 222 / 345 / 563 | 178 / 298 / 541 |
| Links with 자취 in title or tags | 11.5% | 9.8% | 7.8% | 6.8% | 14.5% |
| Cost per request; median latency | $0.0075; 3.2 s | $0.0075; 3.4 s | $0.0075; 3.4 s | $0.0074; 3.3 s | $0.0075; 4.6 s |

Paired difference to D0 in relevant share (E; pooled over dishes, 95% bootstrap over dishes): D1 -6.6 points (-15.8 to +2.1), D2 -4.7 (-14.0 to +4.4), D3 -6.4 (-17.0 to +4.7); with J1: -1.7, -1.7, -1.5 (all intervals contain 0). OLD minus D0: -6.4 (-12.7 to -0.2). E and J1 agree on 90.5% of the 495 usable links (kappa 0.73).

**Decision by the frozen rule: keep D0.** Eligible were D0, D1 and D2 (D3 fails the links-per-dish condition: 3.07 against 3.78 - 0.5); D0 has the highest share and the others are not better, so no variant is adopted (the same under J1).

What the numbers show:

- **No extra wording beat the plain "follow along and cook it" request.** All four variants lie within about 7 points of each other and every interval against D0 contains 0, so the differences are not distinguishable from run-to-run variation of the search.
- **The word 자취생 did not draw 자취 videos.** Links with 자취 in the title or tags fell from 9.8% (D0) to 7.8% (D1) and 6.8% (D2), so the audience word was not used as a search keyword here. It also did not improve relevance. This is one wording, not a general statement.
- **The "exactly this dish, exclude ..." wording (D3) made the model return more ids that do not exist** (89 of 112 exist, against 94% to 97% for the others), leaving 3.07 usable links per dish, and more shorts (14.5%). It is the only variant that clearly lost something.
- **D0 vs the earlier request (OLD):** D0 is 6.4 points higher (interval -12.7 to -0.2 for OLD minus D0, just excluding 0). They differ in two things at once (D0 no longer asks for "most popular, best-rated" and says "follow along"), so which change helped is unknown.
- **Running time**: D2 and D3 ask for short videos; the median fell from 354 s (D0) to 345 s and 298 s. Running time is only a weak proxy of "simple"; the judges do not measure "easy for a person living alone". That has to be judged by people.

Failure types of the usable links E calls irrelevant (pre-set rule on title, tags and length; the judges' reasons were not read one by one): D0 18 links (10 other, 4 other dish, 2 vlog or show, 2 short); D1 25 (13 other, 5 neighbouring dish, 4 vlog or show, 3 other dish); D2 23 (12 other, 6 neighbouring dish, 2 vlog or show, 2 short, 1 other dish); D3 20 (8 other, 5 neighbouring dish, 4 short, 2 vlog or show, 1 other dish); OLD 25 (16 other, 3 neighbouring dish, 3 short, 2 other dish, 1 vlog or show). "Other" is the largest class under this rule because a neighbouring dish is only detected when its catalog name appears in the title; the earlier manual reading of OLD found 16 neighbouring-dish links. Neighbour-dish errors are therefore under-counted here, and the types are a proxy.

**Amendment** (written before the repeat): the call for egg-fried-rice with variant D1 failed after two retries (HTTP 429); it was repeated once (it succeeded: 5 links). The failed attempt is kept in the stored data.

### Round 3 limits

One run per variant; the web search of the model changes from day to day, so a repeat could rank the variants differently. 27 dishes, many of them fried-rice dishes. Relevance comes from two language models (kappa 0.61 against one labeller's 60 labels in their validation) that read title, channel, description and tags, not the video. The judgements of videos judged in the earlier study were reused, the others were judged in one batch per dish and judge with the order shuffled, so the judge saw batches of different composition. OLD and D0 differ in two ways. The wording of each variant is a single sentence; other sentences could behave differently. "Easy to follow for a person living alone" and the quality of the videos for that audience were not measured.

## Result files

Not committed. Round 3: `analysis.json`, `collected.json`, `judgements.json` in `artifacts/dish-recipes/run-data/ytdemo-prompt/data/dish-pipeline-round3/` (a former working copy), sha256 first 12 hex digits `124f438d911e`, `3c137e090a60`, `969c71941da7`.
