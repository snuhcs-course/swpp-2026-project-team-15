#!/usr/bin/env sh
# AI-generated with Claude Code (Opus 5.5), 2026-10-11; reviewed by Jaehyuk Choi.
# Starts the backend on this computer and installs/launches the app on a USB-connected phone.
# Usage: sh scripts/run-local-demo.sh [path/to/recipes_csv_with_ingredients.zip]
set -eu

REPO_ROOT=$(cd "$(dirname "$0")/.." && pwd)
SERVER_DIR="$REPO_ROOT/server"
ANDROID_DIR="$REPO_ROOT/android/MyLittleChef"
RECIPE_DIR="$REPO_ROOT/data/recipes"
RECIPE_DB="$RECIPE_DIR/recipes.sqlite3"
HOST_PORT="${PORT:-8000}"
DEVICE_PORT=8000 # Fixed in the app (ApiClient.BASE_URL).
APP_ACTIVITY="com.example.mylittlechef/.MainActivity"

step() { printf '\n==> %s\n' "$1"; }
fail() { printf 'ERROR: %s\n' "$1" >&2; exit 1; }

find_android_sdk() {
    for dir in "${ANDROID_HOME:-}" "${ANDROID_SDK_ROOT:-}" "$HOME/Android/Sdk" \
        "$HOME/Library/Android/sdk" "${LOCALAPPDATA:-}/Android/Sdk"; do
        if [ -n "$dir" ] && [ -d "$dir/platform-tools" ]; then
            echo "$dir"
            return
        fi
    done
    fail "Android SDK not found. Install it with Android Studio or set ANDROID_HOME."
}

step "Checking tools"
command -v uv >/dev/null || fail "uv not found. Install: https://docs.astral.sh/uv/"
command -v java >/dev/null || fail "java not found. Install JDK 21 (Android Studio bundles one)."
ANDROID_HOME=$(find_android_sdk)
export ANDROID_HOME
ADB="$ANDROID_HOME/platform-tools/adb"
[ -x "$ADB" ] || ADB="$ADB.exe"

step "Checking the phone"
"$ADB" start-server >/dev/null
state=$("$ADB" get-state 2>/dev/null || true)
[ "$state" = "device" ] || fail "No authorized phone. Connect it by USB, enable USB debugging and accept the prompt. ('adb devices' shows: $("$ADB" devices | tail -n +2 | tr '\n' ' '))"

step "Preparing the recipe database"
if [ ! -f "$RECIPE_DB" ]; then
    if [ ! -f "$RECIPE_DIR/Recipe.csv" ]; then
        [ $# -ge 1 ] || fail "Recipe CSVs are distributed outside Git. Re-run with the zip path: sh scripts/run-local-demo.sh path/to/recipes_csv_with_ingredients.zip"
        mkdir -p "$RECIPE_DIR"
        (cd "$SERVER_DIR" && uv run python -c "import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "$1" "$RECIPE_DIR")
    fi
    (cd "$SERVER_DIR" && uv run python db/import_recipes.py)
fi

step "Preparing the server"
[ -f "$SERVER_DIR/.env" ] || cp "$SERVER_DIR/.env.example" "$SERVER_DIR/.env"
(cd "$SERVER_DIR" && uv sync --quiet)

step "Building and installing the app"
(cd "$ANDROID_DIR" && sh ./gradlew --quiet installDebug)
"$ADB" reverse "tcp:$DEVICE_PORT" "tcp:$HOST_PORT" >/dev/null
"$ADB" shell am start -n "$APP_ACTIVITY" >/dev/null

step "Server running on http://127.0.0.1:$HOST_PORT (phone -> adb reverse). Ctrl+C to stop."
cd "$SERVER_DIR"
exec uv run --env-file .env uvicorn app.main:create_app_from_env --factory --host 127.0.0.1 --port "$HOST_PORT"
