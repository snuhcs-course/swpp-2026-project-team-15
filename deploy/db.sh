#!/usr/bin/env bash
# Usage from checkout: bash deploy/db.sh init|reset dataset.zip
set -euo pipefail
cd "$(dirname "$0")/.."
export HOST_UID=${HOST_UID:-$(id -u)} HOST_GID=${HOST_GID:-$(id -g)}
export APP_IMAGE=${APP_IMAGE:-mylittlechef:$(git rev-parse HEAD)}
action=${1:?Usage: db.sh init|reset dataset.zip}
exec 9>/opt/mylittlechef/deploy.lock
flock -n 9 || { echo "Deployment or DB operation is running"; exit 1; }
archive=${2:?ZIP basename inside DATASET_DIR required}
[[ $archive == "$(basename "$archive")" && $archive == *.zip ]] || { echo 'Use a ZIP basename'; exit 2; }
case "$action" in
  init) docker compose --profile tools run --rm --no-deps importer "/datasets/$archive" ;;
  reset)
    # Keep requests from crossing a dataset change. Backup before stopping API.
    mkdir -p /opt/mylittlechef/backups
    backup="/opt/mylittlechef/backups/recipes-$(date -u +%Y%m%dT%H%M%S)-$$.dump"
    umask 077
    docker compose exec -T postgres pg_dump -U chef -d chef -Fc > "$backup"
    docker compose stop api
    trap 'docker compose start api' EXIT
    docker compose --profile tools run --rm --no-deps importer "/datasets/$archive" --replace ;;
  *) echo 'Use init or reset'; exit 2 ;;
esac
