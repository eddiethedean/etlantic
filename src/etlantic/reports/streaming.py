"""Continuous-run report snapshot (046-R). Namespaced metadata only; no payloads."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from etlantic.streaming.envelope import assert_no_payload

STREAM_OPS_KEY = "etlantic.streaming.operations"
STREAM_TRIGGER_KEY = "etlantic.streaming.trigger"


@dataclass(frozen=True, slots=True)
class StreamOperationsSnapshot:
    """Watermark, lag, backpressure, and rejected-record identifiers."""

    status: str = "running"
    watermark: str | None = None
    lateness: str | None = None
    lag: int | None = None
    backpressure: str | None = None
    replay_window: str | None = None
    dedupe_horizon: str | None = None
    state_version: str | None = None
    provider_guarantee: str | None = None
    rejected_record_count: int = 0
    rejected_record_ids: tuple[str, ...] = ()
    snapshot_identity: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "status": self.status,
            "watermark": self.watermark,
            "lateness": self.lateness,
            "lag": self.lag,
            "backpressure": self.backpressure,
            "replay_window": self.replay_window,
            "dedupe_horizon": self.dedupe_horizon,
            "state_version": self.state_version,
            "provider_guarantee": self.provider_guarantee,
            "rejected_record_count": self.rejected_record_count,
            "rejected_record_ids": list(self.rejected_record_ids),
            "snapshot_identity": self.snapshot_identity,
        }
        assert_no_payload(payload)
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> StreamOperationsSnapshot:
        assert_no_payload(data)
        ids = data.get("rejected_record_ids") or ()
        return cls(
            status=str(data.get("status") or "running"),
            watermark=_opt_str(data.get("watermark")),
            lateness=_opt_str(data.get("lateness")),
            lag=_opt_int(data.get("lag")),
            backpressure=_opt_str(data.get("backpressure")),
            replay_window=_opt_str(data.get("replay_window")),
            dedupe_horizon=_opt_str(data.get("dedupe_horizon")),
            state_version=_opt_str(data.get("state_version")),
            provider_guarantee=_opt_str(data.get("provider_guarantee")),
            rejected_record_count=int(data.get("rejected_record_count") or 0),
            rejected_record_ids=tuple(str(i) for i in ids),
            snapshot_identity=_opt_str(data.get("snapshot_identity")),
        )

    def as_metadata(self) -> dict[str, Any]:
        """Return a namespaced overlay safe for ``PipelineRunReport.metadata``."""
        return {STREAM_OPS_KEY: self.to_dict()}


def _opt_str(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _opt_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def attach_stream_operations(
    metadata: Mapping[str, Any] | None,
    snapshot: StreamOperationsSnapshot,
) -> dict[str, Any]:
    """Merge snapshot fields into report metadata (identifiers only)."""
    out = dict(metadata or {})
    out.update(snapshot.as_metadata())
    assert_no_payload(out)
    return out
