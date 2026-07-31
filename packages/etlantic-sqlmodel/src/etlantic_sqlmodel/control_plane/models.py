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
            "idempotency_key",
            name="uq_cp_submission_idem",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    tenant_id: str = Field(sa_column=Column(String(), index=True, nullable=False))
    workspace_id: str = Field(sa_column=Column(String(), index=True, nullable=False))
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


__all__ = ["DefinitionRow", "SubmissionRow"]
