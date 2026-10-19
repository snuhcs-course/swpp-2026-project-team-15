#!/usr/bin/env sh
# AI-generated with Claude Code (Opus 5.5), 2026-10-11 to 2026-10-14; reviewed by Jaehyuk Choi.
# Starts the backend on this computer and installs/launches the app on a USB-connected phone.
# Usage: sh scripts/run-local-demo.sh [path/to/entities-2026-10-19.zip]
set -eu

REPO_ROOT=$(cd "$(dirname "$0")/.." && pwd)
SERVER_DIR="$REPO_ROOT/server"
ANDROID_DIR="$REPO_ROOT/android/MyLittleChef"
RECIPE_DIR="$REPO_ROOT/data/recipes-iter2"
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

# Prefer a USB phone over a running emulator; ANDROID_SERIAL overrides the choice.
select_device() {
    ready=$("$ADB" devices | awk 'NR > 1 && $2 == "device" { print $1 }')
    if [ -n "${ANDROID_SERIAL:-}" ]; then
        echo "$ready" | grep -qx "$ANDROID_SERIAL" ||
            fail "ANDROID_SERIAL=$ANDROID_SERIAL is not connected and authorized."
        echo "$ANDROID_SERIAL"
        return
    fi
    phones=$(echo "$ready" | grep -v '^emulator-' || true)
    emulators=$(echo "$ready" | grep '^emulator-' || true)
    pending=$("$ADB" devices | awk 'NR > 1 && $2 != "device" && $1 !~ /^emulator-/ { print $1 " (" $2 ")" }')
    if [ -z "$phones" ] && [ -n "$pending" ]; then
        fail "Phone not ready: $pending. Accept the USB debugging prompt on the phone and re-run."
    fi
    for candidates in "$phones" "$emulators"; do
        count=$(echo "$candidates" | grep -c . || true)
        if [ "$count" -eq 1 ]; then
            echo "$candidates"
            return
        elif [ "$count" -gt 1 ]; then
            fail "Several devices: $(echo "$candidates" | tr '\n' ' ')- choose one with ANDROID_SERIAL=<serial> sh scripts/run-local-demo.sh"
        fi
    done
    fail "No authorized device. Connect the phone by USB, enable USB debugging and accept the prompt. ('adb devices' shows: $("$ADB" devices | tail -n +2 | tr '\n' ' '))"
}

step "Choosing the device"
"$ADB" start-server >/dev/null
ANDROID_SERIAL=$(select_device)
export ANDROID_SERIAL # adb and Gradle both target only this device.
echo "Using $("$ADB" shell getprop ro.product.model | tr -d '\r') ($ANDROID_SERIAL)"

step "Preparing the recipe database"
if [ ! -f "$RECIPE_DB" ]; then
    if [ ! -f "$RECIPE_DIR/Recipe.csv" ]; then
        [ $# -ge 1 ] || fail "Recipe CSVs are distributed outside Git. Re-run with the zip path: sh scripts/run-local-demo.sh path/to/entities-2026-10-19.zip"
        mkdir -p "$RECIPE_DIR"
        (cd "$SERVER_DIR" && uv run python -c "import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "$1" "$RECIPE_DIR")
    fi
    # The importer preserves its original data/recipes defaults; this increment uses a separate DB.
    (cd "$SERVER_DIR" && uv run python db/import_recipes.py --csv-dir "$RECIPE_DIR" --db "$RECIPE_DB")
fi

# Fail before installing the app or making any provider request if IDs use another catalog.
(cd "$SERVER_DIR" && uv run python -c 'import sqlite3,sys; db=sqlite3.connect(sys.argv[1]); row=db.execute("SELECT name FROM ingredient WHERE ingredient_id=204").fetchone(); assert row == ("물",), "Expected the Iteration 2 water catalog; preserve the old DB and import the matching bundle"' "$RECIPE_DB")

step "Preparing the server"
[ -f "$SERVER_DIR/.env" ] || cp "$SERVER_DIR/.env.example" "$SERVER_DIR/.env"
(cd "$SERVER_DIR" && uv sync --quiet)

step "Building and installing the app"
(cd "$ANDROID_DIR" && sh ./gradlew --quiet installDebug)
"$ADB" push "$REPO_ROOT/docs/demo/mock-photo.png" /sdcard/Pictures/MyLittleChef-mock.png >/dev/null
"$ADB" shell am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE \
    -d file:///sdcard/Pictures/MyLittleChef-mock.png >/dev/null
"$ADB" reverse "tcp:$DEVICE_PORT" "tcp:$HOST_PORT" >/dev/null
"$ADB" shell am start -n "$APP_ACTIVITY" >/dev/null

step "Server running on http://127.0.0.1:$HOST_PORT (phone -> adb reverse). Ctrl+C to stop."
cd "$SERVER_DIR"
exec uv run --env-file .env uvicorn app.main:create_app_from_env --factory --host 127.0.0.1 --port "$HOST_PORT"
