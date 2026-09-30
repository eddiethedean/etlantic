"""006 — copy legacy CP1 definitions into the immutable CP2 revision registry.

The previous SQLModel managed backend stored one mutable document per
definition. The managed application backend now reads append-only revisions.
This migration imports each legacy document as an old, content-addressed
revision while preserving the CP1 rows for rollback and audit.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from sqlalchemy.engine import Engine

from etlantic.control_plane.registry_memory import (
    content_fingerprint,
    safe_registry_content,
)
from etlantic_sqlmodel.control_plane.models import (
    DefinitionRow,
    LogicalIdentityRow,
    RevisionRow,
)
from etlantic_sqlmodel.control_plane.session import session_scope
from sqlmodel import select

_LEGACY_CREATED_AT = "1970-01-01T00:00:00Z"


def _legacy_revision_id(
    *, tenant_id: str, workspace_id: str, definition_id: str, content: Mapping[str, Any]
) -> str:
    canonical = json.dumps(
        dict(content), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    identity = json.dumps(
        [tenant_id, workspace_id, definition_id, canonical],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return f"defrev-legacy-{hashlib.sha256(identity.encode('utf-8')).hexdigest()}"


def upgrade(engine: Engine) -> None:
    """Import CP1 definition rows as secret-free immutable registry revisions."""
    with session_scope(engine) as session:
        legacy_rows = session.exec(select(DefinitionRow)).all()
        for legacy in legacy_rows:
            raw = json.loads(legacy.document_json)
            if not isinstance(raw, Mapping):
                # Keep malformed historical rows in CP1. They cannot become
                # canonical definitions or executable managed work.
                continue
            document = safe_registry_content(dict(raw))
            definition_id = legacy.definition_id
            revision_id = _legacy_revision_id(
                tenant_id=legacy.tenant_id,
                workspace_id=legacy.workspace_id,
                definition_id=definition_id,
                content=document,
            )
            identity_statement = select(LogicalIdentityRow).where(
                LogicalIdentityRow.tenant_id == legacy.tenant_id,
                LogicalIdentityRow.workspace_id == legacy.workspace_id,
                LogicalIdentityRow.logical_id == definition_id,
            )
            identity = session.exec(identity_statement).first()
            if identity is None:
                session.add(
                    LogicalIdentityRow(
                        tenant_id=legacy.tenant_id,
                        workspace_id=legacy.workspace_id,
                        logical_id=definition_id,
                        kind="definition",
                        created_at=_LEGACY_CREATED_AT,
                    )
                )
            elif identity.kind != "definition":
                raise ValueError(
                    "Legacy definition conflicts with a registry identity of a different kind"
                )

            content = {
                "document_fingerprint": content_fingerprint(document),
                "document": document,
                "kind": "definition",
            }
            revision_statement = select(RevisionRow).where(
                RevisionRow.tenant_id == legacy.tenant_id,
                RevisionRow.workspace_id == legacy.workspace_id,
                RevisionRow.revision_id == revision_id,
            )
            revision = session.exec(revision_statement).first()
            if revision is not None:
                if (
                    revision.logical_id != definition_id
                    or revision.content_json != json.dumps(content, sort_keys=True)
                ):
                    raise ValueError("Legacy definition revision identity collision")
                continue
            session.add(
                RevisionRow(
                    tenant_id=legacy.tenant_id,
                    workspace_id=legacy.workspace_id,
                    logical_id=definition_id,
                    revision_id=revision_id,
                    content_fingerprint=content_fingerprint(content),
                    content_json=json.dumps(content, sort_keys=True),
                    created_at=_LEGACY_CREATED_AT,
                    kind="definition",
                )
            )


def downgrade(engine: Engine) -> None:
    """Keep imported revisions so rollback never removes accepted references."""
    _ = engine


__all__ = ["downgrade", "upgrade"]
