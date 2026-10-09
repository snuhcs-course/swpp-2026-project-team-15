# My Little Chef

My Little Chef is Team 15's SWPP Fall 2026 project for people cooking in small households. The intended flow is to review ingredients identified from a photo, keep an editable fridge inventory, and find recipes that fit the available ingredients, tools, allergies, and serving size.

## Iteration 1 state (2026-10-09)

Iteration 1 produced separate prototypes and source data; it did **not** produce an integrated end-to-end service. The Android branch demonstrates screens with mock data. The recipe database branch contains a SQLite schema and CSV importer. The research branch compares candidate recognition and recommendation approaches using a limited, simulated benchmark. Real-photo detection quality and the integrated API flow remain to be established.

| Area | Branch | Current artifact |
| --- | --- | --- |
| Android UI | [`origin/feat/android-studio`](https://github.com/snuhcs-course/swpp-2026-project-team-15/tree/origin/feat/android-studio) | Android prototype and navigation; mock responses |
| Recipe data | [`feat/recipe-db-schema-import`](https://github.com/snuhcs-course/swpp-2026-project-team-15/tree/feat/recipe-db-schema-import) | SQLite schema, CSV importer, data notes |
| Research | [`feat/research-pipeline`](https://github.com/snuhcs-course/swpp-2026-project-team-15/tree/feat/research-pipeline) | Candidate pipelines and simulated benchmark |

The remote Android branch is literally named `origin/feat/android-studio`; this is why its remote-tracking name appears as `origin/origin/feat/android-studio` locally. The feature branches have not yet been merged into `main`.

## Documentation

- [Project documentation](docs/README.md): Iteration 1 status, meeting log, decisions, and PM handoff.
- [GitHub Wiki](https://github.com/snuhcs-course/swpp-2026-project-team-15/wiki): design, research, and recipe database documentation.
- [Figma design](https://www.figma.com/design/bxDeYMiAzC9LY7oHNj2OQV/my-little-chef?t=4IKrs5VSkKNKfJMZ-1).

The entity CSV bundle and generated SQLite database are distributed separately and are not tracked in Git. The [recipe database Wiki page](https://github.com/snuhcs-course/swpp-2026-project-team-15/wiki/Recipe-Database) describes the source and import process.

## Collaboration

Work on a focused branch, open a pull request to `main`, and identify the actual contributors in the schedule. Record meeting decisions in [`docs/meetings/`](docs/meetings/README.md); update [`docs/decisions.md`](docs/decisions.md) when a choice changes. The PM handoff checklist is in [`docs/pm-handoff.md`](docs/pm-handoff.md).
