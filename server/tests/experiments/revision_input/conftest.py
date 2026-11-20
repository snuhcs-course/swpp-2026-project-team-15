# AI-generated with Claude Code (Sonnet 5.5), 2026-11-03; reviewed by Jaehyuk Choi.
"""These tests exercise the revision pipeline steps; skip them where that code is not present."""

import importlib.util


def _present(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except ModuleNotFoundError:
        return False


collect_ignore_glob = [] if _present("recipe_revision.pipeline") else ["test_*.py"]
