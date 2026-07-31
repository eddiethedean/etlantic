"""Immutable registry directory and revision models (CP2 / 040-T, 040-R).

These models are FastAPI- and SQLModel-free. They extend ADR-016 refs with
durable directory **records**, lifecycle, and append-only revisions
(ADR-017). Serialization is secret-free and never carries source rows.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

TENANT_RECORD_SCHEMA = "etlantic.control_plane.tenant_record/1"
WORKSPACE_RECORD_SCHEMA = "etlantic.control_plane.workspace_record/1"
ENVIRONMENT_RECORD_SCHEMA = "etlantic.control_plane.environment_record/1"
SECURITY_DOMAIN_RECORD_SCHEMA = "etlantic.control_plane.security_domain_record/1"
LOGICAL_IDENTITY_SCHEMA = "etlantic.control_plane.logical_identity/1"
REGISTRY_REVISION_SCHEMA = "etlantic.control_plane.registry_revision/1"
ALIAS_RECORD_SCHEMA = "etlantic.control_plane.alias/1"
PROMOTION_RECORD_SCHEMA = "etlantic.control_plane.promotion/1"


class LifecycleState(StrEnum):
    """Directory lifecycle states (ADR-017)."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"


def _lifecycle(value: LifecycleState | str) -> LifecycleState:
    if isinstance(value, LifecycleState):
        return value
    return LifecycleState(str(value))


@dataclass(frozen=True, slots=True)
class TenantRecord:
    """Durable tenant directory entry (distinct from :class:`TenantRef`)."""

    tenant_id: str
    lifecycle: LifecycleState = LifecycleState.ACTIVE
    display_name: str | None = None
    security_domain_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": TENANT_RECORD_SCHEMA,
            "tenant_id": self.tenant_id,
            "lifecycle": self.lifecycle.value,
            "display_name": self.display_name,
            "security_domain_id": self.security_domain_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> TenantRecord:
        return cls(
            tenant_id=str(data["tenant_id"]),
            lifecycle=_lifecycle(data.get("lifecycle") or LifecycleState.ACTIVE),
            display_name=(
                str(data["display_name"])
                if data.get("display_name") is not None
                else None
            ),
            security_domain_id=(
                str(data["security_domain_id"])
                if data.get("security_domain_id") is not None
                else None
            ),
            created_at=(
                str(data["created_at"]) if data.get("created_at") is not None else None
            ),
            updated_at=(
                str(data["updated_at"]) if data.get("updated_at") is not None else None
            ),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True, slots=True)
class WorkspaceRecord:
    """Durable workspace directory entry (tenant-owned)."""

    tenant_id: str
    workspace_id: str
    lifecycle: LifecycleState = LifecycleState.ACTIVE
    display_name: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": WORKSPACE_RECORD_SCHEMA,
            "tenant_id": self.tenant_id,
            "workspace_id": self.workspace_id,
            "lifecycle": self.lifecycle.value,
            "display_name": self.display_name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> WorkspaceRecord:
        return cls(
            tenant_id=str(data["tenant_id"]),
            workspace_id=str(data["workspace_id"]),
            lifecycle=_lifecycle(data.get("lifecycle") or LifecycleState.ACTIVE),
            display_name=(
                str(data["display_name"])
                if data.get("display_name") is not None
                else None
            ),
            created_at=(
                str(data["created_at"]) if data.get("created_at") is not None else None
            ),
            updated_at=(
                str(data["updated_at"]) if data.get("updated_at") is not None else None
            ),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True, slots=True)
class EnvironmentRecord:
    """Durable deployment / promotion environment directory entry."""

    tenant_id: str
    environment_id: str
    name: str
    workspace_id: str | None = None
    lifecycle: LifecycleState = LifecycleState.ACTIVE
    created_at: str | None = None
    updated_at: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": ENVIRONMENT_RECORD_SCHEMA,
            "tenant_id": self.tenant_id,
            "environment_id": self.environment_id,
            "name": self.name,
            "workspace_id": self.workspace_id,
            "lifecycle": self.lifecycle.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> EnvironmentRecord:
        return cls(
            tenant_id=str(data["tenant_id"]),
            environment_id=str(data["environment_id"]),
            name=str(data["name"]),
            workspace_id=(
                str(data["workspace_id"])
                if data.get("workspace_id") is not None
                else None
            ),
            lifecycle=_lifecycle(data.get("lifecycle") or LifecycleState.ACTIVE),
            created_at=(
                str(data["created_at"]) if data.get("created_at") is not None else None
            ),
            updated_at=(
                str(data["updated_at"]) if data.get("updated_at") is not None else None
            ),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True, slots=True)
class SecurityDomainRecord:
    """Durable security-domain directory entry (distinct from the CP1 ref)."""

    domain_id: str
    lifecycle: LifecycleState = LifecycleState.ACTIVE
    display_name: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SECURITY_DOMAIN_RECORD_SCHEMA,
            "domain_id": self.domain_id,
            "lifecycle": self.lifecycle.value,
            "display_name": self.display_name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> SecurityDomainRecord:
        return cls(
            domain_id=str(data["domain_id"]),
            lifecycle=_lifecycle(data.get("lifecycle") or LifecycleState.ACTIVE),
            display_name=(
                str(data["display_name"])
                if data.get("display_name") is not None
                else None
            ),
            created_at=(
                str(data["created_at"]) if data.get("created_at") is not None else None
            ),
            updated_at=(
                str(data["updated_at"]) if data.get("updated_at") is not None else None
            ),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True, slots=True)
class LogicalIdentity:
    """Stable logical identity preserved across revisions and promotions."""

    logical_id: str
    tenant_id: str
    workspace_id: str
    kind: str
    created_at: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": LOGICAL_IDENTITY_SCHEMA,
            "logical_id": self.logical_id,
            "tenant_id": self.tenant_id,
            "workspace_id": self.workspace_id,
            "kind": self.kind,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> LogicalIdentity:
        return cls(
            logical_id=str(data["logical_id"]),
            tenant_id=str(data["tenant_id"]),
            workspace_id=str(data["workspace_id"]),
            kind=str(data["kind"]),
            created_at=(
                str(data["created_at"]) if data.get("created_at") is not None else None
            ),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True, slots=True)
class RegistryRevision:
    """Immutable, append-only registry revision (never updated in place)."""

    logical_id: str
    revision_id: str
    tenant_id: str
    workspace_id: str
    content_fingerprint: str
    content: Mapping[str, Any] = field(default_factory=dict)
    created_at: str | None = None
    kind: str | None = None
    signature_placeholder: str | None = None
    provenance_placeholder: Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": REGISTRY_REVISION_SCHEMA,
            "logical_id": self.logical_id,
            "revision_id": self.revision_id,
            "tenant_id": self.tenant_id,
            "workspace_id": self.workspace_id,
            "content_fingerprint": self.content_fingerprint,
            "content": dict(self.content),
            "created_at": self.created_at,
            "kind": self.kind,
            "signature_placeholder": self.signature_placeholder,
            "provenance_placeholder": (
                dict(self.provenance_placeholder)
                if self.provenance_placeholder is not None
                else None
            ),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RegistryRevision:
        provenance = data.get("provenance_placeholder")
        return cls(
            logical_id=str(data["logical_id"]),
            revision_id=str(data["revision_id"]),
            tenant_id=str(data["tenant_id"]),
            workspace_id=str(data["workspace_id"]),
            content_fingerprint=str(data["content_fingerprint"]),
            content=dict(data.get("content") or {}),
            created_at=(
                str(data["created_at"]) if data.get("created_at") is not None else None
            ),
            kind=(str(data["kind"]) if data.get("kind") is not None else None),
            signature_placeholder=(
                str(data["signature_placeholder"])
                if data.get("signature_placeholder") is not None
                else None
            ),
            provenance_placeholder=(
                dict(provenance) if isinstance(provenance, Mapping) else None
            ),
        )


@dataclass(frozen=True, slots=True)
class AliasRecord:
    """Scoped alias pointing at an immutable revision."""

    tenant_id: str
    workspace_id: str
    alias: str
    logical_id: str
    revision_id: str
    created_at: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": ALIAS_RECORD_SCHEMA,
            "tenant_id": self.tenant_id,
            "workspace_id": self.workspace_id,
            "alias": self.alias,
            "logical_id": self.logical_id,
            "revision_id": self.revision_id,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> AliasRecord:
        return cls(
            tenant_id=str(data["tenant_id"]),
            workspace_id=str(data["workspace_id"]),
            alias=str(data["alias"]),
            logical_id=str(data["logical_id"]),
            revision_id=str(data["revision_id"]),
            created_at=(
                str(data["created_at"]) if data.get("created_at") is not None else None
            ),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True, slots=True)
class PromotionRecord:
    """Immutable record of a promotion that preserves ``logical_id``."""

    promotion_id: str
    tenant_id: str
    workspace_id: str
    logical_id: str
    from_revision_id: str
    to_revision_id: str
    from_environment: str
    to_environment: str
    created_at: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": PROMOTION_RECORD_SCHEMA,
            "promotion_id": self.promotion_id,
            "tenant_id": self.tenant_id,
            "workspace_id": self.workspace_id,
            "logical_id": self.logical_id,
            "from_revision_id": self.from_revision_id,
            "to_revision_id": self.to_revision_id,
            "from_environment": self.from_environment,
            "to_environment": self.to_environment,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PromotionRecord:
        return cls(
            promotion_id=str(data["promotion_id"]),
            tenant_id=str(data["tenant_id"]),
            workspace_id=str(data["workspace_id"]),
            logical_id=str(data["logical_id"]),
            from_revision_id=str(data["from_revision_id"]),
            to_revision_id=str(data["to_revision_id"]),
            from_environment=str(data["from_environment"]),
            to_environment=str(data["to_environment"]),
            created_at=(
                str(data["created_at"]) if data.get("created_at") is not None else None
            ),
            metadata=dict(data.get("metadata") or {}),
        )


__all__ = [
    "ALIAS_RECORD_SCHEMA",
    "ENVIRONMENT_RECORD_SCHEMA",
    "LOGICAL_IDENTITY_SCHEMA",
    "PROMOTION_RECORD_SCHEMA",
    "REGISTRY_REVISION_SCHEMA",
    "SECURITY_DOMAIN_RECORD_SCHEMA",
    "TENANT_RECORD_SCHEMA",
    "WORKSPACE_RECORD_SCHEMA",
    "AliasRecord",
    "EnvironmentRecord",
    "LifecycleState",
    "LogicalIdentity",
    "PromotionRecord",
    "RegistryRevision",
    "SecurityDomainRecord",
    "TenantRecord",
    "WorkspaceRecord",
]
