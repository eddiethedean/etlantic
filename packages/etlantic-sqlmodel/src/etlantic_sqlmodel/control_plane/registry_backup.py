"""Registry SQLite backup/restore transcript helpers (CP2 / 040-O).

Dump and load tenants, workspaces, and revisions while preserving compound
tenant/workspace scope. Content bodies are included for round-trip fidelity
but histories/impact remain separate (metadata-only stores).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.engine import Engine

from etlantic.control_plane import (
    AliasRecord,
    ControlPlaneContext,
    EnvironmentRecord,
    EnvironmentRef,
    LogicalIdentity,
    Principal,
    PromotionRecord,
    RegistryRevision,
    SecurityDomain,
    SecurityDomainRecord,
    TenantRecord,
    TenantRef,
    WorkspaceRecord,
    WorkspaceRef,
    content_fingerprint,
)
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
from etlantic_sqlmodel.control_plane.registry_stores import (
    SqlModelRegistryProvider,
    create_registry_tables,
)
from etlantic_sqlmodel.control_plane.session import session_scope
from sqlmodel import select


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _admin_ctx(
    *,
    tenant_id: str,
    workspace_id: str,
    domain_id: str = "backup-domain",
) -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal(subject="backup", kind="service"),
        tenant=TenantRef(tenant_id=tenant_id),
        workspace=WorkspaceRef(tenant_id=tenant_id, workspace_id=workspace_id),
        environment=EnvironmentRef(name="development"),
        security_domain=SecurityDomain(domain_id=domain_id),
    )


@dataclass(frozen=True, slots=True)
class BackupTranscript:
    """Structured backup transcript (scope-preserving)."""

    schema: str
    created_at: str
    tenants: tuple[dict[str, Any], ...]
    workspaces: tuple[dict[str, Any], ...]
    revisions: tuple[dict[str, Any], ...]
    logicals: tuple[dict[str, Any], ...] = ()
    aliases: tuple[dict[str, Any], ...] = ()
    promotions: tuple[dict[str, Any], ...] = ()
    environments: tuple[dict[str, Any], ...] = ()
    security_domains: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "created_at": self.created_at,
            "tenants": list(self.tenants),
            "workspaces": list(self.workspaces),
            "revisions": list(self.revisions),
            "logicals": list(self.logicals),
            "aliases": list(self.aliases),
            "promotions": list(self.promotions),
            "environments": list(self.environments),
            "security_domains": list(self.security_domains),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> BackupTranscript:
        return cls(
            schema=str(data.get("schema") or "etlantic.registry_backup/1"),
            created_at=str(data.get("created_at") or _utcnow_iso()),
            tenants=tuple(dict(item) for item in data.get("tenants") or ()),
            workspaces=tuple(dict(item) for item in data.get("workspaces") or ()),
            revisions=tuple(dict(item) for item in data.get("revisions") or ()),
            logicals=tuple(dict(item) for item in data.get("logicals") or ()),
            aliases=tuple(dict(item) for item in data.get("aliases") or ()),
            promotions=tuple(dict(item) for item in data.get("promotions") or ()),
            environments=tuple(dict(item) for item in data.get("environments") or ()),
            security_domains=tuple(
                dict(item) for item in data.get("security_domains") or ()
            ),
        )


BACKUP_SCHEMA = "etlantic.registry_backup/1"


def dump_registry_sqlite(engine: Engine) -> BackupTranscript:
    """Dump tenants, workspaces, and revisions from a registry SQLite engine."""
    with session_scope(engine) as session:
        tenants = [
            {
                "tenant_id": row.tenant_id,
                "lifecycle": row.lifecycle,
                "display_name": row.display_name,
                "security_domain_id": row.security_domain_id,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
                "metadata": json.loads(row.metadata_json or "{}"),
            }
            for row in session.exec(select(TenantRow)).all()
        ]
        workspaces = [
            {
                "tenant_id": row.tenant_id,
                "workspace_id": row.workspace_id,
                "lifecycle": row.lifecycle,
                "display_name": row.display_name,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
                "metadata": json.loads(row.metadata_json or "{}"),
            }
            for row in session.exec(select(WorkspaceRow)).all()
        ]
        revisions = [
            {
                "tenant_id": row.tenant_id,
                "workspace_id": row.workspace_id,
                "logical_id": row.logical_id,
                "revision_id": row.revision_id,
                "content_fingerprint": row.content_fingerprint,
                "content": json.loads(row.content_json or "{}"),
                "created_at": row.created_at,
                "kind": row.kind,
                "signature_placeholder": row.signature_placeholder,
                "provenance": (
                    json.loads(row.provenance_json) if row.provenance_json else {}
                ),
            }
            for row in session.exec(select(RevisionRow)).all()
        ]
        logicals = [
            {
                "tenant_id": row.tenant_id,
                "workspace_id": row.workspace_id,
                "logical_id": row.logical_id,
                "kind": row.kind,
                "created_at": row.created_at,
                "metadata": json.loads(row.metadata_json or "{}"),
            }
            for row in session.exec(select(LogicalIdentityRow)).all()
        ]
        aliases = [
            {
                "tenant_id": row.tenant_id,
                "workspace_id": row.workspace_id,
                "alias": row.alias,
                "logical_id": row.logical_id,
                "revision_id": row.revision_id,
                "created_at": row.created_at,
                "metadata": json.loads(row.metadata_json or "{}"),
            }
            for row in session.exec(select(AliasRow)).all()
        ]
        promotions = [
            {
                "tenant_id": row.tenant_id,
                "workspace_id": row.workspace_id,
                "promotion_id": row.promotion_id,
                "logical_id": row.logical_id,
                "from_revision_id": row.from_revision_id,
                "to_revision_id": row.to_revision_id,
                "from_environment": row.from_environment,
                "to_environment": row.to_environment,
                "created_at": row.created_at,
                "metadata": json.loads(row.metadata_json or "{}"),
            }
            for row in session.exec(select(PromotionRow)).all()
        ]
        environments = [
            {
                "tenant_id": row.tenant_id,
                "environment_id": row.environment_id,
                "name": row.name,
                "workspace_id": row.workspace_id,
                "lifecycle": row.lifecycle,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
                "metadata": json.loads(row.metadata_json or "{}"),
            }
            for row in session.exec(select(EnvironmentRow)).all()
        ]
        security_domains = [
            {
                "domain_id": row.domain_id,
                "lifecycle": row.lifecycle,
                "display_name": row.display_name,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
                "metadata": json.loads(row.metadata_json or "{}"),
            }
            for row in session.exec(select(SecurityDomainRow)).all()
        ]
    return BackupTranscript(
        schema=BACKUP_SCHEMA,
        created_at=_utcnow_iso(),
        tenants=tuple(tenants),
        workspaces=tuple(workspaces),
        revisions=tuple(revisions),
        logicals=tuple(logicals),
        aliases=tuple(aliases),
        promotions=tuple(promotions),
        environments=tuple(environments),
        security_domains=tuple(security_domains),
    )


def write_backup_transcript(path: str | Path, transcript: BackupTranscript) -> None:
    """Write a backup transcript JSON file."""
    Path(path).write_text(
        json.dumps(transcript.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def read_backup_transcript(path: str | Path) -> BackupTranscript:
    """Read a backup transcript JSON file."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return BackupTranscript.from_dict(data)


def load_registry_sqlite(
    engine: Engine,
    transcript: BackupTranscript,
    *,
    create_tables: bool = True,
) -> SqlModelRegistryProvider:
    """Restore tenants/workspaces/revisions into ``engine``, preserving scope."""
    if create_tables:
        create_registry_tables(engine)
    provider = SqlModelRegistryProvider(engine)

    for domain in transcript.security_domains:
        domain_id = str(domain["domain_id"])
        provider.put_security_domain(
            _admin_ctx(
                tenant_id="__backup__",
                workspace_id="__backup__",
                domain_id=domain_id,
            ),
            SecurityDomainRecord.from_dict(domain),
        )

    # Group by tenant for scoped puts.
    for tenant in transcript.tenants:
        tenant_id = str(tenant["tenant_id"])
        domain_id = str(tenant.get("security_domain_id") or "backup-domain")
        # Use a placeholder workspace for tenant put (directory APIs need ctx).
        ctx = _admin_ctx(
            tenant_id=tenant_id,
            workspace_id="__backup__",
            domain_id=domain_id,
        )
        provider.tenants.put(ctx, TenantRecord.from_dict(tenant))

    for workspace in transcript.workspaces:
        tenant_id = str(workspace["tenant_id"])
        workspace_id = str(workspace["workspace_id"])
        # Resolve domain from tenant row when present.
        domain_id = "backup-domain"
        for tenant in transcript.tenants:
            if tenant.get("tenant_id") == tenant_id and tenant.get(
                "security_domain_id"
            ):
                domain_id = str(tenant["security_domain_id"])
                break
        ctx = _admin_ctx(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            domain_id=domain_id,
        )
        provider.workspaces.put(ctx, WorkspaceRecord.from_dict(workspace))

    for environment in transcript.environments:
        tenant_id = str(environment["tenant_id"])
        workspace_id = str(environment.get("workspace_id") or "__backup__")
        domain_id = next(
            (
                str(tenant["security_domain_id"])
                for tenant in transcript.tenants
                if tenant.get("tenant_id") == tenant_id
                and tenant.get("security_domain_id")
            ),
            "backup-domain",
        )
        provider.put_environment(
            _admin_ctx(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                domain_id=domain_id,
            ),
            EnvironmentRecord.from_dict(environment),
        )

    for logical in transcript.logicals:
        tenant_id = str(logical["tenant_id"])
        workspace_id = str(logical["workspace_id"])
        domain_id = next(
            (
                str(tenant["security_domain_id"])
                for tenant in transcript.tenants
                if tenant.get("tenant_id") == tenant_id
                and tenant.get("security_domain_id")
            ),
            "backup-domain",
        )
        provider.revisions.put_logical(
            _admin_ctx(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                domain_id=domain_id,
            ),
            LogicalIdentity.from_dict(logical),
        )

    for revision in transcript.revisions:
        tenant_id = str(revision["tenant_id"])
        workspace_id = str(revision["workspace_id"])
        domain_id = "backup-domain"
        for tenant in transcript.tenants:
            if tenant.get("tenant_id") == tenant_id and tenant.get(
                "security_domain_id"
            ):
                domain_id = str(tenant["security_domain_id"])
                break
        ctx = _admin_ctx(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            domain_id=domain_id,
        )
        content = dict(revision.get("content") or {})
        fingerprint = str(
            revision.get("content_fingerprint") or content_fingerprint(content)
        )
        rev = RegistryRevision(
            logical_id=str(revision["logical_id"]),
            revision_id=str(revision["revision_id"]),
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            content_fingerprint=fingerprint,
            content=content,
            created_at=revision.get("created_at"),
            kind=revision.get("kind"),
            signature_placeholder=revision.get("signature_placeholder"),
            provenance_placeholder=dict(revision.get("provenance") or {}),
        )
        provider.revisions.put_revision(ctx, rev)

    for alias in transcript.aliases:
        tenant_id = str(alias["tenant_id"])
        workspace_id = str(alias["workspace_id"])
        domain_id = next(
            (
                str(tenant["security_domain_id"])
                for tenant in transcript.tenants
                if tenant.get("tenant_id") == tenant_id
                and tenant.get("security_domain_id")
            ),
            "backup-domain",
        )
        provider.revisions.put_alias(
            _admin_ctx(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                domain_id=domain_id,
            ),
            AliasRecord.from_dict(alias),
        )

    for promotion in transcript.promotions:
        record = PromotionRecord.from_dict(promotion)
        with session_scope(engine) as session:
            session.add(
                PromotionRow(
                    tenant_id=record.tenant_id,
                    workspace_id=record.workspace_id,
                    promotion_id=record.promotion_id,
                    logical_id=record.logical_id,
                    from_revision_id=record.from_revision_id,
                    to_revision_id=record.to_revision_id,
                    from_environment=record.from_environment,
                    to_environment=record.to_environment,
                    created_at=record.created_at,
                    metadata_json=json.dumps(dict(record.metadata), sort_keys=True),
                )
            )

    return provider


def backup_round_trip(
    source: Engine,
    destination: Engine,
) -> BackupTranscript:
    """Dump ``source`` and load into ``destination``; return the transcript."""
    transcript = dump_registry_sqlite(source)
    load_registry_sqlite(destination, transcript, create_tables=True)
    return transcript


__all__ = [
    "BACKUP_SCHEMA",
    "BackupTranscript",
    "backup_round_trip",
    "dump_registry_sqlite",
    "load_registry_sqlite",
    "read_backup_transcript",
    "write_backup_transcript",
]
