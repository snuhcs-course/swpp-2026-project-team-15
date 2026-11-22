#!/usr/bin/env bash
# AI-assisted with Claude Code (Opus 5.5), 2026-11-20; reviewed by Jaehyuk Choi.
# Run on the ARM host: bash /path/to/checkout/deploy/release.sh <40-char commit>
# Deploys the database-free stack (api + nginx on :80). The checkout must be clean and at <sha>.
# Keys stay in $ROOT/config/runtime-dishes.env (not in Git); recipe and video files in
# $ROOT/data/dish-data; the usage file in $ROOT/data/telemetry. An older postgres container of the
# same compose project is left running untouched: this stack does not use it.
set -euo pipefail
sha=${1:?40-character commit SHA required}
[[ $sha =~ ^[a-f0-9]{40}$ ]] || exit 2
cd -P "$(dirname "$0")/.."
[[ $(git rev-parse HEAD) == "$sha" && -z $(git status --porcelain --untracked-files=no) ]] || { echo 'Clean matching revision required'; exit 2; }
ROOT=/opt/mylittlechef
exec 9>"$ROOT/deploy.lock"
flock -n 9 || { echo 'Another deployment is running'; exit 1; }
previous=$(readlink -f "$ROOT/current" || true)

export APP_IMAGE="mylittlechef:$sha"
export RUNTIME_ENV="$ROOT/config/runtime-dishes.env"
export DISH_DATA_DIR="$ROOT/data/dish-data"
export TELEMETRY_DIR="$ROOT/data/telemetry"
export HTTP_PORT=80
[[ -r $RUNTIME_ENV && -d $DISH_DATA_DIR && -d $TELEMETRY_DIR ]] || { echo 'Missing runtime env or data folders'; exit 2; }

ready() {
  # /ready plus two routes that read the dish list and the name table (no model call, no cost).
  curl -fsS --max-time 15 http://127.0.0.1/ready >/dev/null &&
    curl -fsS --max-time 15 http://127.0.0.1/dishes >/dev/null &&
    curl -fsS --max-time 15 http://127.0.0.1/recipes/ingredients >/dev/null
}

docker compose build api
docker compose up -d --no-deps api
docker compose up -d --no-deps --force-recreate nginx
for attempt in $(seq 1 45); do
  if ready; then
    ln -sfn "$PWD" "$ROOT/current"
    printf '%s\n' "$sha" > "$ROOT/deployed-sha"
    echo "Deployed $sha"
    exit 0
  fi
  sleep 2
done

if [[ -n $previous && -d $previous && $previous != "$PWD" ]]; then
  cd "$previous"
  export APP_IMAGE="mylittlechef:$(git rev-parse HEAD)"
  if grep -q '^  postgres:' compose.yaml; then
    # An older release of the recipe-database stack: its own env file and services.
    unset RUNTIME_ENV DISH_DATA_DIR TELEMETRY_DIR
    docker compose up -d --no-build postgres api
  else
    docker compose up -d --no-build --no-deps api
  fi
  docker compose up -d --no-build --no-deps --force-recreate nginx
  echo 'Candidate failed readiness; restored previous image/config' >&2
fi
exit 1
