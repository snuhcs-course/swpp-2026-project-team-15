# Decision log — effective state

[English](decisions.md) · [한국어](decisions.ko.md)

Reconciled 2026-10-20 against main `a27bf0a` and the latest reviewed branches. Earlier discussion/decisions remain in [meeting records](meetings/README.md) and the [prior log at b1e508a](https://github.com/snuhcs-course/swpp-2026-project-team-15/blob/b1e508af2be675ac6cad5403ace3d7e2fb1a49d2/docs/decisions.md). The table preserves main-baseline decisions; the dated integration section below records feature-branch changes.

| Topic | Effective state / evidence | Boundary |
| --- | --- | --- |
| Product and user review | Small-household cooking; photo-assisted candidates reviewed before inventory, then recipe browsing/detail (September planning and October 7 TA discussion) | One-person conversion, tools and allergies are intended requirements, not fully delivered |
| Backend | October 11 FastAPI/SQLModel/uv/SQLite choice is implemented and merged through PR #6 | PostgreSQL/Redis/Docker/public deployment remain future proposals |
| Local demo | USB adb reverse; laptop server, phone app; current script builds DB only if absent | Dataset version and existing server/reverse state must be checked |
| Recognition | Provider interface; mock or configurable Gemini. Mock selects a recorded fixture by image hash | Historical model availability/20-of-26 recall observations are dated, not current availability or universal quality claims |
| Baseline recommendation | Names, limited synonyms, ten assumed seasonings, at least one fridge ingredient, max_missing=3 by default | Temporary main behavior; new revision branch has different ID/filter/seasoning policy |
| Inventory/profile | Main uses memory; Hyeokjun's DataStore/VM implementation is on `88d3380` and its ancestor | Persistence is implemented on a branch, not an undecided technology choice or merged main feature. Full favorite objects are not restored |
| Android build | minSdk 26/target 36/compile 37; Retrofit/Gson/OkHttp | compile 37 supports the current AndroidX dependencies |
| Photo handling | October 14: client long-side 2048px preparation, selected EXIF retained, GPS excluded; server forwards uploaded content | Differs from the PM's unprocessed-photo premise. Sample 1090-token observations do not prove constant cost; recall impact remains to be checked |
| Testing | CI configured for server ruff/pytest coverage and Android lint/JVM/JaCoCo; local device checks separate | Baseline 33 passed/95%, older Android 2% lines; these do not cover the new combined implementation |
| Catalog | Main 701 ingredients, new bundle 560, shared IDs change meaning | New matching schema/importer and separate DB verification required; redistribution rights not established |
| AI reporting | Current course AI Guidelines v1.1; useful manual-fix comments conditional | Blanket AI-file markers are not required. Preserve existing attribution and original prompts |

## Integration decisions — 2026-10-20 feature branch

- Preserve Hyeokjun88d3380/1edadc0 and Suhyeon89fc8ba through merges on main a27bf0a; reuse original domains/repositories/filtering/revision/tests.
- Resolve saved names against a versioned560-item catalog, disclose unknown/ambiguous names, send the version header and preserve the old701-item DB separately. Prevent known ID mixing without replacing name persistence.
- Add dedicated ID DTO/RecipeSource while retaining the legacy API. Only water is assumed; filtering excludes water/resolved seasonings from counts. Sort by missing count, matched count descending and ID. Keep the complete absent-ingredient list distinct.
- Render original text and separate AI statuses/suggestions. Extend the new transport timeout for the existing sequential plan; cancel old coroutines and reject stale results without automatic transport retry. Restore favorite originals through read-only source lookup, with no AI call.
- Include runtime filtering/revision in coverage, original experiment tests and deterministic chain/state/reopen/device scenarios. Quick pre-commit integrity/lint checks complement CI. [Contract](iterations/iteration-2/integration-contract.md) and [execution](iterations/iteration-2/execution-report.md) contain scope and results.
- Allergy/tool metadata, authoritative serving conversion, semantic AI evaluation and source URLs remain gaps. Docker/nginx/deployment software is deferred to Iteration3 preparation by user decision.

These feature-branch decisions do not claim main merge, official Wiki publication or human review. No new teammate obligations/deadlines are assigned. Preserve previous decision history and publish official records separately.
