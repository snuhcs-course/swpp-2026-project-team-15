# Removing vertical videos (Shorts) from the stored dish videos

Decision (user, 2026-11-19): vertical videos leave the stored lists. On the phone a vertical video fills 31.6% of the app's 16:9 player area, a horizontal one all of it.

## Protocol (fixed before any call)

Inputs: the verified stored links (128 dishes, 365 links) and the orientation of every link from `videos.list` `player.embedWidth`/`embedHeight` (see `../dish_recipes/README.md`, "Vertical videos").

1. **Landscape list.** Drop every link whose orientation is vertical; keep horizontal and square ones in their stored order.
2. **Refill.** Targets: the dishes left with no link and the dishes left with one link. Per dish:
   - candidates = the server's own discovery request (web-search model, the "follow along and cook" wording) then the official search (`search.list`, "<dish> 레시피", 25 results, embeddable, Korean region); an earlier search of the same dish (2026-11-19 01:06 KST) is reused instead of a new call;
   - ids already judged for the dish, or already stored, are skipped;
   - one `videos.list` call per 50 ids (snippet, contentDetails, statistics, status, player): keep public, embeddable, processed and **not vertical** (horizontal or square; unknown orientation is dropped);
   - the two judges validated earlier (`google/gemini-2.5-pro`, `anthropic/claude-haiku-4.5`, same prompt) judge relevance from metadata;
   - a person reads every candidate in order (with the judges' answers) until the dish has five links, the same per-dish cap as the earlier search supplement; only "relevant" is kept.
3. **Recipes.** The stored recipes whose source video is vertical are rebuilt with the same build (`run_video_recipes build`, `google/gemini-2.5-flash`, Google AI Studio, up to three verified videos per dish, same checks) from the new landscape list; then the same hand review of dishes whose cooked dish differs from the dish name.

Measured: links and dishes per count before and after, candidates found and dropped by reason, judge agreement with the review, recipes rebuilt or flagged, YouTube quota units, model calls and cost. No pass/fail thresholds; the numbers are reported and interpreted.

Outputs: video data, titles and recipes are third-party content and stay outside the repository (`artifacts/dish-recipes/`); only counts are recorded here (`results.json`).

**Amendment (before the recipe step, 2026-11-19).** The user added the 32 stored recipes whose main ingredient differs from the dish list (revision round 3, `../dish_revision/README.md`). For the union of both sets (47 dishes) the stored landscape videos are tried in order (the served recipe's own video is skipped for the 32); the first valid recipe whose main rows are all available with the fridge = the dish's key ingredients (round 3's offline measure, reviewed name table) is taken. A vertical-source dish with no such video takes its first valid landscape recipe; a mismatch-only dish with none keeps its recipe. Measured before and after: the offline count, and the served revision (name table and one re-ask) on the changed recipes with the key ingredients only, both versions run now, one run each. Local agent CLI (Gemini) was checked first as a cheaper route: it has no video input (only files, shell and web tools), so the paid video input stays.

## Results (2026-11-19)

Counts only; video data and recipes stay in `artifacts/dish-recipes/` (`results.json` here).

| | before | after |
|---|---|---|
| Stored links (vertical / horizontal / square) | 365 (94 / 270 / 1) | 439 (0 / 430 / 9) |
| Dishes with 0 / 1 / 2 / 3 / 4 / 5 links | 0 / 26 / 36 / 24 / 15 / 27; once vertical links are dropped 12 / 35 / 38 / 22 / 11 / 10 | 0 / 4 / 39 / 26 / 16 / 43 |
| Recipes made from a vertical video | 24 of 124 | 0 of 124 |
| Recipes with a main row missing although the card counts nothing missing | 32 | 16 |

**Refill (47 dishes).** 1,064 new ids (search results and 179 discovery-model proposals); 634 were vertical, 37 did not exist, 14 not playable; 379 landscape candidates were judged and read in order, 227 read until each dish had five links: 168 relevant, 30 irrelevant, 20 a neighbouring dish of the list (김치볶음밥 for 참치볶음밥, 소시지야채볶음 for 햄야채볶음, 제육볶음 for 제육덮밥, the rule of the earlier reviews), 9 unsure (not kept). Both judges said yes on 182 pairs, of which 156 were relevant on reading; 15 of the other 26 were neighbouring dishes, a rule the judges are not told. Seven of the 168 kept links came from the discovery model. Dishes still on one link: 제육덮밥, 김치비빔밥, 간장닭구이, 삼겹살김치구이 (searches return mostly vertical videos or neighbouring dishes).

**Recipes (47 dishes, 92 build calls).** 31 got a landscape recipe whose mains are covered; 2 vertical-source dishes kept a gap (고추장찌개: all five videos use pork, which the dish list does not count; 김치비빔밥: 열무김치); 14 mismatch dishes found no covering video and keep their recipe (e.g. 커리라이스 all use meat, 스팸마요덮밥's 스팸 is not covered by 햄 in the name table, 비빔밥 videos use beef or tuna). One accepted video was removed by reading (김치덮밥: the video cooks 김치볶음밥) and the next was taken.

**Revision with the key ingredients only (the 33 changed recipes, served path, one run each).** Before: 19 revised, 5 refused, 7 failed, 2 provider cut. After: 22, 3, 6, 2. Paired: 12 revised both times, 10 moved to revised, 7 moved away from it, 4 not revised either time. The refusals that named a video-only main (오이, 새우, 간 돼지고기, 밥) are gone; the moves in both directions are of the size seen between repeated runs in round 3, so the gain in revised answers is not separable from run-to-run variation. A new one: the new 참치샐러드 recipe has a row named 샐러드 (garnish), which the dish-name prescreen reads as the dish's own name and refuses.

**Limits.** One reviewer read the links (titles and descriptions, not the videos); the main labels are one model's judgement; square videos (9) are kept as not vertical but fill about 56% of the 16:9 player width; one run per revision variant.

**Cost.** YouTube quota about 4,060 units (40 searches, the rest `videos.list`). Model calls: discovery and judges 201 calls $3.19; recipe builds 92 calls $4.17; revision measure 87 calls about $0.04 (from tokens). Total about $7.40. Local agent: one capability check, no cost.

**Follow-up (2026-11-19, main thread).** The 참치샐러드 row named 샐러드 (no amount, listed next to 야채) was renamed in the stored data to 샐러드용 채소, so the prescreen no longer reads it as the dish's own name. A server-side rule was not chosen: of the 106 rows across the stored recipes whose name occurs in their dish name, 95 are main rows, and the 11 others include true refusals (김치덮밥's 김치, 콘치즈's 치즈), so neither role nor dish-type words separate this one case. The server now also drops vertical videos itself (`youtube.py`, `part=player` with `maxWidth` in the same `videos.list` call, no extra quota), so a model-discovered Short never reaches the app.
