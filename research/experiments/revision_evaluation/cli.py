# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An
"""Offline plan preview and contract-fixture validation; live execution is not enabled."""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from app.dishes.http import RETRY_WAITS
from app.dishes.recipes import RecipeStore

from .budgeting import read_run_budget
from .compatibility import (
    capture_code_identity,
    capture_input_identities,
    load_resume_metadata,
    validate_resume,
)
from .contract import fixture_root, validate_fixture_bundle
from .live import require_live_key, resolve_live_settings
from .persistence import PersistenceError, _redact
from .planning import FROZEN_MANIFEST, ExecutionPlan, build_plan, load_manifest
from .staples import StaplesSnapshot


class _SafeParser(argparse.ArgumentParser):
    """Do not echo arbitrary argument values, which may contain credentials."""

    def error(self, message: str) -> None:
        self.exit(2, "invalid command-line arguments; use --help\n")


def planned_bounds(plan: ExecutionPlan) -> dict:
    """Return conservative single-pass bounds, not predicted calls or a spending cap.

    Production permits one initial call and at most one check-triggered re-ask.
    Each logical call permits one send plus the configured 429 retries. Zero-call
    branches and time budgets may reduce these maxima; no branch policy is copied
    here to tighten the bounds. Resumed execution attempts are not included.
    """
    logical_maximum = 2 * len(plan.units)
    return {
        "logical_calls": {"minimum": 0, "maximum": logical_maximum},
        "http_attempts": {
            "minimum": 0,
            "maximum": logical_maximum * (1 + len(RETRY_WAITS)),
        },
        "http_attempts_per_logical_call_maximum": 1 + len(RETRY_WAITS),
        "scope": "conservative single execution per planned repetition; excludes resume",
        "enforced_budget": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Keep existing diagnostics, but never expose an unexpected exception traceback."""
    try:
        return _main(argv)
    except Exception:  # noqa: BLE001 - the console boundary must not echo private exceptions
        print("evaluation command failed", file=sys.stderr)
        return 2


def _main(argv: Sequence[str] | None = None) -> int:
    """Validate fixtures and print a read-only plan by default, never constructing a model.

    Validation-only mode does not require recipe/catalog/availability configuration.
    Errors are fixed diagnostics rather than raw file/validation exceptions. Output
    is console JSON only: no run directory, checkpoint or report is published.
    """
    parser = _SafeParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=FROZEN_MANIFEST)
    parser.add_argument(
        "--recipes", type=Path, default=FROZEN_MANIFEST.with_name("fixtures.json")
    )
    parser.add_argument(
        "--cases",
        nargs="+",
        help="explicit case IDs in execution order; default: all manifest cases",
    )
    parser.add_argument(
        "--repetitions", type=int, help="default: 1, or the stored count for --resume"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--validate-fixtures",
        action="store_true",
        help="validate fixtures only, without building a plan",
    )
    mode.add_argument(
        "--resume",
        type=Path,
        help="read-only compatibility check of an existing incomplete run",
    )
    parser.add_argument("--fixture-root", type=Path, default=fixture_root())
    parser.add_argument(
        "--allow-live-api",
        action="store_true",
        help="explicitly authorize live start/resume configuration (preflight only until integration)",
    )
    parser.add_argument(
        "--model", help="production model ID; defaults to production/stored model"
    )
    parser.add_argument(
        "--max-http-attempts",
        type=int,
        help="required positive run cap for a live start; cannot change on resume",
    )
    parser.add_argument("--input-per-million-usd", type=float)
    parser.add_argument("--output-per-million-usd", type=float)
    args = parser.parse_args(argv)
    configured = any(
        value is not None
        for value in (
            args.model,
            args.max_http_attempts,
            args.input_per_million_usd,
            args.output_per_million_usd,
        )
    )
    if args.validate_fixtures and (args.allow_live_api or configured):
        parser.error("fixture validation cannot configure live access")
    if configured and not args.allow_live_api and args.resume is None:
        parser.error("live settings require opt-in or an existing run")
    stored = None
    if args.resume is not None:
        try:
            stored = load_resume_metadata(args.resume)
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            print("resume compatibility check failed", file=sys.stderr)
            return 2
    try:
        _, observations, _ = validate_fixture_bundle(args.fixture_root)
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        print("contract fixture validation failed", file=sys.stderr)
        return 2
    result = {
        "mode": "fixture_validation" if args.validate_fixtures else "dry_run",
        "fixture_observations_validated": len(observations),
        "network_requests_sent": 0,
    }
    if not args.validate_fixtures:
        try:
            manifest = load_manifest(args.manifest)
            snapshot = StaplesSnapshot()
            selected = args.cases
            if selected is None:
                selected = (
                    list(dict.fromkeys(unit.case_id for unit in stored.plan))
                    if stored
                    else [case.id for case in manifest]
                )
            repetitions = args.repetitions
            if repetitions is None:
                repetitions = (
                    max((unit.repetition for unit in stored.plan), default=0)
                    if stored
                    else 1
                )
            plan = build_plan(
                manifest,
                selected,
                repetitions,
                recipes=RecipeStore.load(args.recipes),
                catalog=snapshot.catalog(),
                snapshot=snapshot,
            )
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            print("offline plan validation failed", file=sys.stderr)
            return 2
        settings = requested_model = requested_prices = None
        if stored is not None or args.allow_live_api:
            try:
                settings = resolve_live_settings(
                    model_id=args.model,
                    maximum=args.max_http_attempts,
                    input_price=args.input_per_million_usd,
                    output_price=args.output_per_million_usd,
                    stored=stored,
                )
                requested_model = (
                    {**stored.model, "id": settings.model_id}
                    if stored
                    else settings.model_metadata()
                )
                requested_prices = (
                    stored.pricing
                    if stored
                    and args.input_per_million_usd is None
                    and args.output_per_million_usd is None
                    else settings.pricing_metadata()
                )
            except (ValueError, TypeError):
                print("live configuration or budget validation failed", file=sys.stderr)
                return 2
        if stored is not None:
            try:
                validate_resume(
                    stored,
                    plan,
                    capture_input_identities(plan, args.manifest, args.recipes),
                    capture_code_identity(),
                    model=requested_model,
                    pricing=requested_prices,
                )
            except (OSError, ValueError, TypeError, KeyError, AttributeError):
                print("resume compatibility check failed", file=sys.stderr)
                return 2
            result.update(
                mode="resume_compatibility_check",
                compatible=True,
                execution_resumed=False,
            )
        result.update(
            plan=[
                {"case_id": unit.case_id, "repetition": unit.repetition}
                for unit in plan.units
            ],
            effective_assumed_staples=list(plan.effective_assumed_staples),
            planned_bounds=planned_bounds(plan),
        )
        if args.allow_live_api or configured:
            try:
                if stored is not None:
                    budget = read_run_budget(
                        args.resume, maximum=settings.maximum
                    ).budget
                else:
                    budget = None
                key = (
                    require_live_key(args.allow_live_api)
                    if args.allow_live_api
                    else None
                )
                if args.allow_live_api and budget is not None and budget.remaining == 0:
                    raise ValueError("HTTP-attempt budget exhausted")
            except (
                OSError,
                ValueError,
                TypeError,
                KeyError,
                AttributeError,
                PersistenceError,
            ):
                print("live configuration or budget validation failed", file=sys.stderr)
                return 2
            result.update(
                model=requested_model,
                pricing=requested_prices,
                http_attempt_budget=budget.model_dump()
                if budget is not None
                else {
                    "maximum": settings.maximum,
                    "consumed": 0,
                    "remaining": settings.maximum,
                },
            )
            if args.allow_live_api:
                # Sequential execution/publication is the next integration unit;
                # opt-in must never make a preparation result look like a live run.
                result.update(
                    mode="live_resume_preflight" if stored else "live_start_preflight",
                    execution_started=False,
                    live_execution_available=False,
                    budget_persisted=stored is not None,
                )
                result = _redact(result, (key,))
    # ASCII JSON keeps console behavior independent of the Windows code page.
    print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))
    return 0
