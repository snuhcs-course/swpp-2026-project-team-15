#!/usr/bin/env sh
# Build and install the isolated cloudTest app; no backend, data reset or AI calls.
# Usage: [ANDROID_SERIAL=<serial>] sh scripts/install-android.sh [http(s)://host/]
set -eu

fail() { printf 'ERROR: %s\n' "$1" >&2; exit 1; }
if [ "${1:-}" = --help ] || [ "${1:-}" = -h ]; then
    printf '%s\n' 'Usage: [ANDROID_SERIAL=<serial>] sh scripts/install-android.sh [http(s)://host/]' \
        'Default endpoint: serverBaseUrl configured by android/app/build.gradle.kts.' \
        'Installs com.example.mylittlechef.cloudtest without launching it.'
    exit 0
fi
[ "$#" -le 1 ] || fail 'Expected at most one server URL; see --help.'
if [ "$#" -eq 1 ]; then
    case "$1" in
        http://*/|https://*/) ;;
        *) fail 'Server URL must start with http:// or https:// and end in /.' ;;
    esac
fi
REPO_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
command -v java >/dev/null 2>&1 || fail 'Java not found. Install the JDK required by android/README.md.'

ADB=$(command -v adb || true)
if [ -z "$ADB" ]; then
    for sdk in "${ANDROID_HOME:-}" "${ANDROID_SDK_ROOT:-}" "$HOME/Android/Sdk" \
        "$HOME/Library/Android/sdk" "${LOCALAPPDATA:-}/Android/Sdk"; do
        [ -n "$sdk" ] || continue
        for candidate in "$sdk/platform-tools/adb" "$sdk/platform-tools/adb.exe"; do
            if [ -x "$candidate" ]; then
                ADB="$candidate"
                ANDROID_HOME="$sdk"
                export ANDROID_HOME
                break 2
            fi
        done
    done
fi
[ -n "$ADB" ] || fail 'adb not found. Set ANDROID_HOME or put Android platform-tools on PATH.'
"$ADB" start-server >/dev/null
ready=$("$ADB" devices | awk 'NR > 1 && $2 == "device" { print $1 }')
if [ -n "${ANDROID_SERIAL:-}" ]; then
    printf '%s\n' "$ready" | awk -v serial="$ANDROID_SERIAL" '$0 == serial { found=1 } END { exit !found }' ||
        fail 'ANDROID_SERIAL is not connected and authorized; check adb devices.'
else
    count=$(printf '%s\n' "$ready" | awk 'NF { n++ } END { print n+0 }')
    [ "$count" -gt 0 ] || fail 'No authorized device. Enable USB debugging and accept its authorization prompt.'
    [ "$count" -eq 1 ] || fail 'Multiple devices. Select one with ANDROID_SERIAL=<serial>.'
    ANDROID_SERIAL="$ready"
fi
export ANDROID_SERIAL

# Build once, then explicitly install on only the selected device.
if [ "$#" -eq 1 ]; then
    (cd "$REPO_ROOT/android" && sh ./gradlew --quiet assembleCloudTest "-PserverBaseUrl=$1")
else
    (cd "$REPO_ROOT/android" && sh ./gradlew --quiet assembleCloudTest)
fi
APK="$REPO_ROOT/android/app/build/outputs/apk/cloudTest/app-cloudTest.apk"
[ -f "$APK" ] || fail 'Expected cloudTest APK was not produced.'
"$ADB" -s "$ANDROID_SERIAL" install -r "$APK"
printf 'Installed MyLittleChef Cloud Test on %s. Open it on the device.\n' "$ANDROID_SERIAL"
