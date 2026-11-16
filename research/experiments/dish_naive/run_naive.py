# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""Run the frozen naive-dish criteria through the real service code.

Default: a dry run that prints the plan and makes no model call. ``--allow-live-api`` makes one
model call per well-formed case (key from OPENROUTER_API_KEY or ~/.config/mylittlechef/).
Results go to the ignored ``data/dish-naive/`` directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
from pydantic import ValidationError

from app.dishes.catalog import Catalog
from app.dishes.llm import DEFAULT_MODEL, MAX_TOKENS, DishLLM, DishLLMError
from app.dishes.schemas import SuggestRequest
from app.dishes.service import SUGGEST_SYSTEM, DishService

from . import scoring

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
KEY_FILE = Path.home() / ".config" / "mylittlechef" / "openrouter.env"
PRICE_PER_MTOK = (0.10, 0.40)  # google/gemini-2.5-flash-lite input/output, USD (OpenRouter listing)


class Usage:
    """Per-request usage read from the response (no change to the application code)."""

    def __init__(self) -> None:
        self.rows: list[dict] = []


class UsageTransport(httpx.BaseTransport):
    def __init__(self, usage: Usage) -> None:
        self._inner = httpx.HTTPTransport()
        self._usage = usage

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        started = time.monotonic()
        response = self._inner.handle_request(request)
        response.read()
        row = {"latency_s": time.monotonic() - started, "status": response.status_code}
        try:
            body = json.loads(response.content)
            u = body.get("usage", {})
            row.update(
                prompt_tokens=int(u.get("prompt_tokens") or 0),
                completion_tokens=int(u.get("completion_tokens") or 0),
                reasoning_tokens=int(
                    (u.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0
                ),
                cached_tokens=int((u.get("prompt_tokens_details") or {}).get("cached_tokens") or 0),
                cost=u.get("cost"),
                finish_reason=(body.get("choices") or [{}])[0].get("finish_reason"),
            )
        except (ValueError, TypeError, AttributeError):
            pass
        self._usage.rows.append(row)
        return response

    def close(self) -> None:
        self._inner.close()


class RecordingLLM:
    """Wraps DishLLM and keeps the raw model answer of the last call."""

    def __init__(self, inner: DishLLM) -> None:
        self._inner = inner
        self.last: dict | None = None

    def complete(self, *args, **kwargs) -> dict:
        self.last = None
        self.last = self._inner.complete(*args, **kwargs)
        return self.last


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), *args], capture_output=True, text=True, check=True
        )
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def read_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key and KEY_FILE.exists():
        for line in KEY_FILE.read_text(encoding="utf-8").splitlines():
            if line.startswith("OPENROUTER_API_KEY="):
                key = line.split("=", 1)[1].strip().strip("\"'")
    return key


def reference(catalog: Catalog, ingredients: list[str]) -> set[str]:
    """Dishes with an owned key ingredient and at most one missing key ingredient."""
    return {m.dish.id for m in catalog.rank(ingredients) if len(m.missing) <= 1}


def missing_counts(catalog: Catalog, ingredients: list[str]) -> dict[str, int]:
    owned = catalog.owned(ingredients)
    return {d.id: len(catalog.match(d, owned).missing) for d in catalog.dishes.values()}


def hybrid_answers(path: Path | None) -> dict[str, list[str]]:
    """Dish ids returned by the stored answers of the earlier (hybrid) design, by case id."""
    if path is None or not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        c["id"]: [d["id"] for d in c["response"]["dishes"]]
        for c in data.get("cases", [])
        if c.get("endpoint") == "suggest" and isinstance(c.get("response"), dict)
    }


def well_formed(ingredients: list[str]) -> bool:
    try:
        SuggestRequest(ingredients=ingredients)
    except ValidationError:
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-live-api", action="store_true")
    parser.add_argument("--hybrid", type=Path, help="summary-llm-*.json of the earlier design")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "data" / "dish-naive")
    args = parser.parse_args(argv)

    criteria_path = HERE / "criteria.json"
    criteria = json.loads(criteria_path.read_text(encoding="utf-8"))
    cases = criteria["cases"]
    planned = [c for c in cases if c["expect_status"] == 200]
    cap = criteria["max_model_calls"]
    print(f"{len(cases)} cases, {len(planned)} model calls planned (cap {cap})")
    if not args.allow_live_api:
        print("dry run: no model call (use --allow-live-api)")
        return 0
    key = read_key()
    if not key:
        print("no OPENROUTER_API_KEY", file=sys.stderr)
        return 2

    catalog = Catalog.load()
    usage = Usage()
    inner = DishLLM(key, DEFAULT_MODEL, transport=UsageTransport(usage))
    llm = RecordingLLM(inner)
    service = DishService(catalog, llm)
    names = set(service._by_name)  # noqa: SLF001 - the list the model is shown
    hybrid = hybrid_answers(args.hybrid)

    per_case, results, hybrid_results, refused = [], [], [], {}
    for case in cases:
        ingredients = case["ingredients"]
        if case["expect_status"] != 200:
            refused[case["id"]] = not well_formed(ingredients)
            continue
        ref = reference(catalog, ingredients)
        counts = missing_counts(catalog, ingredients)
        error = None
        try:
            response = service.suggest(ingredients)
            dishes = [d.model_dump() for d in response.dishes]
        except DishLLMError as exc:
            dishes, error = [], str(exc)
        raw = (llm.last or {}).get("dishes", []) if isinstance(llm.last, dict) else []
        raw_names = [
            d.get("name") for d in raw if isinstance(d, dict) and isinstance(d.get("name"), str)
        ]
        result = scoring.case_result(
            raw_names, dishes, ingredients, names, ref, counts, catalog.staples
        )
        results.append(result)
        if case["id"] in hybrid:
            ids = hybrid[case["id"]]
            hybrid_results.append(
                {
                    "reference_size": len(ref),
                    "reference_hits": len(ref & set(ids)),
                    "dishes": len(ids),
                }
            )
        per_case.append(
            {
                "id": case["id"],
                "error": error,
                "reference": sorted(ref),
                "result": result,
                "returned": [
                    {"name": d["name"], "have": d["have"], "missing": d["missing"]} for d in dishes
                ],
                "usage": usage.rows[-1] if usage.rows else None,
            }
        )
    metrics = scoring.aggregate(results)
    metrics["malformed_refused"] = scoring.share(sum(refused.values()), len(refused))
    lat = [r["latency_s"] for r in usage.rows if "latency_s" in r]
    metrics["median_latency_s"] = scoring.median_or_none(lat)
    ptok = sum(r.get("prompt_tokens", 0) for r in usage.rows)
    ctok = sum(r.get("completion_tokens", 0) for r in usage.rows)
    thresholds = {k: v for k, v in criteria["thresholds"].items() if k != "model_failure_is_502"}
    summary = {
        "settings": {
            "date": datetime.now(UTC).isoformat(timespec="seconds"),
            "model": DEFAULT_MODEL,
            "temperature": 0,
            "max_tokens": MAX_TOKENS,
            "commit": git("rev-parse", "HEAD"),
            "tree_dirty": bool(git("status", "--porcelain")),
            "sha256": {
                "criteria": sha256(criteria_path),
                "dishes": sha256(REPO_ROOT / "server/app/dishes/dishes.json"),
            },
            "prompt_sha256": hashlib.sha256(SUGGEST_SYSTEM.encode()).hexdigest(),
            "python": platform.python_version(),
        },
        "metrics": metrics,
        "verdict": scoring.verdict(metrics, thresholds),
        "hybrid_reference": {
            "cases": len(hybrid_results),
            "recall": scoring.share(
                sum(r["reference_hits"] for r in hybrid_results),
                sum(r["reference_size"] for r in hybrid_results),
            ),
            "precision": scoring.share(
                sum(r["reference_hits"] for r in hybrid_results),
                sum(r["dishes"] for r in hybrid_results),
            ),
        },
        "model_calls": len(usage.rows),
        "failed_calls": sum(1 for c in per_case if c["error"]),
        "truncated_answers": sum(1 for r in usage.rows if r.get("finish_reason") == "length"),
        "tokens": {
            "input": ptok,
            "output": ctok,
            "reasoning": sum(r.get("reasoning_tokens", 0) for r in usage.rows),
            "cached": sum(r.get("cached_tokens", 0) for r in usage.rows),
        },
        "cost_usd": sum(r.get("cost") or 0 for r in usage.rows)
        or (ptok * PRICE_PER_MTOK[0] + ctok * PRICE_PER_MTOK[1]) / 1e6,
        "cases": per_case,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"summary-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                k: summary[k]
                for k in (
                    "metrics",
                    "verdict",
                    "hybrid_reference",
                    "model_calls",
                    "failed_calls",
                    "truncated_answers",
                    "tokens",
                    "cost_usd",
                )
            },
            ensure_ascii=False,
            indent=1,
        )
    )
    print("wrote", path.relative_to(REPO_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
