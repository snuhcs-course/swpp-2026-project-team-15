# Running the server

Compose runs nginx → FastAPI/Uvicorn from a fresh clone. There is no database. Recipe and video files are optional (see below). Docker builds the locked Python dependencies and copies only the server runtime files.

```bash
git clone -b feat/youtube-recipe-demo git@github.com:snuhcs-course/swpp-2026-project-team-15.git
cd swpp-2026-project-team-15
cp deploy/runtime.env.example deploy/runtime.env && chmod 600 deploy/runtime.env   # then fill in the keys
docker compose up -d --build                                                       # nginx on port 80 (HTTP_PORT to change)
curl -f http://127.0.0.1/ready
```

| Setting | Meaning |
| --- | --- |
| `HTTP_PORT` | Host port of nginx (default 80) |
| `COMPOSE_PROJECT_NAME` | Use another name to run a second copy next to the first |
| `RUNTIME_ENV` | Path of the key file (default `deploy/runtime.env`) |
| `OPENROUTER_API_KEY` | Dish suggestions, substitutes, video proposals and photo recognition |
| `YOUTUBE_API_KEY` | `videos.list` for `/dishes/videos` |
| `DISH_DATA_DIR` | Host folder mounted read-only at `/data` in the API container (default `deploy/data`, gitignored) |
| `TELEMETRY_DIR` | Host folder mounted writable at `/telemetry` (default `deploy/telemetry`, gitignored); create it owned by uid 10001, mode 700 |
| `TELEMETRY_FILE` | In `runtime.env`, e.g. `/telemetry/usage.jsonl`: app usage events and one line per request (route, status, time; no bodies). Unset = off. Summary: `research/experiments/telemetry/summarize.py` |
| `DISH_RECIPES`, `DISH_VIDEOS` | Files inside that folder, set in `runtime.env` as `/data/recipes.json` and `/data/dish-videos.json`; without them no dish has a recipe and videos are found on request |

Keys stay in `deploy/runtime.env` (gitignored): never in Git, images or the app. The recipe and video files are made by the tools in `research/experiments/dish_recipes/`, contain content derived from third-party videos and are copied to the server by hand, not committed.

## Runtime details

| Component | Configuration |
| --- | --- |
| API | One Uvicorn worker; no reload; synchronous routes use the threadpool; nonroot, read-only root filesystem |
| nginx | One proxy location, 210 s read timeout, 16 MiB upload limit; **no rate limit** |

`/health` is liveness; `/ready` checks the dish list. This small demo service has **no user authentication and no rate limit**: every model call costs money, so monitor OpenRouter usage and stop the containers when not in use (`docker compose down`).

## Operations

```bash
docker compose ps
docker compose logs --tail=50 api nginx     # one line per model or video call; no keys, no ingredient text
docker compose down
```

## Android

Every build defaults to the team server `http://158.101.141.165/`; HTTP is allowed only for this IP and localhost. The release (store) build, application id `kr.ac.snu.swpp15.mylittlechef`, uses the same server and allows HTTP only to that IP; sign it with `-PreleaseSigning=/path/to/file.properties` (storeFile, storePassword, keyAlias, keyPassword; kept outside the repository) and point it elsewhere with `-PreleaseServerBaseUrl=...`. To build against another server: `sh scripts/install-android.sh http://host:port/`.

## CI

CI checks preserved contributor tests, Python lint and tests, Android lint/JVM tests/APKs and a native ARM image smoke test.

## Deployment

Every green CI run of a push to `main` triggers `.github/workflows/deploy.yml`: it clones the commit into `/opt/mylittlechef/releases/<sha>` on the team server and runs `deploy/release.sh <sha>`. The script builds the image, restarts only `api` and `nginx` on port 80 with keys from `/opt/mylittlechef/config/runtime-dishes.env`, recipe and video files from `/opt/mylittlechef/data/dish-data` and the usage file in `/opt/mylittlechef/data/telemetry`, checks `/ready`, `/dishes` and `/recipes/ingredients`, then records the release in `/opt/mylittlechef/current` and `deployed-sha`. If the checks fail it restarts the previous release. An older postgres container of the same project is left running; this stack does not use it.
