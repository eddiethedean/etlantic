"""Registry revision search/pagination and retention hooks (CP2 / 040-O).

Search returns **metadata only** (no revision content bodies / source rows).
Retention deletes expired observation metadata by age.
"""

from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from etlantic.control_plane.errors import ControlPlaneError
from etlantic.control_plane.history_memory import MemoryHistoryStore
from etlantic.control_plane.history_models import ObservationKind
from etlantic.control_plane.models import ControlPlaneContext
from etlantic.control_plane.registry_models import RegistryRevision
from etlantic.control_plane.registry_protocols import RegistryProvider


@dataclass(frozen=True, slots=True)
class RevisionSearchHit:
    """Metadata-only revision search hit (no content body)."""

    tenant_id: str
    workspace_id: str
    logical_id: str
    revision_id: str
    content_fingerprint: str
    kind: str | None = None
    created_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "workspace_id": self.workspace_id,
            "logical_id": self.logical_id,
            "revision_id": self.revision_id,
            "content_fingerprint": self.content_fingerprint,
            "kind": self.kind,
            "created_at": self.created_at,
        }


@dataclass(frozen=True, slots=True)
class RevisionSearchPage:
    """Paginated search result over revision metadata."""

    items: tuple[RevisionSearchHit, ...]
    next_cursor: str | None = None
    total: int | None = None


def _encode_cursor(offset: int) -> str:
    payload = json.dumps({"o": offset}, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii")


def _decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii"))
        data = json.loads(raw.decode("utf-8"))
        return max(0, int(data["o"]))
    except (
        binascii.Error,
        KeyError,
        TypeError,
        UnicodeError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        raise ControlPlaneError(
            "Invalid search cursor",
            code="PMCP400",
            status=400,
            type="etlantic.control_plane/bad_request",
            title="Bad Request",
            extensions={"cursor": cursor},
        ) from exc


def _hit_from_revision(rev: RegistryRevision) -> RevisionSearchHit:
    return RevisionSearchHit(
        tenant_id=rev.tenant_id,
        workspace_id=rev.workspace_id,
        logical_id=rev.logical_id,
        revision_id=rev.revision_id,
        content_fingerprint=rev.content_fingerprint,
        kind=rev.kind,
        created_at=rev.created_at,
    )


def _page_hits(
    hits: list[RevisionSearchHit],
    *,
    limit: int,
    cursor: str | None,
) -> RevisionSearchPage:
    if limit < 1 or limit > 500:
        raise ControlPlaneError(
            "limit must be between 1 and 500",
            code="PMCP400",
            status=400,
            type="etlantic.control_plane/bad_request",
            title="Bad Request",
            extensions={"limit": limit},
        )
    offset = _decode_cursor(cursor)
    hits.sort(key=lambda h: (h.logical_id, h.revision_id))
    total = len(hits)
    page = hits[offset : offset + limit]
    next_cursor = _encode_cursor(offset + limit) if offset + limit < total else None
    return RevisionSearchPage(
        items=tuple(page),
        next_cursor=next_cursor,
        total=total,
    )


def search_revisions(
    provider: RegistryProvider,
    ctx: ControlPlaneContext,
    *,
    logical_id: str | None = None,
    kind: str | None = None,
    limit: int = 50,
    cursor: str | None = None,
) -> RevisionSearchPage:
    """Search revision **metadata** inside ``ctx`` tenant/workspace scope.

    Does not return revision content bodies. Pagination uses an opaque offset
    cursor suitable for memory and SQLModel reference providers.
    """
    hits: list[RevisionSearchHit] = []
    revisions = getattr(provider.revisions, "_revisions", None)
    if isinstance(revisions, dict):
        # Ensure suspended scopes fail closed via a scoped peek.
        provider.tenants.get(ctx, ctx.tenant.tenant_id)
        provider.workspaces.get(ctx, ctx.workspace.workspace_id)
        tenant_id, workspace_id = ctx.scope_key
        for (t, w, _), rev in revisions.items():
            if t != tenant_id or w != workspace_id:
                continue
            if logical_id is not None and rev.logical_id != logical_id:
                continue
            if kind is not None and rev.kind != kind:
                continue
            hits.append(_hit_from_revision(rev))
    elif hasattr(provider, "engine"):
        # Optional SQLModel path (lazy importlib to keep core free of SQLModel).
        import importlib

        search_mod = importlib.import_module(
            "etlantic_sqlmodel.control_plane.registry_search"
        )
        hits = list(
            search_mod.collect_revision_hits(
                provider,
                ctx,
                logical_id=logical_id,
                kind=kind,
            )
        )
    else:
        if logical_id is None:
            raise ControlPlaneError(
                "logical_id is required for providers without a revision index",
                code="PMCP400",
                status=400,
                type="etlantic.control_plane/bad_request",
                title="Bad Request",
                extensions={
                    "hint": "pass logical_id or use a memory/sqlmodel provider",
                },
            )
        for rev in provider.revisions.list_revisions(ctx, logical_id):
            if kind is not None and rev.kind != kind:
                continue
            hits.append(_hit_from_revision(rev))

    return _page_hits(hits, limit=limit, cursor=cursor)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _is_older(observed_at: str | None, older_than: datetime) -> bool:
    parsed = _parse_iso(observed_at)
    if parsed is None:
        # Corrupt or absent timestamps must not cause destructive retention.
        return False
    cutoff = (
        older_than
        if older_than.tzinfo is not None
        else older_than.replace(tzinfo=parsed.tzinfo)
    )
    if parsed.tzinfo is None and cutoff.tzinfo is not None:
        parsed = parsed.replace(tzinfo=cutoff.tzinfo)
    return parsed < cutoff


@runtime_checkable
class RetentionHook(Protocol):
    """Delete expired observation metadata by age (metadata stores only)."""

    def purge_expired_observations(
        self,
        ctx: ControlPlaneContext,
        *,
        older_than: datetime,
        kinds: Sequence[ObservationKind] | None = None,
    ) -> int:
        """Remove observations older than ``older_than``; return deleted count."""
        ...


@dataclass
class MemoryRetentionHook:
    """Retention hook over :class:`MemoryHistoryStore`."""

    history: MemoryHistoryStore

    def purge_expired_observations(
        self,
        ctx: ControlPlaneContext,
        *,
        older_than: datetime,
        kinds: Sequence[ObservationKind] | None = None,
    ) -> int:
        selected = set(kinds or ("schema", "reliability", "plan"))
        deleted = 0
        tenant_id, workspace_id = ctx.scope_key
        with self.history._lock:
            if "schema" in selected:
                keys = [
                    key
                    for key, record in self.history._schema.items()
                    if key[0] == tenant_id
                    and key[1] == workspace_id
                    and _is_older(record.observed_at, older_than)
                ]
                for key in keys:
                    del self.history._schema[key]
                    deleted += 1
            if "reliability" in selected:
                keys = [
                    key
                    for key, record in self.history._reliability.items()
                    if key[0] == tenant_id
                    and key[1] == workspace_id
                    and _is_older(record.observed_at, older_than)
                ]
                for key in keys:
                    del self.history._reliability[key]
                    deleted += 1
            if "plan" in selected:
                keys = [
                    key
                    for key, record in self.history._plan.items()
                    if key[0] == tenant_id
                    and key[1] == workspace_id
                    and _is_older(record.observed_at, older_than)
                ]
                for key in keys:
                    del self.history._plan[key]
                    deleted += 1
        return deleted


__all__ = [
    "MemoryRetentionHook",
    "RetentionHook",
    "RevisionSearchHit",
    "RevisionSearchPage",
    "search_revisions",
]
