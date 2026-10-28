# Iteration 3 inventory and images implementation plan

> **For agentic workers:** Use superpowers:executing-plans task by task. The user's feature review checkpoints take precedence over uninterrupted execution.

**Goal:** Deliver confirmed inventory deletion, clear missing information and bundled public artwork by November 4.
**Architecture:** Extend existing Compose screens, DataStore and ViewModels. Preserve the deployed API and separate artwork from ingredient identity.
**Tech Stack:** Kotlin, Compose, DataStore, coroutines, JUnit, Android UI tests.
**Spec:** docs/iterations/iteration-3-client-work.md and the verbatim approved implementation request.

## Global Constraints

- Local branch frontend/iter3-inventory-and-images, one PR after local user review.
- Target 2026-11-04; record actual dates/results separately.
- Latest main Android layout (android/) and isolated cloudTest package.
- Preserve protected tests/references, API and deployment configuration.
- Actual prompts/model/checks/human edits only. Cooking-completion cleanup is deferred.

## Review Focus

- Failed writes must not silently remove visible ingredients.
- A shared icon must not cause another inventory name to be removed.
- Old recommendation responses must not win after rapid changes.
- Old favorite/detail data must not make false availability claims.
- Artwork must match the subject and have verifiable credits/fallbacks.

### Task 1: Confirmed inventory deletion and recommendation freshness

**Files:** fridge screen/shelves, FridgeViewModel, RecipeViewModel; new regression tests only.
**Interfaces:** Keep FridgeRepository.remove(String), FridgeViewModel.removeIngredient(String) and RecipeViewModel.refresh(List<Ingredient>). Add removal progress and dismissible error state. Pass deletion-request callbacks through shelves to items.

- [x] Test that an item remains visible until a delayed repository removal succeeds; run it against baseline and observe failure.
- [x] Implement persistence-first removal, a single-operation guard, cancellation propagation and visible write-failure feedback.
- [x] Test failure/retry, exact-name isolation and a genuinely reopened DataStore.
- [x] Reproduce a late canceled API response, then add request-version protection and preserve cancellation.
- [x] Test long-press/management confirmation, cancel, last-item removal and failure feedback; wire both controls to one dialog.
- [x] Verify recipe tab entry sends the changed inventory to a controlled API.
- [x] Run JVM tests, lint, APK/UI-test compilation, protected-reference checks and available connected tests.
- [x] Commit feat(android): add confirmed inventory deletion; explain the code in Korean for user review.

Expected: deletion/persistence/failure/freshness assertions pass. Original protected tests remain unchanged.

### Task 2: Priority ingredient artwork

**Interfaces:** Display-name artwork resolver, independent of domain identity; 20 agreed names plus 10 additional frequency names; category/generic fallbacks.

- [ ] Record mapping and licenses, acquire public artwork, test exact/related/unknown lookups, then connect existing displays.
- [ ] Visually inspect all 30 names and commit for user review.

Expected: distinct names remain distinct; absent mappings have a deliberate fallback.

### Task 3: Missing-ingredient presentation

**Interfaces:** Shared card/detail presentation, using current API missing/staple information and existing sort choices.

- [ ] Test zero/one/many/long names and stale favorites/details after inventory changes.
- [ ] Show count, at most two names and remaining count on cards; text/color status and staple notice in details.
- [ ] Verify current inventory consistency, run checks and commit.

Expected: compact cards, complete details and no stale availability claims.

### Task 4: Recipe photos and credits

**Interfaces:** Recipe-ID resource resolver shared by list/details; unknown-ID fallback; credits reachable from profile.

- [ ] Select 20 suitable dish/photo pairs, verify author/license/edits, and bundle optimized resources.
- [ ] Test known/unknown IDs and list/detail consistency; inspect offline rendering and credits, then commit.

Expected: 20 verifiable photo mappings and complete credits; private source CSV/DB remains untracked.

### Task 5: User validation, report evidence and PR

- [ ] Run required checks and controlled full flow; capture actual results/screens.
- [ ] Explain changed code and record real user review/edits.
- [ ] Review source sessions and guide's six items; retain genuine findings.
- [ ] Review the branch, fix blockers, compare latest main and prepare one reproducible PR after user review.

Expected: required checks and user validation have evidence. Optional recovery work is not falsely marked complete.
