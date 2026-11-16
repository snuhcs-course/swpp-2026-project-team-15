# Oracle ARM development deployment

Compose runs nginx → FastAPI/Uvicorn. Only port 80 is published. Docker uses the locked Python dependencies and copies only server runtime files. There is no database.
The default Android debug endpoint is `http://158.101.141.165/`: HTTP is allowed only for this IP and localhost in debug/cloudTest. Release disables cleartext; supply `-PreleaseServerBaseUrl=https://YOUR-DOMAIN/` after configuring DNS and TLS. The VM IP is ephemeral; update the endpoint if it changes.

## Runtime settings

| Component | Configuration |
| --- | --- |
| API | One Uvicorn worker; no reload; synchronous routes use the threadpool |
| nginx | Port 80; one proxy location, 210 s read timeout, 16 MiB upload limit; **no rate limit** |
| Containers | API runs nonroot with a read-only root filesystem and temporary /tmp |
| Video cache | Host folder `/opt/mylittlechef/data/dish-videos` mounted read-only at `/data`; survives releases |

## Versions

A version is a git commit. `release.sh` needs a clean checkout of exactly that commit under `/opt/mylittlechef/releases/<commit>`, builds its image, starts it and keeps the previous release if the new one fails `/ready`. To run another version, clone (or fetch) that commit into its own release folder and run `release.sh` there; nothing is migrated.

## Host configuration

Install Docker Engine/Compose and Git on Ubuntu ARM, add the SSH user to the docker group. Create `/opt/mylittlechef/{config,data,releases}` owned by that user. Copy `runtime.env.example` to `/opt/mylittlechef/config/runtime.env` (0600) and set the OpenRouter key. Keys stay outside Git, images and APKs.

From a clean checkout under `/opt/mylittlechef/releases/<commit>`:

```bash
bash deploy/release.sh "$(git rev-parse HEAD)"
```

## Operations over SSH

```bash
ssh -i /path/to/team-key -o IdentitiesOnly=yes ubuntu@158.101.141.165
cd /opt/mylittlechef/current
export APP_IMAGE="mylittlechef:$(git rev-parse HEAD)"
docker compose ps
docker compose logs --tail=50 api nginx
curl -f http://127.0.0.1/ready
```

`/health` is liveness; `/ready` checks the dish list. Recognition errors stay visible to the client; there is no paid automatic retry. This small development service has **no user authentication and no rate limit**: every model call costs money, so monitor OpenRouter usage and stop the API when not in use. A global daily cap is a possible later step.

## Dish video cache

The API reads the cache from `/data/dish-videos.json` and re-reads it when the file changes. Fill it on the host; the key stays outside `runtime.env`:

```bash
sudo install -d -m 755 -o "$USER" /opt/mylittlechef/data/dish-videos
install -m 600 /dev/null /opt/mylittlechef/config/youtube.env   # then add: YOUTUBE_API_KEY=...
cd /opt/mylittlechef/current
bash deploy/dish-cache.sh --max-requests 120            # dry run: plan and quota estimate
bash deploy/dish-cache.sh --max-requests 120 --live     # 60 dishes: 6,060 quota units
```

A search costs 100 quota units and a video lookup 1, against a default of 10,000 units a day (resets at midnight Pacific time), so 130 dishes take two days. YouTube API data may be cached for a limited time only (30 days as of the terms we read; check the current terms) and entries older than 30 days are ignored by the API. Refresh example, not installed by any script: run `bash /opt/mylittlechef/current/deploy/dish-cache.sh --max-requests 120 --live --max-age-days 20` once a day after the quota reset; only dishes older than 20 days are fetched.

## CI/CD and Android

CI checks preserved contributor tests, Python lint/tests, Android lint/JVM/APKs, and a native ARM image/import smoke test. Successful **push CI on main** triggers SSH deployment of that exact revision; PR jobs receive no deployment key. Repository secrets: `ORACLE_DEPLOY_KEY`, `ORACLE_KNOWN_HOSTS`. The host builds its native ARM image, checks readiness, and restores the previous image/config if a candidate fails.
