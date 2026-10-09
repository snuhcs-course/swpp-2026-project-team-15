# Research and implementation: 2026-09-27 to 2026-10-06

Source: team discussion summary, branch commits, recipe database Wiki, and dates supplied by the Iteration 1 PM. These notes summarize progress; they do not claim an integrated release.

## Timeline

| Date | Discussion and evidence |
| --- | --- |
| Sep 27–30 | Explored recipe data and image-recognition approaches. The research branch later added candidate pipelines and a benchmark. The benchmark uses simulated ingredient mentions and is not a real-photo accuracy result. |
| Oct 4 | Discussed the recipe DB structure. SQLite was chosen for local schema/import experiments; a server DB and ORM remain open. |
| Oct 5 | Shared Android work in progress and recipe DB progress. The DB branch added schema, importer, and setup notes. |
| Oct 6 | Shared the Android prototype, further recipe data progress, and server responsibilities. The Android screens use mock data; the server and client are not yet connected. |

## Recipe data findings

- The source has recipe basics, cooking steps, and ingredients with main/secondary/seasoning categories. The ingredient quantities describe a whole recipe, not each step.
- The current local DB has 537 recipes, 2,870 steps, 701 unique ingredients, and 5,933 recipe-ingredient rows. Tool and allergen relation tables still have no rows.
- The source recipe and step image URLs were confirmed by the provider to be unused. Images for selected recipes will be sourced separately.
- One-person serving conversion, recipe selection, synonym cleanup, and tool/allergen mapping are later work.

## Open integration work

- Specify image-to-candidate-ingredients and inventory-to-recipes API contracts.
- Determine where inventory is stored and how the Android client saves confirmed changes.
- Test recognition against real photos before selecting a production model or reporting detection accuracy.

Related: [Recipe Database Wiki](https://github.com/snuhcs-course/swpp-2026-project-team-15/wiki/Recipe-Database), [Iteration 1 status](../iterations/iteration-1-status.md).
