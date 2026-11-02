"""Load the assumed-seasoning policy from a small config file.

The built-in file ``assumed_seasonings.json`` holds the default list. For development, either edit
it or override per run, without touching code:

- ``RECIPE_ASSUMED_SEASONINGS_FILE``: path to another JSON file with the same shape.
- ``RECIPE_SEASONING_MODE``: ``list`` / ``all`` / ``none``, overriding the file's mode.

``validate_against_catalog`` checks the ids and names against the ingredient table (done at
application start, so a bad list fails immediately with a clear message).
"""

import json
import os
from collections.abc import Mapping
from pathlib import Path

from recipe_revision.seasoning import SeasoningConfigError, SeasoningPolicy

DEFAULT_FILE = Path(__file__).with_name("assumed_seasonings.json")
FILE_ENV = "RECIPE_ASSUMED_SEASONINGS_FILE"
MODE_ENV = "RECIPE_SEASONING_MODE"


def load_seasoning_policy(
    env: Mapping[str, str] | None = None, *, path: Path | str | None = None
) -> SeasoningPolicy:
    """Read the policy from ``path``, else the env override, else the built-in file."""
    env = os.environ if env is None else env
    file = Path(path or env.get(FILE_ENV) or DEFAULT_FILE)
    try:
        config = json.loads(file.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SeasoningConfigError(f"cannot read seasoning config {file}: {exc.strerror}") from exc
    except json.JSONDecodeError as exc:
        raise SeasoningConfigError(f"seasoning config {file} is not valid JSON: {exc}") from exc
    try:
        return SeasoningPolicy.from_config(config, mode=env.get(MODE_ENV) or None)
    except SeasoningConfigError as exc:
        raise SeasoningConfigError(f"{file}: {exc}") from exc


def validate_against_catalog(policy: SeasoningPolicy, catalog: Mapping[int, str]) -> None:
    policy.check_catalog(catalog)
