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

## Results (2026-11-19, one run, `data/revision-kinds/run1.json`, outside git)

| Outcome (128 recipes) | Count |
|---|---|
| revised | 100 |
| failed: mentions an unavailable ingredient | 10 |
| failed: model answer cut or incomplete | 8 |
| failed: main ingredient dropped | 3 |
| failed: bad reference | 3 |
| failed: unavailable ingredient / unexplained change | 2 / 2 |

Unusable answers: 28 of 128 here against 24 of 124 in `../e2e_followups/` (old schema, before the
four new recipes and the name-table changes). One run each on inputs that are not identical, so
the difference is not attributed to the kind field.

Kinds in the 100 revised answers: omission 248, step 145, substitution 57, quantity 2, servings 0.
Against the rows (452 changes; 261 decided by the rows):

| model \ rows | omission | substitution | not decided |
|---|---|---|---|
| omission | 164 | 74 | 10 |
| substitution | 9 | 13 | 35 |
| step | 0 | 1 | 144 |
| quantity | 0 | 0 | 2 |

Limit of the row rule: it calls a change "substitution" when the revised list has any row the
source did not have, anywhere in the recipe, so the 74 omission/substitution cells are mostly the
rule's error (one added row in a recipe turns every omission of that recipe into "substitution").
Where the rule is unambiguous (no added row in the answer), the model said omission for 164 of
173 rows the answer removed (95%). Steps are labelled `step` when only steps change, as asked.

Model calls: one run of 128 revisions plus re-asks; the call count and cost were not recorded by
the runner (about 170 calls and well under $0.1 by the rate of `../e2e_followups/`, an estimate).
