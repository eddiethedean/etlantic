"""In-memory control-plane fakes with tenant/workspace isolation."""

from __future__ import annotations

import hashlib
import threading
import uuid
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from etlantic.control_plane.errors import ControlPlaneError
from etlantic.control_plane.models import (
    AcceptReceipt,
    ControlPlaneContext,
    ControlPlaneEvent,
)
from etlantic.control_plane.protocols import AuthzDecision


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _scope(ctx: ControlPlaneContext) -> tuple[str, str]:
    return ctx.scope_key


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

    def get(self, ctx: ControlPlaneContext, definition_id: str) -> Mapping[str, Any]:
        key = (*_scope(ctx), definition_id)
        try:
            return deepcopy(self._docs[key])
        except KeyError as exc:
            raise KeyError(definition_id) from exc

    def list(self, ctx: ControlPlaneContext) -> Sequence[str]:
        tenant_id, workspace_id = _scope(ctx)
        return sorted(
            def_id
            for (t, w, def_id) in self._docs
            if t == tenant_id and w == workspace_id
        )

    def put(
        self,
        ctx: ControlPlaneContext,
        definition_id: str,
        document: Mapping[str, Any],
    ) -> None:
        key = (*_scope(ctx), definition_id)
        self._docs[key] = deepcopy(dict(document))


@dataclass
class MemorySubmissionStore:
    """In-memory durable acceptance with scoped idempotency keys.

    Also tracks accepted run records for status/cancel observation. Acceptance
    is durable store commit only — no pipeline execution and no BackgroundTasks.
    """

    _by_id: dict[tuple[str, str, str], AcceptReceipt] = field(default_factory=dict)
    _payloads: dict[tuple[str, str, str], dict[str, Any]] = field(default_factory=dict)
    _runs: dict[tuple[str, str, str], dict[str, Any]] = field(default_factory=dict)
    _accepted_queue: list[tuple[str, str, str]] = field(default_factory=list)
    _lock: threading.RLock = field(default_factory=threading.RLock)

    def lookup_idempotency(
        self,
        ctx: ControlPlaneContext,
        idempotency_key: str,
    ) -> AcceptReceipt | None:
        key = (*_scope(ctx), idempotency_key)
        with self._lock:
            receipt = self._by_id.get(key)
            return deepcopy(receipt) if receipt is not None else None

    def accept(
        self,
        ctx: ControlPlaneContext,
        *,
        idempotency_key: str,
        payload: Mapping[str, Any],
        resource_type: str = "run",
        resource_id: str | None = None,
    ) -> AcceptReceipt:
        key = (*_scope(ctx), idempotency_key)
        with self._lock:
            existing = self._by_id.get(key)
            if existing is not None:
                prior = self._payloads[key]
                if prior != dict(payload):
                    raise ControlPlaneError.conflict(
                        "Idempotency key reuse with a different payload",
                        extensions={"idempotency_key": idempotency_key},
                    )
                return deepcopy(existing)

            acceptance_id = f"acc-{uuid.uuid4().hex[:16]}"
            submission_id = f"sub-{uuid.uuid4().hex[:16]}"
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
            self._payloads[key] = dict(payload)
            run_key = (*_scope(ctx), run_id)
            self._runs[run_key] = {
                "run_id": run_id,
                "submission_id": submission_id,
                "acceptance_id": acceptance_id,
                "status": "accepted",
                "tenant_id": ctx.tenant.tenant_id,
                "workspace_id": ctx.workspace.workspace_id,
                "definition_id": payload.get("definition_id"),
                "created_at": created,
                "updated_at": created,
                "idempotency_key": idempotency_key,
                "resource_type": resource_type,
            }
            self._accepted_queue.append(run_key)
            return deepcopy(receipt)

    def get_run(self, ctx: ControlPlaneContext, run_id: str) -> dict[str, Any]:
        """Return scoped run status metadata (raises KeyError when absent)."""
        key = (*_scope(ctx), run_id)
        with self._lock:
            try:
                return deepcopy(self._runs[key])
            except KeyError as exc:
                raise KeyError(run_id) from exc

    def cancel_run(self, ctx: ControlPlaneContext, run_id: str) -> dict[str, Any]:
        """Mark an accepted run as cancel_requested (observation only)."""
        key = (*_scope(ctx), run_id)
        with self._lock:
            try:
                record = self._runs[key]
            except KeyError as exc:
                raise KeyError(run_id) from exc
            if record["status"] in ("accepted", "cancel_requested"):
                record["status"] = "cancel_requested"
                record["updated_at"] = _utcnow_iso()
            return deepcopy(record)

    def poll_accepted(self, *, limit: int = 1) -> Sequence[dict[str, Any]]:
        """Return accepted jobs for an external worker poller (no execution)."""
        if limit < 1:
            return ()
        with self._lock:
            out: list[dict[str, Any]] = []
            for key in list(self._accepted_queue):
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

    def append(
        self,
        ctx: ControlPlaneContext,
        *,
        kind: str,
        payload: Mapping[str, Any] | None = None,
    ) -> ControlPlaneEvent:
        scope = _scope(ctx)
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
            payload=dict(payload or {}),
        )
        bucket.append(event)
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
        return [deepcopy(ev) for ev in bucket[start : start + limit]]


__all__ = [
    "MemoryAuthorizer",
    "MemoryDefinitionRepository",
    "MemoryEventStore",
    "MemorySubmissionStore",
]
