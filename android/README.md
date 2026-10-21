# Android development

Run commands from the repository root unless stated otherwise. Install Android SDK37
and JDK21; the committed Gradle daemon criteria select/provision JDK25. Set
`ANDROID_HOME` to the SDK, or configure `sdk.dir` in private `android/local.properties`.
For device installation, enable USB debugging and accept the authorization prompt.

## Install the app only

```sh
sh scripts/install-android.sh
# If several phones/emulators are connected:
ANDROID_SERIAL=<serial> sh scripts/install-android.sh
# Explicit endpoint override:
sh scripts/install-android.sh https://your-api.example/
```

The script builds and installs `com.example.mylittlechef.cloudtest` on exactly one
authorized device. It preserves the regular app and its data, and does not start
the backend, initialize data, launch the app or invoke AI. Open **MyLittleChef Cloud
Test** on the device; the default cloud endpoint needs Wi-Fi/mobile Internet, with
no `adb reverse`. The Gradle `serverBaseUrl` configuration supplies the default.

For a running local server, use the explicit override and configure the USB tunnel:

```sh
ANDROID_SERIAL=<serial> sh scripts/install-android.sh http://127.0.0.1:8000/
adb -s <serial> reverse tcp:8000 tcp:8000
```

To prepare a local DB, start the server and launch the app together, use the
[root local-demo instructions](../README.md#run-locally).

## Build variants and endpoints

| Variant | Package | Endpoint setting | Use |
| --- | --- | --- | --- |
| debug | `com.example.mylittlechef` | `serverBaseUrl` | Regular development app |
| cloudTest | `com.example.mylittlechef.cloudtest` | `serverBaseUrl` | Isolated installation/device tests |
| release | `com.example.mylittlechef` | `releaseServerBaseUrl` | HTTPS deployment; configure before distribution |

Debug/cloudTest default to `http://158.101.141.165/`. HTTP is permitted only for
that IP, localhost and 127.0.0.1 by their network security configuration. An HTTP
override to another host also requires updating that allowlist. Release disables
cleartext and defaults to `https://localhost/`, a placeholder requiring an explicit
HTTPS endpoint. The deployment IP is ephemeral.

```sh
(cd android && sh ./gradlew assembleCloudTest)
(cd android && sh ./gradlew assembleDebug -PserverBaseUrl=https://your-api.example/)
(cd android && sh ./gradlew assembleRelease -PreleaseServerBaseUrl=https://your-api.example/)
```

`assembleRelease` builds the release variant; signing/distribution require their
own setup. An app can contact paid AI when its user invokes a cloud feature; an
installation or successful build does not verify provider behavior.

## Checks

```sh
(cd android && sh ./gradlew lintDebug testDebugUnitTest createDebugUnitTestCoverageReport assembleCloudTest)
```

See [root device-test instructions](../README.md#checks-and-pre-commit) for controlled
mock integration tests and [deployment operations](../deploy/README.md#cicd-and-android)
for the opt-in live smoke. Device tests and installation are separate commands.
