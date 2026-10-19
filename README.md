# My Little Chef

SNU SWPP Fall 2026 · Team15. Review photo ingredient candidates, maintain a local fridge and browse original recipes alongside explicitly labeled AI revision outcomes.

## Iteration2 integration branch

This branch merges Hyeokjun's `88d3380` (including `1edadc0`) and Suhyeon's `89fc8ba` on main `a27bf0a`, preserving their original commits, repositories, filtering/revision and tests. Integration adds a versioned ingredient catalog and Android adapter, source restoration, state handling and scenario tests. [Contract and test plan](docs/iterations/iteration-2/integration-contract.md).

- DataStore persists fridge/profile/onboarding/favorite IDs. Favorite originals restore from the server without invoking AI; old AI suggestions are not persisted.
- Reviewed names resolve to the current catalog before ID requests. Unknown/ambiguous names are disclosed; no arbitrary IDs are invented. Only water is assumed available.
- Original quantities, textual servings/time, steps and tips remain visible. Revised/refused/failed/not_attempted are distinct; successful HTTP does not imply successful AI revision.
- Loading, empty results, mapping warnings, errors and retry differ. Latest-request guards prevent older responses replacing newer inventory results. New recommendation transport allows the existing three sequential60-second revision attempts; no automatic retry.
- Tool/allergy metadata are empty: suitability and cooking safety are **not verified**. Semantic revision correctness and authoritative one-serving conversion are not established features.

P0–P5 is a [historical simulation archive](research/README.md). [Iteration1 status](docs/iterations/iteration-1-status.md) remains a dated record.

## Run locally

Requires uv/Python≥3.12, Android SDK37, JDK21 for the entry environment, and an authorized USB-debugging phone. The existing Gradle daemon criteria select/provision JDK25 independently of JAVA_HOME. App minSdk26/target36/compile37. The **October19 560-ingredient entity ZIP**, distributed privately, must match this schema/importer. From repository root:

```sh
sh scripts/run-local-demo.sh path/to/entities-2026-10-19.zip
# Subsequent runs:
sh scripts/run-local-demo.sh
```

The script imports into `data/recipes-iter2/recipes.sqlite3` only when absent, checks the water catalog, creates server `.env` if absent, installs the app, configures adb reverse8000 and starts uvicorn. Stop with Ctrl+C. Use `ANDROID_SERIAL=<serial>` when choosing a device. In WSL attach the phone first.

The previous701-ingredient bundle/DB is preserved at its old path. Never mix IDs: old204=된장 versus new204=물. A changed server catalog yields409 before revision when the client sends its version. Data redistribution rights remain unconfirmed; CSV/DB/recipe data stay outside Git.

Both providers default to mock, with no API key or paid calls. Vision mock selects recorded candidates by image hash rather than recognizing the photo. Revision mock is a labeled refusal; it does not generate a real revised recipe. Live settings are listed in `server/.env.example`; keep keys only in `.env`, never in the app/Git. Confirm provider cost/authorization before a live run.

| Endpoint | Purpose |
| --- | --- |
| POST `/analyze` | Photo→unconfirmed candidates |
| GET `/recipes/catalog` | Versioned IDs/names for mapping |
| POST `/recipes/recommendations` | IDs→original/filtering/revision outcomes; optional X-Ingredient-Catalog protects mapping version |
| GET `/recipes/source/{id}` | Original lookup for saved favorites; no AI |
| POST `/recipes/recommend` | Preserved legacy name API and staple policy, separate from new app behavior |
| GET `/health` | Liveness |

API docs: <http://127.0.0.1:8000/docs> while running. Catalog validation catches the known old-water-ID mismatch; it is not a data rights or food-safety check. Catalog/DB replacement during a request is unsupported; use an immutable imported DB while the server runs.

## Checks and pre-commit

From the repository root:

```sh
(cd server && uv sync --locked)
uv run --project server --locked pre-commit install --allow-missing-config
uv run --project server --locked pre-commit run --all-files
(cd server && uv run --locked pytest --cov --cov-report=term-missing --cov-report=html --junitxml=test-results.xml)
(cd android/MyLittleChef && sh ./gradlew lintDebug testDebugUnitTest createDebugUnitTestCoverageReport assembleDebug)
```

CI collects original server and experiment tests, covers app/filtering/revision, and saves server reports and Android reports/debug APK. Pre-commit uses the same quick lint/format and protected-reference integrity checks, without running Gradle or live AI. Existing contributor tests are preserved byte-for-byte. [Quality environment](docs/iterations/iteration-2/quality-environment.md).

For connected tests, start the server with both providers=mock and the matching560-item DB, authorize USB and configure reverse8000, then run:

```sh
(cd android/MyLittleChef && sh ./gradlew connectedDebugAndroidTest)
```

The device suite includes photo upload→reviewed names→catalog→new recommendations→rendered original detail. Confirmation is scripted in the network/render test; manual camera/gallery/navigation usability remains separate. UI tests also check original/suggestion toggling with synthetic fixtures. Do not interpret mock success as recognition accuracy or safe revisions. [Testing evidence](docs/iterations/iteration-2/README.md).

Docker/nginx/deployment stack is deferred to Iteration3 planning by the user. This is a local runnable increment with CI, not a production deployment.

## Documents and external records

[Documentation index](docs/README.md) · [decisions](docs/decisions.md) · [PM handoff](docs/pm-handoff.md) · [official Wiki](https://github.com/snuhcs-course/swpp-2026-project-team-15/wiki).

Wiki/Sheet/Figma/eTL are agent read-only. Updated document sources are prepared locally for the user to publish; a code PR does not publish them. Review/merge, actual Wiki revisions, iteration-2-demo/video, PDF/XLSX exports and eTL upload require separate completion evidence. Preserve original authorship/history and use a main-targeting PR; do not force-push or commit private data/credentials/raw messages.
