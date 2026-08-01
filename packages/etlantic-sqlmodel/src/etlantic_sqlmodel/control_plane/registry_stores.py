"""SQLModel-backed RegistryProvider implementations (CP2 / 040-P).

Production deployments must apply versioned migrations — do not rely on
``create_all`` / ``create_registry_tables`` as the sole schema path.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from etlantic.control_plane import (
    AliasRecord,
    ControlPlaneContext,
    ControlPlaneError,
    EnvironmentRecord,
    LifecycleState,
    LogicalIdentity,
    PromotionRecord,
    RegistryRevision,
    SecurityDomainRecord,
    TenantRecord,
    WorkspaceRecord,
    content_fingerprint,
    redact_control_plane_payload,
)
from etlantic.control_plane.redaction import redact_control_plane_text
from etlantic.control_plane.registry_memory import safe_registry_content
from etlantic_sqlmodel.control_plane.models import (
    AliasRow,
    EnvironmentRow,
    LogicalIdentityRow,
    PromotionRow,
    RevisionRow,
    SecurityDomainRow,
    TenantRow,
    WorkspaceRow,
)
from etlantic_sqlmodel.control_plane.session import session_scope
from sqlmodel import Session, SQLModel, select


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _require_active(lifecycle: LifecycleState | str, *, resource: str) -> None:
    state = (
        lifecycle
        if isinstance(lifecycle, LifecycleState)
        else LifecycleState(str(lifecycle))
    )
    if state == LifecycleState.SUSPENDED:
        raise ControlPlaneError.forbidden(
            f"{resource} is suspended; registry operations fail closed",
            extensions={"lifecycle": state.value, "resource": resource},
        )
    if state == LifecycleState.ARCHIVED:
        raise ControlPlaneError.forbidden(
            f"{resource} is archived; registry writes fail closed",
            extensions={"lifecycle": state.value, "resource": resource},
        )


def _meta(data: Mapping[str, Any] | None) -> str:
    redacted = redact_control_plane_payload(deepcopy(dict(data or {})))
    return json.dumps(redacted if isinstance(redacted, dict) else {}, sort_keys=True)


def _load_meta(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    return dict(json.loads(raw))


REGISTRY_TABLES = (
    TenantRow,
    WorkspaceRow,
    LogicalIdentityRow,
    RevisionRow,
    AliasRow,
    PromotionRow,
    EnvironmentRow,
    SecurityDomainRow,
)


def create_registry_tables(engine: Engine) -> None:
    """Create CP2 registry tables.

    Intended for tests and local demos — not a production migration path.
    Prefer :mod:`etlantic_sqlmodel.migrations`.
    """
    SQLModel.metadata.create_all(
        engine,
        tables=[cls.__table__ for cls in REGISTRY_TABLES],  # type: ignore[list-item]
    )


def _tenant_from_row(row: TenantRow) -> TenantRecord:
    return TenantRecord(
        tenant_id=row.tenant_id,
        lifecycle=LifecycleState(row.lifecycle),
        display_name=row.display_name,
        security_domain_id=row.security_domain_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
        metadata=_load_meta(row.metadata_json),
    )


def _workspace_from_row(row: WorkspaceRow) -> WorkspaceRecord:
    return WorkspaceRecord(
        tenant_id=row.tenant_id,
        workspace_id=row.workspace_id,
        lifecycle=LifecycleState(row.lifecycle),
        display_name=row.display_name,
        created_at=row.created_at,
        updated_at=row.updated_at,
        metadata=_load_meta(row.metadata_json),
    )


def _logical_from_row(row: LogicalIdentityRow) -> LogicalIdentity:
    return LogicalIdentity(
        logical_id=row.logical_id,
        tenant_id=row.tenant_id,
        workspace_id=row.workspace_id,
        kind=row.kind,
        created_at=row.created_at,
        metadata=_load_meta(row.metadata_json),
    )


def _revision_from_row(row: RevisionRow) -> RegistryRevision:
    provenance = json.loads(row.provenance_json) if row.provenance_json else None
    return RegistryRevision(
        logical_id=row.logical_id,
        revision_id=row.revision_id,
        tenant_id=row.tenant_id,
        workspace_id=row.workspace_id,
        content_fingerprint=row.content_fingerprint,
        content=dict(json.loads(row.content_json)),
        created_at=row.created_at,
        kind=row.kind,
        signature_placeholder=row.signature_placeholder,
        provenance_placeholder=(
            dict(provenance) if isinstance(provenance, dict) else None
        ),
    )


def _alias_from_row(row: AliasRow) -> AliasRecord:
    return AliasRecord(
        tenant_id=row.tenant_id,
        workspace_id=row.workspace_id,
        alias=row.alias,
        logical_id=row.logical_id,
        revision_id=row.revision_id,
        created_at=row.created_at,
        metadata=_load_meta(row.metadata_json),
    )


def _promotion_from_row(row: PromotionRow) -> PromotionRecord:
    return PromotionRecord(
        promotion_id=row.promotion_id,
        tenant_id=row.tenant_id,
        workspace_id=row.workspace_id,
        logical_id=row.logical_id,
        from_revision_id=row.from_revision_id,
        to_revision_id=row.to_revision_id,
        from_environment=row.from_environment,
        to_environment=row.to_environment,
        created_at=row.created_at,
        metadata=_load_meta(row.metadata_json),
    )


@dataclass
class SqlModelTenantDirectory:
    """SQLModel tenant directory with isolation and suspension fail-closed."""

    engine: Engine

    def get(self, ctx: ControlPlaneContext, tenant_id: str) -> TenantRecord:
        with session_scope(self.engine) as session:
            row = self._by_id(session, tenant_id)
            if row is None:
                raise ControlPlaneError.not_found(
                    "Tenant not found",
                    extensions={"tenant_id": tenant_id},
                )
            record = _tenant_from_row(row)
            in_scope = ctx.tenant.tenant_id == tenant_id
            admin_scope = (
                record.security_domain_id is not None
                and record.security_domain_id == ctx.security_domain.domain_id
            )
            if not in_scope and not admin_scope:
                raise ControlPlaneError.not_found(
                    "Tenant not found",
                    extensions={"tenant_id": tenant_id},
                )
            _require_active(record.lifecycle, resource=f"tenant:{tenant_id}")
            return deepcopy(record)

    def put(self, ctx: ControlPlaneContext, record: TenantRecord) -> None:
        with session_scope(self.engine) as session:
            existing = self._by_id(session, record.tenant_id)
            if existing is not None:
                _require_active(
                    LifecycleState(existing.lifecycle),
                    resource=f"tenant:{record.tenant_id}",
                )
                existing_in_scope = ctx.tenant.tenant_id == record.tenant_id
                existing_admin_scope = (
                    existing.security_domain_id is not None
                    and existing.security_domain_id == ctx.security_domain.domain_id
                )
                if not existing_in_scope and not existing_admin_scope:
                    raise ControlPlaneError.not_found(
                        "Tenant not found",
                        extensions={"tenant_id": record.tenant_id},
                    )
                if existing.security_domain_id != record.security_domain_id:
                    raise ControlPlaneError.conflict(
                        "Tenant security domain is immutable through directory put",
                        extensions={"tenant_id": record.tenant_id},
                    )
            in_scope = ctx.tenant.tenant_id == record.tenant_id
            admin_scope = (
                record.security_domain_id is not None
                and record.security_domain_id == ctx.security_domain.domain_id
            )
            if not in_scope and not admin_scope:
                raise ControlPlaneError.not_found(
                    "Tenant not found",
                    extensions={"tenant_id": record.tenant_id},
                )
            now = _utcnow_iso()
            if existing is None:
                session.add(
                    TenantRow(
                        tenant_id=record.tenant_id,
                        lifecycle=record.lifecycle.value,
                        display_name=record.display_name,
                        security_domain_id=record.security_domain_id,
                        created_at=record.created_at or now,
                        updated_at=now,
                        metadata_json=_meta(record.metadata),
                    )
                )
            else:
                existing.lifecycle = record.lifecycle.value
                existing.display_name = record.display_name
                existing.security_domain_id = record.security_domain_id
                existing.updated_at = now
                existing.metadata_json = _meta(record.metadata)
                session.add(existing)

    def list(self, ctx: ControlPlaneContext) -> Sequence[TenantRecord]:
        with session_scope(self.engine) as session:
            rows = session.exec(select(TenantRow)).all()
            out: list[TenantRecord] = []
            for row in rows:
                record = _tenant_from_row(row)
                if record.tenant_id == ctx.tenant.tenant_id or (
                    record.security_domain_id is not None
                    and record.security_domain_id == ctx.security_domain.domain_id
                ):
                    out.append(deepcopy(record))
            return sorted(out, key=lambda r: r.tenant_id)

    def set_lifecycle(
        self,
        ctx: ControlPlaneContext,
        tenant_id: str,
        state: LifecycleState,
    ) -> TenantRecord:
        with session_scope(self.engine) as session:
            row = self._by_id(session, tenant_id)
            if row is None or (
                ctx.tenant.tenant_id != tenant_id
                and row.security_domain_id != ctx.security_domain.domain_id
            ):
                raise ControlPlaneError.not_found(
                    "Tenant not found",
                    extensions={"tenant_id": tenant_id},
                )
            row.lifecycle = state.value
            row.updated_at = _utcnow_iso()
            session.add(row)
            session.flush()
            return deepcopy(_tenant_from_row(row))

    def peek(self, tenant_id: str) -> TenantRecord | None:
        with session_scope(self.engine) as session:
            row = self._by_id(session, tenant_id)
            return deepcopy(_tenant_from_row(row)) if row is not None else None

    @staticmethod
    def _by_id(session: Session, tenant_id: str) -> TenantRow | None:
        return session.exec(
            select(TenantRow).where(TenantRow.tenant_id == tenant_id)
        ).first()


@dataclass
class SqlModelWorkspaceDirectory:
    """SQLModel workspace directory keyed by (tenant_id, workspace_id)."""

    engine: Engine
    tenants: SqlModelTenantDirectory | None = None

    def _assert_tenant_active(self, tenant_id: str) -> None:
        if self.tenants is None:
            return
        tenant = self.tenants.peek(tenant_id)
        if tenant is not None:
            _require_active(tenant.lifecycle, resource=f"tenant:{tenant_id}")

    def get(self, ctx: ControlPlaneContext, workspace_id: str) -> WorkspaceRecord:
        with session_scope(self.engine) as session:
            self._assert_tenant_active(ctx.tenant.tenant_id)
            row = self._by_key(session, ctx.tenant.tenant_id, workspace_id)
            if row is None:
                raise ControlPlaneError.not_found(
                    "Workspace not found",
                    extensions={"workspace_id": workspace_id},
                )
            record = _workspace_from_row(row)
            _require_active(
                record.lifecycle,
                resource=f"workspace:{workspace_id}",
            )
            return deepcopy(record)

    def put(self, ctx: ControlPlaneContext, record: WorkspaceRecord) -> None:
        if record.tenant_id != ctx.tenant.tenant_id:
            raise ControlPlaneError.not_found(
                "Workspace not found",
                extensions={"workspace_id": record.workspace_id},
            )
        with session_scope(self.engine) as session:
            self._assert_tenant_active(record.tenant_id)
            existing = self._by_key(session, record.tenant_id, record.workspace_id)
            if existing is not None:
                _require_active(
                    LifecycleState(existing.lifecycle),
                    resource=f"workspace:{record.workspace_id}",
                )
            now = _utcnow_iso()
            if existing is None:
                session.add(
                    WorkspaceRow(
                        tenant_id=record.tenant_id,
                        workspace_id=record.workspace_id,
                        lifecycle=record.lifecycle.value,
                        display_name=record.display_name,
                        created_at=record.created_at or now,
                        updated_at=now,
                        metadata_json=_meta(record.metadata),
                    )
                )
            else:
                existing.lifecycle = record.lifecycle.value
                existing.display_name = record.display_name
                existing.updated_at = now
                existing.metadata_json = _meta(record.metadata)
                session.add(existing)

    def list(self, ctx: ControlPlaneContext) -> Sequence[WorkspaceRecord]:
        tenant_id = ctx.tenant.tenant_id
        with session_scope(self.engine) as session:
            self._assert_tenant_active(tenant_id)
            rows = session.exec(
                select(WorkspaceRow).where(WorkspaceRow.tenant_id == tenant_id)
            ).all()
            return sorted(
                (deepcopy(_workspace_from_row(r)) for r in rows),
                key=lambda r: r.workspace_id,
            )

    def set_lifecycle(
        self,
        ctx: ControlPlaneContext,
        workspace_id: str,
        state: LifecycleState,
    ) -> WorkspaceRecord:
        with session_scope(self.engine) as session:
            self._assert_tenant_active(ctx.tenant.tenant_id)
            row = self._by_key(session, ctx.tenant.tenant_id, workspace_id)
            if row is None:
                raise ControlPlaneError.not_found(
                    "Workspace not found",
                    extensions={"workspace_id": workspace_id},
                )
            row.lifecycle = state.value
            row.updated_at = _utcnow_iso()
            session.add(row)
            session.flush()
            return deepcopy(_workspace_from_row(row))

    def peek(self, tenant_id: str, workspace_id: str) -> WorkspaceRecord | None:
        with session_scope(self.engine) as session:
            row = self._by_key(session, tenant_id, workspace_id)
            return deepcopy(_workspace_from_row(row)) if row is not None else None

    @staticmethod
    def _by_key(
        session: Session, tenant_id: str, workspace_id: str
    ) -> WorkspaceRow | None:
        return session.exec(
            select(WorkspaceRow).where(
                WorkspaceRow.tenant_id == tenant_id,
                WorkspaceRow.workspace_id == workspace_id,
            )
        ).first()


@dataclass
class SqlModelRevisionRegistry:
    """Append-only SQLModel revision store with aliases and promotions."""

    engine: Engine
    tenants: SqlModelTenantDirectory | None = None
    workspaces: SqlModelWorkspaceDirectory | None = None

    def _assert_scope_active(self, ctx: ControlPlaneContext) -> None:
        tenant_id, workspace_id = ctx.tenant.tenant_id, ctx.workspace.workspace_id
        if self.tenants is not None:
            tenant = self.tenants.peek(tenant_id)
            if tenant is not None:
                _require_active(tenant.lifecycle, resource=f"tenant:{tenant_id}")
        if self.workspaces is not None:
            workspace = self.workspaces.peek(tenant_id, workspace_id)
            if workspace is not None:
                _require_active(
                    workspace.lifecycle,
                    resource=f"workspace:{workspace_id}",
                )

    def _verify(self, revision: RegistryRevision) -> RegistryRevision:
        expected = content_fingerprint(revision.content)
        if expected != revision.content_fingerprint:
            raise ControlPlaneError.conflict(
                "Revision content fingerprint mismatch (tamper detected)",
                extensions={
                    "revision_id": revision.revision_id,
                    "expected": expected,
                    "recorded": revision.content_fingerprint,
                },
            )
        return deepcopy(revision)

    def put_logical(self, ctx: ControlPlaneContext, identity: LogicalIdentity) -> None:
        if (
            identity.tenant_id != ctx.tenant.tenant_id
            or identity.workspace_id != ctx.workspace.workspace_id
        ):
            raise ControlPlaneError.not_found(
                "Logical identity not found",
                extensions={"logical_id": identity.logical_id},
            )
        with session_scope(self.engine) as session:
            self._assert_scope_active(ctx)
            existing = self._logical_row(
                session,
                ctx.tenant.tenant_id,
                ctx.workspace.workspace_id,
                identity.logical_id,
            )
            if existing is not None:
                raise ControlPlaneError.conflict(
                    "Logical identity already exists",
                    extensions={"logical_id": identity.logical_id},
                )
            session.add(
                LogicalIdentityRow(
                    tenant_id=identity.tenant_id,
                    workspace_id=identity.workspace_id,
                    logical_id=identity.logical_id,
                    kind=identity.kind,
                    created_at=identity.created_at or _utcnow_iso(),
                    metadata_json=_meta(identity.metadata),
                )
            )

    def get_logical(self, ctx: ControlPlaneContext, logical_id: str) -> LogicalIdentity:
        with session_scope(self.engine) as session:
            self._assert_scope_active(ctx)
            row = self._logical_row(
                session, ctx.tenant.tenant_id, ctx.workspace.workspace_id, logical_id
            )
            if row is None:
                raise ControlPlaneError.not_found(
                    "Logical identity not found",
                    extensions={"logical_id": logical_id},
                )
            return deepcopy(_logical_from_row(row))

    def list_logical(
        self,
        ctx: ControlPlaneContext,
        *,
        kind: str | None = None,
    ) -> Sequence[LogicalIdentity]:
        with session_scope(self.engine) as session:
            self._assert_scope_active(ctx)
            statement = select(LogicalIdentityRow).where(
                LogicalIdentityRow.tenant_id == ctx.tenant.tenant_id,
                LogicalIdentityRow.workspace_id == ctx.workspace.workspace_id,
            )
            if kind is not None:
                statement = statement.where(LogicalIdentityRow.kind == kind)
            rows = session.exec(statement).all()
            return sorted(
                (deepcopy(_logical_from_row(r)) for r in rows),
                key=lambda r: r.logical_id,
            )

    def put_revision(
        self,
        ctx: ControlPlaneContext,
        revision: RegistryRevision,
    ) -> None:
        if (
            revision.tenant_id != ctx.tenant.tenant_id
            or revision.workspace_id != ctx.workspace.workspace_id
        ):
            raise ControlPlaneError.not_found(
                "Revision not found",
                extensions={"revision_id": revision.revision_id},
            )
        expected = content_fingerprint(revision.content)
        if revision.content_fingerprint != expected:
            raise ControlPlaneError.conflict(
                "Revision content fingerprint mismatch",
                extensions={
                    "revision_id": revision.revision_id,
                    "expected": expected,
                    "recorded": revision.content_fingerprint,
                },
            )
        safe_content = safe_registry_content(revision.content)
        try:
            with session_scope(self.engine) as session:
                self._assert_scope_active(ctx)
                if (
                    self._revision_row(
                        session,
                        ctx.tenant.tenant_id,
                        ctx.workspace.workspace_id,
                        revision.revision_id,
                    )
                    is not None
                ):
                    raise ControlPlaneError.conflict(
                        "Revision is immutable; cannot overwrite",
                        extensions={"revision_id": revision.revision_id},
                    )
                logical = self._logical_row(
                    session,
                    ctx.tenant.tenant_id,
                    ctx.workspace.workspace_id,
                    revision.logical_id,
                )
                if logical is None:
                    session.add(
                        LogicalIdentityRow(
                            tenant_id=revision.tenant_id,
                            workspace_id=revision.workspace_id,
                            logical_id=revision.logical_id,
                            kind=revision.kind or "artifact",
                            created_at=revision.created_at or _utcnow_iso(),
                            metadata_json="{}",
                        )
                    )
                elif revision.kind is not None and logical.kind != revision.kind:
                    raise ControlPlaneError.conflict(
                        "Revision kind does not match its logical identity",
                        extensions={
                            "logical_id": revision.logical_id,
                            "logical_kind": logical.kind,
                            "revision_kind": revision.kind,
                        },
                    )
                session.add(
                    RevisionRow(
                        tenant_id=revision.tenant_id,
                        workspace_id=revision.workspace_id,
                        logical_id=revision.logical_id,
                        revision_id=revision.revision_id,
                        content_fingerprint=content_fingerprint(safe_content),
                        content_json=json.dumps(safe_content, sort_keys=True),
                        created_at=revision.created_at or _utcnow_iso(),
                        kind=revision.kind,
                        signature_placeholder=(
                            redact_control_plane_text(revision.signature_placeholder)
                            if revision.signature_placeholder is not None
                            else None
                        ),
                        provenance_json=(
                            _meta(revision.provenance_placeholder)
                            if revision.provenance_placeholder is not None
                            else None
                        ),
                    )
                )
        except IntegrityError as exc:
            raise ControlPlaneError.conflict(
                "Revision is immutable; cannot overwrite",
                extensions={"revision_id": revision.revision_id},
            ) from exc

    def get_revision(
        self,
        ctx: ControlPlaneContext,
        revision_id: str,
    ) -> RegistryRevision:
        with session_scope(self.engine) as session:
            self._assert_scope_active(ctx)
            row = self._revision_row(
                session, ctx.tenant.tenant_id, ctx.workspace.workspace_id, revision_id
            )
            if row is None:
                raise ControlPlaneError.not_found(
                    "Revision not found",
                    extensions={"revision_id": revision_id},
                )
            return self._verify(_revision_from_row(row))

    def list_revisions(
        self,
        ctx: ControlPlaneContext,
        logical_id: str,
    ) -> Sequence[RegistryRevision]:
        with session_scope(self.engine) as session:
            self._assert_scope_active(ctx)
            rows = session.exec(
                select(RevisionRow).where(
                    RevisionRow.tenant_id == ctx.tenant.tenant_id,
                    RevisionRow.workspace_id == ctx.workspace.workspace_id,
                    RevisionRow.logical_id == logical_id,
                )
            ).all()
            return sorted(
                (self._verify(_revision_from_row(r)) for r in rows),
                key=lambda r: r.revision_id,
            )

    def put_alias(self, ctx: ControlPlaneContext, alias: AliasRecord) -> None:
        if (
            alias.tenant_id != ctx.tenant.tenant_id
            or alias.workspace_id != ctx.workspace.workspace_id
        ):
            raise ControlPlaneError.not_found(
                "Alias not found",
                extensions={"alias": alias.alias},
            )
        with session_scope(self.engine) as session:
            self._assert_scope_active(ctx)
            revision = self._revision_row(
                session,
                ctx.tenant.tenant_id,
                ctx.workspace.workspace_id,
                alias.revision_id,
            )
            if revision is None:
                raise ControlPlaneError.not_found(
                    "Revision not found",
                    extensions={"revision_id": alias.revision_id},
                )
            if revision.logical_id != alias.logical_id:
                raise ControlPlaneError.conflict(
                    "Alias logical_id does not match target revision",
                    extensions={
                        "alias": alias.alias,
                        "logical_id": alias.logical_id,
                        "revision_id": alias.revision_id,
                    },
                )
            existing = self._alias_row(
                session, ctx.tenant.tenant_id, ctx.workspace.workspace_id, alias.alias
            )
            created = alias.created_at or _utcnow_iso()
            if existing is None:
                session.add(
                    AliasRow(
                        tenant_id=alias.tenant_id,
                        workspace_id=alias.workspace_id,
                        alias=alias.alias,
                        logical_id=alias.logical_id,
                        revision_id=alias.revision_id,
                        created_at=created,
                        metadata_json=_meta(alias.metadata),
                    )
                )
            else:
                existing.logical_id = alias.logical_id
                existing.revision_id = alias.revision_id
                existing.created_at = created
                existing.metadata_json = _meta(alias.metadata)
                session.add(existing)

    def resolve_alias(self, ctx: ControlPlaneContext, alias: str) -> RegistryRevision:
        with session_scope(self.engine) as session:
            self._assert_scope_active(ctx)
            record = self._alias_row(
                session, ctx.tenant.tenant_id, ctx.workspace.workspace_id, alias
            )
            if record is None:
                raise ControlPlaneError.not_found(
                    "Alias not found",
                    extensions={"alias": alias},
                )
            rev = self._revision_row(
                session,
                ctx.tenant.tenant_id,
                ctx.workspace.workspace_id,
                record.revision_id,
            )
            if rev is None:
                raise ControlPlaneError.not_found(
                    "Revision not found",
                    extensions={"revision_id": record.revision_id},
                )
            return self._verify(_revision_from_row(rev))

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
        with session_scope(self.engine) as session:
            self._assert_scope_active(ctx)
            source_row = self._revision_row(
                session,
                ctx.tenant.tenant_id,
                ctx.workspace.workspace_id,
                from_revision_id,
            )
            if source_row is None or source_row.logical_id != logical_id:
                raise ControlPlaneError.not_found(
                    "Revision not found",
                    extensions={"revision_id": from_revision_id},
                )
            source = _revision_from_row(source_row)
            source_snapshot = deepcopy(source)
            requested_body = (
                deepcopy(dict(content))
                if content is not None
                else deepcopy(dict(source.content))
            )
            body = safe_registry_content(requested_body)
            new_revision_id = f"rev-{uuid.uuid4().hex[:16]}"
            created = _utcnow_iso()
            new_rev = RegistryRevision(
                logical_id=logical_id,
                revision_id=new_revision_id,
                tenant_id=ctx.tenant.tenant_id,
                workspace_id=ctx.workspace.workspace_id,
                content_fingerprint=content_fingerprint(body),
                content=body,
                created_at=created,
                kind=source.kind,
                signature_placeholder=source.signature_placeholder,
                provenance_placeholder={
                    "promoted_from": from_revision_id,
                    "from_environment": from_environment,
                    "to_environment": to_environment,
                },
            )
            session.add(
                RevisionRow(
                    tenant_id=new_rev.tenant_id,
                    workspace_id=new_rev.workspace_id,
                    logical_id=new_rev.logical_id,
                    revision_id=new_rev.revision_id,
                    content_fingerprint=new_rev.content_fingerprint,
                    content_json=json.dumps(dict(new_rev.content), sort_keys=True),
                    created_at=created,
                    kind=new_rev.kind,
                    signature_placeholder=new_rev.signature_placeholder,
                    provenance_json=json.dumps(
                        dict(new_rev.provenance_placeholder or {}), sort_keys=True
                    ),
                )
            )
            # Prior revision must remain unchanged (immutability guard).
            session.flush()
            prior = self._revision_row(
                session,
                ctx.tenant.tenant_id,
                ctx.workspace.workspace_id,
                from_revision_id,
            )
            if prior is None or _revision_from_row(prior) != source_snapshot:
                raise ControlPlaneError.conflict(
                    "Promotion attempted to mutate prior revision",
                    extensions={"revision_id": from_revision_id},
                )
            promotion = PromotionRecord(
                promotion_id=f"promo-{uuid.uuid4().hex[:16]}",
                tenant_id=ctx.tenant.tenant_id,
                workspace_id=ctx.workspace.workspace_id,
                logical_id=logical_id,
                from_revision_id=from_revision_id,
                to_revision_id=new_revision_id,
                from_environment=from_environment,
                to_environment=to_environment,
                created_at=created,
                metadata=json.loads(_meta(metadata)),
            )
            session.add(
                PromotionRow(
                    tenant_id=promotion.tenant_id,
                    workspace_id=promotion.workspace_id,
                    promotion_id=promotion.promotion_id,
                    logical_id=promotion.logical_id,
                    from_revision_id=promotion.from_revision_id,
                    to_revision_id=promotion.to_revision_id,
                    from_environment=promotion.from_environment,
                    to_environment=promotion.to_environment,
                    created_at=created,
                    metadata_json=_meta(promotion.metadata),
                )
            )
            return deepcopy(promotion)

    def get_promotion(
        self,
        ctx: ControlPlaneContext,
        promotion_id: str,
    ) -> PromotionRecord:
        with session_scope(self.engine) as session:
            self._assert_scope_active(ctx)
            row = session.exec(
                select(PromotionRow).where(
                    PromotionRow.tenant_id == ctx.tenant.tenant_id,
                    PromotionRow.workspace_id == ctx.workspace.workspace_id,
                    PromotionRow.promotion_id == promotion_id,
                )
            ).first()
            if row is None:
                raise ControlPlaneError.not_found(
                    "Promotion not found",
                    extensions={"promotion_id": promotion_id},
                )
            return deepcopy(_promotion_from_row(row))

    @staticmethod
    def _logical_row(
        session: Session, tenant_id: str, workspace_id: str, logical_id: str
    ) -> LogicalIdentityRow | None:
        return session.exec(
            select(LogicalIdentityRow).where(
                LogicalIdentityRow.tenant_id == tenant_id,
                LogicalIdentityRow.workspace_id == workspace_id,
                LogicalIdentityRow.logical_id == logical_id,
            )
        ).first()

    @staticmethod
    def _revision_row(
        session: Session, tenant_id: str, workspace_id: str, revision_id: str
    ) -> RevisionRow | None:
        return session.exec(
            select(RevisionRow).where(
                RevisionRow.tenant_id == tenant_id,
                RevisionRow.workspace_id == workspace_id,
                RevisionRow.revision_id == revision_id,
            )
        ).first()

    @staticmethod
    def _alias_row(
        session: Session, tenant_id: str, workspace_id: str, alias: str
    ) -> AliasRow | None:
        return session.exec(
            select(AliasRow).where(
                AliasRow.tenant_id == tenant_id,
                AliasRow.workspace_id == workspace_id,
                AliasRow.alias == alias,
            )
        ).first()


@dataclass
class SqlModelRegistryProvider:
    """SQLModel :class:`RegistryProvider` with shared suspension checks."""

    engine: Engine
    tenants: SqlModelTenantDirectory | None = None
    workspaces: SqlModelWorkspaceDirectory | None = None
    revisions: SqlModelRevisionRegistry | None = None

    def __post_init__(self) -> None:
        if self.tenants is None:
            self.tenants = SqlModelTenantDirectory(engine=self.engine)
        if self.workspaces is None:
            self.workspaces = SqlModelWorkspaceDirectory(
                engine=self.engine, tenants=self.tenants
            )
        else:
            self.workspaces.tenants = self.tenants
        if self.revisions is None:
            self.revisions = SqlModelRevisionRegistry(
                engine=self.engine,
                tenants=self.tenants,
                workspaces=self.workspaces,
            )
        else:
            self.revisions.tenants = self.tenants
            self.revisions.workspaces = self.workspaces

    def put_environment(
        self,
        ctx: ControlPlaneContext,
        record: EnvironmentRecord,
    ) -> None:
        if record.tenant_id != ctx.tenant.tenant_id:
            raise ControlPlaneError.not_found(
                "Environment not found",
                extensions={"environment_id": record.environment_id},
            )
        if (
            record.workspace_id is not None
            and record.workspace_id != ctx.workspace.workspace_id
        ):
            raise ControlPlaneError.not_found(
                "Environment not found",
                extensions={"environment_id": record.environment_id},
            )
        assert self.tenants is not None
        with session_scope(self.engine) as session:
            tenant = self.tenants.peek(ctx.tenant.tenant_id)
            if tenant is not None:
                _require_active(
                    tenant.lifecycle, resource=f"tenant:{ctx.tenant.tenant_id}"
                )
            assert self.workspaces is not None
            workspace = self.workspaces.peek(
                ctx.tenant.tenant_id, ctx.workspace.workspace_id
            )
            if workspace is not None:
                _require_active(
                    workspace.lifecycle,
                    resource=f"workspace:{ctx.workspace.workspace_id}",
                )
            now = _utcnow_iso()
            existing = session.exec(
                select(EnvironmentRow).where(
                    EnvironmentRow.tenant_id == record.tenant_id,
                    EnvironmentRow.environment_id == record.environment_id,
                )
            ).first()
            if (
                existing is not None
                and existing.workspace_id is not None
                and existing.workspace_id != ctx.workspace.workspace_id
            ):
                raise ControlPlaneError.not_found(
                    "Environment not found",
                    extensions={"environment_id": record.environment_id},
                )
            if existing is not None:
                _require_active(
                    LifecycleState(existing.lifecycle),
                    resource=f"environment:{record.environment_id}",
                )
            if existing is None:
                session.add(
                    EnvironmentRow(
                        tenant_id=record.tenant_id,
                        environment_id=record.environment_id,
                        name=record.name,
                        workspace_id=record.workspace_id,
                        lifecycle=record.lifecycle.value,
                        created_at=record.created_at or now,
                        updated_at=now,
                        metadata_json=_meta(record.metadata),
                    )
                )
            else:
                existing.name = record.name
                existing.workspace_id = record.workspace_id
                existing.lifecycle = record.lifecycle.value
                existing.updated_at = now
                existing.metadata_json = _meta(record.metadata)
                session.add(existing)

    def get_environment(
        self,
        ctx: ControlPlaneContext,
        environment_id: str,
    ) -> EnvironmentRecord:
        assert self.tenants is not None
        with session_scope(self.engine) as session:
            tenant = self.tenants.peek(ctx.tenant.tenant_id)
            if tenant is not None:
                _require_active(
                    tenant.lifecycle, resource=f"tenant:{ctx.tenant.tenant_id}"
                )
            assert self.workspaces is not None
            workspace = self.workspaces.peek(
                ctx.tenant.tenant_id, ctx.workspace.workspace_id
            )
            if workspace is not None:
                _require_active(
                    workspace.lifecycle,
                    resource=f"workspace:{ctx.workspace.workspace_id}",
                )
            row = session.exec(
                select(EnvironmentRow).where(
                    EnvironmentRow.tenant_id == ctx.tenant.tenant_id,
                    EnvironmentRow.environment_id == environment_id,
                )
            ).first()
            if row is None or (
                row.workspace_id is not None
                and row.workspace_id != ctx.workspace.workspace_id
            ):
                raise ControlPlaneError.not_found(
                    "Environment not found",
                    extensions={"environment_id": environment_id},
                )
            record = EnvironmentRecord(
                tenant_id=row.tenant_id,
                environment_id=row.environment_id,
                name=row.name,
                workspace_id=row.workspace_id,
                lifecycle=LifecycleState(row.lifecycle),
                created_at=row.created_at,
                updated_at=row.updated_at,
                metadata=_load_meta(row.metadata_json),
            )
            _require_active(
                record.lifecycle,
                resource=f"environment:{environment_id}",
            )
            return deepcopy(record)

    def put_security_domain(
        self,
        ctx: ControlPlaneContext,
        record: SecurityDomainRecord,
    ) -> None:
        if record.domain_id != ctx.security_domain.domain_id:
            raise ControlPlaneError.not_found(
                "Security domain not found",
                extensions={"domain_id": record.domain_id},
            )
        with session_scope(self.engine) as session:
            now = _utcnow_iso()
            existing = session.exec(
                select(SecurityDomainRow).where(
                    SecurityDomainRow.domain_id == record.domain_id
                )
            ).first()
            if existing is not None:
                _require_active(
                    LifecycleState(existing.lifecycle),
                    resource=f"security_domain:{record.domain_id}",
                )
                existing.lifecycle = record.lifecycle.value
                existing.display_name = record.display_name
                existing.updated_at = now
                existing.metadata_json = _meta(record.metadata)
                session.add(existing)
            else:
                session.add(
                    SecurityDomainRow(
                        domain_id=record.domain_id,
                        lifecycle=record.lifecycle.value,
                        display_name=record.display_name,
                        created_at=record.created_at or now,
                        updated_at=now,
                        metadata_json=_meta(record.metadata),
                    )
                )

    def get_security_domain(
        self,
        ctx: ControlPlaneContext,
        domain_id: str,
    ) -> SecurityDomainRecord:
        with session_scope(self.engine) as session:
            row = session.exec(
                select(SecurityDomainRow).where(
                    SecurityDomainRow.domain_id == domain_id
                )
            ).first()
            if row is None or row.domain_id != ctx.security_domain.domain_id:
                raise ControlPlaneError.not_found(
                    "Security domain not found",
                    extensions={"domain_id": domain_id},
                )
            record = SecurityDomainRecord(
                domain_id=row.domain_id,
                lifecycle=LifecycleState(row.lifecycle),
                display_name=row.display_name,
                created_at=row.created_at,
                updated_at=row.updated_at,
                metadata=_load_meta(row.metadata_json),
            )
            _require_active(record.lifecycle, resource=f"security_domain:{domain_id}")
            return deepcopy(record)


__all__ = [
    "REGISTRY_TABLES",
    "SqlModelRegistryProvider",
    "SqlModelRevisionRegistry",
    "SqlModelTenantDirectory",
    "SqlModelWorkspaceDirectory",
    "create_registry_tables",
]
