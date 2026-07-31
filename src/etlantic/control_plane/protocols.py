"""Scoped control-plane provider protocols (DI seams; no FastAPI/SQLModel).

Every method that reads or mutates a tenant-owned resource takes an immutable
:class:`~etlantic.control_plane.models.ControlPlaneContext`. Unscoped
``get(id)`` APIs are non-conforming for tenant-owned resources.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from etlantic.control_plane.models import (
    AcceptReceipt,
    ControlPlaneContext,
    ControlPlaneEvent,
)


@dataclass(frozen=True, slots=True)
class AuthzDecision:
    """Allow/deny outcome from an :class:`Authorizer`."""

    allowed: bool
    reason: str = ""
    # When denied: preferred disclosure for non-enumeration mapping.
    disclosure: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "disclosure": self.disclosure,
        }


@runtime_checkable
class Authorizer(Protocol):
    """Object-level authorization evaluated before lookup or disclosure."""

    def authorize(
        self,
        ctx: ControlPlaneContext,
        action: str,
        resource: str,
    ) -> AuthzDecision:
        """Return an allow/deny decision for ``action`` on ``resource``."""
        ...


@runtime_checkable
class DefinitionRepository(Protocol):
    """Workspace-scoped pipeline/definition registry."""

    def get(self, ctx: ControlPlaneContext, definition_id: str) -> Mapping[str, Any]:
        """Fetch a definition document inside ``ctx`` scope."""
        ...

    def list(self, ctx: ControlPlaneContext) -> Sequence[str]:
        """List definition ids visible inside ``ctx`` scope."""
        ...

    def put(
        self,
        ctx: ControlPlaneContext,
        definition_id: str,
        document: Mapping[str, Any],
    ) -> None:
        """Store or replace a definition document inside ``ctx`` scope."""
        ...


@runtime_checkable
class SubmissionStore(Protocol):
    """Durable acceptance and scoped idempotency lookup."""

    def accept(
        self,
        ctx: ControlPlaneContext,
        *,
        idempotency_key: str,
        payload: Mapping[str, Any],
        resource_type: str = "run",
        resource_id: str | None = None,
    ) -> AcceptReceipt:
        """Durably accept work; same key returns the original receipt."""
        ...

    def lookup_idempotency(
        self,
        ctx: ControlPlaneContext,
        idempotency_key: str,
    ) -> AcceptReceipt | None:
        """Return a prior acceptance for ``idempotency_key`` in ``ctx`` scope."""
        ...


@runtime_checkable
class EventStore(Protocol):
    """Append-only, scoped event history with opaque cursors."""

    def append(
        self,
        ctx: ControlPlaneContext,
        *,
        kind: str,
        payload: Mapping[str, Any] | None = None,
    ) -> ControlPlaneEvent:
        """Append an event in ``ctx`` scope and return the stored envelope."""
        ...

    def list_after_cursor(
        self,
        ctx: ControlPlaneContext,
        cursor: str | None,
        *,
        limit: int = 100,
    ) -> Sequence[ControlPlaneEvent]:
        """List events strictly after ``cursor`` inside ``ctx`` scope.

        Unknown or expired cursors must fail closed (for example HTTP 410)
        rather than silently skipping history.
        """
        ...


__all__ = [
    "Authorizer",
    "AuthzDecision",
    "DefinitionRepository",
    "EventStore",
    "SubmissionStore",
]
