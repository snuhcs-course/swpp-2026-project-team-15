# Iteration 1 status

Updated: 2026-10-09. Scope: Team 15's Iteration 1, ending 2026-10-09. The team aimed to finish core work by 2026-10-07 and use the remaining time for feedback and corrections.

## Evidence and responsibility

| Area | Owner | Evidence | State at the iteration boundary |
| --- | --- | --- | --- |
| PM, proposal, schedule, documentation coordination | Hyeokjun Kweon | proposals, team schedule, TA meeting and follow-up | Iteration 1 planning and coordination recorded; submission documents being assembled |
| Android prototype | Ahyoon Choi | `origin/feat/android-studio`, head `ae22ec7` (Oct 6) | Navigation and major screens demonstrated with mock data; server integration and persistence pending |
| Recipe dataset and local DB | Soohyun An | `feat/recipe-db-schema-import`, head `0405ffc` (Oct 6); Wiki Recipe Database | SQLite schema and CSV importer prepared; 537 recipes, 2,870 steps, 701 ingredients, 5,933 recipe-ingredient rows in the local prototype |
| Research and server preparation | Jaehyuk Choi | `feat/research-pipeline`, head `4ea64e3` (Oct 2); Wiki research pages | Candidate pipelines and benchmark code prepared; no running production API established in this branch |

The CSV bundle is supplied outside Git. Cooking-tool and allergen association tables are structurally present but empty. Recipe quantities still need normalization for one-person servings. The data provider said the original recipe and step image URL fields are unused; selected recipe images need a separate source.

## What remains for integration

1. Define and implement the two server flows: image to candidate ingredient list, and confirmed inventory/profile to recommended recipes.
2. Connect the Android app to those APIs and persist user state. Keep user confirmation/editing in the recognition flow.
3. Test ingredient recognition with real fridge or ingredient photos and report misses, false positives, and manual correction effort. The current research benchmark uses simulated ingredient mentions, so its numbers are not real-photo performance.
4. Curate a smaller set of recipes for one-person meals, normalize quantities and ingredient names, and add cooking-tool and allergen mappings before enforcing those filters.
5. Define bounded AI recipe adjustments, including when substitution is disallowed, and record original recipe provenance and generated changes.

The team discussed a course-provided OpenAI API key with a US$20 cap and optional GPU/CPU servers. Availability and architecture details should be confirmed before treating either as a deployed dependency.
