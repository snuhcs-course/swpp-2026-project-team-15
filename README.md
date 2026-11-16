# My Little Chef — dish suggestion version

SNU SWPP Fall 2026 · Team 15. The Android app recognises the ingredients in a fridge from photos or a short sweep, keeps the fridge and profile on the phone, and suggests **dishes** to cook with them, with YouTube videos and substitutes for what is missing. This version has **no recipe database**: dishes come from one self-authored list on the server, and videos are YouTube embeds that link to YouTube. Other versions (for example the recipe-database version on `main`) are other branches or commits; there are no mode flags.

## Source layout

```text
.
├── .github/workflows/      # Server, Android and ARM checks
├── android/                # Compose app, DataStore, JVM/device tests
├── server/
│   ├── app/dishes/         # Dish list, model-based suggestion, substitutes and video links
│   ├── app/vision/         # Ingredient recognition providers
│   ├── fixtures/           # Recorded recognition responses, synthetic demo image
│   └── tests/              # Automated checks and protected references
├── research/               # Evaluation tools and experiments (the record of decisions)
├── scripts/                # Android install, integrity check, packaging
├── deploy/                 # nginx and the runtime template
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

Dish suggestions need `OPENROUTER_API_KEY` (without it `/dishes/suggest` answers 502; there is no rules fallback). `/dishes/videos` also needs `YOUTUBE_API_KEY`. See [server README](server/README.md).

## Install the app

Requires Android SDK 37, Java and an authorized USB-debugging device.

```sh
sh scripts/install-android.sh [http://host/]     # builds and installs only the isolated .cloudtest app
adb reverse tcp:8000 tcp:8000                    # for a server on this computer
```

See [Android setup](android/README.md) for SDK configuration and endpoint overrides.

## App and API

The app uploads a photo, or the sharpest frames of a 5 s sweep, to `/analyze`; the user reviews the ingredient names; `/dishes/suggest` returns dishes (with `have`/`missing` and a search link), `/dishes/videos` returns embeddable YouTube videos for one dish when the user opens it, and `/dishes/adapt` returns substitutes or skips.

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

## Demo UAT (2026-11-17)

Run on a phone against the demo server, from fresh clones of this branch (server: `docker compose up`; app: `scripts/install-android.sh`). Evidence is the app's accessibility tree and the server logs; no photos of private scenes were used.

| # | Story | Result |
| --- | --- | --- |
| 1 | Given a fresh install, when I enter a nickname and skip tools and allergies, then I choose pantry items and reach the fridge with them listed | Pass |
| 2 | Given the camera permission is denied, when I open the add button, then I can still choose "type it in" | Pass |
| 3 | Given the fridge, when I open the ingredient suggestion, then it lists ingredients with example dishes and one back press closes it | Pass |
| 4 | Given ingredients, when I open the recipe tab, then dish cards show what I have and what is missing | Pass |
| 5 | Given a dish card, when I open its videos, then a loading text appears and 3–4 videos with channel names are listed within about 4 s | Pass |
| 6 | Given the video list, when I tap one, then the embedded player opens and audio playback starts | Pass |
| 7 | Given a dish with a missing ingredient, when I ask for a substitute, then I get one from my fridge or the message that none fits | Pass (the "none fits" answer; a substitute was returned in the server check) |
| 8 | Given the video sheet, when I look at its bottom, then one caption row "Videos provided by YouTube · 서비스 약관 · 개인정보처리방침" is shown and each link opens its page | Pass |
| 9 | Given a fridge item, when I long-press it and confirm, then it is removed and the recipes update | Pass |
| 10 | Given the server cannot be reached, when I open a dish's videos, then an error with "retry" and a YouTube search button appears, and retry works after the server is back | Pass |
| 11 | Given I changed the screen mode, when I reset the data, then the app returns to the first screen and the screen mode follows the system again | Pass |
| 12 | Given a photo of the fridge, when I add it, then ingredients are recognised | Not run (needs a private photo and the camera permission) |
| 13 | Given typed Korean text, when I type a name, then completions appear | Not run on the phone (adb cannot type Korean); covered by unit tests |

Observed limits: a common input of four ingredients made the model list so many dishes that the answer was cut at the 4,096-token limit in 3 of 4 calls; the server now keeps the complete dishes before the cut (about 30 cards, 10 s). The model service answered with rate-limit errors several times; calls are retried twice.
