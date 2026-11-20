# AI-generated with Claude Code (Sonnet 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""Round 2 of the answer-format study: per-request enums and mapping of unmatched ingredients.

Pure builders and scorers (no network). R0 is the S2 format of round 1; R1 narrows the `missing`
enum per request; R2 adds a model-written `mapping` for user items that match no vocabulary name
and a deterministic removal step. See ``criteria_round2.json``.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.dishes.synonyms import SYNONYM_GROUPS

from . import formats

HERE = Path(__file__).resolve().parent
NONE = "none"
VARIANTS = ("R0", "R1", "R2")


def criteria() -> dict:
    return json.loads((HERE / "criteria_round2.json").read_text(encoding="utf-8"))


def mapping_set() -> list[dict]:
    return json.loads((HERE / "mapping_set.json").read_text(encoding="utf-8"))["lists"]


def norm(text: str) -> str:
    return text.strip().replace(" ", "")


def vocab_match(item: str, vocab: list[str]) -> str | None:
    """The vocabulary name an item equals by spelling or synonym group, else None."""
    name = norm(item)
    forms = {name}
    for group in SYNONYM_GROUPS:
        if name in group:
            forms |= group
    return next((v for v in vocab if v in forms), None)


def matched_vocab(ingredients: list[str], vocab: list[str]) -> set[str]:
    found = (vocab_match(i, vocab) for i in formats.owned_enum(ingredients))
    return {m for m in found if m}


def unmatched_items(ingredients: list[str], vocab: list[str]) -> list[str]:
    out: list[str] = []
    for item in formats.owned_enum(ingredients):
        if vocab_match(item, vocab) is None and norm(item) not in {norm(o) for o in out}:
            out.append(item)
    return out


def x_names(unmatched: list[str]) -> dict[str, str]:
    return {f"X{i}": item for i, item in enumerate(unmatched, start=1)}


def missing_enum(ingredients: list[str], vocab: list[str]) -> list[str]:
    owned = matched_vocab(ingredients, vocab)
    return [v for v in vocab if v not in owned]


def system_prompt(variant: str, unmatched: list[str]) -> str:
    prompts = criteria()["prompts"]
    return prompts["R2"] if variant == "R2" and unmatched else prompts["R0_R1"]


def user_message(variant: str, ingredients: list[str], names: list[str], unmatched: list[str]):
    if variant == "R2" and unmatched:
        body = {"owned": ingredients, "unmatched": x_names(unmatched), "dishes": names}
        return json.dumps(body, ensure_ascii=False)
    return json.dumps({"owned": ingredients, "dishes": names}, ensure_ascii=False)


def answer_schema(
    variant: str, names: list[str], ingredients: list[str], vocab: list[str], unmatched: list[str]
) -> dict:
    owned = formats.owned_enum(ingredients)
    if variant == "R0":
        return formats.schema_for("S2", names, owned, vocab)
    schema = formats.schema_for("S2", names, owned, missing_enum(ingredients, vocab))
    if variant == "R2" and unmatched:
        mapping = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "item": formats._enum(list(x_names(unmatched))),
                    "same_as": formats._enum([*vocab, NONE]),
                },
                "required": ["item", "same_as"],
                "additionalProperties": False,
            },
        }
        schema = {
            "type": "object",
            "properties": {"mapping": mapping, "dishes": schema["properties"]["dishes"]},
            "required": ["mapping", "dishes"],
            "additionalProperties": False,
        }
    return schema


def payload(variant: str, ingredients: list[str], names: list[str], vocab: list[str]) -> dict:
    unmatched = unmatched_items(ingredients, vocab)
    return {
        "model": formats.MODEL,
        "messages": [
            {"role": "system", "content": system_prompt(variant, unmatched)},
            {"role": "user", "content": user_message(variant, ingredients, names, unmatched)},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "dish_choice",
                "strict": True,
                "schema": answer_schema(variant, names, ingredients, vocab, unmatched),
            },
        },
        "provider": {"require_parameters": True},
        "max_tokens": formats.MAX_TOKENS,
        "temperature": 0,
    }


def read_mapping(data: dict | None, unmatched: list[str], vocab: list[str]) -> dict[str, str]:
    """item (the user's wording) -> same_as, from the model's `mapping`; invalid entries dropped."""
    names = x_names(unmatched)
    out: dict[str, str] = {}
    entries = (data or {}).get("mapping")
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        item, same = entry.get("item"), entry.get("same_as")
        if item in names and (same == NONE or same in vocab):
            out.setdefault(names[item], same)
    return out


def remove_mapped(data: dict | None, mapping: dict[str, str]) -> tuple[dict | None, int, list]:
    """Drop from every dish's `missing` the vocabulary names the model's mapping says are owned."""
    owned = {same for same in mapping.values() if same != NONE}
    items = (data or {}).get("dishes")
    if not owned or not isinstance(items, list):
        return data, 0, []
    removed: list[tuple[str, str]] = []
    dishes = []
    for item in items:
        if isinstance(item, dict) and isinstance(item.get("missing"), list):
            keep = [m for m in item["missing"] if m not in owned]
            removed += [(str(item.get("name")), m) for m in item["missing"] if m in owned]
            item = {**item, "missing": keep}
        dishes.append(item)
    return {**data, "dishes": dishes}, len(removed), removed


def count_violations(
    data: dict | None,
    ingredients: list[str],
    names: list[str],
    vocab: list[str],
    request_enum: list[str],
    unmatched: list[str],
) -> dict[str, int]:
    base = formats.count_violations("S2", data, ingredients, names, vocab)
    out = {
        k: base[k]
        for k in ("names_outside_list", "have_outside_owned", "missing_outside", "repeated")
    }
    allowed = set(request_enum)
    out["missing_outside_request_enum"] = 0
    out["mapping_outside_enum"] = 0
    for item in formats.service_data("S2", data)["dishes"]:
        miss = item["missing"] if isinstance(item["missing"], list) else []
        out["missing_outside_request_enum"] += sum(1 for m in miss if m not in allowed)
    entries = (data or {}).get("mapping")
    if unmatched and isinstance(entries, list):
        keys, targets = set(x_names(unmatched)), {*vocab, NONE}
        for entry in entries:
            ok = isinstance(entry, dict) and entry.get("item") in keys
            out["mapping_outside_enum"] += (not ok) or entry.get("same_as") not in targets
    return out


def expected_owned_vocab(case: dict, vocab: list[str]) -> set[str]:
    """Vocabulary names the user owns according to the labels (ambiguous items excluded)."""
    owned = matched_vocab(case["ingredients"], vocab)
    ambiguous = set(case.get("ambiguous", []))
    owned |= {v for k, v in case["expected"].items() if v != NONE and k not in ambiguous}
    return owned


def owned_listed_as_missing(dishes: list[dict], truly_owned: set[str]) -> int:
    return sum(1 for d in dishes if truly_owned & set(d["missing"]))


def score_mapping(case: dict, mapping: dict[str, str]) -> dict[str, int]:
    """Counts for one list: accuracy, false/missed merges, wrong targets (ambiguous apart)."""
    out = dict.fromkeys(
        ("items", "correct", "false_merge", "missed_merge", "wrong_target", "ambiguous"), 0
    )
    ambiguous = set(case.get("ambiguous", []))
    for item, label in case["expected"].items():
        if item in ambiguous:
            out["ambiguous"] += 1
            continue
        said = mapping.get(item, NONE)
        out["items"] += 1
        if said == label:
            out["correct"] += 1
        elif label == NONE:
            out["false_merge"] += 1
        elif said == NONE:
            out["missed_merge"] += 1
        else:
            out["wrong_target"] += 1
    return out


def wrongly_hidden(removed: list, truly_owned: set[str]) -> int:
    return sum(1 for _, name in removed if name not in truly_owned)
