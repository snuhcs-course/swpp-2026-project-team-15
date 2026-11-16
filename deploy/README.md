# Running the server

Compose runs nginx → FastAPI/Uvicorn from a fresh clone. There is no database and no host folder to prepare. Docker builds the locked Python dependencies and copies only the server runtime files.

```bash
git clone -b feat/youtube-recipe-demo git@github.com:snuhcs-course/swpp-2026-project-team-15.git
cd swpp-2026-project-team-15
cp deploy/runtime.env.example deploy/runtime.env && chmod 600 deploy/runtime.env   # then fill in the keys
HTTP_PORT=8080 docker compose up -d --build                                        # HTTP_PORT defaults to 80
curl -f http://127.0.0.1:8080/ready
```

| Setting | Meaning |
| --- | --- |
| `HTTP_PORT` | Host port of nginx (default 80) |
| `COMPOSE_PROJECT_NAME` | Use another name to run a second copy next to the first |
| `RUNTIME_ENV` | Path of the key file (default `deploy/runtime.env`) |
| `OPENROUTER_API_KEY` | Dish suggestions, substitutes, video proposals and photo recognition |
| `YOUTUBE_API_KEY` | `videos.list` for `/dishes/videos` |

Keys stay in `deploy/runtime.env` (gitignored): never in Git, images or the app.

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

The default debug/cloudTest endpoint is the demo server `http://158.101.141.165:8080/`; HTTP is allowed only for this IP and localhost. Release builds disable cleartext traffic; supply `-PreleaseServerBaseUrl=https://YOUR-DOMAIN/` after configuring DNS and TLS. To build against another server: `sh scripts/install-android.sh http://host:port/`.

## CI

CI checks preserved contributor tests, Python lint and tests, Android lint/JVM tests/APKs and a native ARM image smoke test. This branch has no deployment workflow.
