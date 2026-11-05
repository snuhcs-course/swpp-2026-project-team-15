# AI-generated with Claude Code (Sonnet 5.5), 2026-11-03; reviewed by Jaehyuk Choi.
"""These tests exercise the revision pipeline steps; skip them where that code is not present."""

import importlib.util

collect_ignore_glob = [] if importlib.util.find_spec("recipe_revision.pipeline") else ["test_*.py"]
