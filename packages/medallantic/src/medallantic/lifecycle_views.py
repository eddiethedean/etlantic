"""Layer-aware lifecycle views over normalized ETLantic events."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from etlantic.reports.model import PipelineRunReport
from etlantic.runtime.events import LifecycleEvent, SecurityEvent


def enrich_lifecycle_event(
    event: LifecycleEvent | SecurityEvent,
    layer_by_node: dict[str, str],
) -> LifecycleEvent | SecurityEvent:
    """Attach medallion layer annotation when step is known."""
    if not isinstance(event, LifecycleEvent):
        return event
    step = event.step_name
    layer = layer_by_node.get(step or "")
    if not layer:
        return event
    annotations = {**dict(event.annotations), "layer": layer}
    return LifecycleEvent(
        kind=event.kind,
        run_id=event.run_id,
        pipeline_id=event.pipeline_id,
        at=event.at,
        step_name=event.step_name,
        attempt=event.attempt,
        status=event.status,
        message=event.message,
        plan_id=event.plan_id,
        region_id=event.region_id,
        physical_unit=event.physical_unit,
        backend=event.backend,
        correlation_id=event.correlation_id,
        annotations=annotations,
        metadata=dict(event.metadata),
        schema_version=event.schema_version,
    )


def group_events_by_layer(
    events: list[LifecycleEvent | SecurityEvent],
    layer_by_node: dict[str, str],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        if isinstance(event, LifecycleEvent):
            enriched = enrich_lifecycle_event(event, layer_by_node)
            layer = str(enriched.annotations.get("layer") or "unknown")
            grouped[layer].append(enriched.to_dict())
        else:
            grouped["security"].append(event.to_dict())
    return dict(grouped)


def layer_run_summary(
    report: PipelineRunReport,
    layer_by_node: dict[str, str],
) -> dict[str, Any]:
    """Summarize run report steps grouped by medallion layer."""
    by_layer: dict[str, dict[str, int]] = defaultdict(
        lambda: {"total": 0, "succeeded": 0, "failed": 0, "skipped": 0}
    )
    for step in report.steps:
        layer = layer_by_node.get(step.step_name, "unknown")
        bucket = by_layer[layer]
        bucket["total"] += 1
        status = step.status.value
        if status in bucket:
            bucket[status] += 1
        elif status == "succeeded":
            bucket["succeeded"] += 1
        elif status == "failed":
            bucket["failed"] += 1
        elif status == "skipped":
            bucket["skipped"] += 1
    return {
        "run_id": report.run_id,
        "pipeline_id": report.pipeline_id,
        "status": report.status.value,
        "layers": dict(by_layer),
    }
