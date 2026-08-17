"""Snapshot-to-stream handoff protocol (046-H)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from etlantic.streaming.diagnostics import str_diagnostic


@dataclass(frozen=True, slots=True)
class SnapshotCut:
    """Bounded snapshot identity plus stream cutover position."""

    snapshot_identity: str
    stream_position: str
    schema_identity: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_identity": self.snapshot_identity,
            "stream_position": self.stream_position,
            "schema_identity": self.schema_identity,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> SnapshotCut:
        return cls(
            snapshot_identity=str(data["snapshot_identity"]),
            stream_position=str(data["stream_position"]),
            schema_identity=str(data["schema_identity"]),
        )


@dataclass(frozen=True, slots=True)
class HandoffResult:
    """Gap/overlap detection for concurrent snapshot and stream cutover."""

    accepted: bool
    gap_detected: bool
    overlap_detected: bool
    snapshot_identity: str
    stream_position: str
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "gap_detected": self.gap_detected,
            "overlap_detected": self.overlap_detected,
            "snapshot_identity": self.snapshot_identity,
            "stream_position": self.stream_position,
            "message": self.message,
        }


def evaluate_handoff(
    *,
    snapshot: SnapshotCut,
    first_stream_position: str,
    last_snapshot_position: str,
    concurrent_schema_identity: str | None = None,
) -> HandoffResult:
    """Detect unreported gap or overlap between snapshot and stream.

    Positions are opaque totally-ordered strings compared lexicographically
    (in-memory fixtures use zero-padded integers). Schema mismatch during
    concurrent change fails closed.
    """
    if (
        concurrent_schema_identity is not None
        and concurrent_schema_identity != snapshot.schema_identity
    ):
        return HandoffResult(
            accepted=False,
            gap_detected=False,
            overlap_detected=False,
            snapshot_identity=snapshot.snapshot_identity,
            stream_position=snapshot.stream_position,
            message="concurrent schema change during snapshot-to-stream handoff",
        )
    gap = first_stream_position > snapshot.stream_position and (
        last_snapshot_position < snapshot.stream_position
    )
    # Gap: stream starts after the declared cut with a hole after snapshot.
    if first_stream_position > snapshot.stream_position:
        gap = True
    overlap = first_stream_position < snapshot.stream_position
    if gap:
        return HandoffResult(
            accepted=False,
            gap_detected=True,
            overlap_detected=False,
            snapshot_identity=snapshot.snapshot_identity,
            stream_position=snapshot.stream_position,
            message="unreported gap between snapshot and stream cutover",
        )
    if overlap:
        return HandoffResult(
            accepted=False,
            gap_detected=False,
            overlap_detected=True,
            snapshot_identity=snapshot.snapshot_identity,
            stream_position=snapshot.stream_position,
            message="unreported overlap between snapshot and stream cutover",
        )
    return HandoffResult(
        accepted=True,
        gap_detected=False,
        overlap_detected=False,
        snapshot_identity=snapshot.snapshot_identity,
        stream_position=snapshot.stream_position,
    )


def handoff_failure_diagnostic(result: HandoffResult) -> Any:
    """Map a rejected handoff to PMSTR200/201."""
    if result.gap_detected:
        return str_diagnostic(
            "handoff_gap",
            result.message or "snapshot-to-stream gap",
            path=("streaming", "handoff"),
            metadata=result.to_dict(),
        )
    if result.overlap_detected:
        return str_diagnostic(
            "handoff_overlap",
            result.message or "snapshot-to-stream overlap",
            path=("streaming", "handoff"),
            metadata=result.to_dict(),
        )
    return str_diagnostic(
        "unsupported_semantics",
        result.message or "snapshot-to-stream handoff rejected",
        path=("streaming", "handoff"),
        metadata=result.to_dict(),
    )
