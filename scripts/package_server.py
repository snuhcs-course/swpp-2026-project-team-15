"""Build a runtime-only server archive from the exact committed Git source.

No working-tree secrets, data, tests or evaluation tools are read into the archive.
"""

import argparse
import gzip
import hashlib
import io
import json
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIRECTORIES = (
    "server/app/",
    "server/recipe_filtering/",
    "server/recipe_revision/",
    "server/fixtures/vision/",
)
RUNTIME_FILES = {
    "server/pyproject.toml",
    "server/uv.lock",
    "server/.env.example",
    "server/README.md",
}


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def add(archive: tarfile.TarFile, name: str, data: bytes) -> None:
    entry = tarfile.TarInfo(name)
    entry.size, entry.mode, entry.mtime = len(data), 0o644, 0
    archive.addfile(entry, io.BytesIO(data))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist/server.tar.gz")
    args = parser.parse_args()
    commit = git("rev-parse", "HEAD").decode().strip()
    files = git("ls-tree", "-r", "--name-only", "HEAD").decode().splitlines()
    selected = sorted(
        name for name in files if name in RUNTIME_FILES or name.startswith(RUNTIME_DIRECTORIES)
    )
    if not RUNTIME_FILES <= set(selected):
        raise SystemExit("Committed runtime configuration is incomplete")
    contents = {name: git("show", f"HEAD:{name}") for name in selected}
    manifest = {
        "source_commit": commit,
        "files": {name: hashlib.sha256(data).hexdigest() for name, data in contents.items()},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with (
        args.output.open("wb") as handle,
        gzip.GzipFile(fileobj=handle, mode="wb", filename="", mtime=0) as compressed,
        tarfile.open(fileobj=compressed, mode="w") as archive,
    ):
        for name, data in contents.items():
            add(archive, name, data)
        add(archive, "manifest.json", (json.dumps(manifest, indent=2) + "\n").encode())
    print(f"Created {args.output} from {commit}: {len(selected)} runtime files")


if __name__ == "__main__":
    main()
