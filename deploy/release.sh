#!/usr/bin/env bash
# Run on ARM host: bash /path/to/checkout/deploy/release.sh <40-char commit>
# Source checkout must match the requested revision. Existing data is never reset.
set -euo pipefail
sha=${1:?40-character commit SHA required}
[[ $sha =~ ^[a-f0-9]{40}$ ]] || exit 2
cd "$(dirname "$0")/.."
[[ $(git rev-parse HEAD) == "$sha" && -z $(git status --porcelain --untracked-files=no) ]] || { echo 'Clean matching revision required'; exit 2; }
exec 9>/opt/mylittlechef/deploy.lock
flock -n 9 || { echo 'Another deployment is running'; exit 1; }
previous=$(readlink -f /opt/mylittlechef/current || true)
export APP_IMAGE="mylittlechef:$sha"
docker compose build api
docker compose up -d postgres api
docker compose up -d --force-recreate nginx
for attempt in $(seq 1 45); do
  if curl -fsS --max-time 15 http://127.0.0.1/ready >/dev/null; then
    ln -sfn "$PWD" /opt/mylittlechef/current
    printf '%s\n' "$sha" > /opt/mylittlechef/deployed-sha
    echo "Deployed $sha"
    exit 0
  fi
  sleep 2
done
if [[ -n $previous && -d $previous && $previous != "$PWD" ]]; then
  cd "$previous"
  export APP_IMAGE="mylittlechef:$(git rev-parse HEAD)"
  docker compose up -d --no-build postgres api
  docker compose up -d --no-build --force-recreate nginx
  echo 'Candidate failed readiness; restored previous image/config' >&2
fi
exit 1
