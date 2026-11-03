# Iteration 3 AI work record - Hyeokjun

Source material for the team report, not the final one-page report.
Tool/model: Codex, GPT-6.1 Sol. Dates: Asia/Seoul.
Start with the actual October 28 assignment; earlier preparation is excluded.

## 2026-10-28 - setup and first deletion checkpoint

- Human request: implement the approved local plan with feature checkpoints and one later PR; see verbatim inputs.
- AI: inspected current/local code, identified removal persistence without UI, and created an isolated worktree from main e621ffd on frontend/iter3-inventory-and-images.
- Human choices: long-press plus management controls; summary/detail missing display; public assets; 20 names plus about 10 frequent additions; one PR; November 4 deadline. Cooking-completion cleanup deferred.
- Baseline checks: running; append actual outcomes.
- Implementation and regression checks: in progress, not verified yet.
- Human code review, app observations and manual edits: not performed yet for this checkpoint.
- Confirmed model errors, revised coding prompts and manual human code fixes: no findings recorded yet; do not invent examples.

## Recording rules

Preserve actual input wording. Add dated commands/results and commit/PR/code references after they exist. An agent fix is not a manual human fix. Do not invent saved time, dates or review activity. Review relevant complete sessions at report time; exclude credentials/private data from shared exports.

### Verified findings during this checkpoint

- Existing behavior: deleting before a suspended write finished and accepting an obsolete recommendation response both failed targeted assertions. The two original JVM regressions passed after Codex's changes.
- AI test-code error: Codex imported Compose assertDoesNotExist as a top-level extension; the installed API exposes it as a member. Kotlin compilation caught the invalid import. Codex removed that import before rerunning UI tests. This was not a human manual fix.
- Environment: the emulator initially appeared unauthorized. Restarting this session's ADB server with the existing user key authorized it; no phone was connected.

- AI test-code lint finding: two UserViewModel constructions inside setContent were rejected by ViewModelConstructorInComposable. Codex moved construction outside the composable; no lint suppression and no human manual edit.
- Protected-file verification: the unchanged checker failed against the Windows CRLF checkout. All 29 committed blobs match the approved manifest and all working copies match their blobs after line-ending normalization. No protected test/reference/manifest was edited.
- Emulator deletion/flow tests: 5 passed on Android 16 before adding screenshot capture. Human phone verification remains pending.

- Screenshot-only test failure: Codex assumed onRoot selected one root while a dialog creates a second root. Four behavior checks passed but the capture in the cancel test failed. Switched to instrumentation's full-display screenshot API; behavioral assertions were not weakened.
- Gradle invocation finding: cloudDeviceTest selects cloud instrumentation and cannot be combined with the debug unit-test task in this project. Run debug checks and cloud device tests separately; no build configuration was changed.
- Independent read-only Task 1 review: no Critical/Important/Minor code findings. Appearance, actual execution evidence and later planned features were not assessed by the reviewer.

- Visual review caught an issue the behavior tests did not: tinting the existing two-color remove vector erased its white minus. Codex retained the asset's own colors. The first default-screen capture also preceded the visible window; move it after the cancel assertions and wait for display idleness. No screenshot was retouched.

### Final verified state - 2026-10-28

- Implemented: named long-press/management confirmation, cancel, persistent exact-name deletion, progress/failure feedback, last-item state, and latest-request protection.
- Full Android JVM suite: 28 tests, 0 failures, 0 skipped.
- Android lintDebug, createDebugUnitTestCoverageReport, assembleDebug and assembleCloudTest: successful. Build override used http://127.0.0.1:8000/; tracked endpoint settings unchanged.
- connectedCloudTestAndroidTest, package com.example.mylittlechef.ui.fridge: 5 tests, 0 failures, 0 skipped on Android 16 Medium_Phone. This covers UI deletion/cancel/empty/failure plus the changed-inventory recipe-tab flow using an in-process controlled API.
- Screenshot evidence: management and confirmation screens in the ignored local output/iter3-deletion-review directory, visually reviewed by Codex. A normal-screen capture overlapped a window transition and was excluded; no screenshot was retouched.
- Source logs in the ignored plan workspace include task-1-red.log, task-1-final-checks.log and task-1-ui-final.log. Main regression tests were observed failing before production changes and then passing.
- Independent read-only review: no Task 1 code findings. Reviewer did not independently execute checks, assess device appearance, or judge later features.
- Remaining checks/limitations: no human phone/code review yet, no real deployed-server E2E in this checkpoint, existing Compose test API deprecation warnings, and the documented Windows raw-hash/CRLF checker limitation.
- Next step: Hyeokjun reviews docs/iterations/iteration-3-deletion-review.ko.md and tries the deletion flow. Then proceed to priority icons (30 ingredient mappings), missing display and recipe photos/credits. Publication remains pending local review.
- User asked to finish the current checkpoint, save work and shut down the computer. No remote publication was performed.


## 2026-10-29 — Restore earlier local features (paused)

User prompt: "그러면 그 기능들을 모두 통합해줄 수 있어?"
Stop prompt: "일단 작업 여기까지 해줘. 이후에 이어서 할게."

Codex ported the earlier uncommitted pantry/suggestion/catalog changes into the current worktree, retained deletion and existing APIs, and added atomic pantry persistence and request freshness handling. Human review pending; no human manual edits claimed. No push, PR, or deployment.

Intermediate checks: 4 new server tests passed; an Android JVM/lint/cloudTest build completed successfully before the latest added test files. Latest extra JVM/UI tests remain unexecuted. Full server run: 187 passed, 9 failed, 1 skipped, 106 subtests passed; 8 failures report missing sh on Windows and 1 experiment metadata failure still needs baseline diagnosis. Initial merge/build issues and an invalid test assumption (minced garlic is itself a preset) were corrected by the agent, not by the user. Gradle cloudDeviceTest instrumentation must run separately from ordinary debug JVM tasks.

Resume details: docs/iterations/iteration-3-restoration-checkpoint.ko.md. Work remains uncommitted locally on top of b632976.


## 2026-10-29 — Restoration resumed

Actual resume prompt: "재개해줘." Related inputs are in hyeokjun-prompts-2026-10-29.md.

The agent completed the new persistence/request tests and integrated the old local screens with the current code. A source-only independent AI reviewer identified two Important issues: directional 대파/다진파 capabilities could be mislabeled/count incorrectly, and navigating back during a delayed pantry save could pop an unrelated screen. The agent wrote regressions, observed failure (missing correct 대파 recommendation and back count 1 instead of 0), fixed the implementation, and the reviewer confirmed both source fixes. These are AI corrections, not human manual fixes. A test fixture initially omitted a required ingredient_type_code; this agent test mistake was corrected before observing the behavioral failure.

Evidence: Android JVM 34 passed; UI 14 passed; real Android-to-local-server Retrofit integration 1 passed. Recipe tests 84 passed. Full server before the last regression addition: 196 passed, 1 skipped, 106 subtests passed. Latest whole-server run: 195 passed, 2 failed, 1 skipped, 106 subtests passed; failures were Windows file-replace PermissionError and a shell 10-second timeout. Both failing tests passed unchanged when rerun individually. Do not claim a clean latest single full-suite run. Git sh was added only to the test process PATH. No tests/protected references were weakened.

A private local DB was imported (537 recipes, 560 ingredients); it and the virtualenv/logs remain ignored. The local server uses mock recognition and revision; no paid model quality test, deployment, push, or PR was performed. Human source review/device observations/manual edits remain unconfirmed. Review instructions: docs/iterations/iteration-3-restoration-review.ko.md.

Final unchanged behavior verification: Android JVM 34/34 and lintDebug passed after the navigation fix; cloudTest APK and UI tests compiled successfully. The tested loopback APK was installed and launched on emulator-5554 for user review, with adb reverse port 8000. Local mock server remains running for review. The original phone app/cloud deployment were not updated. Source changes and records are saved in a local commit; see git log.


## 2026-11-01 — Original-first, explicit on-demand revision

User authorization: "응 그거 진행하자" (verbatim input saved in hyeokjun-prompts-2026-11-01.md). The approved proposal moved AI work from listing to an explicit detail button and retained the original plus app-session reuse.

AI scope: designed and implemented additive server catalog/candidate/single-revision routes, Android DTO/API integration, RecipeRevisionSession, original-first detail toggling, candidate/missing badges, context invalidation, and tests. No new dependency, data schema, protected test change, external deployment, push or PR. The existing batch and name-based APIs remain intact. Allergy/utensil context invalidates cache but is not sent as a supported server constraint; this is explicitly shown in UI.

Actual verification: four server on-demand tests failed on the absent routes initially; two additional tests were subsequently added and all six passed. Android contract compilation initially failed because new interfaces/model fields/session were not implemented. The first behavioral run caught a new test's case-sensitive expectation against normalized unknown names; agent corrected that test to compare case-insensitively while retaining the requirement to show the unknown name. Final JVM 40/40 and lintDebug passed. Real Android Retrofit-to-local-server mock revision test passed; it returned the expected MOCK ONLY refusal, not a live model success.

Independent AI source review: no Important/Critical findings; a Minor note pointed out hardcoded assumed water ID. Agent consumed assumed_ingredient_ids from the server and added a regression with ID999; reviewer confirmed the fix. Another automated UI run found an existing LikeButton accessibility label incorrectly equal to BackButton's 'back'. Agent fixed the favorite label (without changing BackButton), retaining the same back-navigation test. These are agent corrections, not human edits.

Whole server run: 200 passed, 3 failed, 1 skipped, 106 subtests passed. The three failures were existing shell installer tests hitting Windows subprocess timeouts. The unchanged installer test file was rerun separately: 6 passed. Do not represent the latest full run as a single clean pass. No tests were weakened/skipped to pass. Ruff check passed on affected server files.

No paid AI calls or live output-quality evaluation were performed. Scripted successful UI responses test rendering/cache flow only. Actual user review, manual code changes, HE observations and permanent result storage remain pending. Full local verification commands/logs are in .superpowers/on-demand-*.log; review guide is docs/iterations/iteration-3-on-demand-review.ko.md.

Final on-demand checkpoint: UI 15/15 passed (including original→request→toggle→revisit cache); JVM40/40 and lint green; real local mock API integration1 passed. APK installed/launched for user review after tests. User acceptance remains pending. Local-only commit; no publication or live model evaluation.

## 2026-11-02 — Ingredient icons, metadata and three fridge sorts

Actual inputs: hyeokjun-prompts-2026-11-02.md. Human contributions were style/background selection, approval of the initial five-icon direction, three concrete shape corrections and clarification that sorting must include added order. No human source edits or final device acceptance are claimed.

Codex authored 28 vector studies, the standalone 560-row presentation CSV, and Android vector resources; implemented validated CSV loading, display-only Korean/category/added sorting, fridge dropdown/headings, unknown-name fallback and per-ingredient colors. Display aliases for 달걀/후춧가루 do not change stored names. The existing pantry re-selection algorithm moved all checked presets to the end; Codex wrote a failing persistence-order test and changed the domain/repository/VM paths to keep retained ingredients in their arrival positions and append new names. There are no historical timestamps; previously lost arrival order cannot be reconstructed.

Evidence: initial contract compilation failed because the new catalog/types were absent. With minimal contract stubs, 7 focused tests ran and 5 failed behaviorally. Adding the added-order requirement then produced 2 failures among 10 focused tests (missing menu option and persistence reordering). Initial new UI tests failed on the missing sort control. Final JVM suite: 50 tests, no failures/errors/skips. Final testDebugUnitTest/lintDebug/assembleCloudTest invocation succeeded with a loopback URL override; tracked endpoint defaults unchanged.

One whole UI run could not start because the emulator went offline (0 tests), then the next run executed 19 tests and found one real metadata defect: the agent's color rule matched 고추 but missed the spelling 고춧가루, leaving three red-pepper-powder variants with the neutral seasoning color. Codex corrected the CSV generator and both local/app CSV copies; the existing UI color assertion was retained. Latest whole UI run: 19 passed, no failures/skips. This checks dropdown order changes, separate names sharing icons, unknown-name cancellation/deletion, the packed 560 mappings and distinct seasoning colors, plus existing UI regressions. Tests use controlled data rather than human phone acceptance.

An independent AI source reviewer found no Critical/Important issues and two Minor points: empty category view omitted basic shelves, and a test named as deletion only cancelled. Codex restored the empty-inventory fallback and added actual confirmation/removal assertions; reviewer confirmed both source fixes without executing tests. These are agent corrections, not human edits. The first metadata coverage check also found two missing IDs (적양배추/탄산수), which the agent added before output creation.

The original recipe CSV/DB/schema, server APIs and protected tests were not changed. Runtime mapping is android/app/src/main/assets/ingredient_presentation.csv; it retains review notes and 22 review flags. No external icon download, new dependency, paid AI call, push, PR, merge or deployment. The derived private-data mapping must remain local until the team's redistribution review. Local server restarted with mock recognition/revision and returned ready. Review guide: docs/iterations/iteration-3-fridge-icons-review.ko.md. Logs: ignored .superpowers/fridge-icons-*.log. Final user acceptance and manual edits remain pending.

Final runtime checkpoint: the final saved XML reports confirm JVM50 and UI19 with zero failures/errors/skips; final lintDebug and assembleCloudTest succeeded. The emulator shut down gracefully before the first final reinstall attempt (log showed snapshot save), so it was restarted without wiping data. adb reverse tcp:8000 succeeded; install -r returned Success; activity launch returned Status: ok and process PID was confirmed. The visible app is on initial nickname onboarding; no demo inventory was injected and no human verification is implied. The final startup screenshot is ignored under output/iter3-fridge-icons/app-after-install.png. Test-cache screenshots were not available after runner cleanup/restart; do not present them as delivered screenshots. No local Git commit or remote publication in this checkpoint.

## 2026-11-03 — Latest main integration and application launcher

User requested an installed-app icon and incorporation of Jaehyuk's newly merged revision changes. The user supplied a green refrigerator/tilted-chef-hat reference and specifically asked to remove the side accents. Full safe prompts are in hyeokjun-prompts-2026-11-03.md; secret-bearing earlier input remains redacted.

Codex preserved the previous work in local checkpoint f3cf940, fetched main0cd7589 (PR14 compact revision/policy and PR15 multi-frame upload), and resolved the shared Retrofit conflict without dropping the original-first or multi-image interfaces. Merge commit a99ee82 includes current pipeline settings, recipe-specific assumptions and the authoritative single-response assumption override. Client read timeout is150s for the configured optional two60s attempts, with transport-level automatic retry disabled. Existing source IDs, DB schema and user inventory identities remain unchanged.

Actual failure/correction: Git's automatic merge left two same-named ingredient_catalog methods, returning tuples versus a dict; three local API tests failed. Agent retained the upstream dict contract with sanitized errors and adapted the route to items(). Three new policy tests then failed against the old direct-revise path and water-only assumptions. Agent connected revise_with_steps/Steps and per-recipe seasoning assumptions. Two Android JSON-decoding regressions failed when per-recipe/current-response assumptions were ignored; agent added the backward-compatible fields and precedence. These are AI-detected/corrected integration issues, not human manual edits. Two line-length findings were fixed without suppressions or behavioral changes.

Artwork content was edited with built-in imagegen by an isolated image-task agent. Codex used Pillow only to resize/re-encode the selected result for Android packaging, authored a themed silhouette, and wired all launcher aliases. Actual prompt/output records are local under .superpowers/launcher-artwork. No model identifier was invented. User guidance/visual selection is human contribution; no human source edit or post-install acceptance is claimed.

Verification: Android JVM74 passed, UI19 passed, real Android-to-local-mock API integration1 passed; lint and normal/cloudTest APK builds succeeded. Recipe+vision server run195 passed2 skipped (private real-catalog path absent); both skipped catalog checks passed separately once the existing private DB was copied to the ignored default path. Ruff check/format passed for changed server code. Independent AI source review reported no findings and executed no tests. Do not claim an all-green197-test single run or real provider quality.

Both APKs contain the exact new artwork bytes and passed apksigner verification. Cloud Test reinstall returned Success and cold activity start Status:ok. An actual emulator home-screen capture shows the green fridge/chef icon with no side accents; screenshot was not retouched. Runtime server remains explicitly mock; public OpenAPI still lacks the three local additive routes. No paid request, SSH use, remote push/PR/merge or shared deployment occurred.
# 2026-11-03 — deployed main API compatibility follow-up

- User required latest main API compatibility, local inventory features retained, actual-server Cloud Test installation, no GitHub upload or server deployment.
- Codex read main3c6310e and actual OpenAPI, changed Android's default interface from unpublished on-demand routes to name-list plus explicit server-selected batch revision. Added bundle-based ID mapping with unknown-name blocking and post-response ID/name validation. Exposed original/cached suggestion toggle, retained generation-based invalidation, recorded the need for a future targeted server API rather than implementing it.
- Actual AI code scope: BatchRecipeApi, CloudRecipeRevisionSession, RecipeViewModel/navigation/UI mapping, ingredient catalog ID exposure and regression/UI tests. Human source-code edits/time were not supplied and are not invented.
- Evidence:81 JVM green,21 Galaxy S23 Ultra UI green, lint0errors/30warnings/1hint and Cloud Test build green. Real name-list returned20; a separate single bounded batch returned133entries and recipe291revised. Actual-server photo recognition was not re-tested. The current device-test path does not call paid APIs. One independent AI review finding (original quantities lost on merge) was reproduced by a failing test and fixed by Codex; lint caught a test fixture construction mistake, also fixed by Codex.
- User unlocked the phone for tests. Final human visual acceptance remains separate. Existing Cloud Test installed-r; normal app/data untouched; no publish or deployment.

## 2026-11-03 — handheld UI checkpoint (paused at user request)

- User requested seven concrete UI changes and accepted scroll fallback for small/large-font/keyboard cases. AI implemented responsive onboarding, fridge+menu/multi-select atomic deletion, shared icon/color badges, persisted SYSTEM/LIGHT/DARK appearance, exact-match autocomplete and compact recipe header/info/FAB.
- AI authored source and tests; independent AI review identified one important contrast pairing error. Agent reproduced2.5435:1 with rendered test and corrected paired semantic colors. No human source edits or estimated human/agent hours are invented.
- Evidence:87JVM pass;28UI pass; later2targeted contrast/large-font tests pass separately; final Cloud Test build/lint pass. Profile theme selection and recipe/pantry icon semantics were automatically verified. Actual keyboard and final phone visual checks remain outstanding.
- User requested pause during contrast verification. Agent finished that work only, saved `docs/iterations/iteration-3-ui-resume.ko.md`, preserved the checkpoint APK and a local commit. No phone reinstall or remote change after this pause. Resume only on user request; no automatic continuation scheduled.

## 2026-11-03 — resumed device verification and right-hand controls

- User explicitly resumed, connected/unlocked phone and paused manual interaction for tests. User corrected both floating controls from bottom-left to bottom-right; agent changed only their alignment and related location assertion.
- Added supplemental actualIME test;31emulatorUI passed. After alignment correction10phoneUI passed and separate actualAPI/list1passed. Final build/lint0errors30warnings1hint and APK signature verification succeeded. Existing87JVM checkpoint result was not relabeled as a new run.
- Agent test-code mistake (DpRect.center does not exist) was corrected after compile failure. Phone's initialNetwork is unreachable resolved after user network confirmation; no client transport or server fix was falsely claimed.
- Verified real phone appearance persistence and common badges; restoredSYSTEM and original emulator keyboard setting0. Camera preview controls only, no capture/upload/AI. APK and local screenshots retained ignored; no remote upload/deployment. Full result: `docs/iterations/iteration-3-ui-verification.ko.md`.

## 2026-11-03 — recipe card and repeat AI request

- User requested whole-card detail navigation and re-enabled AI request after completion. AI authored parent click semantics with independent favorite child, removed successful-session lock and unrelated list-error/loading guards, retained in-flight suppression/context invalidation, merged per-dish cache results, and wrote regressions. Teammate image code already in17142ed was preserved.
- Reproduced unit4failures+separate1failure and UI2failures before implementation. Final95JVM/7phoneUI passed; lint0errors36warnings1hint, builds passed. Physical touches covered title/body/image/favorite and explicit second fake batch call; independent AI review found no Critical/Important issue.
- Agent attempted an invalid multi-operation patch and then a mismatched import anchor; patch verification rejected both before source edits. Corrected patches were applied after reading exact source. No fabricated human corrections.
- No paid model call, server deployment, GitHub upload or data reset. Details: `docs/iterations/iteration-3-recipe-interactions.ko.md`.
