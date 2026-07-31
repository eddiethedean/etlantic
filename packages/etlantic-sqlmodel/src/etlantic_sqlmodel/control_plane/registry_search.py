"""SQLModel-backed revision metadata search (CP2 / 040-O)."""

from __future__ import annotations

from collections.abc import Sequence

from etlantic.control_plane.models import ControlPlaneContext
from etlantic.control_plane.registry_ops import RevisionSearchHit
from etlantic_sqlmodel.control_plane.models import RevisionRow
from etlantic_sqlmodel.control_plane.registry_stores import SqlModelRegistryProvider
from etlantic_sqlmodel.control_plane.session import session_scope
from sqlmodel import select


def collect_revision_hits(
    provider: SqlModelRegistryProvider,
    ctx: ControlPlaneContext,
    *,
    logical_id: str | None = None,
    kind: str | None = None,
) -> Sequence[RevisionSearchHit]:
    """Return metadata-only hits for ``ctx`` scope (no content bodies)."""
    # Fail closed on suspended scopes via directory get.
    provider.tenants.get(ctx, ctx.tenant.tenant_id)
    provider.workspaces.get(ctx, ctx.workspace.workspace_id)

    with session_scope(provider.engine) as session:
        statement = select(RevisionRow).where(
            RevisionRow.tenant_id == ctx.tenant.tenant_id,
            RevisionRow.workspace_id == ctx.workspace.workspace_id,
        )
        if logical_id is not None:
            statement = statement.where(RevisionRow.logical_id == logical_id)
        if kind is not None:
            statement = statement.where(RevisionRow.kind == kind)
        rows = session.exec(statement).all()
        return [
            RevisionSearchHit(
                tenant_id=row.tenant_id,
                workspace_id=row.workspace_id,
                logical_id=row.logical_id,
                revision_id=row.revision_id,
                content_fingerprint=row.content_fingerprint,
                kind=row.kind,
                created_at=row.created_at,
            )
            for row in rows
        ]


__all__ = ["collect_revision_hits"]
