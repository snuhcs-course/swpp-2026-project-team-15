# Capture research demo (Android)

A standalone app for measuring, on a real phone, how a short fridge sweep can be turned into a few sharp, non-redundant frames for recognition. It is a separate Gradle project (package `com.mylittlechef.researchdemo`, debug only) and is not part of the team app or its CI. The production implementation lives in the app; this demo keeps the alternatives and the measurement code.

## What it measures

- **Selection strategies** on one recorded clip, so every strategy sees the same frames: `single` (sharpest frame), `uniform`, `time-bins` (sharpest per time bin), `overlap` (blur gate, groups that share most of their view, sharpest per group, farthest-first; ties go to the frame farthest in time), `overlap-strict` (stricter blur gate) and `all` (about 2.5 frames per second). Logic is pure Kotlin in `Arms.kt` and `Selector.kt`; `LiveSelector.kt` is the streaming version of `overlap`.
- **Per-frame cost**: Y-plane copy, downscale, sharpness, ORB features and overlap (OpenCV), recorded per stage.
- **Camera path** (`CameraBench.kt`): CameraX analysis stream at several sizes and frame rates, conversion costs on live frames, recording then decoding, still-capture loop, Camera2 burst and full-size YUV stream.
- **Video-file input** (`VideoRun.kt`): decodes every frame of a clip with `MediaMetadataRetriever` (or `MediaCodec`) and runs the same analysis, so clips can be evaluated without the camera.
- **Device probe** (`Probe.kt`): supported stream combinations and camera characteristics.

## Build and run

```sh
cd research/experiments/capture/android-demo
echo "sdk.dir=$ANDROID_HOME" > local.properties     # not tracked
./gradlew --no-daemon assembleDebug testDebugUnitTest
adb -s $SERIAL install -r app/build/outputs/apk/debug/app-debug.apk
adb -s $SERIAL shell pm grant com.mylittlechef.researchdemo android.permission.CAMERA
adb -s $SERIAL shell input keyevent KEYCODE_WAKEUP
```

Launch modes (extras of `MainActivity`); `adb logcat -d -s MLCDemo` shows `RUN_DONE`, `PROBE_DONE`, `BENCH_DONE`, `VIDEO_ALL_DONE` or `CAMBENCH_DONE` when a mode finishes:

```sh
A="adb -s $SERIAL shell am start -n com.mylittlechef.researchdemo/.MainActivity"
$A --ez autorun true --ei seconds 5 --ei delay 3 --es res 1280x720   # record 5 s after a 3 s countdown
$A --ez autorun true --es arm uniform --ei cap 12                    # save the frames of one strategy (8..15)
$A --ez autorun true --es live with_offline                          # also run the streaming selector
$A --ez probe true                                                   # stream combinations, camera characteristics
$A --ez bench true                                                   # synthetic sweep: OpenCV path check and timing
$A --ez camera true                                                  # live camera stream measurements
D=/sdcard/Android/data/com.mylittlechef.researchdemo/files/in
adb -s $SERIAL shell mkdir -p $D; adb -s $SERIAL push clip.mp4 $D/
$A --es video all --ei cap 8                                         # every clip in files/in
adb -s $SERIAL shell rm -f $D/*.mp4                                  # remove pushed clips afterwards
```

Outputs are app-private under `/sdcard/Android/data/com.mylittlechef.researchdemo/files/` (`runs/`, `video-runs/`, `probe.json`, `bench.json`, `camera-bench.json`); pull them with `adb pull` into an ignored directory. Analysis sizes: 640x480, 960x720, 1440x1080, 1280x720, 1920x1080.

## Limits

- Camera stream timing, throughput, memory and thermal numbers are valid for any scene. Compressed sizes, sharpness and keypoint counts are not representative when the camera sees a black or featureless scene; those fields are marked `content_dependent` and must not be read as results.
- `single` is a stand-in for a still photo; the demo does not capture photos.
- Video-file mode decodes through bitmaps, so luma differs slightly from the original decoder output; selections can differ from a host decode.
- The output files contain no images except the saved JPEGs of one chosen strategy. Do not commit recordings, JPEGs or run outputs.
