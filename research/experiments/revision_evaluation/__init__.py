# AI-assisted with Codex, 2026-11-20; reviewed by Soohyun An
"""Public v1 artifact contract for evaluating the current dish Revision pipeline.

The package exports contract types only so fixture consumers do not depend on a
future Runner implementation.
"""

from .contract import (
    ARTIFACT_SCHEMAS,
    METADATA_SCHEMA,
    OBSERVATION_SCHEMA,
    SUMMARY_SCHEMA,
    ContractVersionError,
    validate_artifact,
)

__all__ = [
    "ARTIFACT_SCHEMAS",
    "METADATA_SCHEMA",
    "OBSERVATION_SCHEMA",
    "SUMMARY_SCHEMA",
    "ContractVersionError",
    "validate_artifact",
]
