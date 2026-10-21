# My Little Chef

SNU SWPP Fall 2026 · Team15. Review photo ingredient candidates, maintain a local fridge and browse original recipes alongside explicitly labeled AI revision outcomes.

## Implemented behavior

The Android app uses the versioned ingredient catalog and ID-based recommendation API. The backend supports mock/live providers, SQLite for local development and PostgreSQL in the Oracle ARM deployment.

- DataStore persists fridge/profile/onboarding/favorite IDs. Favorite originals restore from the server without invoking AI; old AI suggestions are not persisted.
- Reviewed names resolve to the current catalog before ID requests. Unknown/ambiguous names are disclosed; no arbitrary IDs are invented. Only water is assumed available.
- Original quantities, textual servings/time, steps and tips remain visible. Revised/refused/failed/not_attempted are distinct; successful HTTP does not imply successful AI revision.
- Loading, empty results, mapping warnings, errors and retry differ. Latest-request guards prevent older responses replacing newer inventory results. New recommendation transport allows the existing three sequential60-second revision attempts; no automatic retry.
- Tool/allergy metadata are empty: suitability and cooking safety are **not verified**. Semantic revision correctness and authoritative one-serving conversion are not established features.

## Source layout

Selected tracked source below; generated environments, builds and private datasets are omitted. Development tools stay in the repository; deployment packages contain only runtime files.

```text
.
├── .github/workflows/             # Server/Android/ARM CI and verified-main deployment
├── Dockerfile                    # Runtime-only, nonroot ARM-compatible API image
├── compose.yaml                  # nginx/API/PostgreSQL and explicit importer service
├── deploy/                       # Runtime template, nginx, DB reset and release scripts
├── README.md                     # Setup and source navigation
├── android/                      # Android Gradle project
│   ├── README.md                 # App installation, variants and endpoint configuration
│   ├── app/src/
│   │   ├── main/                 # Compose UI, navigation, data and domain code
│   │   ├── debug/, cloudTest/    # Development-only network policy and isolated test app
│   │   ├── test/                 # JVM tests
│   │   └── androidTest/          # Device and backend integration tests
│   └── gradle/                   # Wrapper, versions and JVM criteria
├── research/                     # Feature exploration and reproducible comparisons
│   ├── evaluation/               # Photo-recognition benchmark and ground truth
│   └── experiments/
│       ├── filtering/            # Filtering comparisons using the server core
│       └── revision/             # Revision cases, adapters and observation runner
├── scripts/                      # App installation, local demo, source integrity and runtime packaging
└── server/
    ├── app/                      # FastAPI configuration, vision and recipe APIs
    ├── recipe_filtering/         # Runtime filtering and ranking algorithms
    ├── recipe_revision/          # Runtime revision logic and provider adapters
    ├── db/                       # Schema, SQLite CSV importer and PostgreSQL ZIP importer
    ├── fixtures/
    │   ├── vision/               # Recorded candidates for the runtime mock provider
    │   └── demo/                 # Synthetic photo for local integration checks
    ├── tests/                    # All automated Python checks
    │   ├── experiments/          # Preserved filtering/revision regression tests
    │   ├── manual/               # Explicit live integration check; not auto-collected
    │   ├── recipes/              # Recipe API and integration contracts
    │   ├── references/           # Protected specifications and test hashes
    │   └── vision/               # Vision provider and API tests
    ├── pyproject.toml            # Runtime/development dependencies and pytest config
    ├── uv.lock                   # Locked dependency versions
    ├── .env.example              # Provider and database configuration template
    └── README.md                 # Server setup and API details
```

`server/tests/` asserts expected behavior with pytest. `research/` holds prototypes, measurements and comparison tools for feature development; adopted logic belongs in the Android/server implementation with regression tests. Existing research tools reuse server modules. Their Python namespaces (`evaluation`, `experiments`) are preserved, so the original regression tests remain byte-for-byte unchanged; pytest adds research/ to its import path. See [research setup](research/README.md) for commands and the development workflow.

The photo benchmark compares candidates against 11 ground-truth photos, reporting accepted-name matches, misses, unmatched candidates, latency and direct-call token usage. Substring matching can credit one candidate to multiple expected items, so its recall is diagnostic rather than strict object-level accuracy or precision. Photos and reports stay outside Git. The manual live integration check requires `--live` and records vision → catalog IDs → at most one recipe revision. Research/live commands can call external providers; normal startup and CI do not run them. Neither parsing success nor an HTTP response establishes semantic correctness.

## Install Android for the cloud server

```sh
sh scripts/install-android.sh
# Select a device when several are connected:
ANDROID_SERIAL=<serial> sh scripts/install-android.sh
```

Builds and installs the isolated `.cloudtest` app using the configured cloud endpoint.
Open it on the device with Internet access. See [Android setup](android/README.md)
for prerequisites, endpoint overrides and build variants.

## Run locally

Requires uv/Python≥3.12, Android SDK37, JDK21 for the entry environment, and an authorized USB-debugging phone. The existing Gradle daemon criteria select/provision JDK25 independently of JAVA_HOME. App minSdk26/target36/compile37. The **October19 560-ingredient entity ZIP**, distributed privately, must match this schema/importer. From repository root:

```sh
sh scripts/run-local-demo.sh path/to/entities-2026-10-19.zip
# Subsequent runs:
sh scripts/run-local-demo.sh
```

The script imports into `data/recipes-iter2/recipes.sqlite3` only when absent, checks the water catalog, creates server `.env` if absent, installs the isolated `.cloudtest` app with an explicit localhost endpoint, configures adb reverse8000 and starts uvicorn. Stop with Ctrl+C. Use `ANDROID_SERIAL=<serial>` when choosing a device. In WSL attach the phone first.

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
| GET `/ready` | Database/catalog and recipe-source readiness |

API docs: <http://127.0.0.1:8000/docs> while running. Catalog validation catches the known old-water-ID mismatch; it is not a data rights or food-safety check. For SQLite, use an immutable imported DB while the server runs. For the Compose PostgreSQL deployment, use `deploy/db.sh` for serialized init/reset with backup and rollback; see [deployment operations](deploy/README.md).

## Checks and pre-commit

From the repository root:

```sh
(cd server && uv sync --locked)
uv run --project server --locked pre-commit install --allow-missing-config
uv run --project server --locked pre-commit run --all-files
(cd server && uv run --locked pytest --cov --cov-report=term-missing --cov-report=html --junitxml=test-results.xml)
(cd android && sh ./gradlew lintDebug testDebugUnitTest createDebugUnitTestCoverageReport assembleDebug)
```

CI runs server tests with PostgreSQL, Android lint/JVM tests/APK builds, and a native ARM image/import check. Connected-device and live AI tests run separately. Reports and APKs are saved as artifacts. Pre-commit uses the same quick lint/format and protected-reference integrity checks, without running Gradle or live AI. Existing contributor tests are preserved byte-for-byte. Protected specification/test references live in `server/tests/references`; CI checks their unchanged contents.

For connected tests, start the server with both providers=mock and the matching560-item DB, authorize USB and configure reverse8000, then run:

```sh
(cd android && sh ./gradlew -PcloudDeviceTest \
  -PserverBaseUrl=http://127.0.0.1:8000/ \
  -Pandroid.testInstrumentationRunnerArguments.notClass=com.example.mylittlechef.ExampleInstrumentedTest \
  connectedCloudTestAndroidTest)
```

The preserved sample test asserts the original package name, so it is excluded only for `.cloudtest`. The device suite includes photo upload→reviewed names→catalog→new recommendations→rendered original detail. Confirmation is scripted in the network/render test; manual camera/gallery/navigation usability remains separate. UI tests also check original/suggestion toggling with synthetic fixtures. Do not interpret mock success as recognition accuracy or safe revisions. See the Wiki Testing Documentation for measured results and remaining gaps.

Iteration3 provides an Oracle ARM development deployment using nginx, FastAPI and PostgreSQL. See [deployment and recovery](deploy/README.md). The public-IP HTTP endpoint is for development; production DNS/TLS are separate configuration.

## Build a server deployment artifact

```sh
python3 scripts/package_server.py --output dist/server.tar.gz
# Extract on the target; supply the separately imported matching DB:
cd server
uv sync --locked --no-dev
RECIPE_DB_PATH=/absolute/path/recipes.sqlite3 uv run --locked --no-dev uvicorn app.main:create_app_from_env --factory --host 0.0.0.0 --port 8000
```

The archive contains only committed runtime code, vision fixtures, locked dependency metadata and server setup instructions, with a commit/file-hash manifest. Tests, experiments, research, local config/keys and recipe data are excluded. Configure provider variables from server/.env.example through the target environment. Mock defaults need no API keys.

For APK endpoint configuration, see [Android build variants](android/README.md#build-variants-and-endpoints).

## Further documentation

- [Server setup and API](server/README.md)
- [Android installation and builds](android/README.md)
- [Compose deployment, DB reset and recovery](deploy/README.md)
- [Research commands](research/README.md)
- [Project Wiki](https://github.com/snuhcs-course/swpp-2026-project-team-15/wiki)
