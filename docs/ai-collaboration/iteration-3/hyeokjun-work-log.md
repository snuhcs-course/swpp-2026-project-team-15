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
