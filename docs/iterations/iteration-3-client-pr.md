# Iteration 3 Android changes

This PR contains app code and build-time assets only. It uses the main server's name-based recipe list and explicit, server-selected batch revision API. Server/deploy experiments from the local work branch are not included.

## Assets included

- 28 ingredient vectors: `android/app/src/main/res/drawable/ic_ingredient_*.xml`.
- 560 ingredient display mappings: `android/app/src/main/assets/ingredient_presentation.csv` (ID/name, category, icon, background color and review flags).
- Launcher artwork and Android adaptive/themed/density resources under the app's main resources.
- The app reads these packaged assets; teammates do not need the local prototype folder or image ZIP.

Vectors and display mappings were prepared for this project with Codex assistance. Appearance aliases do not merge inventory identities, and categories are not allergy classifications. Unknown names use a generic badge. Raw recipe CSVs, databases, keys, APKs and the recipe-photo originals are not included.

## Run and review

Open `android/` in Android Studio. For an isolated package, build `:app:assembleCloudTest`; the label is MyLittleChef Cloud Test and the package ends in`.cloudtest`. The default endpoint is the existing team server. Local mock builds may override`-PserverBaseUrl=http://127.0.0.1:8000/` and use adb reverse; paid image/revision endpoints are not required for JVM tests.

Check the fridge's bottom-right+menu, long-press/multi-select deletion, three inventory sorts, pantry badges, profile appearance menu and recipe card/detail behavior. SYSTEM/LIGHT/DARK is persisted separately from inventory. AI requests run only on an explicit tap; completed requests can be requested again, while concurrent taps are blocked.

## Recipe image coordination

The client accepts optional`main_image_url` from PR #17 and retains drawable fallback support. This PR does not add the server image column, static route, photo files or recipe-to-photo mapping. Coordinate overlapping Recipe model/image-rendering changes with #17; keep a single `imageUrl` field and retain inventory/revision metadata. Until the server provides URLs, placeholders are expected.

## Validation and AI assistance

Current app sources passed 95 JVM tests, lintDebug (0 errors, 36 warnings, 1 hint) and assembleCloudTest during PR preparation. No device test, paid AI call or server deployment was performed for this preparation; earlier device checks and their exact scopes are recorded in the iteration documents.

Codex assisted implementation, refactoring, regression tests and asset preparation. User feedback determined sort options, multi-delete behavior, icon shapes/colors, theme choices and final bottom-right placement. This does not claim that the user manually authored or reviewed every code change. Related prompts and corrections are recorded in`docs/ai-collaboration/iteration-3/`.
