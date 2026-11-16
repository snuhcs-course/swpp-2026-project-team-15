# Oracle ARM development deployment

Compose runs nginx → FastAPI/Uvicorn → PostgreSQL 17. Only port 80 is published.
Docker uses the locked Python dependencies and copies only server runtime files.
The current default Android debug endpoint is `http://158.101.141.165/`.
This is a development endpoint: HTTP is allowed only for this IP and localhost in
debug/cloudTest. Release disables cleartext; supply `-PreleaseServerBaseUrl=https://YOUR-DOMAIN/`
after configuring DNS and TLS. The VM IP is ephemeral; update the endpoint if it changes.

## Runtime settings

| Component | Configuration |
| --- | --- |
| API | One Uvicorn worker by default; no reload; synchronous routes use the threadpool |
| PostgreSQL | Persistent volume; read-only API transactions with REPEATABLE READ |
| nginx | Port 80; one proxy location, 210 s read timeout, 16 MiB upload limit; no rate limit |
| Containers | API runs nonroot with a read-only root filesystem and temporary /tmp |

## Host configuration

Install Docker Engine/Compose and Git on Ubuntu ARM, add the SSH user to the docker group.
Create `/opt/mylittlechef/{config,datasets,backups,releases}` owned by that user.
Keep config/datasets/backups private. Copy `runtime.env.example` to
`/opt/mylittlechef/config/runtime.env` (0600), set a random DB password and the team
OpenRouter key, and put the same password in `config/db_password` (0600).
API keys and dataset ZIPs stay outside Git, images and APKs. Both OpenRouter modes
use explicit model IDs; mock modes remain available for offline development.

From a clean checkout under `/opt/mylittlechef/releases/<commit>`:

```bash
export APP_IMAGE="mylittlechef:$(git rev-parse HEAD)"
docker compose build api
docker compose up -d postgres
# Upload ZIP to /opt/mylittlechef/datasets first.
bash deploy/db.sh init entities.zip
bash deploy/release.sh "$(git rev-parse HEAD)"
```

## Developer operations over SSH

```bash
ssh -i /path/to/team-key -o IdentitiesOnly=yes ubuntu@158.101.141.165
cd /opt/mylittlechef/current
export APP_IMAGE="mylittlechef:$(git rev-parse HEAD)"
bash deploy/db.sh reset entities.zip
docker compose ps
docker compose logs --tail=50 api nginx
curl -f http://127.0.0.1/ready
```

`db.sh` and `release.sh` share a nonblocking host lock: a concurrent scripted operation exits. Do not mix direct imports with these operations.

`init` refuses an initialized DB. `reset` takes a custom-format pg_dump backup,
stops the API briefly, validates the ZIP, replaces only the eight recipe tables in
one transaction, and restarts the API even on failure. Invalid CSV/foreign keys or
failed PostgreSQL writes preserve the old dataset. Never use `down -v` to reset data.
ZIP must contain the eight canonical CSV basenames at its root, at most 32 MiB
compressed / 64 MiB expanded. Water must be ingredient 204; recipe sources must be complete.
The APK uses the original name-based recommendation API. Favorites remain local
recipe IDs; preserve recipe identity when replacing datasets.

To restore a backup, stop API, then feed the dump into
`docker compose exec -T postgres pg_restore -U chef -d chef --clean --if-exists --single-transaction`,
and start API. Backups can contain project data; keep them private and prune manually.

`/health` is liveness; `/ready` checks DB/catalog and complete recipe sources.
Nginx limits upload bodies to 16 MiB and uses a 210-second upstream read timeout
(an idle-read timeout, not an overall request deadline). The separate ID-based revision API defaults to three sequential attempts and
permits five, which can exceed that wait when providers are slow. The app uses
the name-based endpoint and does not request revisions.
Recognition and revision errors stay visible to the client;
there is no paid automatic retry or mock fallback. This small development service
has no user authentication and no rate limit: every model call costs money, so monitor OpenRouter usage and stop the API when not in use. A global daily cap is a possible later step.

## Dish suggestions (YouTube videos, no recipe database)

`POST /dishes/suggest`, `POST /dishes/adapt` and `GET /dishes` pick dishes from the closed list in
`server/app/dishes/dishes.json` (shipped in the image and the runtime archive). Videos come from a
cache file; without it the response carries only a YouTube search link.

| Mode | Settings in `runtime.env` | Effect |
| --- | --- | --- |
| Default (unchanged) | none | Needs the recipe DB; `/ready` fails if it is unavailable or lacks a column the code reads (for example `recipe.main_image_url`) |
| Dish only | `DISH_ONLY=1` | Never opens the recipe DB; only the dish, analyze and health routes exist; `/ready` checks the dish list |
| Optional DB | `RECIPE_DB_OPTIONAL=1` | Starts without the DB only if opening it fails at start; a DB that opens but lacks a column still fails `/ready`, so prefer `DISH_ONLY=1` |

`DISH_LLM_MODEL` (default `google/gemini-2.5-flash-lite`) uses `OPENROUTER_API_KEY`; without a key the
rules-only ranking answers. There is no rate limit.

The API reads the cache from `/data/dish-videos.json` (`DISH_DATA_DIR`, default
`/opt/mylittlechef/data/dish-videos`, mounted read-only) and re-reads it when the file changes.
Fill it on the host; the key stays outside `runtime.env`:

```bash
sudo install -d -m 755 -o "$USER" /opt/mylittlechef/data/dish-videos
install -m 600 /dev/null /opt/mylittlechef/config/youtube.env   # then add: YOUTUBE_API_KEY=...
cd /opt/mylittlechef/current
bash deploy/dish-cache.sh --max-requests 120            # dry run: plan and quota estimate
bash deploy/dish-cache.sh --max-requests 120 --live     # 60 dishes: 6,060 quota units
```

A search costs 100 quota units and a video lookup 1, against a default of 10,000 units a day
(resets at midnight Pacific time), so 130 dishes take two days. YouTube API data may be cached for a
limited time only (30 days as of the terms we read; check the current terms) and entries older than 30
days are ignored by the API. Refresh example, not installed by any script (`~/.config/systemd/user` or
a crontab): run `bash /opt/mylittlechef/current/deploy/dish-cache.sh --max-requests 120 --live
--max-age-days 20` once a day after the quota reset (for example 10:00 UTC); only dishes older than 20
days are fetched, so a full refresh spreads over a few days.

## CI/CD and Android

CI checks preserved contributor tests, Python lint/tests with real PostgreSQL,
Android lint/JVM/APKs, and a native ARM image/import smoke test. Successful **push
CI on main** triggers SSH deployment of that exact revision; PR jobs receive no
deployment key. Repository secrets: `ORACLE_DEPLOY_KEY`, `ORACLE_KNOWN_HOSTS`.
The host builds its native ARM image, checks readiness, and restores the previous
image/config if a candidate fails. Deployment never imports or resets a dataset.

Install the isolated app with `sh scripts/install-android.sh` from repository root.
See [Android setup](../android/README.md) for endpoint configuration and
[root device tests](../README.md#checks-and-pre-commit) for mock integration checks.

`db.sh` passes the deployment user UID/GID to the importer so it can read the
private, read-only dataset mount without widening directory permissions.

The preserved `ExampleInstrumentedTest` asserts the original package name and is
excluded only for the isolated `.cloudtest` package. The photo/name-API fixture test runs against a mock server; the live cloud smoke
skips unless explicitly enabled. For the live smoke,
install the default cloud APK/test APK, place a real JPEG at the test app's
`cache/cloud-smoke.jpg`, then run instrumentation with
`-e class com.example.mylittlechef.integration.CloudEndpointSmokeTest -e liveCloud true`.
It checks live photo recognition, explicit review/save, name-based recommendation
and the original detail screen on the public cloud endpoint. Wi-Fi/Internet on the device is required; no USB tunnel is
used by this test. Screenshots/results are written to the test app cache.
