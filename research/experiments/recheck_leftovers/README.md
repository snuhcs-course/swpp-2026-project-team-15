# Leftovers of the phone recheck (2026-11-19)

Items found when the store build was checked on the phone after the follow-up fixes
(`../e2e_followups/`). Each item: question, what is measured, then results. Written before
measuring; results are appended below with the date.

## Protocol

1. **짜장라면 is never suggested for 라면·양파·돼지고기 (2/2 on the demo).** Question: does the
   model leave it out, or does the server drop it after the model names it? Measure: the raw model
   answer for that fridge (3 calls) and, for each named dish, whether the server keeps it
   (`check_suggest`), with the dish list's key ingredients of 짜장라면 next to the fridge names.
2. **One web fridge photo always gives 502 "incomplete recognition".** Question: what in the
   model's answer makes the server call it incomplete (output cut at the token limit, a schema
   field missing, an empty list)? Measure: the raw provider response for that photo (finish reason,
   output tokens, parsed fields), 2 calls, and the same for one photo that works.
3. **천일염 shows "없음" in 감자국; 식초 shows "없음" in 마늘새우볶음.** Question: which names in the
   stored recipes are grades or forms of a staple or of an onboarding seasoning but are not mapped?
   Measure: every recipe row name against the name table and the staples, listing unmapped rows
   that contain a staple's name. No model calls.
4. **청양고추 shows a tomato-like icon.** Question: which icon key does the app's ingredient table
   give it, and is there a closer existing icon? Measure: the table row and the icon list.

## Results (2026-11-19)

Raw outputs: `data/recheck/` (outside git: item1-*.json, item2-*.json, item3-names.json).

| Item | Measured | Cause | Change |
|---|---|---|---|
| 1 짜장라면 | Fridge 라면·양파·돼지고기: the model named 6 dishes, never 짜장라면 (3/3 identical); the server dropped only 김치볶음밥. Fridge 짜파게티·양파·돼지고기: 짜장라면 named and kept (2/2). | The model is right: the dish is cooked from the jjajang ramen product (the stored recipe has a 짜파게티 스프 row). The dish list had plain 라면 as its key ingredient. | Key ingredient 라면 → 짜장라면; name table 짜파게티, 짜파게티스프, 짜장라면스프 → 짜장라면; 짜장라면 is a kind of 라면 (covers a recipe's 라면 row). After: with 짜파게티 it is suggested (2/2); with plain 라면 it is not, as intended. |
| 2 photo 502 | fridge1: finish `length` at 2,034 output tokens, 1 item finished, then the model looped on tab characters inside a package label (`"Ch\t\t\t…`); fridge2: `stop`, 439 tokens, 12 items. | A generation loop on label text, not the schema or the image. | The server keeps the items finished before the cut (same salvage as the dish answers, moved to `app/json_lists.py`); a cut with no finished item is still an error. After: fridge1 returns 1 item instead of 502. The loop itself is not fixed: the prompt and model belong to the recognition study and were not changed. |
| 3 names | 8 unmapped rows contain a staple's name (국간장 10, 맛소금 5, 맛간장 2, 만능간장, 아미노 간장, 초간장, 백후추, 돼지고기 고추장볶음); 천일염 has no staple's name in it. | Name table gaps. 식초 is not a staple: it is an onboarding choice, and the recheck fridge had not picked it, so "없음" was correct. | 천일염 → 소금, 백후추 → 후추. The soy-sauce mixes and 맛소금 stay separate kinds (as decided in revision round 3). |
| 4 청양고추 icon | The table gave all 9 pepper rows the `fruit_vegetable` icon (the tomato-like one); no pepper icon existed. | Missing icon. | New `chili` icon; the 9 pepper rows use it. |

Model calls: suggestions 7 (about $0.003), recognition 4 (about $0.003).
