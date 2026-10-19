# Iteration 2 integration contract

Recorded 2026-10-20 before integration implementation. Jaehyuk's integration scope; original Hyeokjun/Suhyeon histories and behavior remain the baseline. This is not a new assignment to other contributors.

## Inputs and preservation

main a27bf0a; previous local-integration b1e508a (identical tree); Hyeokjun 88d3380 (includes backend1edadc0); Suhyeon89fc8ba. Local documentation changes are preserved separately. Original repositories/domain/ranking/filtering/revision and existing tests are reused. Existing APIs and test doubles remain supported; integration adds a dedicated Android adapter and read-only catalog/source endpoints. Original design and attribution stay intact.

## Contract decisions

- Retain name-based DataStore inventory; resolve against the server catalog immediately before every new recommendation. Exact trimmed case-insensitive names first; only the existing egg alias 달걀→계란 when no exact match. Unknown/ambiguous names remain visible as unmapped, never fabricated IDs.
- The server exposes catalog SHA-256 and IDs/names. The client sends that version in X-Ingredient-Catalog; a changed catalog yields409 before AI. Water ID204 must actually denote water. A separate imported560-ingredient DB replaces no existing local DB.
- New DTOs retain original textual servings/time, quantities, repeated ingredient rows, ordered steps and tips, and revision metadata. Original is always available; suggested content is explicitly labeled and separately selectable. No claim of verified safety, exact one-serving conversion or semantic correctness.
- Client recommended order: filtering missing_count ascending, matched_count descending, recipe ID ascending. Other dropdown modes reuse Hyeokjun's sorter; explicit filtering count is distinct from the displayed full list of absent ingredients, including seasonings. Only water is assumed in the new API.
- Keep the legacy MyLittleChefApi/DTO path for compatibility tests and clients. Actual app navigation injects a separate ID-based RecipeSource. Do not silently fall back to the old endpoint on new endpoint failure.
- Default revision_limit3; sequential per-call60seconds can consume180seconds. New recommendation transport read210seconds/call240seconds, no automatic retry. Generation guard and cancellation preserve newest client state. Client cancellation cannot guarantee an already running synchronous server/provider call stops; no automatic paid retries.
- Loading, empty, mapping warning and network/server error are distinct. HTTP200 with revised/refused/failed/not_attempted is not treated as all-AI success.
- Existing favorite IDs remain in user DataStore. Restore missing recipe originals through read-only source lookup, without calling AI. Previous AI suggestions are not guaranteed across restart. Allergy/tool filtering remains unsupported due to absent metadata; disclose it instead of inventing data.

## Test plan

Reuse all existing tests unchanged. Add server chained analyze→catalog→recommend cases, catalog mismatch/no-AI, source lookup, legacy compatibility, mixed/empty/failure paths. Add Android mapping/DTO validation, adapter-to-VM status/sort/error flows, cancellation/stale response and fresh DataStore reopen tests; Compose detail/flow tests and USB checks provide UI evidence. Cases trace to US02/03/04/05/06 and NFR01/02/03/05/06; protected source expectations are preserved verbatim in docs/acceptance.

Existing Jaehyuk draft coverage goals90% vision/API and60% wiring are preserved. Add a personal integration target80% combined statement/branch coverage over server app+recipe_filtering+recipe_revision, justified by deterministic provider/DB isolation; compare legacy targets separately. Android adapter/domain/VM get scenario assertions and reported per-class coverage; do not invent a team-wide numeric client target. Experiment runner tests are collected explicitly but CLI/report utilities remain outside runtime coverage. Screens/generated/platform-dependent code are disclosed separately.

CI runs locked Python lint/tests/coverage and Android lint/JVM/build/report artifacts; deterministic flows need no secrets/paid services. Device tests run separately when an emulator/USB target is available. pre-commit runs the same quick lint/format checks without full Gradle or live AI. Docker/nginx/deployment stack is deferred to Iteration3 planning by user instruction.

## Course and remaining gaps

PO20–21: feature/unit/critical-flow integration, US/AC mapping and regression. Testing Guidelines1–2: Plan/Results and measured evidence. TestingIII24: human-owned acceptance/source expectations; no weakened/deleted/skipped tests. Official Wiki snapshot still10-09; latest Sheet P3/P4/P25/P26 and P27–P35 are read-only references. Figma/eTL latest contents require user input. Official publication, review/merge and eTL submission require actual external evidence and are never inferred from a local draft or successful test.
