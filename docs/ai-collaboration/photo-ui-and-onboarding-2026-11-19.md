# UI implementation AI assistance — 2026-11-19

Tool: Codex. This record covers the photo-oriented UI and the following onboarding, real-screen tour and entry-sheet implementation. Existing contributor attribution and protected tests were retained.

## Requests and implementation

Representative author requests, translated from Korean:

- "Apply this design to the actual app, keep the HE improvements, and work locally so I can review it in the emulator. Make the animations smooth."
- "Use the same icons in onboarding, put nickname entry in the middle-lower area, show a short startup animation, and guide users through the actual fridge, recipe and profile tabs."
- "Keep the HE features and data, implement locally, and install it on the connected phone for review."

Codex wrote/adapted Compose layouts, the shared icon choices and nine simple vector assets, fridge filtering/presentation, recipe card/detail presentation, the entry-sheet host, tour/version storage, startup transitions, the separate preview variant and regression tests. Existing persistence/recommendation/recognition APIs and their HE behavior were reused. The photo view model gained an entry token to distinguish screen restoration from explicitly reopening the same photo.

## Corrections and validation

Compilation exposed an implicit BoxWithConstraints receiver and an invalid DpRect center reference in a new test. Lint caught ViewModel construction inside new test composables; construction was moved outside rather than suppressing the rule. UI regressions exposed icon test metadata hidden by cleared semantics and premature tour activation before completed onboarding.

A real-device walkthrough then found a draft-dismissal defect missed by the isolated sheet tests: editor snapshots were read only inside SideEffect, so typing did not reliably recompose the parent guard. The value is now calculated in composition and passed to the side effect. Two tests using the real ManualAddScreen inside EntrySheet cover draft preservation/discard and one-time save completion. Existing contributor tests were not edited.

Recorded results: 132 JVM tests and 71 physical-device UI tests passed; lint reported zero errors. ADB-driven device walkthroughs checked onboarding fit, actual-tab guide/replay, keyboard/save reachability and draft confirmation. A binary-preference comparison verified that seven original stored values were unchanged and only the tour-version key was added. These automated checks are not represented as the author manually reviewing or rewriting every generated line.

## Review boundaries

The author reviewed the earlier photo-layout implementation and requested the subsequent changes. Final reviewer hands-on validation of all new onboarding/sheet interactions remains outstanding. Local mock revision and the existing recognition bridge were used; this work does not claim live model quality, valid bounding boxes, new recipe-data review, or deployed support for local-only endpoints. APK publication uses an explicit team-server build; it does not deploy backend changes or include private local data.
