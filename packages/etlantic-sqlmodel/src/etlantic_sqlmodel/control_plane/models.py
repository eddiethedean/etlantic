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


__all__ = ["DefinitionRow", "EventRow", "SubmissionRow"]
