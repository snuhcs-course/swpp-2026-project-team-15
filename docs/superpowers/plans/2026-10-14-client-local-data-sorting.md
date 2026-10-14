# Client Local Data and Recipe Sorting Implementation Plan

> For agentic workers: implement each task with a failing test first, then a passing test.

**Goal:** Persist confirmed fridge ingredient names and user profile locally, and let users sort recipe cards by server recommendation order, cooking time, or missing ingredient count.

**Architecture:** Android Preferences DataStore stores small lists and profile fields. Pure domain models normalize input and a pure sorter returns a new list without changing the API order. Existing ViewModels observe repositories; RecipeViewModel owns the selected sort and exposes visible recommendations. Compose renders a dropdown and consumes ViewModel state.

**Tech Stack:** Kotlin, Jetpack Compose Material3, AndroidX ViewModel, Preferences DataStore 1.2.1, JUnit 4, Compose UI tests.

**Baseline:** Work from PR #6 feat/local-integration. Existing testDebugUnitTest passed on 2026-10-14.

## Global constraints

- Only ingredient names are stored; no quantity or expiry field.
- Sort options are recommendation order, shortest cooking time, and fewest missing ingredients.
- Preserve server order for recommendation mode and as a tie-breaker.
- Unknown cooking time is 0 in the current API mapper and sorts last.
- User utensils and allergies are stored, but the current API does not enforce them.
- Do not persist drawable resource IDs or the complete recipe response.

## Tasks

### 1. Pure domain models and sorter
- Add FridgeInventory and UserProfile models with normalized, duplicate-free names and existing nickname, utensils, allergies, likes, and onboarding state.
- Add RecipeSortType and a pure sorter. Use server missing items when present; fall back to local name comparison for preset recipes.
- Add JVM tests for empty/duplicate names, equality, sort modes, ties, unknown time, and empty lists.

### 2. Local repositories
- Add repository interfaces and Preferences DataStore implementations for fridge and user data.
- Preserve list order in serialization and make writes atomic through DataStore.
- Add tests that recreate repository instances against the same temporary file and confirm persistence, updates, and empty defaults.

### 3. ViewModel wiring
- Make FridgeViewModel and UserViewModel observe the repositories and persist existing actions; avoid losing early UI edits before initial load.
- Make RecipeViewModel own the sort choice and expose sorted recommended and liked lists without mutating server results.
- Connect factories in AppNavHost and route to main after a completed onboarding profile has loaded.
- Add ViewModel tests with fake repositories for restore and update behavior.

### 4. Compose dropdown
- Add a reusable sorting dropdown to RecipeScreen, visible in recommendations and favorites.
- Use stable semantics labels for accessibility and testing.
- Add an androidTest UI test for opening, selecting each option, and observing the selected label and card order on an emulator.

### 5. Integration checks
- Run testDebugUnitTest and connectedDebugAndroidTest.
- Manually verify onboarding, ingredient add, app restart, profile persistence, and sorting on the emulator.
- Review PR #6 changes before rebasing or merging this branch.
