#!/usr/bin/env bash
# Fill or refresh the dish video cache on the ARM host (see deploy/README.md, "Dish suggestions").
#   bash deploy/dish-cache.sh --max-requests 40                  # dry run: prints the plan and quota estimate
#   bash deploy/dish-cache.sh --max-requests 120 --live          # calls the YouTube Data API
#   bash deploy/dish-cache.sh --max-requests 4 --live --only kimchi-fried-rice egg-roll
# Each dish costs two requests (one search, 100 quota units, and one video lookup, 1 unit). The default
# daily quota is 10,000 units, so cap the run with --max-requests. The key is read from
# $YOUTUBE_KEY_FILE (default /opt/mylittlechef/config/youtube.env, mode 0600, line YOUTUBE_API_KEY=...)
# and is never printed.
set -euo pipefail

usage() { sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-2}"; }

max_requests=""
live=0
max_age=20
force=0
only=()
while (($#)); do
  case "$1" in
    --max-requests) max_requests=${2:?--max-requests needs a number}; shift 2 ;;
    --live) live=1; shift ;;
    --max-age-days) max_age=${2:?--max-age-days needs a number}; shift 2 ;;
    --force) force=1; shift ;;
    --only) shift; while (($#)) && [[ $1 != --* ]]; do only+=("$1"); shift; done ;;
    -h|--help) usage 0 ;;
    *) echo "unknown option: $1" >&2; usage ;;
  esac
done
[[ $max_requests =~ ^[1-9][0-9]*$ ]] || { echo "--max-requests <positive number> is required (quota cap)" >&2; usage; }
[[ $max_age =~ ^[0-9]+$ ]] || { echo "--max-age-days must be a number" >&2; exit 2; }

cd -P "$(dirname "$0")/.."
export DISH_DATA_DIR=${DISH_DATA_DIR:-/opt/mylittlechef/data/dish-videos}
export HOST_UID=${HOST_UID:-$(id -u)} HOST_GID=${HOST_GID:-$(id -g)}
if [[ -z ${APP_IMAGE:-} ]]; then
  [[ -r /opt/mylittlechef/deployed-sha ]] || { echo "set APP_IMAGE (no /opt/mylittlechef/deployed-sha)" >&2; exit 2; }
  deployed=$(< /opt/mylittlechef/deployed-sha)
  export APP_IMAGE="mylittlechef:$deployed"
fi
docker image inspect "$APP_IMAGE" >/dev/null 2>&1 || { echo "image $APP_IMAGE not found on this host" >&2; exit 2; }

exec 9>/opt/mylittlechef/dish-cache.lock
flock -n 9 || { echo "another dish-cache run is active" >&2; exit 1; }

# The API container reads the cache as another user: keep the directory and file world-readable.
umask 022
mkdir -p "$DISH_DATA_DIR"

args=(--max-requests "$max_requests" --max-age-days "$max_age")
((force)) && args+=(--force)
((${#only[@]})) && args+=(--only "${only[@]}")
if ((live)); then
  key_file=${YOUTUBE_KEY_FILE:-/opt/mylittlechef/config/youtube.env}
  [[ -f $key_file ]] || { echo "key file $key_file not found" >&2; exit 2; }
  mode=$(stat -c %a "$key_file")
  [[ $mode == 600 || $mode == 400 ]] || { echo "$key_file must be mode 600 (is $mode)" >&2; exit 2; }
  key=$(grep -m1 '^YOUTUBE_API_KEY=' "$key_file" | cut -d= -f2- | tr -d '"'"'"'\r ')
  [[ -n $key ]] || { echo "no YOUTUBE_API_KEY= line in $key_file" >&2; exit 2; }
  export YOUTUBE_API_KEY=$key
  args+=(--live)
else
  unset YOUTUBE_API_KEY
fi
docker compose --profile tools run --rm --no-deps dish-cache "${args[@]}"
