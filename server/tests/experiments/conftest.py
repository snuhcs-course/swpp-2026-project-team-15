# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""Research tests that target the previous version (recipe database) skip where its code is gone."""

import importlib.util


def _present(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except ModuleNotFoundError:
        return False


collect_ignore = []
if not _present("recipe_filtering"):
    collect_ignore.append("filtering")
if not _present("recipe_revision"):
    collect_ignore.append("revision")
if not _present("app.recipes"):
    collect_ignore.append("name_mapping")
