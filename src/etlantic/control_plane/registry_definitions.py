# pyright: reportUnknownArgumentType=false
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
from typing import Any, cast

from etlantic.control_plane.errors import ControlPlaneError
from etlantic.control_plane.models import ControlPlaneContext
from etlantic.control_plane.protocols import DefinitionResolution
from etlantic.control_plane.registry_memory import (
    content_fingerprint,
    revision_order_key,
    safe_registry_content,
)
from etlantic.control_plane.registry_models import (
    LogicalIdentity,
    RegistryRevision,
)
from etlantic.control_plane.registry_protocols import RegistryProvider

DEFINITION_KIND = "definition"


def _document_content(document: Mapping[str, Any]) -> dict[str, Any]:
    """Fingerprint after secret reseal so nested and outer digests stay aligned."""
    payload = safe_registry_content(dict(document))
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
            raise ControlPlaneError.not_found(f"Definition {definition_id!r} not found")
        latest = max(
            revisions,
            key=lambda rev: revision_order_key(rev.created_at, rev.revision_id),
        )
        document = latest.content.get("document")
        if not isinstance(document, Mapping):
            raise ControlPlaneError.not_found(f"Definition {definition_id!r} not found")
        return deepcopy(dict(document))

    def resolve_revision(
        self,
        ctx: ControlPlaneContext,
        definition_id: str,
        selector: str,
    ) -> DefinitionResolution:
        """Resolve one scoped immutable definition revision.

        ``current`` selects the newest append-only revision. Other selectors
        first match an exact revision id and then a configured registry alias;
        this supports operator-maintained selectors such as
        ``latest-approved`` without trusting caller-supplied content hashes.
        """
        if selector == "current":
            revisions = self.registry.revisions.list_revisions(ctx, definition_id)
            if not revisions:
                raise ControlPlaneError.not_found(
                    f"Definition {definition_id!r} not found"
                )
            revision = max(
                revisions,
                key=lambda rev: revision_order_key(rev.created_at, rev.revision_id),
            )
        else:
            try:
                revision = self.registry.revisions.get_revision(ctx, selector)
            except ControlPlaneError as exc:
                if getattr(exc, "status", None) != 404:
                    raise
                try:
                    revision = self.registry.revisions.resolve_alias(ctx, selector)
                except ControlPlaneError as alias_exc:
                    if getattr(alias_exc, "status", None) != 404:
                        raise
                    raise ControlPlaneError.not_found(
                        "Definition revision was not found",
                        extensions={"definition_id": definition_id},
                    ) from alias_exc

        if revision.logical_id != definition_id or revision.kind != DEFINITION_KIND:
            raise ControlPlaneError.not_found(
                "Definition revision was not found",
                extensions={"definition_id": definition_id},
            )
        document = revision.content.get("document")
        recorded_fingerprint = revision.content.get("document_fingerprint")
        if not isinstance(document, Mapping) or not isinstance(
            recorded_fingerprint, str
        ):
            raise ControlPlaneError.conflict(
                "Definition revision content fingerprint mismatch (tamper detected)",
                extensions={"revision_id": revision.revision_id},
            )
        document_mapping = cast(Mapping[str, Any], document)
        if recorded_fingerprint != content_fingerprint(document_mapping):
            raise ControlPlaneError.conflict(
                "Definition revision content fingerprint mismatch (tamper detected)",
                extensions={"revision_id": revision.revision_id},
            )
        return DefinitionResolution(
            revision_id=revision.revision_id,
            document=deepcopy(dict(document_mapping)),
        )

    def list(self, ctx: ControlPlaneContext) -> Sequence[str]:
        list_logical = getattr(self.registry.revisions, "list_logical", None)
        if callable(list_logical):
            identities = cast(
                Sequence[LogicalIdentity], list_logical(ctx, kind=DEFINITION_KIND)
            )
            return sorted(i.logical_id for i in identities)
        # Fallback: probe known put path is unavailable without list_logical.
        return ()

    def put(
        self,
        ctx: ControlPlaneContext,
        definition_id: str,
        document: Mapping[str, Any],
    ) -> None:
        self.put_revision(ctx, definition_id, document)

    def put_revision(
        self,
        ctx: ControlPlaneContext,
        definition_id: str,
        document: Mapping[str, Any],
    ) -> str:
        """Append a definition revision and return its immutable revision id."""
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
        return revision.revision_id

    def compare_and_swap(
        self,
        ctx: ControlPlaneContext,
        definition_id: str,
        expected_document: Mapping[str, Any],
        document: Mapping[str, Any],
    ) -> str:
        """Append a definition revision against an atomically checked head."""
        expected_content = _document_content(expected_document)
        content = _document_content(document)
        revision = RegistryRevision(
            logical_id=definition_id,
            revision_id=f"defrev-{uuid.uuid4().hex[:16]}",
            tenant_id=ctx.tenant.tenant_id,
            workspace_id=ctx.workspace.workspace_id,
            content_fingerprint=content_fingerprint(content),
            content=content,
            kind=DEFINITION_KIND,
        )
        put_if_current = getattr(
            self.registry.revisions, "put_revision_if_current", None
        )
        if not callable(put_if_current):
            raise ControlPlaneError(
                "Registry provider does not support atomic definition edits",
                code="PMCP501",
                status=501,
                title="Not Implemented",
            )
        put_if_current(
            ctx,
            revision,
            expected_current_fingerprint=content_fingerprint(expected_content),
        )
        return revision.revision_id


__all__ = ["DEFINITION_KIND", "RegistryDefinitionRepository"]
