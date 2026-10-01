"""Isolated managed-action handlers for saved Foundry connections.

Credentials and connector configuration are resolved by deployment callbacks
inside the action worker. They are never accepted in an action request or
returned in an action receipt.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from etlantic.control_plane import ControlPlaneContext
from etlantic.runtime import ActionHandler
from etlantic_foundry.connectors import (
    FoundrySourceConnector,
    FoundryStorageConnector,
)

ConnectionResolver = Callable[
    [ControlPlaneContext, str], tuple[Mapping[str, Any], Mapping[str, Any]]
]
PreflightHandler = Callable[
    [ControlPlaneContext, str, str],
    Awaitable[Mapping[str, Any]] | Mapping[str, Any],
]
PreviewResourceResolver = Callable[
    [ControlPlaneContext, str, str], tuple[Mapping[str, Any], Mapping[str, Any]]
]


def create_action_handlers(
    resolve_connection: ConnectionResolver,
    *,
    preflight: PreflightHandler | None = None,
    resolve_preview_resource: PreviewResourceResolver | None = None,
) -> dict[str, ActionHandler]:
    """Build Foundry test/schema handlers and an optional definition preflight.

    ``resolve_connection`` receives the authenticated, server-derived context
    and saved connection ID. It returns a Foundry binding and a runtime context
    whose ``secret`` member is an ``etlantic.secrets.SecretValue``. The binding
    must contain only public configuration; token values belong only in the
    runtime context.

    The connection test performs a bounded, read-only schema probe. Schema
    inspection returns at most the action's requested field count. The optional
    preflight callback is provided by the deployment so it can bind definition
    resolution and live checks to its managed service and saved resources.
    ``resolve_preview_resource`` optionally maps an opaque connection/resource
    pair to one exact pinned Foundry CSV file binding and runtime context.
    """
    storage = FoundryStorageConnector()

    async def inspect(
        ctx: ControlPlaneContext,
        request: Mapping[str, Any],
        *,
        max_fields: int,
    ) -> dict[str, Any]:
        if request.get("provider") != "foundry":
            raise ValueError("Foundry action requires provider='foundry'")
        connection_id = str(request["connection_id"])
        binding, runtime_context = resolve_connection(ctx, connection_id)
        result = await storage.inspect_schema(
            binding=binding,
            context=runtime_context,
        )
        payload = result.to_dict()
        payload["fields"] = payload["fields"][:max_fields]
        # Dataset and file names can be sensitive deployment metadata. The
        # worker receipt contains only the provider and bounded schema fields.
        payload["metadata"] = {"inspection": "read_only"}
        return payload

    async def test_connection(
        ctx: ControlPlaneContext,
        request: Mapping[str, Any],
    ) -> dict[str, Any]:
        await inspect(ctx, request, max_fields=1)
        return {"ok": True, "provider": "foundry"}

    async def inspect_schema(
        ctx: ControlPlaneContext,
        request: Mapping[str, Any],
    ) -> dict[str, Any]:
        return await inspect(
            ctx, request, max_fields=int(request.get("max_fields", 100))
        )

    handlers: dict[str, ActionHandler] = {
        "connector.test": test_connection,
        "connector.schema.inspect": inspect_schema,
    }
    if resolve_preview_resource is not None:
        source = FoundrySourceConnector()

        async def preview(
            ctx: ControlPlaneContext,
            request: Mapping[str, Any],
        ) -> dict[str, Any]:
            if request.get("provider") != "foundry":
                raise ValueError("Foundry action requires provider='foundry'")
            binding, runtime_context = resolve_preview_resource(
                ctx,
                str(request["connection_id"]),
                str(request["resource_id"]),
            )
            return await source.preview(
                binding=binding,
                context=runtime_context,
                max_rows=int(request["max_rows"]),
                max_bytes=int(request["max_bytes"]),
            )

        handlers["connector.preview"] = preview
    if preflight is not None:

        async def run_preflight(
            ctx: ControlPlaneContext,
            request: Mapping[str, Any],
        ) -> dict[str, Any]:
            result = preflight(
                ctx,
                str(request["definition_id"]),
                str(request.get("revision_selector", "current")),
            )
            if isinstance(result, Mapping):
                return dict(result)
            return dict(await result)

        handlers["connector.preflight"] = run_preflight
    return handlers


__all__ = [
    "ConnectionResolver",
    "PreflightHandler",
    "PreviewResourceResolver",
    "create_action_handlers",
]
