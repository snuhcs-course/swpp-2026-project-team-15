# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""Prompts, answer parsing and the embeddable check of the pipeline study (no network here)."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable

import httpx

VIDEO_ID = re.compile(r"(?:v=|youtu\.be/|embed/)?([A-Za-z0-9_-]{11})(?![A-Za-z0-9_-])")
WEB_MODEL = "google/gemini-2.5-flash-lite:online"

DISCOVERY_SYSTEM = (
    "You find YouTube cooking videos with web search. For each dish, give the YouTube video ids of "
    "the videos that best show how to cook it, most suitable first. Use only videos you found in "
    "the search results; never guess an id. Answer with JSON only."
)
SELECT_AND_LINK_SYSTEM = (
    "You help a Korean student living alone decide what to cook from the ingredients they have. "
    "Return every dish from the given dish list that can reasonably be cooked with the owned "
    "ingredients, best first, using the names exactly. For each dish give 'have' (main ingredients "
    "the user owns), 'missing' (main ingredients the user lacks; basic seasonings are not listed) "
    "and YouTube video ids of videos that show how to cook it, found with web search, never "
    "guessed. If no dish fits, return an empty list. Answer with JSON only."
)
JUDGE_SYSTEM = (
    "For each video, decide from its title, channel and description whether it is a cooking video "
    "that shows how to make the named dish. Answer with JSON only."
)


def links_instruction(links: int, with_titles: bool) -> str:
    shape = '{"id": "...", "title": "..."}' if with_titles else '"<video id>"'
    return f"Give up to {links} videos per dish, each as {shape}."


def discovery_user(dishes: list[str], links: int, with_titles: bool) -> str:
    key = "videos" if with_titles else "video_ids"
    return (
        f"{links_instruction(links, with_titles)}\n"
        f'Answer {{"dishes": [{{"name": "<dish>", "{key}": [...]}}]}}.\n'
        f"dishes: {json.dumps(dishes, ensure_ascii=False)}"
    )


def select_and_link_user(ingredients: list[str], names: list[str], links: int, titles: bool) -> str:
    key = "videos" if titles else "video_ids"
    return (
        f"{links_instruction(links, titles)}\n"
        f'Answer {{"dishes": [{{"name": "", "have": [], "missing": [], "{key}": []}}]}}.\n'
        f"owned: {json.dumps(ingredients, ensure_ascii=False)}\n"
        f"dishes: {json.dumps(names, ensure_ascii=False)}"
    )


def extract_json(text: str) -> dict | None:
    """The first JSON object in a model answer (it may be wrapped in a code fence)."""
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def clean_ids(values: object) -> list[str]:
    """Video ids from a list of ids, urls or {id, title} items, in order, without repeats."""
    out: list[str] = []
    for item in values if isinstance(values, list) else []:
        raw = item.get("id") if isinstance(item, dict) else item
        match = VIDEO_ID.search(raw) if isinstance(raw, str) else None
        if match and match.group(1) not in out:
            out.append(match.group(1))
    return out


def parse_dishes(data: dict | None) -> dict[str, dict]:
    """name -> {ids, have, missing} from a discovery or select-and-link answer (first name wins)."""
    out: dict[str, dict] = {}
    items = data.get("dishes") if data else None
    for item in items if isinstance(items, list) else []:
        name = item.get("name") if isinstance(item, dict) else None
        if not isinstance(name, str) or name.strip() in out:
            continue
        ids = clean_ids(item.get("video_ids") if "video_ids" in item else item.get("videos"))
        out[name.strip()] = {"ids": ids, "have": item.get("have"), "missing": item.get("missing")}
    return out


Fetcher = Callable[[list[str]], list[dict]]


def youtube_fetcher(key: str, timeout: float = 30.0) -> Fetcher:
    """One videos.list call (1 quota unit) for up to 50 ids; never search.list."""

    def fetch(ids: list[str]) -> list[dict]:
        response = httpx.get(
            "https://www.googleapis.com/youtube/v3/videos",
            params={"part": "snippet,status", "id": ",".join(ids), "key": key},
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json().get("items", [])

    return fetch


def check_ids(ids: Iterable[str], fetch: Fetcher) -> tuple[dict[str, dict], int]:
    """(id -> info for ids that exist, are public and embeddable, number of videos.list calls)."""
    unique = list(dict.fromkeys(ids))
    kept: dict[str, dict] = {}
    existing: set[str] = set()
    calls = 0
    for start in range(0, len(unique), 50):
        calls += 1
        for item in fetch(unique[start : start + 50]):
            existing.add(item.get("id", ""))
            status, snippet = item.get("status", {}), item.get("snippet", {})
            if status.get("embeddable") and status.get("privacyStatus") == "public":
                kept[item["id"]] = {
                    "title": snippet.get("title", ""),
                    "channel": snippet.get("channelTitle", ""),
                    "description": snippet.get("description", "")[:200],
                }
    kept["__existing__"] = {"count": len(existing & set(unique))}
    return kept, calls


def apply_rule_check(ids_by_dish: dict[str, list[str]], fetch: Fetcher) -> dict:
    """Keep the model's order; drop ids that do not exist or are not embeddable and public."""
    all_ids = [i for ids in ids_by_dish.values() for i in ids]
    info, calls = check_ids(all_ids, fetch) if all_ids else ({"__existing__": {"count": 0}}, 0)
    existing = info.pop("__existing__")["count"]
    kept = {d: [i for i in ids if i in info] for d, ids in ids_by_dish.items()}
    return {
        "kept": kept,
        "info": info,
        "returned_ids": len(set(all_ids)),
        "existing_ids": existing,
        "list_calls": calls,
    }


def judge_user(items: list[dict]) -> str:
    return json.dumps(items, ensure_ascii=False)


JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "judgements": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"video_id": {"type": "string"}, "relevant": {"type": "boolean"}},
                "required": ["video_id", "relevant"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["judgements"],
    "additionalProperties": False,
}
