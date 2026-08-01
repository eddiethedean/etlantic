"""Immutable control-plane identity, scope, and key types (CP1 / 039-I).

These models are FastAPI- and SQLModel-free. They carry server-derived
authority only — never credentials, resolved secrets, or source rows.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from etlantic.control_plane.redaction import redact_control_plane_payload

CONTROL_PLANE_CONTEXT_SCHEMA = "etlantic.control_plane.context/1"
ACCEPT_RECEIPT_SCHEMA = "etlantic.control_plane.accept_receipt/1"
CONTROL_PLANE_EVENT_SCHEMA = "etlantic.control_plane.event/1"
SSE_CURSOR_SCHEMA = "etlantic.control_plane.sse_cursor/1"

PrincipalKind = Literal["human", "workload", "service"]


@dataclass(frozen=True, slots=True)
class Principal:
    """Authenticated human or workload (issuer-qualified subject)."""

    subject: str
    issuer: str | None = None
    kind: PrincipalKind = "human"

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "issuer": self.issuer,
            "kind": self.kind,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Principal:
        raw_kind = str(data.get("kind") or "human")
        if raw_kind not in ("human", "workload", "service"):
            raise ValueError(f"unsupported principal kind: {raw_kind!r}")
        return cls(
            subject=str(data["subject"]),
            issuer=(str(data["issuer"]) if data.get("issuer") is not None else None),
            kind=raw_kind,  # type: ignore[arg-type]
        )


@dataclass(frozen=True, slots=True)
class TenantRef:
    """Top-level authorization and billing boundary (opaque id)."""

    tenant_id: str

    def to_dict(self) -> dict[str, Any]:
        return {"tenant_id": self.tenant_id}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> TenantRef:
        return cls(tenant_id=str(data["tenant_id"]))


@dataclass(frozen=True, slots=True)
class WorkspaceRef:
    """Tenant-owned authoring and operations namespace."""

    tenant_id: str
    workspace_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "workspace_id": self.workspace_id,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> WorkspaceRef:
        return cls(
            tenant_id=str(data["tenant_id"]),
            workspace_id=str(data["workspace_id"]),
        )


@dataclass(frozen=True, slots=True)
class EnvironmentRef:
    """Deployment / promotion slice (for example development or production)."""

    name: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> EnvironmentRef:
        return cls(name=str(data["name"]))


@dataclass(frozen=True, slots=True)
class SecurityDomain:
    """Data-handling and reuse boundary preserved across plans and artifacts."""

    domain_id: str

    def to_dict(self) -> dict[str, Any]:
        return {"domain_id": self.domain_id}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> SecurityDomain:
        return cls(domain_id=str(data["domain_id"]))


@dataclass(frozen=True, slots=True)
class CorrelationKey:
    """Opaque request-correlation identifier (logs, traces, events)."""

    value: str

    def to_dict(self) -> dict[str, Any]:
        return {"value": self.value}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CorrelationKey:
        return cls(value=str(data["value"]))


@dataclass(frozen=True, slots=True)
class IdempotencyKey:
    """Caller-scoped key for safely repeatable mutations."""

    value: str

    def to_dict(self) -> dict[str, Any]:
        return {"value": self.value}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> IdempotencyKey:
        return cls(value=str(data["value"]))


@dataclass(frozen=True, slots=True)
class ControlPlaneContext:
    """Immutable, server-derived request scope for control-plane operations.

    Path or body tenant claims never override this context. Serialization is
    secret-free by construction (refs and opaque keys only).
    """

    principal: Principal
    tenant: TenantRef
    workspace: WorkspaceRef
    environment: EnvironmentRef
    security_domain: SecurityDomain
    correlation_key: CorrelationKey | None = None
    idempotency_key: IdempotencyKey | None = None
    request_id: str | None = None

    def __post_init__(self) -> None:
        if self.workspace.tenant_id != self.tenant.tenant_id:
            raise ValueError(
                "workspace.tenant_id must match tenant.tenant_id "
                f"({self.workspace.tenant_id!r} != {self.tenant.tenant_id!r})"
            )

    @property
    def scope_key(self) -> tuple[str, str]:
        """Composite tenant/workspace key used by scoped stores."""
        return (self.tenant.tenant_id, self.workspace.workspace_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": CONTROL_PLANE_CONTEXT_SCHEMA,
            "principal": self.principal.to_dict(),
            "tenant": self.tenant.to_dict(),
            "workspace": self.workspace.to_dict(),
            "environment": self.environment.to_dict(),
            "security_domain": self.security_domain.to_dict(),
            "correlation_key": (
                self.correlation_key.to_dict() if self.correlation_key else None
            ),
            "idempotency_key": (
                self.idempotency_key.to_dict() if self.idempotency_key else None
            ),
            "request_id": self.request_id,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ControlPlaneContext:
        corr = data.get("correlation_key")
        idem = data.get("idempotency_key")
        return cls(
            principal=Principal.from_dict(data["principal"]),
            tenant=TenantRef.from_dict(data["tenant"]),
            workspace=WorkspaceRef.from_dict(data["workspace"]),
            environment=EnvironmentRef.from_dict(data["environment"]),
            security_domain=SecurityDomain.from_dict(data["security_domain"]),
            correlation_key=(
                CorrelationKey.from_dict(corr) if corr is not None else None
            ),
            idempotency_key=(
                IdempotencyKey.from_dict(idem) if idem is not None else None
            ),
            request_id=(
                str(data["request_id"]) if data.get("request_id") is not None else None
            ),
        )


@dataclass(frozen=True, slots=True)
class AcceptReceipt:
    """Durable acceptance record returned after a successful submit accept."""

    acceptance_id: str
    submission_id: str
    tenant_id: str
    workspace_id: str
    idempotency_key: str
    created_at: str
    status: Literal["accepted"] = "accepted"
    resource_type: str = "run"
    resource_id: str | None = None
    status_url: str | None = None
    events_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": ACCEPT_RECEIPT_SCHEMA,
            "acceptance_id": self.acceptance_id,
            "submission_id": self.submission_id,
            "tenant_id": self.tenant_id,
            "workspace_id": self.workspace_id,
            "idempotency_key": self.idempotency_key,
            "created_at": self.created_at,
            "status": self.status,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "status_url": self.status_url,
            "events_url": self.events_url,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> AcceptReceipt:
        status = str(data.get("status") or "accepted")
        if status != "accepted":
            raise ValueError(f"unsupported acceptance status: {status!r}")
        return cls(
            acceptance_id=str(data["acceptance_id"]),
            submission_id=str(data["submission_id"]),
            tenant_id=str(data["tenant_id"]),
            workspace_id=str(data["workspace_id"]),
            idempotency_key=str(data["idempotency_key"]),
            created_at=str(data["created_at"]),
            status="accepted",
            resource_type=str(data.get("resource_type") or "run"),
            resource_id=(
                str(data["resource_id"])
                if data.get("resource_id") is not None
                else None
            ),
            status_url=(
                str(data["status_url"]) if data.get("status_url") is not None else None
            ),
            events_url=(
                str(data["events_url"]) if data.get("events_url") is not None else None
            ),
        )


@dataclass(frozen=True, slots=True)
class AcceptResult:
    """Outcome of :meth:`~etlantic.control_plane.protocols.SubmissionStore.accept`.

    ``created`` is True only when a new acceptance row was written (first
    durable commit for the ADR-016 idempotency tuple). Idempotent replays
    return the original receipt with ``created=False``.
    """

    receipt: AcceptReceipt
    created: bool


@dataclass(frozen=True, slots=True)
class ControlPlaneEvent:
    """Ordered, tenant/workspace-scoped control-plane event envelope."""

    event_id: str
    sequence: int
    cursor: str
    kind: str
    created_at: str
    payload: Mapping[str, Any] | None = None
    correlation_id: str | None = None
    scope: Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = redact_control_plane_payload(dict(self.payload or {}))
        run_id = payload.get("run_id")
        return {
            "schema": CONTROL_PLANE_EVENT_SCHEMA,
            "event_id": self.event_id,
            "sequence": self.sequence,
            "cursor": self.cursor,
            "kind": self.kind,
            # Additive ADR aliases (dual-read friendly for 0.41 migration).
            "type": self.kind,
            "created_at": self.created_at,
            "occurred_at": self.created_at,
            "correlation_id": self.correlation_id,
            "scope": dict(self.scope) if self.scope is not None else None,
            "run_id": str(run_id) if run_id is not None else None,
            "payload": payload,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ControlPlaneEvent:
        kind = data.get("kind")
        if kind is None:
            kind = data.get("type")
        created_at = data.get("created_at")
        if created_at is None:
            created_at = data.get("occurred_at")
        if kind is None:
            raise ValueError("control-plane event requires kind or type")
        if created_at is None:
            raise ValueError("control-plane event requires created_at or occurred_at")
        scope = data.get("scope")
        return cls(
            event_id=str(data["event_id"]),
            sequence=int(data["sequence"]),
            cursor=str(data["cursor"]),
            kind=str(kind),
            created_at=str(created_at),
            payload=dict(data.get("payload") or {}),
            correlation_id=(
                str(data["correlation_id"])
                if data.get("correlation_id") is not None
                else None
            ),
            scope=dict(scope) if isinstance(scope, Mapping) else None,
        )


__all__ = [
    "ACCEPT_RECEIPT_SCHEMA",
    "CONTROL_PLANE_CONTEXT_SCHEMA",
    "CONTROL_PLANE_EVENT_SCHEMA",
    "SSE_CURSOR_SCHEMA",
    "AcceptReceipt",
    "AcceptResult",
    "ControlPlaneContext",
    "ControlPlaneEvent",
    "CorrelationKey",
    "EnvironmentRef",
    "IdempotencyKey",
    "Principal",
    "PrincipalKind",
    "SecurityDomain",
    "TenantRef",
    "WorkspaceRef",
]
