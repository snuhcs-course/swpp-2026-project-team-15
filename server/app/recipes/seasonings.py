# AI-generated with Claude Code (Sonnet 5.5), 2026-11-03; reviewed by Jaehyuk Choi.
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


WATER_ID = 204


def seasoning_labelled_ids(rows) -> set[int]:
    """Ids the recipes label as seasoning, resolved like the filtering policy (main > secondary >
    seasoning for conflicting rows).

    ``rows``: (id, name, type code, type text) as ``RecipeRepository.ingredient_labels`` returns.
    """
    from app.recipes.policy import TYPE_CODES  # imported late: policy imports this module
    from recipe_filtering.metrics import SEASONING, TYPE_PRIORITY

    labels: dict[int, set[str]] = {}
    for ingredient_id, _name, code, text in rows:
        labels.setdefault(ingredient_id, set()).add(TYPE_CODES.get(code, text or ""))
    resolved = {
        i: min(known, key=TYPE_PRIORITY.__getitem__)
        for i, found in labels.items()
        if (known := found & TYPE_PRIORITY.keys())
    }
    return {i for i, kind in resolved.items() if kind == SEASONING}


def resolve_staple_names(
    policy: SeasoningPolicy, catalog: Mapping[int, str], labelled_ids=frozenset()
) -> tuple[str, ...]:
    """Names of the seasonings assumed to be at home, for the name-based recommend path.

    One source of truth: the same policy object that drives candidate selection, the revision
    request and the post-check. Water is always first. ``list``: the declared ids in config order;
    ``all``: every seasoning-labelled ingredient (``labelled_ids``); ``none``: only water.
    Names come from the ingredient table (``validate_against_catalog`` makes sure the config
    agrees with it).
    """
    if policy.mode == "list":
        ordered = [i for i in policy.names if i in policy.assumed_ids]
        ordered += sorted(policy.assumed_ids - set(ordered))
    elif policy.mode == "all":
        ordered = sorted(labelled_ids, key=lambda i: catalog.get(i, ""))
    else:
        ordered = []
    ids = list(dict.fromkeys([WATER_ID, *ordered]))
    return tuple(catalog[i] for i in ids if i in catalog)
