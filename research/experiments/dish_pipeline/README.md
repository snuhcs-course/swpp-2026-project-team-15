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
