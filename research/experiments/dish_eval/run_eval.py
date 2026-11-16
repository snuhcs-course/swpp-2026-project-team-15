# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""Run the frozen dish evaluation (cases.json, thresholds.json) through the real service code.

Default: a dry run that prints the plan and makes no model call.
  --provider rules   deterministic baseline (no model, no network)
  --provider llm     the real model path; needs --allow-live-api and OPENROUTER_API_KEY

The service is called in process (``app.dishes.service.DishService``); requests that the API would
refuse with HTTP 422 are checked against the request models (``SuggestRequest`` / ``AdaptRequest``).
Results are written under the ignored ``data/dish-eval/`` directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
from pydantic import ValidationError

from app.dishes import service as service_module
from app.dishes.catalog import Catalog
from app.dishes.llm import DEFAULT_MODEL, DishLLM, DishLLMError
from app.dishes.schemas import AdaptRequest, SuggestRequest
from app.dishes.service import DishService

from . import scoring

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
KEY_FILE = Path.home() / ".config" / "mylittlechef" / "openrouter.env"
ASSUMED_TOKENS = (3000, 300)  # per model call, only used for the dry-run estimate


class UsageTransport(httpx.BaseTransport):
    """Records token usage of every model response without touching the application code."""

    def __init__(self) -> None:
        self._inner = httpx.HTTPTransport()
        self.requests = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.requests += 1
        response = self._inner.handle_request(request)
        response.read()
        try:
            usage = json.loads(response.content).get("usage", {})
            self.prompt_tokens += int(usage.get("prompt_tokens") or 0)
            self.completion_tokens += int(usage.get("completion_tokens") or 0)
        except (ValueError, TypeError, AttributeError):
            pass
        return response

    def close(self) -> None:
        self._inner.close()


class FailingLLM:
    """A model that is always unavailable (for the fallback check)."""

    def complete(self, *_args, **_kwargs):
        raise DishLLMError("The model service is temporarily unavailable")


class View:
    """What the scorer needs from the catalog."""

    def __init__(self, catalog: Catalog) -> None:
        self._catalog = catalog
        self.staples = catalog.staples
        self.dish_keys = {d.id: d.key_ingredients for d in catalog.dishes.values()}

    def owned(self, ingredients: list[str]) -> set[str]:
        return self._catalog.owned(ingredients)


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


def plan(cases: list[dict], price_in: float, price_out: float) -> None:
    valid = [c for c in cases if c["expect_status"] == 200]
    calls = len(valid)
    cost = calls * (ASSUMED_TOKENS[0] * price_in + ASSUMED_TOKENS[1] * price_out) / 1e6
    kinds = {k: sum(1 for c in cases if c["endpoint"] == k) for k in ("suggest", "adapt")}
    print(f"cases: {len(cases)} (suggest {kinds['suggest']}, adapt {kinds['adapt']})")
    print(f"valid cases that may call the model: {calls} (at most one call each)")
    print(
        f"assumed {ASSUMED_TOKENS[0]} input + {ASSUMED_TOKENS[1]} output tokens per call at "
        f"{price_in}/{price_out} USD per million: at most about ${cost:.3f} (assumed)"
    )
    print(
        "dry run: nothing was executed (add --provider rules, or --provider llm --allow-live-api)"
    )


def run(
    cases: list[dict], thresholds: dict, provider: str, model: str, key: str, limit: int | None
):
    catalog = Catalog.load()
    view = View(catalog)
    transport = UsageTransport() if provider == "llm" else None
    llm = DishLLM(key, model, transport=transport) if provider == "llm" else None
    service = DishService(catalog, llm)
    failing = DishService(catalog, FailingLLM())
    suggest_rows, suggest_invalid, fallback, adapt_rows, adapt_invalid = [], [], [], [], []
    latencies: list[float] = []
    details: list[dict] = []
    chosen = cases[:limit] if limit else cases
    for case in chosen:
        cid, kind = case["id"], case["endpoint"]
        before = transport.requests if transport else 0
        row: dict = {"id": cid, "endpoint": kind}
        if kind == "suggest":
            try:
                request = SuggestRequest(**case["input"])
            except ValidationError:
                suggest_invalid.append(case["expect_status"] == 422)
                row["rejected"] = True
                details.append(row)
                continue
            if case["expect_status"] == 422:
                suggest_invalid.append(False)
                row["rejected"] = False
            start = time.perf_counter()
            response = service.suggest(request.ingredients, request.limit).model_dump()
            elapsed = time.perf_counter() - start
            if transport and transport.requests > before:
                latencies.append(elapsed)
            if case["expect_status"] == 200:
                judged = scoring.check_suggest(case, response, view)
                suggest_rows.append(judged)
                fb = failing.suggest(request.ingredients, request.limit).model_dump()
                fb_ok = (
                    scoring.suggest_schema_ok(fb, request.limit)
                    and fb["source"] == "rules"
                    and all(d["id"] in view.dish_keys for d in fb["dishes"])
                )
                fallback.append(bool(fb_ok))
                row.update(judged)
                row["response"] = response
                row["fallback_ok"] = bool(fb_ok)
        else:
            try:
                request = AdaptRequest(**case["input"])
            except ValidationError:
                adapt_invalid.append(case["expect_status"] == 422)
                row["rejected"] = True
                details.append(row)
                continue
            start = time.perf_counter()
            try:
                result = service.adapt(request.dish_id, request.ingredients)
                error = None
            except DishLLMError as exc:
                result, error = None, str(exc)
            elapsed = time.perf_counter() - start
            if transport and transport.requests > before:
                latencies.append(elapsed)
            if case["expect_status"] == 422:
                adapt_invalid.append(result is None and error is None)
                row["rejected"] = result is None and error is None
            else:
                judged = scoring.check_adapt(
                    case, result.model_dump() if result else None, catalog.staples
                )
                adapt_rows.append(judged)
                row.update(judged)
                row["response"] = result.model_dump() if result else None
                row["error"] = error
        details.append(row)
    metrics = scoring.aggregate(
        suggest_rows, suggest_invalid, fallback, adapt_rows, adapt_invalid, latencies or None
    )
    rows = scoring.verdict(metrics, thresholds)
    return catalog, transport, metrics, rows, details, latencies


def print_table(rows: list[dict]) -> None:
    print(f"{'metric':36} {'value':>9}  {'threshold':>11}  status")
    for r in rows:
        value = "-" if r["value"] is None else f"{r['value']:.3f}"
        print(f"{r['metric']:36} {value:>9}  {r['op']:>2} {r['threshold']:<8}  {r['status']}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--cases", type=Path, default=HERE / "cases.json")
    p.add_argument("--thresholds", type=Path, default=HERE / "thresholds.json")
    p.add_argument("--provider", choices=("rules", "llm"), help="omit for a dry run")
    p.add_argument("--allow-live-api", action="store_true", help="needed for --provider llm")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--limit", type=int, help="run only the first N cases")
    p.add_argument("--price-in", type=float, default=0.10, help="USD per million input tokens")
    p.add_argument("--price-out", type=float, default=0.40, help="USD per million output tokens")
    p.add_argument("--output-dir", type=Path, default=REPO_ROOT / "data" / "dish-eval")
    args = p.parse_args(argv)
    cases = json.loads(args.cases.read_text(encoding="utf-8"))["cases"]
    thresholds = json.loads(args.thresholds.read_text(encoding="utf-8"))
    if args.provider is None:
        plan(cases, args.price_in, args.price_out)
        return 0
    key = ""
    if args.provider == "llm":
        if not args.allow_live_api:
            print(
                "--provider llm sends real, billed requests: add --allow-live-api", file=sys.stderr
            )
            return 2
        key = read_key()
        if not key:
            print(
                "OPENROUTER_API_KEY is not set (env or ~/.config/mylittlechef/openrouter.env)",
                file=sys.stderr,
            )
            return 2
    catalog, transport, metrics, rows, details, latencies = run(
        cases, thresholds, args.provider, args.model, key, args.limit
    )
    calls = transport.requests if transport else 0
    cost = (
        (transport.prompt_tokens * args.price_in + transport.completion_tokens * args.price_out)
        / 1e6
        if transport
        else 0.0
    )
    settings = {
        "date": datetime.now(UTC).isoformat(timespec="seconds"),
        "provider": args.provider,
        "model": args.model if args.provider == "llm" else None,
        "temperature": 0,
        "max_tokens": 1024,
        "decoding_note": "temperature, max_tokens fixed in app.dishes.llm; one call per case",
        "commit": git("rev-parse", "HEAD"),
        "tree_dirty": bool(git("status", "--porcelain")),
        "sha256": {
            "cases": sha256(args.cases),
            "thresholds": sha256(args.thresholds),
            "dishes": sha256(Path(service_module.__file__).with_name("dishes.json")),
        },
        "prompt_sha256": hashlib.sha256(
            json.dumps(
                [
                    service_module.SUGGEST_SYSTEM,
                    service_module.ADAPT_SYSTEM,
                    service_module.SUGGEST_SCHEMA,
                    service_module.ADAPT_SCHEMA,
                ],
                sort_keys=True,
                ensure_ascii=False,
            ).encode()
        ).hexdigest(),
        "python": platform.python_version(),
        "command": "python -m experiments.dish_eval.run_eval " + " ".join(argv or sys.argv[1:]),
        "limit": args.limit,
    }
    summary = {
        "settings": settings,
        "metrics": metrics,
        "verdict": rows,
        "model_calls": calls,
        "prompt_tokens": transport.prompt_tokens if transport else 0,
        "completion_tokens": transport.completion_tokens if transport else 0,
        "cost_usd": round(cost, 6),
        "cost_per_call_usd": round(cost / calls, 6) if calls else None,
        "latency_s": {
            "median": statistics.median(latencies) if latencies else None,
            "max": max(latencies) if latencies else None,
        },
        "cases": details,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = args.output_dir / f"summary-{args.provider}-{stamp}.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print_table(rows)
    print(f"model calls: {calls}; cost: ${cost:.5f}; written: {out}")
    return 0 if all(r["status"] != "fail" for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
