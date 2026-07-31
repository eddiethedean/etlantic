"""In-memory registry provider with tenant isolation (CP2 / 040-T, 040-R)."""

from __future__ import annotations

import hashlib
import json
import threading
import uuid
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any

from etlantic.control_plane.errors import ControlPlaneError
from etlantic.control_plane.models import ControlPlaneContext
from etlantic.control_plane.redaction import (
    redact_control_plane_payload,
    redact_control_plane_text,
)
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


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def content_fingerprint(content: Mapping[str, Any]) -> str:
    """Deterministic fingerprint of a secret-free metadata document."""
    payload = json.dumps(dict(content), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _require_active(lifecycle: LifecycleState, *, resource: str) -> None:
    if lifecycle == LifecycleState.SUSPENDED:
        raise ControlPlaneError.forbidden(
            f"{resource} is suspended; registry operations fail closed",
            extensions={"lifecycle": lifecycle.value, "resource": resource},
        )
    if lifecycle == LifecycleState.ARCHIVED:
        raise ControlPlaneError.forbidden(
            f"{resource} is archived; registry writes fail closed",
            extensions={"lifecycle": lifecycle.value, "resource": resource},
        )


def _safe_metadata(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    redacted = redact_control_plane_payload(deepcopy(dict(metadata or {})))
    return redacted if isinstance(redacted, dict) else {}


def _safe_registry_value(value: Any) -> Any:
    """Redact resolved secrets while preserving canonical ``secret_ref`` objects."""
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for raw_key, child in value.items():
            key = str(raw_key)
            normalized = key.casefold().replace("-", "_")
            if normalized == "secret_ref":
                if not isinstance(child, Mapping):
                    out[key] = "***"
                    continue
                allowed = {"provider", "name"}
                if set(child) == allowed:
                    out[key] = {
                        "provider": redact_control_plane_text(str(child["provider"])),
                        "name": redact_control_plane_text(str(child["name"])),
                    }
                else:
                    out[key] = "***"
                continue
            if normalized in {"has_secret_ref", "secret_provider"}:
                out[key] = _safe_registry_value(child)
                continue
            probe = redact_control_plane_payload({key: "etlantic-safe-probe"})
            if isinstance(probe, dict) and probe.get(key) == "***":
                out[key] = "***"
            else:
                out[key] = _safe_registry_value(child)
        return out
    if isinstance(value, (list, tuple)):
        return [_safe_registry_value(item) for item in value]
    if isinstance(value, str):
        return redact_control_plane_text(value)
    return deepcopy(value)


def safe_registry_content(content: Mapping[str, Any]) -> dict[str, Any]:
    """Return a detached, JSON-shaped, secret-free registry content document."""
    safe = _safe_registry_value(content)
    return safe if isinstance(safe, dict) else {}


@dataclass
class MemoryTenantDirectory:
    """In-memory tenant directory with isolation and suspension fail-closed."""

    _tenants: dict[str, TenantRecord] = field(default_factory=dict)
    _lock: threading.RLock = field(default_factory=threading.RLock)

    def get(self, ctx: ControlPlaneContext, tenant_id: str) -> TenantRecord:
        with self._lock:
            record = self._tenants.get(tenant_id)
            if record is None:
                raise ControlPlaneError.not_found(
                    "Tenant not found",
                    extensions={"tenant_id": tenant_id},
                )
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
        with self._lock:
            existing = self._tenants.get(record.tenant_id)
            if existing is not None:
                _require_active(
                    existing.lifecycle, resource=f"tenant:{record.tenant_id}"
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
            stored = replace(
                record,
                created_at=existing.created_at
                if existing
                else (record.created_at or now),
                updated_at=now,
                metadata=_safe_metadata(record.metadata),
            )
            self._tenants[record.tenant_id] = stored

    def list(self, ctx: ControlPlaneContext) -> Sequence[TenantRecord]:
        with self._lock:
            out: list[TenantRecord] = []
            for record in self._tenants.values():
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
        with self._lock:
            record = self._tenants.get(tenant_id)
            if record is None or (
                ctx.tenant.tenant_id != tenant_id
                and record.security_domain_id != ctx.security_domain.domain_id
            ):
                raise ControlPlaneError.not_found(
                    "Tenant not found",
                    extensions={"tenant_id": tenant_id},
                )
            updated = replace(record, lifecycle=state, updated_at=_utcnow_iso())
            self._tenants[tenant_id] = updated
            return deepcopy(updated)

    def peek(self, tenant_id: str) -> TenantRecord | None:
        """Internal lifecycle peek (no authz) for suspension checks."""
        with self._lock:
            record = self._tenants.get(tenant_id)
            return deepcopy(record) if record is not None else None


@dataclass
class MemoryWorkspaceDirectory:
    """In-memory workspace directory keyed by (tenant_id, workspace_id)."""

    _workspaces: dict[tuple[str, str], WorkspaceRecord] = field(default_factory=dict)
    _tenants: MemoryTenantDirectory | None = None
    _lock: threading.RLock = field(default_factory=threading.RLock)

    def _assert_tenant_active(self, tenant_id: str) -> None:
        if self._tenants is None:
            return
        tenant = self._tenants.peek(tenant_id)
        if tenant is not None:
            _require_active(tenant.lifecycle, resource=f"tenant:{tenant_id}")

    def get(self, ctx: ControlPlaneContext, workspace_id: str) -> WorkspaceRecord:
        key = (ctx.tenant.tenant_id, workspace_id)
        with self._lock:
            self._assert_tenant_active(ctx.tenant.tenant_id)
            record = self._workspaces.get(key)
            if record is None:
                raise ControlPlaneError.not_found(
                    "Workspace not found",
                    extensions={"workspace_id": workspace_id},
                )
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
        key = (record.tenant_id, record.workspace_id)
        with self._lock:
            self._assert_tenant_active(record.tenant_id)
            existing = self._workspaces.get(key)
            if existing is not None:
                _require_active(
                    existing.lifecycle,
                    resource=f"workspace:{record.workspace_id}",
                )
            now = _utcnow_iso()
            stored = replace(
                record,
                created_at=existing.created_at
                if existing
                else (record.created_at or now),
                updated_at=now,
                metadata=_safe_metadata(record.metadata),
            )
            self._workspaces[key] = stored

    def list(self, ctx: ControlPlaneContext) -> Sequence[WorkspaceRecord]:
        tenant_id = ctx.tenant.tenant_id
        with self._lock:
            self._assert_tenant_active(tenant_id)
            return sorted(
                (
                    deepcopy(record)
                    for (t, _), record in self._workspaces.items()
                    if t == tenant_id
                ),
                key=lambda r: r.workspace_id,
            )

    def set_lifecycle(
        self,
        ctx: ControlPlaneContext,
        workspace_id: str,
        state: LifecycleState,
    ) -> WorkspaceRecord:
        key = (ctx.tenant.tenant_id, workspace_id)
        with self._lock:
            self._assert_tenant_active(ctx.tenant.tenant_id)
            record = self._workspaces.get(key)
            if record is None:
                raise ControlPlaneError.not_found(
                    "Workspace not found",
                    extensions={"workspace_id": workspace_id},
                )
            updated = replace(record, lifecycle=state, updated_at=_utcnow_iso())
            self._workspaces[key] = updated
            return deepcopy(updated)

    def peek(self, tenant_id: str, workspace_id: str) -> WorkspaceRecord | None:
        with self._lock:
            record = self._workspaces.get((tenant_id, workspace_id))
            return deepcopy(record) if record is not None else None


@dataclass
class MemoryRevisionRegistry:
    """Append-only revision store with alias resolution and promotion records."""

    _logical: dict[tuple[str, str, str], LogicalIdentity] = field(default_factory=dict)
    _revisions: dict[tuple[str, str, str], RegistryRevision] = field(
        default_factory=dict
    )
    _aliases: dict[tuple[str, str, str], AliasRecord] = field(default_factory=dict)
    _promotions: dict[tuple[str, str, str], PromotionRecord] = field(
        default_factory=dict
    )
    _tenants: MemoryTenantDirectory | None = None
    _workspaces: MemoryWorkspaceDirectory | None = None
    _lock: threading.RLock = field(default_factory=threading.RLock)

    def _assert_scope_active(self, ctx: ControlPlaneContext) -> None:
        tenant_id, workspace_id = ctx.tenant.tenant_id, ctx.workspace.workspace_id
        if self._tenants is not None:
            tenant = self._tenants.peek(tenant_id)
            if tenant is not None:
                _require_active(tenant.lifecycle, resource=f"tenant:{tenant_id}")
        if self._workspaces is not None:
            workspace = self._workspaces.peek(tenant_id, workspace_id)
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
        key = (*ctx.scope_key, identity.logical_id)
        with self._lock:
            self._assert_scope_active(ctx)
            if key in self._logical:
                raise ControlPlaneError.conflict(
                    "Logical identity already exists",
                    extensions={"logical_id": identity.logical_id},
                )
            stored = replace(
                identity,
                created_at=identity.created_at or _utcnow_iso(),
                metadata=_safe_metadata(identity.metadata),
            )
            self._logical[key] = stored

    def get_logical(self, ctx: ControlPlaneContext, logical_id: str) -> LogicalIdentity:
        key = (*ctx.scope_key, logical_id)
        with self._lock:
            self._assert_scope_active(ctx)
            record = self._logical.get(key)
            if record is None:
                raise ControlPlaneError.not_found(
                    "Logical identity not found",
                    extensions={"logical_id": logical_id},
                )
            return deepcopy(record)

    def list_logical(
        self,
        ctx: ControlPlaneContext,
        *,
        kind: str | None = None,
    ) -> Sequence[LogicalIdentity]:
        tenant_id, workspace_id = ctx.scope_key
        with self._lock:
            self._assert_scope_active(ctx)
            out: list[LogicalIdentity] = []
            for (t, w, _), record in self._logical.items():
                if t != tenant_id or w != workspace_id:
                    continue
                if kind is not None and record.kind != kind:
                    continue
                out.append(deepcopy(record))
            return sorted(out, key=lambda r: r.logical_id)

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
        key = (*ctx.scope_key, revision.revision_id)
        with self._lock:
            self._assert_scope_active(ctx)
            if key in self._revisions:
                raise ControlPlaneError.conflict(
                    "Revision is immutable; cannot overwrite",
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
            logical_key = (*ctx.scope_key, revision.logical_id)
            logical = self._logical.get(logical_key)
            if logical is None:
                self._logical[logical_key] = LogicalIdentity(
                    logical_id=revision.logical_id,
                    tenant_id=revision.tenant_id,
                    workspace_id=revision.workspace_id,
                    kind=revision.kind or "artifact",
                    created_at=revision.created_at or _utcnow_iso(),
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
            safe_content = safe_registry_content(revision.content)
            stored = replace(
                revision,
                content=safe_content,
                content_fingerprint=content_fingerprint(safe_content),
                created_at=revision.created_at or _utcnow_iso(),
                signature_placeholder=(
                    redact_control_plane_text(revision.signature_placeholder)
                    if revision.signature_placeholder is not None
                    else None
                ),
                provenance_placeholder=(
                    _safe_metadata(revision.provenance_placeholder)
                    if revision.provenance_placeholder is not None
                    else None
                ),
            )
            self._revisions[key] = stored

    def get_revision(
        self,
        ctx: ControlPlaneContext,
        revision_id: str,
    ) -> RegistryRevision:
        key = (*ctx.scope_key, revision_id)
        with self._lock:
            self._assert_scope_active(ctx)
            record = self._revisions.get(key)
            if record is None:
                raise ControlPlaneError.not_found(
                    "Revision not found",
                    extensions={"revision_id": revision_id},
                )
            return self._verify(record)

    def list_revisions(
        self,
        ctx: ControlPlaneContext,
        logical_id: str,
    ) -> Sequence[RegistryRevision]:
        tenant_id, workspace_id = ctx.scope_key
        with self._lock:
            self._assert_scope_active(ctx)
            return sorted(
                (
                    self._verify(rev)
                    for (t, w, _), rev in self._revisions.items()
                    if t == tenant_id
                    and w == workspace_id
                    and rev.logical_id == logical_id
                ),
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
        rev_key = (*ctx.scope_key, alias.revision_id)
        alias_key = (*ctx.scope_key, alias.alias)
        with self._lock:
            self._assert_scope_active(ctx)
            revision = self._revisions.get(rev_key)
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
            stored = replace(
                alias,
                created_at=alias.created_at or _utcnow_iso(),
                metadata=_safe_metadata(alias.metadata),
            )
            self._aliases[alias_key] = stored

    def resolve_alias(self, ctx: ControlPlaneContext, alias: str) -> RegistryRevision:
        alias_key = (*ctx.scope_key, alias)
        with self._lock:
            self._assert_scope_active(ctx)
            record = self._aliases.get(alias_key)
            if record is None:
                raise ControlPlaneError.not_found(
                    "Alias not found",
                    extensions={"alias": alias},
                )
            rev = self._revisions.get((*ctx.scope_key, record.revision_id))
            if rev is None:
                raise ControlPlaneError.not_found(
                    "Revision not found",
                    extensions={"revision_id": record.revision_id},
                )
            return self._verify(rev)

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
        from_key = (*ctx.scope_key, from_revision_id)
        with self._lock:
            self._assert_scope_active(ctx)
            source = self._revisions.get(from_key)
            if source is None or source.logical_id != logical_id:
                raise ControlPlaneError.not_found(
                    "Revision not found",
                    extensions={"revision_id": from_revision_id},
                )
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
            self._revisions[(*ctx.scope_key, new_revision_id)] = new_rev
            # Prior revision must remain unchanged (immutability guard).
            if self._revisions[from_key] != source_snapshot:
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
                metadata=_safe_metadata(metadata),
            )
            self._promotions[(*ctx.scope_key, promotion.promotion_id)] = promotion
            return deepcopy(promotion)

    def get_promotion(
        self,
        ctx: ControlPlaneContext,
        promotion_id: str,
    ) -> PromotionRecord:
        key = (*ctx.scope_key, promotion_id)
        with self._lock:
            self._assert_scope_active(ctx)
            record = self._promotions.get(key)
            if record is None:
                raise ControlPlaneError.not_found(
                    "Promotion not found",
                    extensions={"promotion_id": promotion_id},
                )
            return deepcopy(record)


@dataclass
class MemoryRegistryProvider:
    """In-memory :class:`RegistryProvider` with shared suspension checks."""

    tenants: MemoryTenantDirectory = field(default_factory=MemoryTenantDirectory)
    workspaces: MemoryWorkspaceDirectory = field(
        default_factory=MemoryWorkspaceDirectory
    )
    revisions: MemoryRevisionRegistry = field(default_factory=MemoryRevisionRegistry)
    _environments: dict[tuple[str, str], EnvironmentRecord] = field(
        default_factory=dict
    )
    _security_domains: dict[str, SecurityDomainRecord] = field(default_factory=dict)
    _lock: threading.RLock = field(default_factory=threading.RLock)

    def __post_init__(self) -> None:
        self.workspaces._tenants = self.tenants
        self.revisions._tenants = self.tenants
        self.revisions._workspaces = self.workspaces

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
        with self._lock:
            tenant = self.tenants.peek(ctx.tenant.tenant_id)
            if tenant is not None:
                _require_active(
                    tenant.lifecycle, resource=f"tenant:{ctx.tenant.tenant_id}"
                )
            workspace = self.workspaces.peek(
                ctx.tenant.tenant_id, ctx.workspace.workspace_id
            )
            if workspace is not None:
                _require_active(
                    workspace.lifecycle,
                    resource=f"workspace:{ctx.workspace.workspace_id}",
                )
            now = _utcnow_iso()
            existing = self._environments.get((record.tenant_id, record.environment_id))
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
                    existing.lifecycle,
                    resource=f"environment:{record.environment_id}",
                )
            stored = replace(
                record,
                created_at=existing.created_at
                if existing
                else (record.created_at or now),
                updated_at=now,
                metadata=_safe_metadata(record.metadata),
            )
            self._environments[(record.tenant_id, record.environment_id)] = stored

    def get_environment(
        self,
        ctx: ControlPlaneContext,
        environment_id: str,
    ) -> EnvironmentRecord:
        key = (ctx.tenant.tenant_id, environment_id)
        with self._lock:
            tenant = self.tenants.peek(ctx.tenant.tenant_id)
            if tenant is not None:
                _require_active(
                    tenant.lifecycle, resource=f"tenant:{ctx.tenant.tenant_id}"
                )
            workspace = self.workspaces.peek(
                ctx.tenant.tenant_id, ctx.workspace.workspace_id
            )
            if workspace is not None:
                _require_active(
                    workspace.lifecycle,
                    resource=f"workspace:{ctx.workspace.workspace_id}",
                )
            record = self._environments.get(key)
            if record is None or (
                record.workspace_id is not None
                and record.workspace_id != ctx.workspace.workspace_id
            ):
                raise ControlPlaneError.not_found(
                    "Environment not found",
                    extensions={"environment_id": environment_id},
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
        # Workload/service identity alone is not cross-domain authority. A
        # separate policy layer must derive a matching security-domain context.
        if record.domain_id != ctx.security_domain.domain_id:
            raise ControlPlaneError.not_found(
                "Security domain not found",
                extensions={"domain_id": record.domain_id},
            )
        with self._lock:
            now = _utcnow_iso()
            existing = self._security_domains.get(record.domain_id)
            if existing is not None:
                _require_active(
                    existing.lifecycle, resource=f"security_domain:{record.domain_id}"
                )
            stored = replace(
                record,
                created_at=existing.created_at
                if existing
                else (record.created_at or now),
                updated_at=now,
                metadata=_safe_metadata(record.metadata),
            )
            self._security_domains[record.domain_id] = stored

    def get_security_domain(
        self,
        ctx: ControlPlaneContext,
        domain_id: str,
    ) -> SecurityDomainRecord:
        with self._lock:
            record = self._security_domains.get(domain_id)
            if record is None or record.domain_id != ctx.security_domain.domain_id:
                raise ControlPlaneError.not_found(
                    "Security domain not found",
                    extensions={"domain_id": domain_id},
                )
            _require_active(record.lifecycle, resource=f"security_domain:{domain_id}")
            return deepcopy(record)


__all__ = [
    "MemoryRegistryProvider",
    "MemoryRevisionRegistry",
    "MemoryTenantDirectory",
    "MemoryWorkspaceDirectory",
    "content_fingerprint",
    "safe_registry_content",
]
