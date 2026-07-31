"""Outbound OpenLineage-compatible event export (CP2 / 040-L).

Export is one-way from ETLantic identities. Transport failures, retries, or
remote acknowledgements must never mutate registry records, revisions, aliases,
promotions, or baselines (ADR-017).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, MutableSequence, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

from etlantic.control_plane.redaction import redact_control_plane_payload


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


@runtime_checkable
class OpenLineageTransport(Protocol):
    """Minimal transport that accepts an OpenLineage-like event dict."""

    def emit(self, event: Mapping[str, Any]) -> None:
        """Send one outbound event. May raise on transport failure."""
        ...


@dataclass
class FakeTransport:
    """In-memory transport for tests (records events; may be configured to fail)."""

    events: MutableSequence[dict[str, Any]] = field(default_factory=list)
    fail_with: BaseException | None = None

    def emit(self, event: Mapping[str, Any]) -> None:
        if self.fail_with is not None:
            raise self.fail_with
        self.events.append(deepcopy(dict(event)))


def build_run_event(
    *,
    plan_identity: Mapping[str, Any],
    run_event: Mapping[str, Any],
    namespace: str = "etlantic",
    producer: str = "https://github.com/eddiethedean/etlantic",
    event_type: str | None = None,
) -> dict[str, Any]:
    """Map plan identity + run metadata to an OpenLineage-compatible event.

    Shapes intentionally stay lightweight and dependency-free. Content is
    secret-free metadata only — never source rows or resolved secrets.
    """
    plan = redact_control_plane_payload(dict(plan_identity))
    run = redact_control_plane_payload(dict(run_event))
    if not isinstance(plan, dict):
        plan = {}
    if not isinstance(run, dict):
        run = {}

    job_name = str(
        plan.get("logical_id")
        or plan.get("plan_id")
        or plan.get("name")
        or "unknown-plan"
    )
    run_id = str(run.get("run_id") or run.get("attempt_id") or run.get("id") or "")
    event_time = str(run.get("event_time") or run.get("observed_at") or _utcnow_iso())
    resolved_type = str(
        event_type or run.get("event_type") or run.get("status") or "START"
    ).upper()
    if resolved_type in {"ACCEPTED", "STARTED"}:
        resolved_type = "START"
    elif resolved_type in {"SUCCEEDED", "SUCCESS", "COMPLETED"}:
        resolved_type = "COMPLETE"
    elif resolved_type in {"FAILED", "ERROR", "FAIL"}:
        resolved_type = "FAIL"
    elif resolved_type in {"ABORTED", "CANCELLED", "CANCELED"}:
        resolved_type = "ABORT"
    elif resolved_type not in {"START", "RUNNING", "COMPLETE", "ABORT", "FAIL"}:
        resolved_type = "OTHER"

    facets: dict[str, Any] = {
        "etlantic": {
            "_producer": producer,
            "_schemaURL": "https://etlantic.readthedocs.io/",
            "tenant_id": plan.get("tenant_id") or run.get("tenant_id"),
            "workspace_id": plan.get("workspace_id") or run.get("workspace_id"),
            "revision_id": plan.get("revision_id"),
            "content_fingerprint": plan.get("content_fingerprint"),
            "environment": plan.get("environment") or run.get("environment"),
        }
    }
    # Drop null facet values for cleaner payloads.
    facets["etlantic"] = {
        key: value for key, value in facets["etlantic"].items() if value is not None
    }

    return {
        "eventType": resolved_type,
        "eventTime": event_time,
        "run": {
            "runId": run_id or f"run-{event_time}",
            "facets": {},
        },
        "job": {
            "namespace": namespace,
            "name": job_name,
            "facets": facets,
        },
        "inputs": list(run.get("inputs") or []),
        "outputs": list(run.get("outputs") or []),
        "producer": producer,
        "schemaURL": "https://openlineage.io/spec/2-0-2/OpenLineage.json#/$defs/RunEvent",
    }


@dataclass
class OpenLineageExporter:
    """Outbound exporter. Never mutates a registry provider.

    Callers that want side effects on *success* may pass ``on_success``; that
    hook is **not** invoked when transport raises. Registry mutators must not
    be wired into failure paths.
    """

    transport: OpenLineageTransport
    namespace: str = "etlantic"
    producer: str = "https://github.com/eddiethedean/etlantic"
    on_success: Callable[[Mapping[str, Any]], None] | None = None

    def export_run(
        self,
        *,
        plan_identity: Mapping[str, Any],
        run_event: Mapping[str, Any],
        event_type: str | None = None,
    ) -> dict[str, Any]:
        """Build and emit one run event. Transport errors propagate unchanged."""
        event = build_run_event(
            plan_identity=plan_identity,
            run_event=run_event,
            namespace=self.namespace,
            producer=self.producer,
            event_type=event_type,
        )
        # Emit first; never call on_success (or any registry mutator) on failure.
        self.transport.emit(event)
        if self.on_success is not None:
            self.on_success(event)
        return event

    def export_many(
        self,
        items: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]],
    ) -> list[dict[str, Any]]:
        """Emit a batch; stop on first transport failure without mutating registry."""
        out: list[dict[str, Any]] = []
        for plan_identity, run_event in items:
            out.append(
                self.export_run(plan_identity=plan_identity, run_event=run_event)
            )
        return out


__all__ = [
    "FakeTransport",
    "OpenLineageExporter",
    "OpenLineageTransport",
    "build_run_event",
]
