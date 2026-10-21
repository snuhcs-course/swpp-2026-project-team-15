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
| nginx | Port 80; AI routes 6 requests/minute/IP, burst 3; 4 active connections/IP |
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
The APK resolves fridge ingredient names against the versioned catalog each request;
stale catalog headers return 409. Favorites are recipe IDs: retain recipe identity
across datasets, or clear favorites in the isolated test app when IDs are reassigned.

To restore a backup, stop API, then feed the dump into
`docker compose exec -T postgres pg_restore -U chef -d chef --clean --if-exists --single-transaction`,
and start API. Backups can contain project data; keep them private and prune manually.

`/health` is liveness; `/ready` checks DB/catalog and complete recipe sources.
Nginx limits AI requests per IP and upload bodies to 16 MiB. AI routes use a
210-second upstream read timeout; this is an idle-read timeout, not an overall
request deadline. The app requests three sequential revision attempts by default;
the API permits five, which can exceed that wait when providers are slow.
Recognition and revision errors stay visible to the client;
there is no paid automatic retry or mock fallback. This small development service
has no user authentication; monitor OpenRouter usage and stop the API when not in use.

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
excluded only for the isolated `.cloudtest` package. Nine functional fixture tests
remain; the paid cloud smoke skips unless explicitly enabled. For the live smoke,
install the default cloud APK/test APK, place a real JPEG at the test app's
`cache/cloud-smoke.jpg`, then run instrumentation with
`-e class com.example.mylittlechef.integration.CloudEndpointSmokeTest -e liveCloud true`.
It checks photo review before saving and one structurally validated revision result on the
public cloud endpoint. Wi-Fi/Internet on the device is required; no USB tunnel is
used by this test. Screenshots/results are written to the test app cache.
