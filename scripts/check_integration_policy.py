"""Verify preserved human specification references and original contributor tests.

CI is a detectable integrity check, not a substitute for human review or branch
protection. The agent must not edit docs/acceptance or its approved references.
"""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    for manifest in ("docs/acceptance/manifest.json", "docs/iterations/iteration-2/test-baseline.json"):
        path = ROOT / manifest
        files = json.loads(path.read_text())
        base = path.parent if "acceptance" in manifest else ROOT
        for name, expected in files.items():
            source = base / name
            if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != expected:
                raise SystemExit(f"Protected reference/test changed: {name}; human review required")
    print("Preserved specification references and original contributor tests verified")


if __name__ == "__main__":
    main()
