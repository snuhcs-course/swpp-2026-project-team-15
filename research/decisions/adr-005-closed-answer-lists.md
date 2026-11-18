# ADR 005: Close the suggestion answer to lists built per request

- **Status:** Accepted (2026-11-19)

## Context

The model answers a suggestion with dishes and, per dish, the ingredients the user has and lacks. In free text it invented dish names and ingredient names and sometimes listed an ingredient the user owns as missing. The provider used enforces JSON schemas with enums (`response_format`, strict). A schema whose `missing` choices were the whole ingredient list still let the model name an owned ingredient (8.3% of dishes).

## Decision

- `choices.py` builds the lists of one request from pure functions: dish names, the user's own items (trimmed, unique) for `have`, and for `missing` the dish list's key ingredients minus the ones the user owns by exact spelling (spaces ignored) or a synonym group.
- `prompts.suggest_schema(choices)` turns them into the answer format; `answers.check_suggest(..., choices)` drops anything outside them, so the guarantee holds even if a provider ignored the schema. A regression test covers "an owned ingredient is never returned as missing".
- The vocabulary is computed once when the service is built (no module-level state).
- Amended 2026-11-19 (round 3): the system text asks only for dishes the user can cook now or after a small purchase, and `answers.fewest_missing_first` orders the checked list by the model's own `missing` count (ties keep the model's order). The model walks the dish list in its given order instead of best first, so the server orders; nothing is dropped.
- Amended 2026-11-19 (round 4): the staples the server assumes at home (`staples.json` plus water, with their synonym spellings) are not `missing` choices. The service receives them from the composition root (`DishService(assumed=catalog.staples)`).

## Consequences

- On 27 frozen inputs the owned-as-missing error went from 8.3% of dishes to 0 with recall and precision unchanged; answers are about one third longer (+$0.0001 and about +1 s per call).
- A user item that matches no vocabulary entry (슬라이스치즈, 청양고추) does not remove its vocabulary form from `missing`; about 1% of dishes in a 15-list mapping set still showed such an item as missing.
- Adding a synonym group or a key ingredient changes the lists automatically.
- Lists are short at the median (16–18 dishes among answers that were not cut) but common inputs still run to the 4,096-token limit (two live requests: cut after 7 and 13 complete dishes, about 8 s), partly because seasonings were allowed `missing` choices; ordering by `missing` puts cookable dishes first (dishes with at most one missing ingredient among the first five: 0.53 to 0.62 on stored answers).

- Round 4: without the staples as choices, cut answers fell from 6 to 2 of 29 inputs, output tokens by about a quarter, and both demo inputs were answered in full (1.7 and 3.0 s); a rare runaway remains (밥 + 계란 + an unknown item: 114 dishes, cut and salvaged). Recall fell slightly (−0.08, interval −0.16 to −0.01).

## Not now

- No model mapping of unmatched items to the vocabulary: in the study it merged 14 of 16 traps (쪽파 → 대파, 두유 → 두부), which hides missing ingredients.
- No function-call route and no LangChain helper (empty or 404 answers on this provider).
- No cap on the number of dishes (`maxItems`): that would be a fixed count.
- No split of the request by dish category: it removed the cut answers and the slow tail but returned 62–90 dishes per input at three times the cost (round 4).
- No per-dish `fit` label: it made lists about three times longer and its labels did not match the missing counts.
