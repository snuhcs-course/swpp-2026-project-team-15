# Follow-ups of the phone test (2026-11-19)

The phone test of the signed app (artifacts, outside git) left server, app and data issues. Each is
reproduced, measured and then fixed; numbers are reported, not judged against a preset bar.

## 1. Unrelated ingredients get dishes ("초콜릿" alone)

**Observed.** With only 초콜릿 in the fridge the demo server suggested 35 egg dishes, each with
`have: ["초콜릿"]`, 3 of 3 times. Earlier the same input showed the app's empty state.

**Question.** Why does the server return dishes that share no key ingredient with the fridge, and
what change keeps only dishes that do, without dropping dishes for ordinary fridges?

**Protocol (written before measuring).**
- Inputs: unrelated fridges 초콜릿 / 우유 / 사과 / 콜라 / 과자 / 바나나; ordinary fridges 계란+밥,
  김치+밥, 두부, 양파+대파+감자, 햇반+계란 (a stand-in name), 참치캔+김.
- Runs: the served suggestion path (service with the real model, google/gemini-2.5-flash via the
  existing key) at HEAD, 3 runs per input; the same inputs once at 4f09726 (the morning build whose
  phone test showed the empty state) to locate the change.
- Measured per run: dishes returned; dishes whose `have` covers none of the dish's key or optional
  ingredients under the server's name table ("unsupported"); latency; tokens.
- Then the fix variant (server keeps a `have` entry only when it covers one of the dish's
  ingredients and drops dishes left with none) is replayed offline on the same answers (no new
  calls) and once live per input.

**Amendments (during the runs).** The first run used google/gemini-2.5-flash; the served model is
the default google/gemini-2.5-flash-lite (the demo sets no DISH_LLM_MODEL), so the runs were
repeated with it. The second run built the service without the staples as assumed names and did
not reproduce the phone; the script now builds the service with the app's own builder. The morning
build 4f09726 was run once per input from an exported tree (git archive, no branch).

**Results** (`results.json`; raw answers in `data/e2e-followups/`, outside git; 132 suggestion calls
in all, about $0.2 estimated from the logged token counts of the served model).

| Fridge | 4f09726 dishes (uses none) | HEAD dishes (uses none), 3 runs | Fixed dishes |
|---|---|---|---|
| 초콜릿 | 35 (35) | 35 (25) each run | 0 |
| 우유 | 71 (68) | 36 (23) | 2 (스크램블에그-type dishes that use 우유) |
| 사과 / 콜라 / 과자 | 80 / 81 / 68 (all) | 36 (25 / 25 / 21) | 0 / 0 / 0 |
| 바나나 | 17 (17) | 17 (11) | 0 |
| 계란 + 밥 | 118 (74) | 36 (7) | 34 |
| 김치 + 밥 | 12 (0) | 12 (0) | 12 |
| 두부 | 11 (6) | 11 (5) | 5 |
| 양파 + 대파 + 감자 | 28 (18) | 28 (12) | 21 |
| 햇반 + 계란 | 18 (0) | 18 (0) | 18 |
| 참치캔 + 김 | 9 (0) | 9 (0) | 9 |

"uses none" = no item of the fridge is one of the dish's key or optional ingredients under the
server's name table; a staple assumed at home does not count.

**Cause.** Not one of today's changes: the morning build gives the same 35 dishes for 초콜릿. The
served model, asked for dishes the user "can cook now", walks the dish list for fridges it cannot
match and fills `have` with the only allowed value (the user's own item). The server checked that
`have` was one of the user's items but never that the dish uses it. The phone's earlier empty state
for 초콜릿 was not reproduced with either build (3 + 1 runs); a different fridge or a different
model answer at that time cannot be ruled out.

**Fix.** The server decides `have` itself: the user's items that are the dish's own ingredients
(name table, staples excluded), in the user's order; a dish that uses none is dropped. The model's
`missing` and order are kept. Repeated runs at HEAD were identical, so one live run of the fix per
input was taken; the offline replay of the HEAD answers gives the same counts.

**Limits.** 12 fridges; the model still spends about 4 s on fridges that end with no dish (the
answer is cut at the token limit); `have` now lists only items the dish uses, so a model's mention
of a stand-in (e.g. 대파 for 쪽파) no longer shows.

## 2. Broken image and unknown dish ids

**Observed.** A broken PNG made by the phone test was sent to the model and came back as 502
(0.24 s); an unknown dish id gave 422 on the video and substitution routes but 404 on the recipe
and revision routes, where 404 also means "known dish, no recipe".

**Fix, no model calls.** Before any model call the server checks the file's structure: it must
start like a JPEG, PNG, WebP or HEIC/HEIF file, and a PNG must contain its end chunk (a cut-off PNG
lacks it); otherwise 415 "Not a readable image". Nothing is decoded, so a JPEG cut short in the
middle still reaches the model (limit). Every dish route now answers 422 for an id outside the
dish list; 404 keeps one meaning. The app never sends an unknown id, so its handling does not
change. Tests fail on the old code (3) and pass on the new.

## 5. Revised recipes that point at rows or steps that do not exist

**Observed (main thread, code reading).** 카레라이스 (11 ingredient rows, 14 steps, no 밥 row) with
the fridge 밥·카레·감자·양파·당근 failed twice: the model's fifth change "밥은 가지고 있으므로
추가합니다" had `ingredient_refs: [14]`, a step number, so the check rejected it (bad_reference),
and the re-ask returned the same answer. Its other changes had `ingredient_refs == step_refs`
(1·1, 2·2, 4·4, 8·8): in range, so they pass, but probably wrong.

**Question.** How often do revised answers carry out-of-range or mirrored references, and which of
three changes reduces that: (V1) per-request closed choices, `ingredient_refs` items limited to
1..rows and `step_refs` items to 1..steps (the idea of ADR 005; a probe call showed the provider
accepts and enforces integer enums); (V2) a re-ask message that names the change, the bad number
and the valid range; (V3) both. V0 is the served path.

**Protocol (written before measuring).** Inputs: every stored recipe (124) with the fridge = the
dish's key ingredients, the served model and served reviser (name table, one re-ask). Per variant,
one run per recipe. Measured: final status (revised / refused / failed by code), first-answer
violation codes, bad_reference on the first and on the final answer, delivered answers with at
least one mirrored change (`ingredient_refs == step_refs`, non-empty), model calls, latency.
Decision by the numbers in words; no preset bar. The recipe build leaving 밥 out of the curry rows
is noted, not fixed.

## 3. App and status fixes (no model calls)

| Observed on the phone | Cause | Fix |
|---|---|---|
| Third autocomplete row hidden behind "냉장고에 반영" with the keyboard open | the list grows below the visible area of the scrolling column | the list scrolls itself into view when it appears |
| 감자 shows the carrot icon | both use the shared "root" icon | a potato icon for 감자 and 토란 |
| Tapping an ingredient suggestion does nothing | the sheet was information only | a "냉장고에 추가" button per suggestion |
| "대체" with no result shows two sentences saying the same | the app's own sentence and the server's note | the app's sentence only when the server sends no note (the server text is kept: the frozen dish evaluation scores it) |
| The ⓘ dialog does not mention recipes or "내 재료로 바꾸기" | written before those features | two sentences added |
| A seasoning the user put in the fridge shows 기본 양념 | the server checked "staple at home" before "owned" | owned first (server; the current app reads it). A staple still never makes a dish count as using the fridge, so pantry seasonings do not bring back item 1 |
