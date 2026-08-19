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


def _pipeline_from_document(document: Mapping[str, Any]) -> Any:
    from etlantic.authoring.serialize import pipeline_from_dict

    return pipeline_from_dict(dict(document), verify=False)


def register_ai_routes(
    router: APIRouter,
    api: ETLanticAPI,
    get_ctx: Callable[..., Any],
) -> None:
    @router.post(
        "/v1/definitions/{definition_id}/context",
        operation_id="cp_definition_context",
        tags=["intelligence"],
    )
    def definition_context(
        definition_id: str,
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, Any]:
        document = authorized_get_definition(
            api.authorizer,
            api.definitions,
            ctx,
            definition_id,
            action="definition.read",
        )
        pipeline = _pipeline_from_document(document)
        bundle = assemble_context_bundle(pipeline, profile="development")
        return redact_control_plane_payload(bundle.to_dict())

    @router.post(
        "/v1/proposals/validate",
        operation_id="cp_proposal_validate",
        tags=["intelligence"],
    )
    def proposal_validate(
        body: dict[str, Any],
        ctx: ControlPlaneContext = Depends(get_ctx),
    ) -> dict[str, Any]:
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
            pipeline = _pipeline_from_document(document)
        proposal = Proposal.from_dict(body.get("proposal") or body)
        result = validate_proposal(proposal, pipeline=pipeline, profile="development")
        return redact_control_plane_payload(result.to_dict())
