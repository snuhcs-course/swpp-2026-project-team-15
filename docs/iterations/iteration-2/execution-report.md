# Iteration2 integrated execution record

Recorded2026-10-20 KST. Runtime source checkpoint: `9454e4c` (integration feature `3de29f6`; later helper correction only). Main base `a27bf0a`; original client `88d3380` including `1edadc0`, server `89fc8ba`. Both original heads are ancestors. Final PR head/fresh-clone evidence is recorded separately after documentation commits.

## Original work preservation

Original DataStore/domain/filtering/revision and contributor tests are reused. Existing tests remain byte-identical against test-baseline.json; independent requirements snapshot hash is unchanged. Integration changes to Hyeokjun runtime are six boundary files: sorter uses explicit filtering count (one expression), Recipe adds optional source/revision metadata, navigation injects new adapter, list/detail add state/explicit source views, RecipeViewModel adds generation/error/restoration handling. Original repositories and domain models are unchanged. Suhyeon's revision/filtering packages are unchanged; server boundaries add catalog/source routes, optional version header and wrong-water-catalog check. Default DB path selects the separate new import; legacy API remains available.

New files contain mapping/DTO/transport/presentation adapters, flow tests and guard/configuration. No blanket reformat, history rewrite, original-test edits, layout/color redesign, dataset/secret commit or Docker stack introduction.

## Local checks

| Run | Result | Scope |
| --- | --- | --- |
| locked ruff/check/format and pre-commit |Pass |Same working directory as CI; original tests/spec hashes verified |
| locked pytest with coverage/XML/HTML/JUnit |180 passed,0 failed,0 skipped |Original server+experiment tests plus catalog/chain cases and the synthetic demo-input regression |
| Python coverage |98% combined |944 statements/198 branches; line98.73%, branch94.44%; app/filtering/revision included |
| Android JVM forced rerun |34 passed,0 failed,0 skipped |Existing23 plus11 new mapping/flow/reopen cases |
| Android lint/assemble/JaCoCo |Pass |JDK21, SDK37; exact commands in README/testing source |
| S22 connected |10 passed |Android14/API34; upload3, original template, sorting3, detail2, chained backend/render1 |
| Shell setup syntax |Pass |sh -n scripts/run-local-demo.sh |

JVM line coverage: overall13.66%, domain97.50%, local repositories92.31%, new recipe adapter81.74%, ViewModels87.69%. UI/platform classes explain the low overall JVM measure; this is not a claim of full UI acceptance coverage. Runtime coverage target80% was declared in integration-contract before tests. Earlier vision90%/wiring60% draft targets remain visible and compare to98.37%/93.59% combined.

Warnings remain visible: Starlette/httpx deprecation and old fixture unclosed-connection warnings; Android DataStore Unsafe deprecation. One newly authored UI assertion was corrected from partial-string/exact-semantics mismatch to the full expected string, then the complete suite passed. Existing tests were not weakened/skipped/deleted. Offline DataStore-cache miss and initial hook cwd mismatch were resolved using the declared dependency and matching CI cwd.

## Live and manual evidence

The existing Gemini key/model were reused after explicit user authorization within free quota; normal development/CI defaults remain mock. Two bounded server checks each requested recognition once and at most one adjustment; both returned200 with explicit refusal outcomes because essential ingredients were absent. First helper exact-only mapping omitted 달걀; the corrected preserved run matched the documented egg alias and submitted IDs103/32. Neither run proves semantic quality, safe cooking or formal AI accuracy. Private full model/recipe responses stay outside Git.

The local live-device receipt records manual gallery→candidate review→DataStore fridge→recommendation→original/refusal detail. The receipt does not establish an independent manual restart acceptance result; persistence reopen is covered by JVM tests. Device test tooling removes the test target on cleanup, so the integrated debug APK was explicitly reinstalled afterward. No adb pm clear/factory reset was used; do not promise preservation of prior app data across the instrumentation tool's uninstall.

## Fresh-clone final gate and reporting

Final verification uses a new GitHub clone of the exact candidate commit, without copying .env/venv/data/APK. Prerequisites are documented Android/Python tools and the privately supplied560-item ZIP. Run the setup flow with default mock/no key and exercise the chained flow, sorting/favorites/reopen/error states. Report exact head, tool/DB/APK hashes, actual executions versus cache reuse, and artifacts in the final PR/local receipt. Preparing this plan is not a successful fresh-clone result.

Official Wiki/Sheet/Figma/eTL are read-only for agents. English Requirements/Design/Testing/AI report sources, source diagrams, coverage evidence, schedule reconciliation and TA briefing are prepared for user review/publication. Actual TA meeting, peer review/main merge, official revision readback and eTL upload require external evidence. Docker/nginx/deployment stack is deferred to Iteration3 preparation by user instruction.

## DAG continuation check — 2026-10-20

Fetched inputs remain main a27bf0a, client88d3380/backend1edadc0 and recipe89fc8ba. Locked server pytest at runtime9454e4c plus the pending synthetic-input regression executed180 tests and106 subtests,0 failed/0 skipped; the coverage invocation emitted38 warnings (existing deprecation/ResourceWarnings). A separate plain invocation emitted one deprecation warning. Coverage remains932/944 lines and187/198 branches. Neither run calls paid providers. Fresh-clone results and exact final candidate are recorded in fresh-clone-validation.md after execution.

## Fresh-clone defect and fix

Candidate999c79a failed during first-time setup: the launcher extracted the private bundle into data/recipes-iter2 but invoked the original importer with its data/recipes defaults. Existing local DBs had hidden this integration defect. The launcher now supplies --csv-dir and --db explicitly, preserving Suhyeon's importer defaults and the old DB. A shell-level regression runs the actual launcher/importer with synthetic CSVs, stubs only platform tools, verifies the new water catalog and untouched old database, and repeats setup without a ZIP to verify no overwrite. The failed clone is retained as failure evidence; a corrected remote candidate is cloned anew for the final gate.

Corrected launcher local check:181 passed/106 subtests,98% combined runtime coverage (932/944 lines,187/198 branches);39 warnings during this invocation, with warning counts dependent on existing fixture finalization. No source importer or protected contributor tests changed.
