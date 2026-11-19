# Change kinds in "내 재료로 바꾸기" (2026-11-19)

The user chose the team repository's approach (server/recipe_revision/core.py): every change of a
revised recipe carries a kind, omission / substitution / quantity / servings / step, and the card's
separate "대체" button goes away. Written before measuring.

**Question.** With the kind added to the answer schema, (1) how often does the model's kind agree
with what the revised recipe shows, and (2) does adding it change how often an answer is unusable?

**Inputs.** The 124 + 4 stored recipes, fridge = each dish's key ingredients (the same input as
`../e2e_followups/`, whose served path gave 24 unusable answers of 124). One run, served path
(name table, one re-ask), new schema.

**Measures.** Outcome counts (revised / refused / failed by code). For each change of a revised
answer, the kind the rows imply: a referenced source row that is gone from the revised list with
no new row → omission; gone with a new (non-source) row added by the same change → substitution;
row still there → quantity or step. Agreement = model kind equals implied kind (omission and
substitution only; quantity/servings/step are reported as counts). All numbers reported; no
threshold.
