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

## Run the local demo

The backend runs on your computer and the app runs on an Android phone connected by USB. The phone reaches the server through `adb reverse`, so no Wi-Fi setup is needed.

**Prerequisites:** [uv](https://docs.astral.sh/uv/), Android Studio (SDK and JDK 21), the recipe CSV zip shared outside Git, and a phone with USB debugging enabled and authorized (`adb devices` shows `device`).

```sh
sh scripts/run-local-demo.sh path/to/recipes_csv_with_ingredients.zip   # first run
sh scripts/run-local-demo.sh                                            # later runs
```

If both a phone and an emulator are running, the script uses the phone; set `ANDROID_SERIAL=<serial>` to choose another device.

The script builds the recipe database (`data/recipes/recipes.sqlite3`), creates `server/.env` from `server/.env.example`, installs and opens the app, and then runs the server in the foreground. Stop it with Ctrl+C. On Windows, run it inside WSL; the phone must be attached to WSL (for example with `usbipd`).

By default `VISION_PROVIDER=mock` replays recorded recognition results, so no API key is needed and the detected items do not depend on the photo. To use Gemini, set `VISION_PROVIDER=gemini`, `GEMINI_API_KEY` and `GEMINI_MODEL` in `server/.env`. Never commit that file.

Checks:

```sh
cd server && uv run ruff check . && uv run pytest --cov --cov-report=term-missing   # server + coverage
cd android/MyLittleChef && sh ./gradlew testDebugUnitTest createDebugUnitTestCoverageReport   # app + JaCoCo
```

| Endpoint | Purpose |
| --- | --- |
| `POST /analyze` | Photo → unconfirmed ingredient candidates |
| `POST /recipes/recommend` | Confirmed ingredients → recipes ranked by missing items (ten staple seasonings assumed) |
| `GET /health` | Liveness check |

Interactive API docs: <http://127.0.0.1:8000/docs> while the server runs.

## Documentation

- [Project documentation](docs/README.md): Iteration 1 status, meeting log, decisions, and PM handoff.
- [GitHub Wiki](https://github.com/snuhcs-course/swpp-2026-project-team-15/wiki): design, research, and recipe database documentation.
- [Figma design](https://www.figma.com/design/bxDeYMiAzC9LY7oHNj2OQV/my-little-chef?t=4IKrs5VSkKNKfJMZ-1).

The entity CSV bundle and generated SQLite database are distributed separately and are not tracked in Git. The [recipe database Wiki page](https://github.com/snuhcs-course/swpp-2026-project-team-15/wiki/Recipe-Database) describes the source and import process.

## Collaboration

Work on a focused branch, open a pull request to `main`, and identify the actual contributors in the schedule. Record meeting decisions in [`docs/meetings/`](docs/meetings/README.md); update [`docs/decisions.md`](docs/decisions.md) when a choice changes. The PM handoff checklist is in [`docs/pm-handoff.md`](docs/pm-handoff.md).
