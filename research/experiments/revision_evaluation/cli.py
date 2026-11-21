# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An
"""Offline plan preview and contract-fixture validation; live execution is not enabled."""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from app.dishes.http import RETRY_WAITS
from app.dishes.recipes import RecipeStore

from .contract import fixture_root, validate_fixture_bundle
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
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument(
        "--validate-fixtures",
        action="store_true",
        help="validate fixtures only, without building a plan",
    )
    parser.add_argument("--fixture-root", type=Path, default=fixture_root())
    args = parser.parse_args(argv)
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
            plan = build_plan(
                manifest,
                args.cases
                if args.cases is not None
                else [case.id for case in manifest],
                args.repetitions,
                recipes=RecipeStore.load(args.recipes),
                catalog=snapshot.catalog(),
                snapshot=snapshot,
            )
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            print("offline plan validation failed", file=sys.stderr)
            return 2
        result.update(
            plan=[
                {"case_id": unit.case_id, "repetition": unit.repetition}
                for unit in plan.units
            ],
            effective_assumed_staples=list(plan.effective_assumed_staples),
            planned_bounds=planned_bounds(plan),
        )
    # ASCII JSON keeps console behavior independent of the Windows code page.
    print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))
    return 0
