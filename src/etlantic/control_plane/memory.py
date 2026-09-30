# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""In-memory control-plane fakes with tenant/workspace isolation."""

from __future__ import annotations

import hashlib
import json
import threading
import uuid
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, cast

from etlantic.control_plane.errors import ControlPlaneError
from etlantic.control_plane.models import (
    AcceptReceipt,
    AcceptResult,
    ControlPlaneContext,
    ControlPlaneEvent,
)
from etlantic.control_plane.protocols import AuthzDecision, DefinitionResolution
from etlantic.control_plane.redaction import (
    redact_control_plane_payload,
    redact_or_preserve_execution_envelope,
)


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _scope(ctx: ControlPlaneContext) -> tuple[str, str]:
    return ctx.scope_key


def _idem_key(
    ctx: ControlPlaneContext,
    idempotency_key: str,
    *,
    operation: str,
) -> tuple[str, str, str, str, str]:
    """ADR-016 scoped idempotency tuple."""
    return (
        ctx.tenant.tenant_id,
        ctx.workspace.workspace_id,
        ctx.principal.subject,
        operation,
        idempotency_key,
    )


def _new_idempotent_event_map() -> dict[
    tuple[str, str, str], tuple[str, dict[str, Any], ControlPlaneEvent]
]:
    return {}


@dataclass
class MemoryAuthorizer:
    """Deny-by-default authorizer with explicit (tenant, workspace, action) grants.

    Grants are scoped; a grant never crosses tenants or workspaces.
    """

    # (tenant_id, workspace_id, action) → allow
    grants: set[tuple[str, str, str]] = field(default_factory=set)
    # Optional per-resource denies that force forbidden disclosure in-scope.
    forbidden_resources: set[tuple[str, str, str, str]] = field(default_factory=set)

    def grant(self, ctx: ControlPlaneContext, action: str) -> None:
        self.grants.add((ctx.tenant.tenant_id, ctx.workspace.workspace_id, action))

    def authorize(
        self,
        ctx: ControlPlaneContext,
        action: str,
        resource: str,
    ) -> AuthzDecision:
        key = (ctx.tenant.tenant_id, ctx.workspace.workspace_id, action)
        forbid = (
            ctx.tenant.tenant_id,
            ctx.workspace.workspace_id,
            action,
            resource,
        )
        if forbid in self.forbidden_resources:
            return AuthzDecision(
                allowed=False,
                reason="action denied for resource",
                disclosure="forbidden",
            )
        if key in self.grants:
            return AuthzDecision(allowed=True, reason="granted")
        return AuthzDecision(
            allowed=False,
            reason="not authorized",
            disclosure="not_found",
        )


@dataclass
class MemoryDefinitionRepository:
    """In-memory definition store keyed by (tenant, workspace, definition_id)."""

    _docs: dict[tuple[str, str, str], dict[str, Any]] = field(default_factory=dict)
    _revisions: dict[tuple[str, str, str], dict[str, dict[str, Any]]] = field(
        default_factory=lambda: dict[tuple[str, str, str], dict[str, dict[str, Any]]]()
    )
    _lock: threading.RLock = field(default_factory=threading.RLock)

    def get(self, ctx: ControlPlaneContext, definition_id: str) -> Mapping[str, Any]:
        key = (*_scope(ctx), definition_id)
        with self._lock:
            try:
                return deepcopy(self._docs[key])
            except KeyError as exc:
                raise ControlPlaneError.not_found(
                    f"Definition {definition_id!r} not found"
                ) from exc

    def list(self, ctx: ControlPlaneContext) -> Sequence[str]:
        tenant_id, workspace_id = _scope(ctx)
        with self._lock:
            return sorted(
                def_id
                for (t, w, def_id) in self._docs
                if t == tenant_id and w == workspace_id
            )

    def resolve_revision(
        self,
        ctx: ControlPlaneContext,
        definition_id: str,
        selector: str,
    ) -> DefinitionResolution:
        """Resolve an immutable in-memory snapshot by selector or content id."""
        key = (*_scope(ctx), definition_id)
        with self._lock:
            revisions: dict[str, dict[str, Any]] = self._revisions.get(key, {})
            if selector == "current":
                revision_id = next(reversed(revisions), None)
            else:
                revision_id = selector if selector in revisions else None
            if revision_id is None:
                raise ControlPlaneError.not_found(
                    "Definition revision was not found",
                    extensions={"definition_id": definition_id},
                )
            return DefinitionResolution(
                revision_id=revision_id,
                document=deepcopy(revisions[revision_id]),
            )

    def put(
        self,
        ctx: ControlPlaneContext,
        definition_id: str,
        document: Mapping[str, Any],
    ) -> None:
        key = (*_scope(ctx), definition_id)
        document_copy = deepcopy(dict(document))
        revision_digest = hashlib.sha256(
            json.dumps(
                document_copy,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()
        revision_id = f"defrev-{revision_digest}"
        with self._lock:
            self._docs[key] = document_copy
            revisions = self._revisions.setdefault(key, {})
            # Re-inserting an earlier content digest is a new current selection
            # even though its immutable revision id and payload are unchanged.
            revisions.pop(revision_id, None)
            revisions[revision_id] = document_copy


@dataclass
class MemorySubmissionStore:
    """In-memory durable acceptance with ADR-016 scoped idempotency keys.

    Also tracks accepted run records for status/cancel observation. Acceptance
    is durable store commit only — no pipeline execution and no BackgroundTasks.
    """

    _by_id: dict[tuple[str, str, str, str, str], AcceptReceipt] = field(
        default_factory=dict
    )
    _payloads: dict[tuple[str, str, str, str, str], dict[str, Any]] = field(
        default_factory=dict
    )
    _runs: dict[tuple[str, str, str], dict[str, Any]] = field(default_factory=dict)
    _accepted_queue: list[tuple[str, str, str]] = field(default_factory=list)
    _lock: threading.RLock = field(default_factory=threading.RLock)

    def lookup_idempotency(
        self,
        ctx: ControlPlaneContext,
        idempotency_key: str,
        *,
        operation: str = "run.submit",
    ) -> AcceptReceipt | None:
        key = _idem_key(ctx, idempotency_key, operation=operation)
        with self._lock:
            receipt = self._by_id.get(key)
            return deepcopy(receipt) if receipt is not None else None

    def lookup_idempotency_payload(
        self,
        ctx: ControlPlaneContext,
        idempotency_key: str,
        *,
        operation: str = "run.submit",
    ) -> Mapping[str, Any] | None:
        key = _idem_key(ctx, idempotency_key, operation=operation)
        with self._lock:
            payload = self._payloads.get(key)
            return deepcopy(payload) if payload is not None else None

    def accept(
        self,
        ctx: ControlPlaneContext,
        *,
        idempotency_key: str,
        payload: Mapping[str, Any],
        resource_type: str = "run",
        resource_id: str | None = None,
        submission_id: str | None = None,
        operation: str = "run.submit",
    ) -> AcceptResult:
        key = _idem_key(ctx, idempotency_key, operation=operation)
        safe_payload = redact_control_plane_payload(deepcopy(dict(payload)))
        if not isinstance(safe_payload, dict):
            safe_payload = {}
        execution_envelope = payload.get("execution_envelope")
        if isinstance(execution_envelope, str):
            safe_payload["execution_envelope"] = redact_or_preserve_execution_envelope(
                execution_envelope
            )
        with self._lock:
            existing = self._by_id.get(key)
            if existing is not None:
                prior = self._payloads[key]
                if prior != safe_payload:
                    raise ControlPlaneError.conflict(
                        "Idempotency key reuse with a different payload",
                        extensions={"idempotency_key": idempotency_key},
                    )
                if (
                    submission_id is not None
                    and existing.submission_id != submission_id
                ):
                    raise ControlPlaneError.conflict(
                        "Idempotency key is bound to a different submission"
                    )
                return AcceptResult(receipt=deepcopy(existing), created=False)

            acceptance_id = f"acc-{uuid.uuid4().hex[:16]}"
            submission_id = submission_id or f"sub-{uuid.uuid4().hex[:16]}"
            if any(
                receipt.submission_id == submission_id
                for receipt in self._by_id.values()
            ):
                raise ControlPlaneError.conflict(
                    "submission_id is already bound to an acceptance"
                )
            run_id = resource_id or submission_id
            created = _utcnow_iso()
            receipt = AcceptReceipt(
                acceptance_id=acceptance_id,
                submission_id=submission_id,
                tenant_id=ctx.tenant.tenant_id,
                workspace_id=ctx.workspace.workspace_id,
                idempotency_key=idempotency_key,
                created_at=created,
                resource_type=resource_type,
                resource_id=run_id,
            )
            self._by_id[key] = receipt
            self._payloads[key] = deepcopy(safe_payload)
            run_key = (*_scope(ctx), run_id)
            self._runs[run_key] = {
                "run_id": run_id,
                "submission_id": submission_id,
                "acceptance_id": acceptance_id,
                "status": "accepted",
                "tenant_id": ctx.tenant.tenant_id,
                "workspace_id": ctx.workspace.workspace_id,
                "definition_id": safe_payload.get("definition_id"),
                "created_at": created,
                "updated_at": created,
                "idempotency_key": idempotency_key,
                "resource_type": resource_type,
            }
            self._accepted_queue.append(run_key)
            return AcceptResult(receipt=deepcopy(receipt), created=True)

    def get_run(self, ctx: ControlPlaneContext, run_id: str) -> dict[str, Any]:
        """Return scoped run status metadata (raises KeyError when absent)."""
        key = (*_scope(ctx), run_id)
        with self._lock:
            try:
                return deepcopy(self._runs[key])
            except KeyError as exc:
                raise KeyError(run_id) from exc

    def cancel_run(
        self, ctx: ControlPlaneContext, run_id: str
    ) -> tuple[dict[str, Any], bool]:
        """Mark an accepted run as cancel_requested (observation only).

        Returns ``(record, changed)`` where ``changed`` is True only on the
        first transition to ``cancel_requested``.
        """
        key = (*_scope(ctx), run_id)
        with self._lock:
            try:
                record = self._runs[key]
            except KeyError as exc:
                raise KeyError(run_id) from exc
            changed = False
            if record["status"] == "accepted":
                record["status"] = "cancel_requested"
                record["updated_at"] = _utcnow_iso()
                changed = True
            return deepcopy(record), changed

    def poll_accepted(
        self, ctx: ControlPlaneContext, *, limit: int = 1
    ) -> Sequence[dict[str, Any]]:
        """Return accepted jobs for an external worker poller (no execution).

        Results are filtered to ``ctx`` tenant/workspace scope.
        """
        if limit < 1:
            return ()
        tenant_id, workspace_id = _scope(ctx)
        with self._lock:
            out: list[dict[str, Any]] = []
            for key in list(self._accepted_queue):
                if key[0] != tenant_id or key[1] != workspace_id:
                    continue
                record = self._runs.get(key)
                if record is None or record["status"] != "accepted":
                    continue
                out.append(deepcopy(record))
                if len(out) >= limit:
                    break
            return out


@dataclass
class MemoryEventStore:
    """In-memory append-only event log scoped by tenant/workspace."""

    _events: dict[tuple[str, str], list[ControlPlaneEvent]] = field(
        default_factory=dict
    )
    _idempotent_events: dict[
        tuple[str, str, str], tuple[str, dict[str, Any], ControlPlaneEvent]
    ] = field(default_factory=_new_idempotent_event_map)
    _lock: threading.RLock = field(default_factory=threading.RLock)

    def append(
        self,
        ctx: ControlPlaneContext,
        *,
        kind: str,
        payload: Mapping[str, Any] | None = None,
    ) -> ControlPlaneEvent:
        scope = _scope(ctx)
        safe_payload = redact_control_plane_payload(deepcopy(dict(payload or {})))
        if not isinstance(safe_payload, dict):
            safe_payload = {}
        with self._lock:
            bucket = self._events.setdefault(scope, [])
            sequence = len(bucket) + 1
            cursor = hashlib.sha256(
                f"{scope[0]}:{scope[1]}:{sequence}".encode()
            ).hexdigest()[:24]
            event = ControlPlaneEvent(
                event_id=f"evt-{uuid.uuid4().hex[:16]}",
                sequence=sequence,
                cursor=cursor,
                kind=kind,
                created_at=_utcnow_iso(),
                payload=safe_payload,
                correlation_id=(
                    ctx.correlation_key.value
                    if ctx.correlation_key is not None
                    else None
                ),
                scope={
                    "tenant_id": ctx.tenant.tenant_id,
                    "workspace_id": ctx.workspace.workspace_id,
                },
            )
            bucket.append(event)
            return deepcopy(event)

    def append_once(
        self,
        ctx: ControlPlaneContext,
        *,
        event_key: str,
        kind: str,
        payload: Mapping[str, Any] | None = None,
    ) -> ControlPlaneEvent:
        """Append once per trusted scope and key; reject key reuse with new content."""
        if not event_key.strip():
            raise ValueError("event_key must not be empty")
        scope = _scope(ctx)
        redacted_payload = redact_control_plane_payload(deepcopy(dict(payload or {})))
        safe_payload = (
            cast(dict[str, Any], redacted_payload)
            if isinstance(redacted_payload, dict)
            else {}
        )
        scoped_key = (*scope, event_key)
        with self._lock:
            previous = self._idempotent_events.get(scoped_key)
            if previous is not None:
                previous_kind, previous_payload, event = previous
                if previous_kind != kind or previous_payload != safe_payload:
                    raise ControlPlaneError.conflict(
                        "Event idempotency key was reused with different content",
                        extensions={"operation": "event.append_once"},
                    )
                return deepcopy(event)
            event = self.append(ctx, kind=kind, payload=safe_payload)
            self._idempotent_events[scoped_key] = (
                kind,
                deepcopy(safe_payload),
                event,
            )
            return deepcopy(event)

    def list_after_cursor(
        self,
        ctx: ControlPlaneContext,
        cursor: str | None,
        *,
        limit: int = 100,
    ) -> Sequence[ControlPlaneEvent]:
        if limit < 1:
            return ()
        with self._lock:
            bucket = self._events.get(_scope(ctx), [])
            start = 0
            if cursor is not None:
                found = False
                for i, ev in enumerate(bucket):
                    if ev.cursor == cursor:
                        start = i + 1
                        found = True
                        break
                if not found:
                    raise ControlPlaneError.gone(
                        "SSE cursor expired or unknown; reconnect without "
                        "cursor (or Last-Event-ID) to replay from the beginning",
                        extensions={
                            "hint": "omit_cursor_or_last_event_id",
                            "schema": "etlantic.control_plane.sse_cursor/1",
                        },
                    )
            items = [deepcopy(ev) for ev in bucket[start : start + limit]]
            return items


__all__ = [
    "MemoryAuthorizer",
    "MemoryDefinitionRepository",
    "MemoryEventStore",
    "MemorySubmissionStore",
]
