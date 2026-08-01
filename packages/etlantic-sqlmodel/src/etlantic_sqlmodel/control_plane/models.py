"""SQLModel persistence tables for control-plane reference stores.

These are persistence models only — not HTTP response models and not ETLantic
pipeline contracts.
"""

from __future__ import annotations

from sqlalchemy import Column, String, UniqueConstraint

from sqlmodel import Field, SQLModel


class DefinitionRow(SQLModel, table=True):
    __tablename__ = "cp_definitions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "workspace_id",
            "definition_id",
            name="uq_cp_definition_scope",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    tenant_id: str = Field(sa_column=Column(String(), index=True, nullable=False))
    workspace_id: str = Field(sa_column=Column(String(), index=True, nullable=False))
    definition_id: str = Field(sa_column=Column(String(), index=True, nullable=False))
    document_json: str


class SubmissionRow(SQLModel, table=True):
    __tablename__ = "cp_submissions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "workspace_id",
            "principal_subject",
            "operation",
            "idempotency_key",
            name="uq_cp_submission_idem",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    tenant_id: str = Field(sa_column=Column(String(), index=True, nullable=False))
    workspace_id: str = Field(sa_column=Column(String(), index=True, nullable=False))
    principal_subject: str = Field(
        sa_column=Column(String(), index=True, nullable=False),
        default="",
    )
    operation: str = Field(
        sa_column=Column(String(), index=True, nullable=False),
        default="run.submit",
    )
    idempotency_key: str = Field(sa_column=Column(String(), index=True, nullable=False))
    acceptance_id: str
    submission_id: str = Field(sa_column=Column(String(), index=True, nullable=False))
    created_at: str
    status: str = "accepted"
    resource_type: str = "run"
    resource_id: str | None = None
    payload_json: str
    run_status: str = "accepted"
    updated_at: str | None = None
    definition_id: str | None = None


class EventRow(SQLModel, table=True):
    __tablename__ = "cp_events"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "workspace_id",
            "sequence",
            name="uq_cp_event_scope_seq",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    tenant_id: str = Field(sa_column=Column(String(), index=True, nullable=False))
    workspace_id: str = Field(sa_column=Column(String(), index=True, nullable=False))
    event_id: str = Field(sa_column=Column(String(), index=True, nullable=False))
    sequence: int = Field(index=True)
    cursor: str = Field(sa_column=Column(String(), index=True, nullable=False))
    kind: str
    created_at: str
    payload_json: str
    correlation_id: str | None = None


class TenantRow(SQLModel, table=True):
    """Durable tenant directory row (CP2 / 040-P)."""

    __tablename__ = "cp_registry_tenants"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_cp_registry_tenant"),)

    id: int | None = Field(default=None, primary_key=True)
    tenant_id: str = Field(sa_column=Column(String(), index=True, nullable=False))
    lifecycle: str = Field(default="active")
    display_name: str | None = None
    security_domain_id: str | None = Field(
        default=None, sa_column=Column(String(), index=True, nullable=True)
    )
    created_at: str | None = None
    updated_at: str | None = None
    metadata_json: str = "{}"


class WorkspaceRow(SQLModel, table=True):
    """Durable workspace directory row (tenant-owned)."""

    __tablename__ = "cp_registry_workspaces"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "workspace_id",
            name="uq_cp_registry_workspace_scope",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    tenant_id: str = Field(sa_column=Column(String(), index=True, nullable=False))
    workspace_id: str = Field(sa_column=Column(String(), index=True, nullable=False))
    lifecycle: str = Field(default="active")
    display_name: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    metadata_json: str = "{}"


class LogicalIdentityRow(SQLModel, table=True):
    """Stable logical identity preserved across revisions."""

    __tablename__ = "cp_registry_logical"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "workspace_id",
            "logical_id",
            name="uq_cp_registry_logical_scope",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    tenant_id: str = Field(sa_column=Column(String(), index=True, nullable=False))
    workspace_id: str = Field(sa_column=Column(String(), index=True, nullable=False))
    logical_id: str = Field(sa_column=Column(String(), index=True, nullable=False))
    kind: str
    created_at: str | None = None
    metadata_json: str = "{}"


class RevisionRow(SQLModel, table=True):
    """Immutable append-only registry revision."""

    __tablename__ = "cp_registry_revisions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "workspace_id",
            "revision_id",
            name="uq_cp_registry_revision_scope",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    tenant_id: str = Field(sa_column=Column(String(), index=True, nullable=False))
    workspace_id: str = Field(sa_column=Column(String(), index=True, nullable=False))
    logical_id: str = Field(sa_column=Column(String(), index=True, nullable=False))
    revision_id: str = Field(sa_column=Column(String(), index=True, nullable=False))
    content_fingerprint: str
    content_json: str
    created_at: str | None = None
    kind: str | None = None
    signature_placeholder: str | None = None
    provenance_json: str | None = None


class AliasRow(SQLModel, table=True):
    """Scoped alias pointing at an immutable revision."""

    __tablename__ = "cp_registry_aliases"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "workspace_id",
            "alias",
            name="uq_cp_registry_alias_scope",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    tenant_id: str = Field(sa_column=Column(String(), index=True, nullable=False))
    workspace_id: str = Field(sa_column=Column(String(), index=True, nullable=False))
    alias: str = Field(sa_column=Column(String(), index=True, nullable=False))
    logical_id: str
    revision_id: str
    created_at: str | None = None
    metadata_json: str = "{}"


class PromotionRow(SQLModel, table=True):
    """Immutable promotion record preserving logical_id."""

    __tablename__ = "cp_registry_promotions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "workspace_id",
            "promotion_id",
            name="uq_cp_registry_promotion_scope",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    tenant_id: str = Field(sa_column=Column(String(), index=True, nullable=False))
    workspace_id: str = Field(sa_column=Column(String(), index=True, nullable=False))
    promotion_id: str = Field(sa_column=Column(String(), index=True, nullable=False))
    logical_id: str
    from_revision_id: str
    to_revision_id: str
    from_environment: str
    to_environment: str
    created_at: str | None = None
    metadata_json: str = "{}"


class EnvironmentRow(SQLModel, table=True):
    """Deployment / promotion environment directory row."""

    __tablename__ = "cp_registry_environments"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "environment_id",
            name="uq_cp_registry_environment_scope",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    tenant_id: str = Field(sa_column=Column(String(), index=True, nullable=False))
    environment_id: str = Field(sa_column=Column(String(), index=True, nullable=False))
    name: str
    workspace_id: str | None = None
    lifecycle: str = Field(default="active")
    created_at: str | None = None
    updated_at: str | None = None
    metadata_json: str = "{}"


class SecurityDomainRow(SQLModel, table=True):
    """Security-domain directory row."""

    __tablename__ = "cp_registry_security_domains"
    __table_args__ = (
        UniqueConstraint("domain_id", name="uq_cp_registry_security_domain"),
    )

    id: int | None = Field(default=None, primary_key=True)
    domain_id: str = Field(sa_column=Column(String(), index=True, nullable=False))
    lifecycle: str = Field(default="active")
    display_name: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    metadata_json: str = "{}"


class DurableSnapshotRow(SQLModel, table=True):
    """Transactional CP3 durable-work snapshot (reference provider).

    One logical store per engine; mutations load/save under a DB transaction so
    accept+outbox and fencing CAS share commit boundaries.
    """

    __tablename__ = "cp_durable_snapshot"
    __table_args__ = (UniqueConstraint("store_id", name="uq_cp_durable_snapshot"),)

    id: int | None = Field(default=None, primary_key=True)
    store_id: str = Field(
        sa_column=Column(String(), index=True, nullable=False), default="default"
    )
    payload_json: str = "{}"
    updated_at: str | None = None


__all__ = [
    "AliasRow",
    "DefinitionRow",
    "DurableSnapshotRow",
    "EnvironmentRow",
    "EventRow",
    "LogicalIdentityRow",
    "PromotionRow",
    "RevisionRow",
    "SecurityDomainRow",
    "SubmissionRow",
    "TenantRow",
    "WorkspaceRow",
]
