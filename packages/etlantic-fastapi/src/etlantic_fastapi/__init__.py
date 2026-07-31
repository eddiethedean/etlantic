"""Thin FastAPI reference adapter for ETLantic authoring/service contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from etlantic.service import AuthoringService, PolicyContext
from fastapi import FastAPI, HTTPException

__version__ = "0.37.0"


class DefinitionDocument(BaseModel):
    document: dict[str, Any]
    idempotency_key: str | None = None


class EditRequest(BaseModel):
    command: dict[str, Any]
    expected_token: str | None = None


class RunSubmitRequest(BaseModel):
    idempotency_key: str | None = None


def create_reference_app(
    *,
    service: AuthoringService | None = None,
    title: str = "ETLantic Authoring Reference",
    version: str = __version__,
) -> FastAPI:
    """Create a FastAPI app exposing the public authoring/service facade."""
    svc = service or AuthoringService(policy=PolicyContext())
    app = FastAPI(title=title, version=version)
    app.state.service = svc

    @app.get("/negotiation")
    def negotiation() -> dict[str, Any]:
        return svc.negotiation()

    @app.get("/catalog")
    def catalog(definition_id: str | None = None) -> dict[str, Any]:
        return svc.catalog(definition_id)

    @app.put("/pipelines/{definition_id}")
    def put_pipeline(definition_id: str, body: DefinitionDocument) -> dict[str, Any]:
        try:
            return svc.put_definition(
                definition_id,
                body.document,
                idempotency_key=body.idempotency_key,
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/pipelines/{definition_id}")
    def get_pipeline(definition_id: str) -> dict[str, Any]:
        try:
            return svc.get_definition(definition_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="definition not found") from exc

    @app.post("/pipelines/{definition_id}/edits")
    def edit_pipeline(definition_id: str, body: EditRequest) -> dict[str, Any]:
        try:
            return svc.apply_edit(
                definition_id, body.command, expected_token=body.expected_token
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/pipelines/{definition_id}/validate")
    def validate_pipeline(definition_id: str) -> dict[str, Any]:
        try:
            return svc.validate(definition_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="definition not found") from exc

    @app.post("/pipelines/{definition_id}/plan")
    def plan_pipeline(definition_id: str) -> dict[str, Any]:
        try:
            return svc.plan(definition_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="definition not found") from exc

    @app.post("/pipelines/{definition_id}/runs")
    def submit_run(
        definition_id: str, body: RunSubmitRequest | None = None
    ) -> dict[str, Any]:
        body = body or RunSubmitRequest()
        try:
            return svc.submit_run(definition_id, idempotency_key=body.idempotency_key)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="definition not found") from exc

    @app.get("/runs/{job_id}")
    def run_status(job_id: str) -> dict[str, Any]:
        try:
            return svc.job_status(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="job not found") from exc

    @app.post("/runs/{job_id}/cancel")
    def cancel_run(job_id: str) -> dict[str, Any]:
        try:
            return svc.cancel_run(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="job not found") from exc

    return app


__all__ = ["AuthoringService", "PolicyContext", "create_reference_app"]
