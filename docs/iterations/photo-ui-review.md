# Fridge, recipe and onboarding UI review

This change builds on `frontend/he-usability` (PR #23). It keeps the HE input, recognition review, deletion/undo, recipe discovery and revision flows while updating their presentation.

## What changed

- A continuous four-column inventory grid, category filters in category order, and direct photo/manual actions. Added/alphabetical/category ordering and multi-select deletion/undo remain available.
- Wide recipe photo cards with a separate bookmark action, full-card navigation, concise missing-ingredient information, and a photo-first detail screen with ingredient icons and supplied quantities.
- Shared icon check tiles for six utensils, eight allergies and twenty pantry ingredients, used by onboarding and profile editing. Small screens and large text can scroll while the next action remains reachable.
- Manual entry and photo review in bottom sheets over the actual fridge. Camera capture remains full-screen. Draft dismissal needs confirmation, saving blocks dismissal, and successful saves close the sheet with an exit animation.
- A four-step tour of the actual fridge, recipe and profile tabs. It starts automatically only after onboarding and can be reopened from Profile > Usage guide. Completion uses a separate version key without replacing the previous help preference.
- A short cold-start logo animation and small navigation/selection transitions. Returning to the app or rotating the activity does not replay the intro.
- A separate `uiPreview` application ID for reviewing fresh onboarding without clearing an existing Cloud Test installation.

## Build and install

Run from `android/` with the Android SDK and Android Studio JBR configured:

```powershell
.\gradlew.bat :app:assembleCloudTest :app:assembleUiPreview -PserverBaseUrl=http://158.101.141.165/
```

Outputs:

- `app/build/outputs/apk/cloudTest/app-cloudTest.apk`: `com.example.mylittlechef.cloudtest`.
- `app/build/outputs/apk/uiPreview/app-uiPreview.apk`: `com.example.mylittlechef.uipreview`, separate local data.

Both review variants permit HTTP only for the existing team host and loopback hosts. Release network policy and signing configuration are unchanged. `uiPreview` supplies its own network policy because `initWith(cloudTest)` does not inherit the app's cloudTest resource source set.

The shared APKs connect directly to the team server; no PC or USB tunnel is required. Runtime services still depend on that server. Photos require image URLs/files supplied by the deployed backend; missing images use the placeholder. The UI does not deploy local backend additions or claim unsupported recognition/revision capabilities.

For a local backend, override `serverBaseUrl` with `http://127.0.0.1:8000/` and set an appropriate `adb reverse` mapping. Local DBs, image files, private preferences and server configuration are not distributed with this PR.

If an existing Cloud Test installation has a different signing certificate, use UI Preview for a separate installation rather than removing the existing app and its data. These are debug-signed review builds, not store releases.

## Review checklist

1. Open UI Preview; check nickname/keyboard reachability, the icon toggles and the twenty pantry choices.
2. Finish onboarding, advance/skip the actual-screen tour, and reopen it from Profile. The guide must not photograph, save, delete or request AI revisions automatically.
3. In Cloud Test, verify inventory ordering/filtering, multi-select deletion and undo.
4. Open manual input, type a draft, try to close, continue editing and then discard. Check that a successful save closes once and that saving disables dismissal.
5. Check photo review, confirmation, candidate editing/undo, cancel/retry and photo enlargement. Model accuracy is a separate verification task.
6. Open a recipe by tapping its body; verify bookmark separation, supplied quantities, missing-ingredient text, and original/revision separation.
7. Check light/dark mode and large text. Reopening an unchanged photo session must not submit a duplicate recognition request.

## Verification already performed

- JVM domain, persistence, sorting and photo-session tests: 132 passed.
- Android UI regressions on Samsung SM-S918N: 71 passed, including the actual ManualAddScreen inside the sheet.
- `lintDebug`: zero errors, 43 warnings and two hints in the recorded local run.
- Cloud Test, UI Preview and Android test APK builds passed; protected specification/contributor-test policy and `git diff --check` passed.
- Update installation preserved all seven existing preference values. Only the new tour version key was added. Temporary typing used for device walkthroughs was discarded.
- The walkthrough and automated checks used local recipe/image fixtures and mock revision. They do not establish deployed AI quality. A reviewer hands-on pass against the team-server APK is still needed.
