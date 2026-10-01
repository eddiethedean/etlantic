"""Shared managed-run retention metadata keys and state vocabulary."""

from dataclasses import dataclass
from typing import Any


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
    "RUN_ARTIFACT_RETENTION_DETAILS_KEY",
    "RUN_ARTIFACT_RETENTION_STATE_KEY",
    "TERMINAL_RUN_STATUSES",
    "ArtifactRetentionResult",
]
