"""Verify preserved human specification references and original contributor tests.

CI is a detectable integrity check, not a substitute for human review or branch
protection. The agent must not edit server/tests/references or its approved references.
"""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Preserve original baseline names/hashes while checking their relocated files.
RELOCATIONS = {"android/MyLittleChef/": "android/", "experiments/": "server/tests/experiments/"}


def main() -> None:
    for manifest, relative_base in (
        ("server/tests/references/specification-manifest.json", "server/tests/references"),
        ("server/tests/references/contributor-tests.json", "."),
    ):
        path = ROOT / manifest
        files = json.loads(path.read_text())
        base = ROOT / relative_base
        for name, expected in files.items():
            current_name = name
            if relative_base == ".":
                for old, new in RELOCATIONS.items():
                    if name.startswith(old):
                        current_name = new + name.removeprefix(old)
                        break
            source = base / current_name
            if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != expected:
                raise SystemExit(f"Protected reference/test changed: {name}; human review required")
    print("Preserved specification references and original contributor tests verified")


if __name__ == "__main__":
    main()
