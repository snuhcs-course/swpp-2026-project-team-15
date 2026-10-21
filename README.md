# My Little Chef

SNU SWPP Fall 2026 · Team 15. Android ingredient recognition, local fridge/profile
storage and recipe browsing, with a FastAPI backend.

## Source layout

```text
.
├── .github/workflows/       # Server, Android and ARM checks; main deployment
├── android/                # Compose app, DataStore, JVM/device tests
├── server/
│   ├── app/                # FastAPI routes, providers and DB access
│   ├── recipe_filtering/   # Contributor filtering/ranking implementation
│   ├── recipe_revision/    # Contributor recipe revision implementation
│   ├── db/                 # Schema, SQLite CSV and PostgreSQL ZIP importers
│   ├── fixtures/           # Runtime vision mocks and synthetic demo image
│   └── tests/              # Automated checks and protected contributor references
├── research/               # Evaluation tools and feature experiments
├── scripts/                # Android install, local demo, integrity and packaging
├── deploy/                 # nginx, runtime template, DB and release scripts
├── Dockerfile              # Nonroot runtime API image
└── compose.yaml            # nginx, API, PostgreSQL and explicit importer
```

`research/` reuses server modules; runtime code does not import research tools.
Generated builds, environments, private data and credentials stay outside tracked source.

## Install Android for the cloud server

Requires Android SDK 37, Java and an authorized USB-debugging device. The committed
Gradle daemon criteria select/provision JDK 25; CI starts with JDK 21.

```sh
sh scripts/install-android.sh
# When several devices are connected:
ANDROID_SERIAL=<serial> sh scripts/install-android.sh
```

Builds and installs only the isolated `.cloudtest` app. Open it on a device with
Internet access. Debug/cloudTest default to `http://158.101.141.165/`.
See [Android setup](android/README.md) for SDK configuration and endpoint overrides.

## Run locally

Install uv/Python ≥3.12 and the Android prerequisites above. Supply the matching
private October 19 entity ZIP. From repository root:

```sh
sh scripts/run-local-demo.sh path/to/entities-2026-10-19.zip
# Subsequent runs:
sh scripts/run-local-demo.sh
```

The script imports SQLite only when absent, creates `.env` if absent, installs
cloudTest with a localhost endpoint, configures USB reverse and starts Uvicorn.
Stop with Ctrl+C. Use `ANDROID_SERIAL=<serial>` to select a device. Both providers
default to mock; configure live providers in the server environment.

## App and API

The app uploads photos to `/analyze`, saves user-reviewed ingredient names and
requests `/recipes/recommend`. It uses the original recipe list/detail screens
and local DataStore storage. The contributor ID-based filtering/revision endpoint
remains available separately; the app does not call it.

| Endpoint | Purpose |
| --- | --- |
| POST `/analyze` | Photo → ingredient candidates |
| POST `/recipes/recommend` | Ingredient names → recipes for the app |
| POST `/recipes/recommendations` | Contributor ID-based filtering/revision API |
| GET `/health` | Liveness |
| GET `/ready` | Database and recipe-source readiness |

OpenAPI: <http://127.0.0.1:8000/docs> while running. Local development uses SQLite;
Compose uses PostgreSQL. See [server setup/API](server/README.md) and
[deployment/DB reset](deploy/README.md).

## Checks

```sh
(cd server && uv sync --locked)
uv run --project server --locked pre-commit install --allow-missing-config
uv run --project server --locked pre-commit run --all-files
(cd server && uv run --locked pytest --cov --cov-report=term-missing --cov-report=html)
(cd android && sh ./gradlew lintDebug testDebugUnitTest assembleDebug assembleCloudTest)
```

CI runs Python/PostgreSQL checks, Android lint/JVM/APK builds and native ARM
image/import checks. Successful main push CI triggers deployment of that exact
revision. Deployment does not initialize/reset the DB or install an APK on a device.

For connected tests, start a matching mock server and configure USB reverse 8000:

```sh
(cd android && sh ./gradlew -PcloudDeviceTest \
  -PserverBaseUrl=http://127.0.0.1:8000/ \
  -Pandroid.testInstrumentationRunnerArguments.notClass=com.example.mylittlechef.ExampleInstrumentedTest \
  connectedCloudTestAndroidTest)
```

The original package-name sample test is excluded only for `.cloudtest`.
Connected-device and opt-in live tests run separately from CI.

## Runtime archive

```sh
python3 scripts/package_server.py --output dist/server.tar.gz
# After extracting on the target:
cd server
uv sync --locked --no-dev
RECIPE_DB_PATH=/absolute/path/recipes.sqlite3 uv run --locked --no-dev \
  uvicorn app.main:create_app_from_env --factory --host 0.0.0.0 --port 8000
```

The archive uses committed runtime source with a commit/file-hash manifest.
Supply the DB and environment separately; tests/research/private data are excluded.

## Further documentation

- [Android installation and builds](android/README.md)
- [Server setup and API](server/README.md)
- [Compose deployment and recovery](deploy/README.md)
- [Research commands](research/README.md)
- [Project Wiki](https://github.com/snuhcs-course/swpp-2026-project-team-15/wiki)
