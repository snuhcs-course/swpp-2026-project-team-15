# AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""Keeping the complete items of a JSON list answer that a model cut off.

Shared by the dish answers (a list cut at the token limit) and the photo recognition (a model that
loops on label text until the limit, research/experiments/recheck_leftovers, item 2)."""

import json
import re

_LIST_START = re.compile(r'\s*\{\s*"(\w+)"\s*:\s*\[')


def salvage_list(text: str) -> dict | None:
    """The complete items of a cut-off ``{"key": [ {...}, {...`` answer, or None if there are none.

    A cut only loses the dishes after the last complete one; the server orders what is kept."""
    start = _LIST_START.match(text)
    if not start:
        return None
    decoder, pos, items = json.JSONDecoder(), start.end(), []
    while True:
        while pos < len(text) and text[pos] in " \n\r\t,":
            pos += 1
        try:
            item, pos = decoder.raw_decode(text, pos)
        except ValueError:
            break
        items.append(item)
    return {start.group(1): items} if items else None
