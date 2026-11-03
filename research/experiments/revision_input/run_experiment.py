# AI-generated with Claude Code (Sonnet 5.5), 2026-11-03; human review pending.
"""Compare revision pipeline arms on a fixed case set; offline mock mode is the default.

Arms (every request uses the same model and settings):
  original    the full-row request, no post-check (``recipe_revision.core.revise``)
  check-only  compact request + post-check, no refusal in code, no completed change list
  default     the shipped defaults: refusal in code + completed change list
  retry       default + one retry with feedback after a rejected answer

Outputs go to a new directory under --output-dir (default: ignored data/): one JSON per call,
metadata.json, summary.json and summary.md. A live provider needs --allow-live-api and the
server's REVISION_LLM_* environment variables; it makes about
(arms x cases x repeats) model calls, so check the case count and the model price first.
"""

import argparse
import hashlib
import os
import sys
import time
from collections import Counter
from pathlib import Path
from uuid import uuid4

from experiments.revision.reports import redact, utc_now, write_json

from app.recipes.seasonings import load_seasoning_policy
from recipe_revision.core import revise
from recipe_revision.pipeline import Steps, revise_with_steps

from . import checkers as ck
from .cases import load_cases
from .catalog import inventory_for, load_catalog
from .criteria import BASELINE, evaluate, summary
from .offline_llm import OfflineLLM
from .scoring import score_record

REPO_ROOT = Path(__file__).resolve().parents[3]
ARMS = ("original", "check-only", "default", "retry")


def jsonable(value):
    """NaN (an undefined ratio or rate) becomes null; the run writer rejects NaN."""
    if isinstance(value, float) and value != value:
        return None
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [jsonable(v) for v in value]
    return value


def arm_runner(arm: str, seasonings):
    """Return fn(recipe, inventory, llm) -> RevisionOutcome for one arm."""
    if arm == "original":
        return lambda recipe, inventory, llm: revise(recipe, inventory, llm)
    steps = {
        "check-only": Steps(prescreen=False, complete_changes=False, seasonings=seasonings),
        "default": Steps(seasonings=seasonings),
        "retry": Steps(retry=True, seasonings=seasonings),
    }[arm]
    return lambda recipe, inventory, llm: revise_with_steps(recipe, inventory, llm, steps)


class Meter:
    """Count model calls of one pipeline run (the outcome's metadata may omit them)."""

    def __init__(self, llm):
        self.llm, self.calls = llm, 0

    def generate(self, request):
        self.calls += 1
        return self.llm.generate(request)


def run_call(arm, case, rep, recipe, names, llm, run, price):
    inventory = inventory_for(case, names)
    meter = Meter(llm)
    started = time.time()
    outcome = run(recipe, inventory, meter)
    latency = time.time() - started
    meta = outcome.provider_metadata or {}
    usage = meta.get("usage") or {}
    cost = None
    if usage.get("prompt_tokens") is not None:
        cost = (
            usage["prompt_tokens"] * price[0] + (usage.get("completion_tokens") or 0) * price[1]
        ) / 1e6
    return {
        "arm": arm,
        "case_id": case["case_id"],
        "rep": rep,
        "status": outcome.status,
        "result": outcome.model_result,
        "raw": outcome.raw_response,
        "error": outcome.error,
        "usage": usage or None,
        "model_calls": meter.calls,
        "cost": cost,
        "latency_s": round(latency, 3),
    }


def make_llm(args):
    if args.provider == "mock":
        return OfflineLLM()
    from recipe_revision.adapters import ChatCompletionsLLM

    return ChatCompletionsLLM.from_environment(
        model=args.model,
        timeout=args.timeout,
        temperature=args.temperature,
        max_completion_tokens=args.max_completion_tokens,
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--db", type=Path, required=True, help="local recipe database (read-only)")
    p.add_argument("--set", choices=("test", "heldout"), default="test", dest="case_set")
    p.add_argument(
        "--arms", default=",".join(ARMS), help="comma-separated subset of: " + ", ".join(ARMS)
    )
    p.add_argument("--repeats", type=int, default=2)
    p.add_argument("--limit", type=int, help="first N cases only (smoke runs)")
    p.add_argument("--output-dir", type=Path, default=REPO_ROOT / "data/recipes/revision-input")
    p.add_argument("--seasoning-file", type=Path, help="alternative assumed-seasoning list")
    p.add_argument("--provider", choices=("mock", "chat-completions"), default="mock")
    p.add_argument("--allow-live-api", action="store_true", help="enable potentially paid calls")
    p.add_argument("--model", help="live model; otherwise REVISION_LLM_MODEL")
    p.add_argument("--timeout", type=float, default=60)
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--max-completion-tokens", type=int, default=4096)
    p.add_argument("--price-in", type=float, default=0.10, help="USD per million input tokens")
    p.add_argument("--price-out", type=float, default=0.40, help="USD per million output tokens")
    args = p.parse_args(argv)
    if args.provider != "mock" and not args.allow_live_api:
        p.error("A live provider requires --allow-live-api; mock mode makes no network calls")
    if args.provider == "mock" and (args.allow_live_api or args.model):
        p.error("Live flags cannot be used in mock mode")
    arms = args.arms.split(",")
    if not set(arms) <= set(ARMS) or BASELINE not in arms:
        p.error(f"--arms must include {BASELINE} and only use: {', '.join(ARMS)}")

    seasonings = load_seasoning_policy({}, path=args.seasoning_file)
    recipes, names = load_catalog(args.db)
    cases = load_cases(args.case_set)[: args.limit]
    missing = [c["case_id"] for c in cases if c["recipe_id"] not in recipes]
    if missing:
        p.error(f"recipes of {len(missing)} cases are not in this database (first: {missing[0]})")
    index = ck.NameIndex(names, recipes)
    llm = make_llm(args)
    run_id = time.strftime("%Y%m%d-%H%M%S-") + uuid4().hex[:6]
    out = args.output_dir / run_id
    (out / "calls").mkdir(parents=True)
    config = llm.configuration() if hasattr(llm, "configuration") else {}
    banner = "MOCK (offline, no model)" if config.get("is_mock") else f"LIVE {config.get('model')}"
    print(f"{banner}: {len(arms)} arms x {len(cases)} cases x {args.repeats} repeats", flush=True)
    secrets = [os.environ.get("REVISION_LLM_API_KEY", "")]
    with args.db.open("rb") as handle:
        db_sha = hashlib.file_digest(handle, "sha256").hexdigest()
    meta = {
        "run_id": run_id,
        "started_at": utc_now(),
        "set": args.case_set,
        "arms": arms,
        "repeats": args.repeats,
        "configuration": config,
        "seasonings": seasonings.describe(),
        "prices_usd_per_million_tokens": [args.price_in, args.price_out],
        "database_sha256": db_sha,
    }
    rows: dict[str, dict[str, list[dict]]] = {a: {} for a in arms}
    counts: Counter = Counter()
    for arm in arms:
        run = arm_runner(arm, seasonings)
        for case in cases:
            recipe = recipes[case["recipe_id"]]
            allowed = ck.allowed_ids(recipe, case["inventory_ids"], "list", seasonings.assumed_ids)
            for rep in (1, 2, 3)[: args.repeats]:
                if hasattr(llm, "prepare"):
                    llm.prepare(recipe, allowed)
                rec = redact(
                    run_call(
                        arm, case, rep, recipe, names, llm, run, (args.price_in, args.price_out)
                    ),
                    secrets,
                )
                write_json(out / "calls" / f"{arm}__{case['case_id']}__r{rep}.json", rec)
                counts[(arm, rec["status"])] += 1
                rows[arm].setdefault(case["case_id"], []).append(
                    score_record(rec, case, recipe, names, index, seasonings.assumed_ids)
                )
    result = {"summary": summary(rows)}
    result["criteria_vs_original"] = {a: evaluate(rows, a) for a in arms if a != BASELINE}
    meta.update(
        finished_at=utc_now(), status_counts={f"{a}:{s}": n for (a, s), n in counts.items()}
    )
    write_json(out / "metadata.json", redact(meta, secrets))
    write_json(out / "summary.json", jsonable(result))
    (out / "summary.md").write_text(render(banner, args, result), encoding="utf-8")
    print((out / "summary.md").read_text(encoding="utf-8"))
    print(f"Results: {out}")
    return 0


def render(banner: str, args, result: dict) -> str:
    lines = [f"# Revision input, {args.case_set} set ({banner})", ""]
    cols = [
        "model_calls_per_request",
        "prompt_tokens_per_request",
        "rejection_of_attempts",
        "false_refusal",
        "false_accept",
        "inconsistent_of_revised",
        "delivered_violation_of_revised",
    ]
    lines.append("| arm | " + " | ".join(cols) + " |")
    lines.append("|---|" + "---|" * len(cols))
    for arm, d in result["summary"].items():
        lines.append(f"| {arm} | " + " | ".join(f"{d[c]:.3f}" for c in cols) + " |")
    lines += ["", "| arm | criterion | pass |", "|---|---|---|"]
    for arm, crit in result["criteria_vs_original"].items():
        for name, v in crit.items():
            lines.append(f"| {arm} | {name} | {v['pass']} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.exit(main())
