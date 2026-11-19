# AI-generated with Claude Code (Sonnet 5.5), 2026-11-18; reviewed by Jaehyuk Choi.
"""Answer formats of the dish suggestion call, constrained by enums, and what a call costs to write.

Pure builders (no network) plus the two client routes under test: the raw HTTP route
(``response_format_payload``, ``tools_payload``, ``post_chat``) and the LangChain route
(``langchain_structured``, ``invoke_langchain``; imported lazily, so the module loads without it).
"""

from __future__ import annotations

import ast
import inspect
import json
import textwrap
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
from experiments.dish_tokens.calls import ENDPOINT, PRICE_PER_MTOK, Call
from experiments.legacy_prompts import SUGGEST_SCHEMA, SUGGEST_SYSTEM

from app.dishes.catalog import Catalog
from app.dishes.prompts import suggest_user_message
from app.dishes.synonyms import SYNONYM_GROUPS

HERE = Path(__file__).resolve().parent
MODEL = "google/gemini-2.5-flash-lite"
MAX_TOKENS = 4096
FUNCTION_NAME = "choose_dishes"


def load_criteria() -> dict:
    return json.loads((HERE / "criteria.json").read_text(encoding="utf-8"))


def frozen_cases() -> list[dict]:
    naive = HERE.parent / "dish_naive" / "criteria.json"
    cases = json.loads(naive.read_text(encoding="utf-8"))["cases"]
    return [c for c in cases if c["expect_status"] == 200]


def prompts() -> dict[str, str]:
    given = load_criteria()["prompts"]
    return {"S0": SUGGEST_SYSTEM, **{k: given[k] for k in ("S1", "S2", "S3")}}


def dish_names(catalog: Catalog) -> list[str]:
    return [d.name for d in catalog.dishes.values()]


def ingredient_vocabulary(catalog: Catalog) -> list[str]:
    """Distinct key ingredients, one spelling per synonym group (the most frequent one)."""
    counts: dict[str, int] = {}
    for dish in catalog.dishes.values():
        for key in dish.key_ingredients:
            counts[key] = counts.get(key, 0) + 1
    canonical: dict[str, str] = {}
    for group in SYNONYM_GROUPS:
        members = [m for m in group if m in counts]
        if members:
            best = min(members, key=lambda m: (-counts[m], m))
            canonical.update({m: best for m in group})
    return sorted({canonical.get(k, k) for k in counts})


def owned_enum(ingredients: list[str]) -> list[str]:
    return list(dict.fromkeys(i.strip() for i in ingredients if i and i.strip()))


def _enum(values: list[str]) -> dict:
    return {"type": "string", "enum": values}


def schema_for(variant: str, names: list[str], owned: list[str], vocab: list[str]) -> dict:
    """Answer schema: S1 names only, S2 family name+have+missing, S3 name+missing."""
    if variant == "S0":
        return SUGGEST_SCHEMA
    if variant == "S1":
        dishes: dict = {"type": "array", "items": _enum(names)}
    else:
        props: dict = {"name": _enum(names), "missing": {"type": "array", "items": _enum(vocab)}}
        if variant != "S3":
            props["have"] = {"type": "array", "items": _enum(owned)}
        dishes = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": props,
                "required": sorted(props),
                "additionalProperties": False,
            },
        }
    return {
        "type": "object",
        "properties": {"dishes": dishes},
        "required": ["dishes"],
        "additionalProperties": False,
    }


def base_variant(variant: str) -> str:
    """The format family a variant uses for its schema and prompt."""
    return {"S4": "S2", "S5a": "S2", "S5b": "S2", "S2n": "S2", "S2r": "S2"}.get(variant, variant)


def messages_for(variant: str, ingredients: list[str], names: list[str]) -> list[dict]:
    return [
        {"role": "system", "content": prompts()[base_variant(variant)]},
        {"role": "user", "content": suggest_user_message(ingredients, names)},
    ]


def response_format_payload(
    variant: str, ingredients: list[str], names: list[str], vocab: list[str]
) -> dict:
    """Raw route: structured output as `response_format` json_schema."""
    schema = schema_for(base_variant(variant), names, owned_enum(ingredients), vocab)
    payload = {
        "model": MODEL,
        "messages": messages_for(variant, ingredients, names),
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "dish_choice", "strict": variant != "S2n", "schema": schema},
        },
        "max_tokens": MAX_TOKENS,
        "temperature": 0,
    }
    if variant != "S2r":
        payload["provider"] = {"require_parameters": True}
    return payload


def tools_payload(variant: str, ingredients: list[str], names: list[str], vocab: list[str]) -> dict:
    """Raw route S4: the same schema as the parameters of a forced function call."""
    schema = schema_for("S2", names, owned_enum(ingredients), vocab)
    function = {"name": FUNCTION_NAME, "description": "Answer the dishes.", "parameters": schema}
    function["strict"] = True
    return {
        "model": MODEL,
        "messages": messages_for(variant, ingredients, names),
        "tools": [{"type": "function", "function": function}],
        "tool_choice": {"type": "function", "function": {"name": FUNCTION_NAME}},
        "provider": {"require_parameters": True},
        "max_tokens": MAX_TOKENS,
        "temperature": 0,
    }


@dataclass
class Answer:
    call: Call
    provider: str | None = None
    raw: str = ""
    attempts: int = 1


def token_cost(prompt_tokens: int, completion_tokens: int) -> float:
    return (prompt_tokens * PRICE_PER_MTOK[0] + completion_tokens * PRICE_PER_MTOK[1]) / 1e6


def post_chat(payload: dict, key: str, timeout: float = 90.0) -> Answer:
    """One request; never raises. The answer is the message content or the forced tool call."""
    started = time.monotonic()
    try:
        r = httpx.post(
            ENDPOINT,
            json=payload,
            headers={"Authorization": f"Bearer {key}"},
            timeout=timeout,
            follow_redirects=False,
        )
        body = r.json()
    except (httpx.HTTPError, ValueError) as exc:
        return Answer(Call(False, latency_s=time.monotonic() - started, error=type(exc).__name__))
    call = Call(r.status_code == 200, r.status_code, time.monotonic() - started)
    if r.status_code != 200:
        call.error = str((body.get("error") or {}).get("message", "error"))[:120]
        return Answer(call)
    usage = body.get("usage") or {}
    call.prompt_tokens = int(usage.get("prompt_tokens") or 0)
    call.completion_tokens = int(usage.get("completion_tokens") or 0)
    call.cost_usd = float(usage["cost"]) if usage.get("cost") is not None else 0.0
    choice = (body.get("choices") or [{}])[0]
    call.finish_reason = choice.get("finish_reason")
    message = choice.get("message") or {}
    tool_calls = message.get("tool_calls") or []
    raw = (tool_calls[0].get("function") or {}).get("arguments") if tool_calls else None
    raw = raw if raw is not None else (message.get("content") or "")
    answer = Answer(call, body.get("provider"), raw)
    if call.finish_reason == "length":
        call.ok, call.error = False, "truncated"
        return answer
    try:
        parsed = json.loads(raw)
    except ValueError:
        call.ok, call.error = False, "answer is not JSON"
        return answer
    call.data = parsed if isinstance(parsed, dict) else None
    call.ok = call.data is not None
    call.error = None if call.ok else "answer is not an object"
    return answer


def langchain_structured(
    variant: str, names: list[str], ingredients: list[str], vocab: list[str], key: str
):
    """LangChain route: a pydantic model with Literal fields behind with_structured_output."""
    from langchain_openai import ChatOpenAI
    from pydantic import create_model

    owned = tuple(owned_enum(ingredients))
    dish = create_model(
        "Dish",
        name=(literal_of(names), ...),
        have=(list[literal_of(list(owned))], ...),
        missing=(list[literal_of(vocab)], ...),
    )
    answer = create_model("DishChoice", dishes=(list[dish], ...))
    chat = ChatOpenAI(
        model=MODEL,
        base_url=ENDPOINT.rsplit("/chat/completions", 1)[0],
        api_key=key,
        temperature=0,
        max_tokens=MAX_TOKENS,
        max_retries=0,
        timeout=90,
        extra_body={"provider": {"require_parameters": True}},
    )
    method = "json_schema" if variant == "S5a" else "function_calling"
    return chat.with_structured_output(answer, method=method, strict=True, include_raw=True)


def literal_of(values: list[str]):
    from typing import Literal

    return Literal[tuple(dict.fromkeys(values))]


def invoke_langchain(chain, variant: str, ingredients: list[str], names: list[str]) -> Answer:
    """Run the chain once; never raises. Usage and finish reason come from the raw message."""
    started = time.monotonic()
    try:
        result = chain.invoke(messages_for(variant, ingredients, names))
    except Exception as exc:  # noqa: BLE001 - the provider and the library raise many types
        status = getattr(exc, "status_code", 0) or 0
        call = Call(False, status, time.monotonic() - started, error=type(exc).__name__)
        return Answer(call)
    raw = result["raw"]
    meta = getattr(raw, "response_metadata", {}) or {}
    usage = getattr(raw, "usage_metadata", {}) or {}
    call = Call(True, 200, time.monotonic() - started)
    call.prompt_tokens = int(usage.get("input_tokens") or 0)
    call.completion_tokens = int(usage.get("output_tokens") or 0)
    call.finish_reason = meta.get("finish_reason")
    parsed = result.get("parsed")
    if call.finish_reason == "length" or parsed is None:
        call.ok = False
        call.error = "truncated" if call.finish_reason == "length" else "parsing failed"
        return Answer(call, meta.get("model_provider"), str(result.get("parsing_error") or ""))
    call.data = parsed.model_dump()
    return Answer(call, meta.get("model_provider"), json.dumps(call.data, ensure_ascii=False))


# --- reading and checking an answer ---------------------------------------------------------


def service_data(variant: str, data: dict | None) -> dict:
    """The answer in the shape the service's name check reads (names only becomes empty lists)."""
    items = (data or {}).get("dishes")
    if not isinstance(items, list):
        return {"dishes": []}
    out = []
    for item in items:
        if isinstance(item, str):
            out.append({"name": item, "have": [], "missing": []})
        elif isinstance(item, dict):
            out.append({"name": item.get("name"), "have": [], "missing": [], **item})
    return {"dishes": out}


def count_violations(
    variant: str, data: dict | None, ingredients: list[str], names: list[str], vocab: list[str]
) -> dict[str, int]:
    """Items the answer format should have made impossible (exact string membership)."""
    items = service_data(variant, data)["dishes"]
    owned, allowed_names, allowed_vocab = set(owned_enum(ingredients)), set(names), set(vocab)
    seen: set = set()
    out = dict.fromkeys(
        (
            "names",
            "names_outside_list",
            "have",
            "have_outside_owned",
            "missing",
            "missing_outside",
            "repeated",
        ),
        0,
    )
    for item in items:
        out["names"] += 1
        out["names_outside_list"] += item["name"] not in allowed_names
        out["repeated"] += item["name"] in seen
        seen.add(item["name"])
        have = item["have"] if isinstance(item["have"], list) else []
        miss = item["missing"] if isinstance(item["missing"], list) else []
        out["have"] += len(have)
        out["have_outside_owned"] += sum(1 for h in have if h not in owned)
        out["missing"] += len(miss)
        out["missing_outside"] += sum(1 for m in miss if m not in allowed_vocab)
    return out


def rules_assisted(catalog: Catalog, data: dict | None, ingredients: list[str]) -> list[dict]:
    """S6: keep the model's names, compute have and missing from the dish's key ingredients."""
    owned = catalog.owned(ingredients)
    by_name = {d.name: d for d in catalog.dishes.values()}
    out, seen = [], set()
    for item in service_data("S1", data)["dishes"]:
        dish = by_name.get(item["name"])
        if dish is None or dish.id in seen:
            continue
        seen.add(dish.id)
        match = catalog.match(dish, owned)
        out.append({"id": dish.id, "have": list(match.have), "missing": list(match.missing)})
    return out


def client_code_lines() -> dict[str, int]:
    """Logical source lines (not blank, not comment, no docstring) of the two client routes."""

    def lines(funcs) -> int:
        total = 0
        for func in funcs:
            tree = ast.parse(textwrap.dedent(inspect.getsource(func)))
            node = tree.body[0]
            body = node.body[1:] if ast.get_docstring(node) else node.body
            stmts = {n.lineno for b in body for n in ast.walk(b) if isinstance(n, ast.stmt)}
            total += len(stmts)
        return total

    raw = lines([response_format_payload, post_chat])
    tools = lines([tools_payload, post_chat])
    chain = lines([langchain_structured, literal_of, invoke_langchain])
    return {"raw_response_format": raw, "raw_tools": tools, "langchain": chain}
