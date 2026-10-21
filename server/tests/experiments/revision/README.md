# Revision regression reference

These fixed inventories and recipe identities are checked against the runner configuration by the preserved test_loader.py. Runner usage is documented in [research](../../../../research/experiments/revision/README.md).

## Experiment conditions

E0/E1 compare the 16 recipes below (32 cases). E2/E3 compare garlic preparation
using the same four recipes under both inventories (8 additional cases).
Each CLI invocation selects one condition.

| Condition | Available ingredients (normalized ingredient IDs in parentheses) |
| --- | --- |
| AI-E0 | 김치(70), 밥(223), 계란(32), 소금(284), 설탕(282), 식용유(313), 후추(554) |
| AI-E1 | E0 + 양파(345), 간장(9), 두부(147) |
| AI-E2 (whole) | E1 + 바게트(214), 어묵(349), 밀가루(213), 마늘(169) |
| AI-E3 (minced) | E1 + 바게트(214), 어묵(349), 밀가루(213), 다진마늘(103) |

All listed ingredients, including seasonings, are considered available. Owned
quantities are unknown. Recipe and ingredient names below match the Korean DB records.

### E0/E1 recipes

| Recipe ID | Recipe name |
| --- | --- |
| 9 | 오므라이스 |
| 18 | 두부국 |
| 97 | 계란말이 |
| 112 | 김치적 |
| 114 | 두부김치 |
| 115 | 오믈렛 |
| 118 | 중국식볶음밥 |
| 130 | 두부양념조림 |
| 192 | 김치채소쌈 |
| 194 | 계란말이주먹밥 |
| 216 | 두부오믈렛 |
| 238 | 김치주먹밥 |
| 291 | 김치쌈밥 |
| 299 | 열무비빔밥 |
| 320 | 김치볶음밥 |
| 421 | 양파전 |

### E2/E3 recipes (execution order)

| Recipe ID | Recipe name |
| --- | --- |
| 335 | 마늘빵 |
| 395 | 어묵볶음 |
| 97 | 계란말이 |
| 421 | 양파전 |

E2 and E3 differ only in garlic ID; all other inventory items are identical.
Observe whether the model adapts preparation steps appropriately, using the
existing prompt and human evaluation criteria.
