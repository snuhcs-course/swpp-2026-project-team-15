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
