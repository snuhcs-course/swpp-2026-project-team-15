# My Little Chef — dish suggestion version

SNU SWPP Fall 2026 · Team 15. The Android app recognises the ingredients in a fridge from photos or a short sweep, keeps the fridge and profile on the phone, and suggests **dishes** to cook with them, with YouTube videos and substitutes for what is missing. This version has **no recipe database**: dishes come from one self-authored list on the server, and videos are YouTube embeds that link to YouTube. Other versions (for example the recipe-database version on `main`) are other branches or commits; there are no mode flags.

## Source layout

```text
.
├── .github/workflows/      # Server, Android and ARM checks
├── android/                # Compose app, DataStore, JVM/device tests
├── server/
│   ├── app/dishes/         # Dish list, model-based suggestion and substitutes, video cache
│   ├── app/vision/         # Ingredient recognition providers
│   ├── fixtures/           # Recorded recognition responses, synthetic demo image
│   └── tests/              # Automated checks and protected references
├── research/               # Evaluation tools and experiments (the record of decisions)
├── scripts/                # Android install, integrity check, packaging, video prefetch
├── deploy/                 # nginx, runtime template, release and video-cache scripts
├── docs/images/            # Images for the Wiki
├── Dockerfile              # Nonroot runtime API image
└── compose.yaml            # nginx and API (no database)
```

## Quick start (app only)

A demo server for this branch runs at `http://158.101.141.165:8080/` (no login, no rate limit; model calls cost money). With a phone attached by USB:

```sh
git clone -b feat/youtube-recipe-demo git@github.com:snuhcs-course/swpp-2026-project-team-15.git
cd swpp-2026-project-team-15
sh scripts/install-android.sh        # builds and installs the isolated .cloudtest app, talking to the demo server
```

The app needs nothing else. To use your own server, pass its URL (`sh scripts/install-android.sh http://host:port/`) and see "Run locally" below.

## Run locally

```sh
cd server
uv sync --locked
cp .env.example .env          # VISION_PROVIDER=mock: no key, no network
uv run --env-file .env uvicorn app.main:create_app_from_env --factory --port 8000
```

Dish suggestions need `OPENROUTER_API_KEY` (without it `/dishes/suggest` answers 502; there is no rules fallback). Without a video cache the app shows a YouTube search link only. See [server README](server/README.md).

## Install the app

Requires Android SDK 37, Java and an authorized USB-debugging device.

```sh
sh scripts/install-android.sh [http://host/]     # builds and installs only the isolated .cloudtest app
adb reverse tcp:8000 tcp:8000                    # for a server on this computer
```

See [Android setup](android/README.md) for SDK configuration and endpoint overrides.

## App and API

The app uploads a photo, or the sharpest frames of a 5 s sweep, to `/analyze`; the user reviews the ingredient names; `/dishes/suggest` returns dishes (with `have`/`missing`, videos and a search link) and `/dishes/adapt` returns substitutes or skips.

| Endpoint | Purpose |
| --- | --- |
| POST `/analyze` | Photo (`image`) or 2–15 views (`images`) → ingredient candidates |
| GET `/dishes`, POST `/dishes/suggest`, POST `/dishes/adapt` | Dish list, suggestions, substitutes |
| GET `/recipes/ingredients`, POST `/recipes/ingredient-suggestions` | Entry completion and "add this to complete more dishes" |
| GET `/health`, GET `/ready` | Liveness; dish list loaded |

OpenAPI: <http://127.0.0.1:8000/docs> while running. Details: [server README](server/README.md), [deployment](deploy/README.md).

## Checks

```sh
cd server && uv sync --locked
uv run ruff check . ../scripts ../research/evaluation
uv run ruff format --check . ../scripts ../research/evaluation
python3 ../scripts/check_integration_policy.py
uv run pytest
cd ../android && sh ./gradlew lintDebug testDebugUnitTest assembleDebug assembleCloudTest
```

CI runs the Python checks, Android lint/JVM tests/APK builds and a native ARM image/import smoke test. Device tests run locally.

## Runtime archive

```sh
python3 scripts/package_server.py --output dist/server.tar.gz
# On the target: cd server && uv sync --locked --no-dev && uv run --locked --no-dev uvicorn app.main:create_app_from_env --factory --host 0.0.0.0 --port 8000
```

## Further documentation

- [Android installation and builds](android/README.md)
- [Server setup and API](server/README.md)
- [Deployment](deploy/README.md)
- [Research](research/README.md)
- [Project Wiki](https://github.com/snuhcs-course/swpp-2026-project-team-15/wiki)
