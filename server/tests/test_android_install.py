"""Run the installer with fake platform tools; never touch a real device."""

import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def installer(tmp_path):
    root = tmp_path / "fresh checkout"
    (root / "scripts").mkdir(parents=True)
    (root / "android").mkdir()
    source = Path(__file__).resolve().parents[2] / "scripts/install-android.sh"
    shutil.copyfile(source, root / "scripts/install-android.sh")
    log = tmp_path / "calls.jsonl"
    stub = tmp_path / "tool.py"
    stub.write_text(
        "import json, os, pathlib, sys\n"
        "tool, *args = sys.argv[1:]\n"
        "with open(os.environ['INSTALL_LOG'], 'a') as f:\n"
        "    f.write(json.dumps([tool, *args]) + '\\n')\n"
        "if tool == 'adb' and args == ['devices']:\n"
        "    print('List of devices attached\\n' + os.environ['INSTALL_DEVICES'])\n"
        "if tool == 'gradle':\n"
        "    if os.environ.get('INSTALL_BUILD_FAIL') == '1': sys.exit(1)\n"
        "    apk = pathlib.Path('app/build/outputs/apk/cloudTest/app-cloudTest.apk')\n"
        "    apk.parent.mkdir(parents=True, exist_ok=True)\n"
        "    apk.write_bytes(b'fake APK')\n"
    )
    tools = tmp_path / "bin"
    tools.mkdir()
    for name, target in (
        ("java", tools / "java"),
        ("adb", tools / "adb"),
        ("gradle", root / "android/gradlew"),
    ):
        target.write_text(
            f'#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(stub))} {name} "$@"\n'
        )
        target.chmod(0o755)
    env = {k: v for k, v in os.environ.items() if not k.startswith("ANDROID_")}
    env.update(
        PATH=f"{tools}:{env['PATH']}",
        INSTALL_LOG=str(log),
        INSTALL_DEVICES="phone-one device",
    )

    def run(*args, **overrides):
        result = subprocess.run(
            ["sh", str(root / "scripts/install-android.sh"), *args],
            env={**env, **overrides},
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
        return result, calls

    return run


def test_installs_default_cloud_variant_only(installer):
    result, calls = installer()
    assert result.returncode == 0, result.stderr
    assert [c for c in calls if c[0] == "gradle"] == [["gradle", "--quiet", "assembleCloudTest"]]
    installs = [c for c in calls if "install" in c]
    assert len(installs) == 1
    assert installs[0][:5] == ["adb", "-s", "phone-one", "install", "-r"]
    assert installs[0][-1].endswith("/cloudTest/app-cloudTest.apk")
    assert not any("reverse" in c or "shell" in c for c in calls)


def test_selects_one_device_and_passes_url_as_one_argument(installer):
    result, calls = installer(
        "http://127.0.0.1:8000/",
        INSTALL_DEVICES="phone-one device\nphone-two device",
        ANDROID_SERIAL="phone-two",
    )
    assert result.returncode == 0, result.stderr
    assert [
        "gradle",
        "--quiet",
        "assembleCloudTest",
        "-PserverBaseUrl=http://127.0.0.1:8000/",
    ] in calls
    assert next(c for c in calls if "install" in c)[2] == "phone-two"


@pytest.mark.parametrize(
    "devices,serial",
    [
        ("phone-one device\nphone-two device", ""),
        ("phone-one unauthorized", ""),
        ("phone-one device", "missing"),
    ],
)
def test_ambiguous_or_unavailable_device_stops_before_build(installer, devices, serial):
    result, calls = installer(INSTALL_DEVICES=devices, ANDROID_SERIAL=serial)
    assert result.returncode != 0
    assert not any(c[0] == "gradle" or "install" in c for c in calls)


def test_build_failure_never_installs_old_apk(installer):
    result, calls = installer(INSTALL_BUILD_FAIL="1")
    assert result.returncode != 0
    assert not any("install" in c for c in calls)
