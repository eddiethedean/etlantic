"""Registry directory and revision protocols (CP2 / 040-T, 040-R).

Every method that reads or mutates a tenant-owned resource takes an immutable
:class:`~etlantic.control_plane.models.ControlPlaneContext`. Tenant-directory
administration may use security-domain principals under separate policy.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol, runtime_checkable

from etlantic.control_plane.models import ControlPlaneContext
from etlantic.control_plane.registry_models import (
    AliasRecord,
    EnvironmentRecord,
    LifecycleState,
    LogicalIdentity,
    PromotionRecord,
    RegistryRevision,
    SecurityDomainRecord,
    TenantRecord,
    WorkspaceRecord,
)


@runtime_checkable
class TenantDirectory(Protocol):
    """Tenant directory with lifecycle (admin may use security-domain principals)."""

    def get(self, ctx: ControlPlaneContext, tenant_id: str) -> TenantRecord:
        """Fetch a tenant record visible to ``ctx``."""
        ...

    def put(self, ctx: ControlPlaneContext, record: TenantRecord) -> None:
        """Create or replace a tenant record (fails closed when suspended)."""
        ...

    def list(self, ctx: ControlPlaneContext) -> Sequence[TenantRecord]:
        """List tenants visible under ``ctx`` / security-domain policy."""
        ...

    def set_lifecycle(
        self,
        ctx: ControlPlaneContext,
        tenant_id: str,
        state: LifecycleState,
    ) -> TenantRecord:
        """Update tenant lifecycle state."""
        ...


@runtime_checkable
class WorkspaceDirectory(Protocol):
    """Workspace directory scoped by tenant via ``ControlPlaneContext``."""

    def get(self, ctx: ControlPlaneContext, workspace_id: str) -> WorkspaceRecord:
        """Fetch a workspace inside ``ctx`` tenant scope."""
        ...

    def put(self, ctx: ControlPlaneContext, record: WorkspaceRecord) -> None:
        """Create or replace a workspace record (fails closed when suspended)."""
        ...

    def list(self, ctx: ControlPlaneContext) -> Sequence[WorkspaceRecord]:
        """List workspaces inside ``ctx`` tenant scope."""
        ...

    def set_lifecycle(
        self,
        ctx: ControlPlaneContext,
        workspace_id: str,
        state: LifecycleState,
    ) -> WorkspaceRecord:
        """Update workspace lifecycle state inside ``ctx`` tenant scope."""
        ...


@runtime_checkable
class RevisionRegistry(Protocol):
    """Append-only revisions, aliases, and promotion records."""

    def put_logical(
        self,
        ctx: ControlPlaneContext,
        identity: LogicalIdentity,
    ) -> None:
        """Register a logical identity inside ``ctx`` scope."""
        ...

    def get_logical(
        self,
        ctx: ControlPlaneContext,
        logical_id: str,
    ) -> LogicalIdentity:
        """Fetch a logical identity inside ``ctx`` scope."""
        ...

    def put_revision(
        self,
        ctx: ControlPlaneContext,
        revision: RegistryRevision,
    ) -> None:
        """Append an immutable revision (never overwrite)."""
        ...

    def get_revision(
        self,
        ctx: ControlPlaneContext,
        revision_id: str,
    ) -> RegistryRevision:
        """Fetch a revision and verify content fingerprint (tamper detection)."""
        ...

    def list_revisions(
        self,
        ctx: ControlPlaneContext,
        logical_id: str,
    ) -> Sequence[RegistryRevision]:
        """List revisions for a logical identity inside ``ctx`` scope."""
        ...

    def put_alias(self, ctx: ControlPlaneContext, alias: AliasRecord) -> AliasRecord:
        """Create or replace an alias mapping to a revision; return stored record."""
        ...

    def resolve_alias(self, ctx: ControlPlaneContext, alias: str) -> RegistryRevision:
        """Resolve an alias to its target revision (with fingerprint check)."""
        ...

    def promote(
        self,
        ctx: ControlPlaneContext,
        *,
        logical_id: str,
        from_revision_id: str,
        from_environment: str,
        to_environment: str,
        content: Mapping[str, object] | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> PromotionRecord:
        """Promote while preserving ``logical_id``; prior revision stays immutable."""
        ...

    def get_promotion(
        self,
        ctx: ControlPlaneContext,
        promotion_id: str,
    ) -> PromotionRecord:
        """Fetch a promotion record inside ``ctx`` scope."""
        ...


@runtime_checkable
class RegistryProvider(Protocol):
    """Façade composing directory and revision registries (histories later)."""

    @property
    def tenants(self) -> TenantDirectory:
        """Tenant directory."""
        ...

    @property
    def workspaces(self) -> WorkspaceDirectory:
        """Workspace directory."""
        ...

    @property
    def revisions(self) -> RevisionRegistry:
        """Revision / alias / promotion registry."""
        ...

    def put_environment(
        self,
        ctx: ControlPlaneContext,
        record: EnvironmentRecord,
    ) -> None:
        """Store an environment directory record."""
        ...

    def get_environment(
        self,
        ctx: ControlPlaneContext,
        environment_id: str,
    ) -> EnvironmentRecord:
        """Fetch an environment directory record."""
        ...

    def put_security_domain(
        self,
        ctx: ControlPlaneContext,
        record: SecurityDomainRecord,
    ) -> None:
        """Store a security-domain directory record."""
        ...

    def get_security_domain(
        self,
        ctx: ControlPlaneContext,
        domain_id: str,
    ) -> SecurityDomainRecord:
        """Fetch a security-domain directory record."""
        ...


__all__ = [
    "RegistryProvider",
    "RevisionRegistry",
    "TenantDirectory",
    "WorkspaceDirectory",
]
