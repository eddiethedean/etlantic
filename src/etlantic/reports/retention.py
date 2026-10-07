"""Shared managed-run retention metadata keys and state vocabulary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from etlantic.reports.model import PipelineRunReport


ARTIFACT_STORAGE_RUN_ID_KEY = "etlantic.control_plane.artifact_storage_run_id"


def artifact_storage_run_id(report: PipelineRunReport) -> str:
    """Resolve managed storage identity, preserving legacy ordinary reports."""
    value = report.metadata.get(ARTIFACT_STORAGE_RUN_ID_KEY, report.run_id)
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Artifact storage run identity is invalid")
    return value


@dataclass(frozen=True, slots=True)
class ArtifactRetentionResult:
    """Outcome of one bounded durable-artifact cleanup pass."""

    enabled: bool
    processed_reports: int = 0
    completed_reports: int = 0
    deleted_artifacts: int = 0
    failed_artifacts: int = 0
    remaining_candidates: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "processed_reports": self.processed_reports,
            "completed_reports": self.completed_reports,
            "deleted_artifacts": self.deleted_artifacts,
            "failed_artifacts": self.failed_artifacts,
            "remaining_candidates": self.remaining_candidates,
        }


RUN_ARTIFACT_RETENTION_STATE_KEY = "etlantic.control_plane.artifact_retention"
RUN_ARTIFACT_RETENTION_DETAILS_KEY = "etlantic.control_plane.artifact_retention_details"
TERMINAL_RUN_STATUSES = frozenset(
    {"succeeded", "failed", "cancelled", "timed_out", "partial"}
)

__all__ = [
    "ARTIFACT_STORAGE_RUN_ID_KEY",
    "RUN_ARTIFACT_RETENTION_DETAILS_KEY",
    "RUN_ARTIFACT_RETENTION_STATE_KEY",
    "TERMINAL_RUN_STATUSES",
    "ArtifactRetentionResult",
    "artifact_storage_run_id",
]
