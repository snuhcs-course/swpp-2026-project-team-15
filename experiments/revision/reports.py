"""Durable local observation records and unscored human evaluation sheets."""
# AI-generated initial importer with Codex (GPT-6.1 Sol)
# 2026-10-14 to 2026-10-17; reviewed by Soohyun An

import csv
from collections.abc import Sequence
from datetime import datetime, timezone
import json
from pathlib import Path
import os
from uuid import uuid4

SCORES = ("decision_validity", "ingredient_compliance", "source_fidelity", "cookability")


def redact(value, secrets: Sequence[str]):
    """Remove known credentials recursively before saving JSON, CSV or console text."""
    if isinstance(value, str):
        for secret in secrets:
            if secret:
                value = value.replace(secret, "[REDACTED]")
        return value
    if isinstance(value, dict):
        return {redact(key, secrets): redact(item, secrets) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item, secrets) for item in value]
    return value


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, value: dict) -> None:
    """Replace one run-owned file atomically; never truncate a prior observation."""
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    # Inherit the run directory's ACLs, including Windows sandbox access.
    with temporary.open("x", encoding="utf-8") as handle:
        try:
            json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        except BaseException:
            handle.close()
            temporary.unlink(missing_ok=True)
            raise
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _write_csv(path: Path, fields: tuple[str, ...], rows: list[dict]) -> None:
    """Write spreadsheet-friendly UTF-8 BOM CSV via an atomic replacement."""
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    with temporary.open("x", encoding="utf-8-sig", newline="") as handle:
        try:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
        except BaseException:
            handle.close()
            temporary.unlink(missing_ok=True)
            raise
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def write_sheets(directory: Path, records: list[dict]) -> None:
    """Include only attempted observations, never invent scores or pending outputs.

    The active run owns these sheets until it stops. Review after completion or
    stop; each subsequent run has another directory and cannot overwrite reviews.
    """
    results, evaluation = [], []
    for record in records:
        keys = {key: record[key] for key in ("run_id", "case_id", "experiment", "recipe_id", "status")}
        model = record["model_result"]
        results.append({**keys, "can_revise": model["can_revise"] if model else "",
                        "reason": model["reason"] if model else record["error"],
                        "artifact": f"{record['case_id']}.json"})
        status = record["status"]
        scores = {key: "" if status == "revised" or
                  (status == "refused" and key == "decision_validity") else "N/A"
                  for key in SCORES}
        evaluation.append({**keys, **scores, "reviewer": "", "rubric_version": "",
                           "notes": ""})
    keys = ("run_id", "case_id", "experiment", "recipe_id", "status")
    _write_csv(directory / "results.csv", keys + ("can_revise", "reason", "artifact"), results)
    _write_csv(directory / "evaluation.csv", keys + SCORES + ("reviewer", "rubric_version", "notes"), evaluation)
