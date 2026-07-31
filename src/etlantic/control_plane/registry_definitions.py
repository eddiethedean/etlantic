"""DefinitionRepository adapter backed by a RegistryProvider (CP2 / 040-P).

Stores definition documents as immutable registry revisions:

* ``logical_id`` = ``definition_id``
* ``kind`` = ``definition``
* revision ``content`` holds document fingerprint + document payload metadata
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from etlantic.control_plane.errors import ControlPlaneError
from etlantic.control_plane.models import ControlPlaneContext
from etlantic.control_plane.registry_memory import content_fingerprint
from etlantic.control_plane.registry_models import (
    LogicalIdentity,
    RegistryRevision,
)
from etlantic.control_plane.registry_protocols import RegistryProvider

DEFINITION_KIND = "definition"


def _document_content(document: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(document)
    return {
        "document_fingerprint": content_fingerprint(payload),
        "document": payload,
        "kind": DEFINITION_KIND,
    }


@dataclass
class RegistryDefinitionRepository:
    """``DefinitionRepository`` that writes through a :class:`RegistryProvider`."""

    registry: RegistryProvider

    def get(self, ctx: ControlPlaneContext, definition_id: str) -> Mapping[str, Any]:
        revisions = self.registry.revisions.list_revisions(ctx, definition_id)
        if not revisions:
            raise KeyError(definition_id)
        # Prefer newest created_at; revision_id sort alone is not chronological
        # when ids are UUID-based.
        latest = max(
            revisions,
            key=lambda rev: (rev.created_at or "", rev.revision_id),
        )
        document = latest.content.get("document")
        if not isinstance(document, Mapping):
            raise KeyError(definition_id)
        return deepcopy(dict(document))

    def list(self, ctx: ControlPlaneContext) -> Sequence[str]:
        list_logical = getattr(self.registry.revisions, "list_logical", None)
        if callable(list_logical):
            identities = list_logical(ctx, kind=DEFINITION_KIND)
            return sorted(i.logical_id for i in identities)
        # Fallback: probe known put path is unavailable without list_logical.
        return ()

    def put(
        self,
        ctx: ControlPlaneContext,
        definition_id: str,
        document: Mapping[str, Any],
    ) -> None:
        content = _document_content(document)
        try:
            self.registry.revisions.get_logical(ctx, definition_id)
        except ControlPlaneError as exc:
            if getattr(exc, "status", None) != 404:
                raise
            self.registry.revisions.put_logical(
                ctx,
                LogicalIdentity(
                    logical_id=definition_id,
                    tenant_id=ctx.tenant.tenant_id,
                    workspace_id=ctx.workspace.workspace_id,
                    kind=DEFINITION_KIND,
                ),
            )
        revision = RegistryRevision(
            logical_id=definition_id,
            revision_id=f"defrev-{uuid.uuid4().hex[:16]}",
            tenant_id=ctx.tenant.tenant_id,
            workspace_id=ctx.workspace.workspace_id,
            content_fingerprint=content_fingerprint(content),
            content=content,
            kind=DEFINITION_KIND,
        )
        self.registry.revisions.put_revision(ctx, revision)


__all__ = ["DEFINITION_KIND", "RegistryDefinitionRepository"]
