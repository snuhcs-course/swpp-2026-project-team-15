"""US03/04: a fresh checkout imports the supplied bundle into the documented DB.

Only platform tools are stubbed; the shell launcher and original CSV importer run.
"""

import os
import shutil
import sqlite3
import subprocess
import sys
import zipfile
from contextlib import closing
from pathlib import Path

pytest_plugins = ("tests.test_recipe_import",)


def test_fresh_demo_imports_separate_catalog_and_keeps_existing_database(recipe_csvs, tmp_path):
    source = Path(__file__).resolve().parents[2]
    root = tmp_path / "fresh demo"
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
    legacy = root / "data/recipes/recipes.sqlite3"
    legacy.parent.mkdir(parents=True)
    legacy.write_bytes(b"existing legacy database must survive")
    android = root / "android/MyLittleChef"
    android.mkdir(parents=True)
    (android / "gradlew").write_text("#!/bin/sh\nexit 0\n")
    sdk = tmp_path / "sdk/platform-tools"
    sdk.mkdir(parents=True)
    adb = sdk / "adb"
    adb.write_text(
        '#!/bin/sh\nif [ "$1" = devices ]; then '
        'printf "List of devices attached\\nfixture device\\n"; fi\n'
    )
    adb.chmod(0o755)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for command in ("java", "uv"):
        path = bin_dir / command
        path.write_text(
            f"#!{sys.executable}\nimport subprocess, sys\n"
            "args = sys.argv[1:]\n"
            "if args[:2] == ['run', 'python']:\n"
            "    raise SystemExit(subprocess.call([sys.executable, *args[2:]]))\n"
        )
        path.chmod(0o755)
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("VISION_", "REVISION_", "GEMINI_", "ANDROID_"))
    }
    env.update(PATH=f"{bin_dir}:{env['PATH']}", ANDROID_HOME=str(sdk.parent))
    result = subprocess.run(
        ["sh", str(root / "scripts/run-local-demo.sh"), str(bundle)],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    database = root / "data/recipes-iter2/recipes.sqlite3"
    with closing(sqlite3.connect(database)) as connection:
        assert connection.execute(
            "SELECT name FROM ingredient WHERE ingredient_id=204"
        ).fetchone() == ("물",)
        assert connection.execute("SELECT COUNT(*) FROM recipe").fetchone() == (1,)
    assert legacy.read_bytes() == b"existing legacy database must survive"
    before = database.read_bytes()
    subprocess.run(
        ["sh", str(root / "scripts/run-local-demo.sh")],
        env=env,
        check=True,
        capture_output=True,
        timeout=30,
    )
    assert database.read_bytes() == before
    config = (root / "server/.env").read_text()
    assert "VISION_PROVIDER=mock" in config and "REVISION_PROVIDER=mock" in config
    assert "GEMINI_API_KEY=\n" in config and "REVISION_LLM_API_KEY=" in config
