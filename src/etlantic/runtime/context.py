# pyright: reportUnknownVariableType=false
"""Typed runtime contexts passed through middleware stacks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class TrustedExecutionScope:
    """Authenticated tenant and workload identity for provider I/O.

    This context is supplied by a managed worker from server-derived
    control-plane identity. It is passed to providers at runtime and is never
    part of a plan, report, or execution envelope.
    """

    principal_id: str
    principal_kind: str
    tenant_id: str
    workspace_id: str
    environment: str
    security_domain_id: str
    principal_issuer: str | None = None
    resource_owner_id: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "principal_id",
            "principal_kind",
            "tenant_id",
            "workspace_id",
            "environment",
            "security_domain_id",
        ):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must be non-empty")
        if self.principal_issuer is not None and not self.principal_issuer.strip():
            raise ValueError("principal_issuer must be non-empty when provided")
        if self.resource_owner_id is not None and not self.resource_owner_id.strip():
            raise ValueError("resource_owner_id must be non-empty when provided")
        if self.principal_kind not in {"human", "workload", "service"}:
            raise ValueError("principal_kind must be human, workload, or service")

    @property
    def workload_id(self) -> str | None:
        """Return the authenticated workload identity when applicable."""
        return self.principal_id if self.principal_kind == "workload" else None

    def to_dict(self) -> dict[str, str | None]:
        """Return the secret-free identity fields for provider contexts."""
        return {
            "principal_id": self.principal_id,
            "principal_kind": self.principal_kind,
            "principal_issuer": self.principal_issuer,
            "workload_id": self.workload_id,
            "tenant_id": self.tenant_id,
            "workspace_id": self.workspace_id,
            "environment": self.environment,
            "security_domain_id": self.security_domain_id,
            "resource_owner_id": self.resource_owner_id,
        }

    @property
    def cache_partition(self) -> tuple[str, ...]:
        """Return the full authority boundary used for runtime secret caching."""
        return (
            self.principal_id,
            self.principal_kind,
            self.principal_issuer or "",
            self.tenant_id,
            self.workspace_id,
            self.environment,
            self.security_domain_id,
            self.resource_owner_id or "",
        )


@dataclass(frozen=True, slots=True)
class RunContext:
    """Context for one pipeline run."""

    run_id: str
    pipeline_id: str
    plan_id: str
    profile: str
    intent: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StepContext:
    """Context for one step invocation within a run."""

    run: RunContext
    step_name: str
    node_kind: str
    attempt: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AttemptContext:
    """Context for a single attempt of a step."""

    step: StepContext
    attempt: int
    metadata: dict[str, Any] = field(default_factory=dict)
