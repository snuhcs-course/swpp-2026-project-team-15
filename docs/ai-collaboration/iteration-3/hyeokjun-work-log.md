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
