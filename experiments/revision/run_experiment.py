"""Run fixed recipe revision observations; offline mock mode is the default."""
# AI-generated initial importer with Codex (GPT-6.1 Sol)
# 2026-10-14 to 2026-10-17; reviewed by Soohyun An

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import math
import os
from collections.abc import Callable, Sequence
from pathlib import Path
import sys
from typing import Protocol
from uuid import uuid4

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVER_ROOT = REPO_ROOT / "server"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.recipe_revision.core import (LLM, PROMPT_VERSION, SCHEMA_VERSION, RevisionOutcome,
                                         build_request, revise)  # noqa: E402
from experiments.revision.cases import ALL_RECIPES, Case, EXPERIMENT_RECIPES, INVENTORIES, matrix  # noqa: E402
from experiments.revision.mock_llm import MockLLM  # noqa: E402
from experiments.revision.reports import redact, utc_now, write_json, write_sheets  # noqa: E402
from experiments.revision.sqlite_loader import PreflightError, load_inputs  # noqa: E402


class ExperimentLLM(LLM, Protocol):
    """Runner adapter contract: generation plus non-secret run configuration."""

    def configuration(self) -> dict:
        """Return settings safe to persist in experiment metadata."""
        ...


@dataclass(frozen=True)
class RunSummary:
    """Run destination and completion; incomplete experiments exit unsuccessfully."""

    directory: Path
    complete: bool
    attempted: int
    reason: str | None


def _fingerprint(path: Path) -> str:
    """Identify the source database without reading it into one large buffer."""
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def run(database: Path, output_dir: Path, llm: LLM | None = None,
        configuration: dict | None = None, *, run_id: str | None = None,
        cases: tuple[Case, ...] | None = None, make_llm: Callable[[], ExperimentLLM] | None = None,
        secrets: Sequence[str] = ()) -> RunSummary:
    """Run selected cases and persist failure-only diagnostics without retrying.

    Supply a generation-only adapter with explicit configuration, or a deferred
    factory returning an ExperimentLLM, invoked only after preflight. A new
    directory is reserved first so pre-attempt errors can be saved
    without inventing case results. Omitted cases retain the full-matrix Python API.
    Existing run directories are never reused, including for error reporting.
    """
    cases = matrix() if cases is None else cases
    if not cases or len(set(cases)) != len(cases) or not set(cases) <= set(matrix(tuple(INVENTORIES))):
        raise ValueError("Cases must be a nonempty unique subset of the fixed matrix")
    if llm is not None and make_llm is not None:
        raise ValueError("Supply either an adapter or a factory")
    run_id = run_id or uuid4().hex
    if not run_id or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for char in run_id):
        raise ValueError("Run ID must be a nonempty safe path component")
    directory = output_dir / run_id
    directory.mkdir(parents=True, exist_ok=False)
    planned = [case.case_id for case in cases]
    metadata = {"run_id": run_id, "started_at": utc_now(), "finished_at": None,
                "complete": False, "run_status": "running", "configuration": configuration or {},
                "prompt_version": PROMPT_VERSION, "schema_version": SCHEMA_VERSION,
                "database": str(database.resolve()), "database_sha256": None,
                "planned_cases": [asdict(case) | {"case_id": case.case_id} for case in cases],
                "inventories": {}, "attempted_case_ids": [], "recorded_case_ids": [],
                "unattempted_case_ids": planned.copy(),
                "stopping_case_id": None, "stopping_reason": None}
    records = []
    current = None
    stage = "persistence"

    def persist_progress() -> None:
        """Record only attempted/recorded cases and redact all persisted metadata."""
        metadata["recorded_case_ids"] = [record["case_id"] for record in records]
        attempted = set(metadata["attempted_case_ids"])
        metadata["unattempted_case_ids"] = [key for key in planned if key not in attempted]
        write_json(directory / "metadata.json", redact(metadata, secrets))

    try:
        persist_progress()
        stage = "preflight"
        recipe_ids = {case.recipe_id for case in cases}
        experiments = {case.experiment for case in cases}
        recipes, inventories = load_inputs(
            database, recipe_pairs=tuple(pair for pair in ALL_RECIPES if pair[0] in recipe_ids),
            inventory_pairs={key: pairs for key, pairs in INVENTORIES.items() if key in experiments})
        metadata["database_sha256"] = _fingerprint(database)
        metadata["inventories"] = {key: [asdict(item) for item in values]
                                   for key, values in inventories.items()}
        stage = "configuration"
        if make_llm is not None:
            configured_llm = make_llm()
            metadata["configuration"] = configured_llm.configuration()
            llm = configured_llm
        if llm is None:
            raise ValueError("An adapter or factory is required")
        stage = "persistence"
        persist_progress()
        write_sheets(directory, records)
        for case in cases:
            current = case.case_id
            started = utc_now()
            original, inventory = recipes[case.recipe_id], inventories[case.experiment]
            metadata["attempted_case_ids"].append(current)
            stage = "revision"
            try:
                outcome = revise(original, inventory, llm)
            except Exception as exc:
                # Arbitrary transport/programming errors may contain credentials.
                outcome = RevisionOutcome("revision_error", build_request(original, inventory),
                                          None, None, f"Unexpected {type(exc).__name__} during revision",
                                          failure_stage="revision")
            record = {"schema_version": SCHEMA_VERSION, "run_id": run_id,
                      "case_id": current, "experiment": case.experiment, "recipe_id": case.recipe_id,
                      "original": asdict(original), "inventory": [asdict(item) for item in inventory],
                      "status": outcome.status, "model_result": outcome.model_result,
                      "raw_response": outcome.raw_response, "error": outcome.error,
                      "request_metadata": {**outcome.request.to_dict(),
                                           "configuration": metadata["configuration"],
                                           "started_at": started, "finished_at": utc_now(),
                                           "provider_metadata": outcome.provider_metadata}}
            failed = outcome.status not in ("revised", "refused")
            if failed:
                record["diagnostics"] = {"stage": outcome.failure_stage, "reason": outcome.error}
            record = redact(record, secrets)
            stage = "persistence"
            write_json(directory / f"{current}.json", record)
            records.append(record)
            write_sheets(directory, records)
            persist_progress()
            if failed:
                metadata.update(run_status="stopped", stopping_case_id=current,
                                stopping_reason=record["error"])
                break
        else:
            metadata.update(complete=True, run_status="completed")
        metadata["finished_at"] = utc_now()
        persist_progress()
    except BaseException as exc:
        # Preserve useful loader errors; never copy arbitrary exception messages.
        reason = str(exc) if isinstance(exc, PreflightError) else f"Run failed during {stage} ({type(exc).__name__})"
        metadata.update(complete=False, run_status="interrupted" if isinstance(exc, KeyboardInterrupt) else "stopped",
                        finished_at=utc_now(), stopping_case_id=current, stopping_reason=reason,
                        diagnostics={"stage": stage, "reason": reason})
        try:
            persist_progress()
        except Exception:
            # An unwritable destination must not mask the original failure.
            pass
        raise
    return RunSummary(directory, metadata["complete"], len(metadata["attempted_case_ids"]),
                      redact(metadata["stopping_reason"], secrets))


def _positive_float(value: str) -> float:
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise argparse.ArgumentTypeError("Must be finite and positive")
    return result


def main(argv: list[str] | None = None) -> int:
    """Parse local settings; live calls require an explicit opt-in and credentials."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=REPO_ROOT / "data/recipes/recipes.sqlite3")
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "data/recipes/revision-experiments")
    parser.add_argument("--experiment-num", type=int, choices=(0, 1, 2, 3), default=0,
                        help="Inventory: 0 (default), 1, 2 (whole garlic), 3 (minced garlic)")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--recipe-id", type=int, choices=[pair[0] for pair in ALL_RECIPES],
                           help="One recipe in the condition (default: 9 for E0/E1, 335 for E2/E3)")
    selection.add_argument("--all", "-all", dest="all_recipes", action="store_true",
                           help="Run all recipes in the condition: 16 for E0/E1, 4 for E2/E3")
    parser.add_argument("--provider", choices=("mock", "chat-completions"), default="mock")
    parser.add_argument("--mock-responses", type=Path, help="Selected-case, original 32-case or full 40-case fixture mapping")
    parser.add_argument("--allow-live-api", action="store_true", help="Explicitly enable potentially paid API calls")
    parser.add_argument("--model", help="Live model; otherwise REVISION_LLM_MODEL")
    parser.add_argument("--timeout", type=_positive_float, default=60)
    parser.add_argument("--temperature", type=float, help="Optional, must be supported by the chosen model")
    parser.add_argument("--max-completion-tokens", type=int, help="Optional live token limit")
    args = parser.parse_args(argv)
    if args.provider != "mock" and not args.allow_live_api:
        parser.error("Live provider requires --allow-live-api; mock mode makes no network calls")
    if args.provider == "mock" and (args.allow_live_api or args.model or args.temperature is not None
                                    or args.max_completion_tokens is not None):
        parser.error("Live flags cannot be used in mock mode")
    if args.provider != "mock" and args.mock_responses:
        parser.error("Mock fixtures cannot be used with the live provider")
    experiment = f"AI-E{args.experiment_num}"
    recipe_pairs = EXPERIMENT_RECIPES[experiment]
    recipe_id = args.recipe_id if args.recipe_id is not None else recipe_pairs[0][0]
    if not args.all_recipes and recipe_id not in dict(recipe_pairs):
        parser.error(f"Recipe {recipe_id} is not available in {experiment}")
    cases = tuple(Case(experiment, selected_id) for selected_id, _ in recipe_pairs
                  if args.all_recipes or selected_id == recipe_id)
    # The factory adds file-loaded credentials before any response can be saved.
    secrets = [os.environ.get("REVISION_LLM_API_KEY", "")]

    def make_llm() -> ExperimentLLM:
        """Construct the selected adapter after inputs pass preflight."""
        load_dotenv(SERVER_ROOT / ".env", override=False)
        secrets.append(os.environ.get("REVISION_LLM_API_KEY", ""))
        if args.provider == "mock":
            return MockLLM.from_file(args.mock_responses, cases=cases) if args.mock_responses else MockLLM(cases=cases)
        from server.recipe_revision.adapters import ChatCompletionsLLM
        return ChatCompletionsLLM.from_environment(model=args.model, timeout=args.timeout,
                                                 temperature=args.temperature,
                                                 max_completion_tokens=args.max_completion_tokens)

    try:
        summary = run(args.db, args.output_dir, cases=cases, make_llm=make_llm,
                      secrets=secrets)
    except KeyboardInterrupt:
        parser.exit(130, "Experiment interrupted; stored results cannot be resumed.\n")
    except Exception as exc:
        parser.exit(1, f"Experiment failed ({type(exc).__name__}); check the output directory for metadata if available.\n")
    print(f"{'Completed' if summary.complete else 'Stopped'}: {summary.attempted}/{len(cases)} attempts; {summary.directory}")
    if summary.reason:
        print(f"Reason: {summary.reason}")
    return 0 if summary.complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
