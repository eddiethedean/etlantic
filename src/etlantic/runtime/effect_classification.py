"""Shared effect classification for failed managed execution reports."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal, cast

from etlantic.reports.model import PipelineRunReport

FailedEffectStatus = Literal["none", "committed", "unknown"]


def classify_failed_report_effect(report: PipelineRunReport) -> FailedEffectStatus:
    """Classify effects evidenced by a failed report, failing closed on ambiguity."""
    metadata = report.metadata
    execution_raw = metadata.get("etlantic.control_plane.execution")
    execution: Mapping[str, object] = {}
    if isinstance(execution_raw, Mapping):
        execution = cast(Mapping[str, object], execution_raw)
    execution_effect_status = execution.get("effect_status")
    unknown_publications = metadata.get("etlantic.unknown_publications")
    outbound_events = metadata.get("etlantic.outbound_events")
    cleanup_obligations = metadata.get("etlantic.cleanup_obligations")
    raw_receipts = metadata.get("etlantic.publication_receipts")
    receipts: list[Mapping[str, object]] = []
    if isinstance(raw_receipts, (list, tuple)):
        values = cast(list[object] | tuple[object, ...], raw_receipts)
        receipts = [
            cast(Mapping[str, object], item)
            for item in values
            if isinstance(item, Mapping)
        ]
    if (
        execution_effect_status == "unknown"
        or unknown_publications
        or outbound_events
        or cleanup_obligations
        or any(item.get("status") == "unknown" for item in receipts)
    ):
        return "unknown"
    if any(item.get("status") == "committed" for item in receipts):
        return "committed"
    return "none"
