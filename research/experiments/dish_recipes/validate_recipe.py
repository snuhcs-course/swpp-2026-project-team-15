# AI-generated with Claude Code (Sonnet 5.5), 2026-11-18; reviewed by Jaehyuk Choi.
"""Check a structured recipe against schema.json and the grounding rules.

    python -m experiments.dish_recipes.validate_recipe RECIPE.json [--input INPUT.json]

Rules beyond the schema: steps are numbered 1..n, no step is longer than 300 characters, the text
is Korean, and every ingredient name appears in the captions (spaces ignored, synonyms accepted)
unless it is listed under `uncertain`. The captions come from `--input` (an inputs/<dish>.json
file) or, by default, from data/dish-recipes/inputs/<dish_id>.json. Exit code 0 means valid.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from app.dishes.synonyms import with_synonyms

from .common import INPUTS_DIR

SCHEMA = json.loads(Path(__file__).with_name("schema.json").read_text(encoding="utf-8"))
HANGUL = re.compile("[가-힣]")


def squash(text: str) -> str:
    return re.sub(r"\s+", "", text)


def transcript_text(record: dict) -> str:
    return squash(" ".join(s["text"] for s in record["transcript"]))


def check_schema(value, schema, path="recipe") -> list[str]:
    """Minimal checker for the subset of JSON Schema that schema.json uses."""
    problems: list[str] = []
    if "const" in schema and value != schema["const"]:
        return [f"{path}: must be {schema['const']!r}"]
    if "enum" in schema and value not in schema["enum"]:
        return [f"{path}: must be one of {schema['enum']}"]
    kinds = schema.get("type")
    if kinds:
        names = kinds if isinstance(kinds, list) else [kinds]
        python = {
            "object": dict,
            "array": list,
            "string": str,
            "integer": int,
            "boolean": bool,
            "null": type(None),
        }
        ok = any(
            isinstance(value, python[n]) and not (n == "integer" and isinstance(value, bool))
            for n in names
        )
        if not ok:
            return [f"{path}: expected {'/'.join(names)}"]
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                problems.append(f"{path}: missing {key}")
        if schema.get("additionalProperties") is False:
            problems += [f"{path}: unexpected {k}" for k in value if k not in schema["properties"]]
        for key, sub in schema.get("properties", {}).items():
            if key in value:
                problems += check_schema(value[key], sub, f"{path}.{key}")
    elif isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            problems.append(f"{path}: needs at least {schema['minItems']} items")
        for i, item in enumerate(value):
            problems += check_schema(item, schema.get("items", {}), f"{path}[{i}]")
    elif isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            problems.append(f"{path}: too short")
        if len(value) > schema.get("maxLength", 10**9):
            problems.append(f"{path}: longer than {schema['maxLength']} characters")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            problems.append(f"{path}: does not match {schema['pattern']}")
    elif isinstance(value, int) and "minimum" in schema and value < schema["minimum"]:
        problems.append(f"{path}: below {schema['minimum']}")
    return problems


def check_recipe(recipe: dict, record: dict | None) -> list[str]:
    problems = check_schema(recipe, SCHEMA)
    if problems:
        return problems
    numbers = [s["n"] for s in recipe["steps"]]
    if numbers != list(range(1, len(numbers) + 1)):
        problems.append("steps must be numbered 1..n in order")
    body = " ".join(s["text"] for s in recipe["steps"])
    if len(HANGUL.findall(body)) < 0.5 * max(1, len(re.sub(r"\s", "", body))):
        problems.append("steps are not mostly Korean")
    if record is None:
        problems.append("captions not found: cannot check the ingredients")
        return problems
    if record["video"]["id"] != recipe["video"]["id"]:
        problems.append("video id differs from the captions' video")
    spoken = transcript_text(record)
    uncertain = {squash(u) for u in recipe["uncertain"]}
    for row in recipe["ingredients"]:
        forms = {squash(n) for n in with_synonyms([row["name"]])}
        if not any(f in spoken for f in forms) and not any(
            f in u or u in f for f in forms for u in uncertain
        ):
            problems.append(
                f"ingredient not in the captions and not marked uncertain: {row['name']}"
            )
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("recipe", type=Path)
    parser.add_argument("--input", type=Path, default=None)
    args = parser.parse_args(argv)
    recipe = json.loads(args.recipe.read_text(encoding="utf-8"))
    path = args.input or INPUTS_DIR / f"{recipe.get('dish_id', '')}.json"
    record = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    problems = check_recipe(recipe, record)
    for problem in problems:
        print(problem, file=sys.stderr)
    print("valid" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
