# AI-assisted with Codex, 2026-11-11; reviewed by Soohyun An
"""Atomic run-local artifacts, immutable raw bytes, and explicit integrity failures."""

import hashlib
import json
import os
import tempfile
from pathlib import Path


class IntegrityError(ValueError):
    """Saved bytes or artifact paths disagree with recorded provenance."""


def plain(value):
    """Convert immutable plan mappings and tuples into independent JSON data."""
    return json.loads(json.dumps(value, default=dict))


def digest(body):
    return hashlib.sha256(body).hexdigest()


class RunStorage:
    """Resolve every write inside one validated run root; publish via os.replace."""

    def __init__(self, root):
        self.root = Path(root).resolve()

    def path(self, relative):
        """Reject absolute/traversing paths, including symlink escapes."""
        relative = Path(relative)
        path = (self.root / relative).resolve()
        if relative.is_absolute() or not path.is_relative_to(self.root) or path == self.root:
            raise IntegrityError("Artifact path escapes run directory")
        return path

    def write(self, relative, body, *, immutable=False):
        """Publish complete bytes, retaining the previous destination on failure."""
        path = self.path(relative)
        if immutable and path.exists():
            if path.read_bytes() != body:
                raise IntegrityError(f"Refusing to overwrite source artifact: {relative}")
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=path.parent, prefix=".pending-", delete=False
            ) as f:
                temporary = Path(f.name)
                f.write(body)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def write_json(self, relative, value, *, immutable=False):
        self.write(
            relative,
            json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8"),
            immutable=immutable,
        )

    def read_json(self, relative):
        return json.loads(self.path(relative).read_text(encoding="utf-8"))

    def verify(self, entry):
        """Read raw/derived bytes only after verifying their recorded SHA-256."""
        path = self.path(entry["path"])
        if not path.is_file() or digest(path.read_bytes()) != entry["sha256"]:
            raise IntegrityError(f"Missing or corrupt artifact: {entry['path']}")
        return path.read_bytes()
