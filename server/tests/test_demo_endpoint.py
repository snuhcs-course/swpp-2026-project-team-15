"""Exercise the local launcher's isolated app and USB endpoint contract."""

import json
import os
import shlex
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

pytest_plugins = ("tests.test_recipe_import",)


def test_local_demo_installs_isolated_app_and_routes_custom_host_port(recipe_csvs, tmp_path):
    source = Path(__file__).resolve().parents[2]
    root = tmp_path / "fresh checkout"
    for name in (
        "scripts/run-local-demo.sh",
        "server/db/import_recipes.py",
        "server/db/schema.sql",
        "server/.env.example",
        "server/fixtures/demo/mock-photo.png",
    ):
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, target)
    with (recipe_csvs / "Ingredient.csv").open("a", encoding="utf-8") as handle:
        handle.write("204,물\n")
    bundle = tmp_path / "private bundle.zip"
    with zipfile.ZipFile(bundle, "w") as archive:
        for path in recipe_csvs.iterdir():
            archive.write(path, path.name)

    calls = tmp_path / "calls.jsonl"
    stub = tmp_path / "fake_tool.py"
    stub.write_text(
        "import json, os, subprocess, sys\n"
        "tool, *args = sys.argv[1:]\n"
        "with open(os.environ['DEMO_CALLS'], 'a') as log:\n"
        "    log.write(json.dumps([tool, *args]) + '\\n')\n"
        "if tool == 'adb' and args == ['devices']:\n"
        "    print('List of devices attached\\nfixture device')\n"
        "if tool == 'uv' and args[:2] == ['run', 'python']:\n"
        "    raise SystemExit(subprocess.call([sys.executable, *args[2:]]))\n"
    )
    bin_dir = tmp_path / "bin"
    sdk = tmp_path / "sdk/platform-tools"
    android = root / "android"
    for directory in (bin_dir, sdk, android):
        directory.mkdir(parents=True)
    for tool, path in (
        ("uv", bin_dir / "uv"),
        ("java", bin_dir / "java"),
        ("adb", sdk / "adb"),
        ("gradle", android / "gradlew"),
    ):
        path.write_text(
            f'#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(stub))} {tool} "$@"\n'
        )
        path.chmod(0o755)
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("VISION_", "REVISION_", "GEMINI_", "ANDROID_"))
    }
    env.update(
        PATH=f"{bin_dir}:{env['PATH']}",
        ANDROID_HOME=str(sdk.parent),
        DEMO_CALLS=str(calls),
        PORT="8765",
    )
    result = subprocess.run(
        ["sh", str(root / "scripts/run-local-demo.sh"), str(bundle)],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    recorded = [json.loads(line) for line in calls.read_text().splitlines()]
    assert [call for call in recorded if call[0] == "gradle"] == [
        ["gradle", "--quiet", "installCloudTest", "-PserverBaseUrl=http://127.0.0.1:8000/"]
    ]
    assert [call for call in recorded if call[:4] == ["adb", "shell", "am", "start"]] == [
        [
            "adb",
            "shell",
            "am",
            "start",
            "-n",
            "com.example.mylittlechef.cloudtest/com.example.mylittlechef.MainActivity",
        ]
    ]
    assert ["adb", "reverse", "tcp:8000", "tcp:8765"] in recorded
    assert recorded[-1] == [
        "uv",
        "run",
        "--env-file",
        ".env",
        "uvicorn",
        "app.main:create_app_from_env",
        "--factory",
        "--host",
        "127.0.0.1",
        "--port",
        "8765",
    ]
