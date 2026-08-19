"""Read-only context-bundle and proposal-validate FastAPI routes (048)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any

from etlantic.agents.context import assemble_context_bundle
from etlantic.agents.proposal import Proposal, validate_proposal
from etlantic.control_plane import (
    ControlPlaneContext,
    authorized_get_definition,
    redact_control_plane_payload,
    require_authorized,
)
from fastapi import APIRouter, Depends

if TYPE_CHECKING:
    from etlantic_fastapi.api import ETLanticAPI


def _pipeline_from_document(document: Mapping[str, Any], *, verify: bool) -> Any:
    from etlantic.authoring.serialize import pipeline_from_dict

    return pipeline_from_dict(dict(document), verify=verify)


def register_ai_routes(
    router: APIRouter,
    api: ETLanticAPI,
    get_ctx: Callable[..., Any],
) -> None:
    from etlantic_fastapi.routes import _profile_meta

    @router.post(
        "/v1/definitions/{definition_id}/context",
        operation_id="cp_definition_context",
        tags=["intelligence"],
    )
    def definition_context(
        definition_id: str,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, Any]:
        profile, production_like, _metadata = _profile_meta(api)
        document = authorized_get_definition(
            api.authorizer,
            api.definitions,
            ctx,
            definition_id,
            action="definition.read",
        )
        if document.get("schema") == "etlantic.pipeline/1" or "nodes" in document:
            pipeline = _pipeline_from_document(document, verify=production_like)
            bundle = assemble_context_bundle(pipeline, profile=profile)
            return redact_control_plane_payload(bundle.to_dict())
        return redact_control_plane_payload(
            {
                "schema": "etlantic.context_bundle/1",
                "pipeline_id": definition_id,
                "sources": [{"kind": "inspect", "identity": definition_id}],
                "redacted": True,
                "ok": False,
                "diagnostics": [
                    {
                        "code": "PMCTX110",
                        "severity": "error",
                        "message": "Definition is not an etlantic.pipeline/1 document.",
                    }
                ],
            }
        )

    @router.post(
        "/v1/proposals/validate",
        operation_id="cp_proposal_validate",
        tags=["intelligence"],
    )
    def proposal_validate(
        body: dict[str, Any],
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, Any]:
        profile, production_like, _metadata = _profile_meta(api)
        require_authorized(
            api.authorizer,
            ctx,
            "definition.read",
            "proposal:validate",
            resource_in_caller_scope=False,
        )
        definition_id = str(body.get("definition_id") or "")
        pipeline = None
        if definition_id:
            document = authorized_get_definition(
                api.authorizer,
                api.definitions,
                ctx,
                definition_id,
                action="definition.read",
            )
            if document.get("schema") == "etlantic.pipeline/1" or "nodes" in document:
                pipeline = _pipeline_from_document(document, verify=production_like)
        proposal = Proposal.from_dict(body.get("proposal") or body)
        result = validate_proposal(proposal, pipeline=pipeline, profile=profile)
        return redact_control_plane_payload(result.to_dict())
