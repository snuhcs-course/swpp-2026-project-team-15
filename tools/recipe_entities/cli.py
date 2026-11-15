# AI-generated with Codex, 2026-11-16; reviewed by Soohyun An
"""Offline recipe entity preparation commands."""

import argparse
import json
import sys
from pathlib import Path

from .build import build_entities
from .review import create_review, read_review


def main() -> int:
    """Review roles or build a verified local bundle from explicitly supplied inputs."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("review", "check-review", "build"):
        command = commands.add_parser(name)
        command.add_argument("--normalized-recipes", required=True, type=Path)
        command.add_argument("--ingredient-catalog", required=True, type=Path)
        if name != "review":
            command.add_argument("--review-dir", required=True, type=Path)
        if name != "check-review":
            command.add_argument("--output", required=True, type=Path)
        if name == "build":
            command.add_argument("--existing-csv", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.command == "review":
            create_review(args.normalized_recipes, args.ingredient_catalog, args.output)
            print(f"Created unclassified review: {args.output}")
        elif args.command == "check-review":
            rows = read_review(args.normalized_recipes, args.ingredient_catalog, args.review_dir)
            print(f"Validated {len(rows)} reviewed occurrences")
        else:
            build_entities(
                args.normalized_recipes,
                args.ingredient_catalog,
                args.review_dir,
                args.existing_csv,
                args.output,
            )
            print(f"Build completed and locally verified: {args.output}")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"Preparation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
