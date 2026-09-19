"""Request-validation rejection never renders or logs original invalid values."""

import logging

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("etlantic_fastapi")
pytest.importorskip("httpx")
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from etlantic.control_plane import (
    MemoryAuthorizer,
    MemoryDefinitionRepository,
    MemoryEventStore,
    MemorySubmissionStore,
    Principal,
)
from etlantic_fastapi import (
    ETLanticAPI,
    RedactedValidationRoute,
    create_app,
    include_router,
    membership_context_factory,
    request_validation_error_handler,
)
from fastapi import FastAPI, Header, Request

pytestmark = pytest.mark.fastapi
SECRET = "synthetic-validation-secret-probe"
SAFE = {"detail": [{"type": "request_validation", "loc": [], "msg": "Invalid request"}]}


def api_with_header_validation():
    def principal(x_principal: int = Header()):
        return Principal(subject=str(x_principal))

    return ETLanticAPI(
        authorizer=MemoryAuthorizer(),
        definitions=MemoryDefinitionRepository(),
        submissions=MemorySubmissionStore(),
        events=MemoryEventStore(),
        context_factory=membership_context_factory(
            {"1": ("tenant-a", "ws-1", "development", "default")}
        ),
        principal_dependency=principal,
    )


@pytest.mark.parametrize("embedded", [False, True])
@pytest.mark.parametrize(
    "probe",
    [
        "nested-password",
        "nested-token",
        "scalar",
        "query",
        "header",
        "json",
        "missing-header",
    ],
)
def test_safe_body_query_header_validation_in_direct_and_embedded_apps(
    embedded, probe, caplog
):
    api = api_with_header_validation()
    app = FastAPI() if embedded else create_app(api)
    if embedded:
        include_router(app, api, prefix="/etl")
    prefix = "/etl" if embedded else ""
    caplog.set_level(logging.DEBUG)
    # Do not put the sentinel in the URL: HTTP clients/access logs own URL logging.
    headers = {"X-Principal": "1"}
    with TestClient(app) as client:
        if probe == "header":
            response = client.get(
                prefix + "/v1/definitions", headers={"X-Principal": SECRET}
            )
        elif probe == "missing-header":
            response = client.get(prefix + "/v1/definitions")
        elif probe == "query":
            # Capture adapter logging only, not the HTTP client's request-URL log.
            with caplog.at_level(logging.WARNING, logger="httpx"):
                response = client.get(
                    prefix + "/v1/audit", params={"limit": SECRET}, headers=headers
                )
        elif probe == "json":
            response = client.post(
                prefix + "/v1/definitions/demo/runs",
                content='{"password":"' + SECRET + '"',
                headers={**headers, "Content-Type": "application/json"},
            )
        else:
            value = (
                {"password": SECRET}
                if probe == "nested-password"
                else {"nested": {"token": SECRET}}
                if probe == "nested-token"
                else SECRET
            )
            body = (
                {"idempotency_key": value} if probe != "scalar" else {"payload": SECRET}
            )
            response = client.post(
                prefix + "/v1/definitions/demo/runs", json=body, headers=headers
            )
        assert response.status_code == 422
        assert response.json() == SAFE
        assert SECRET not in response.text
    assert SECRET not in caplog.text


def test_embedded_host_handler_is_preserved_and_not_used_for_etlantic_routes():
    app = FastAPI()
    calls = []

    async def host_handler(request: Request, exc: RequestValidationError):
        calls.append(request.url.path)
        return JSONResponse(status_code=422, content={"detail": "host validation"})

    app.add_exception_handler(RequestValidationError, host_handler)

    @app.get("/host")
    def host(number: int):
        return {"number": number}

    include_router(app, api_with_header_validation(), prefix="/etl")
    assert app.exception_handlers[RequestValidationError] is host_handler
    with TestClient(app) as client:
        response = client.get("/etl/v1/definitions", headers={"X-Principal": SECRET})
        assert response.status_code == 422 and response.json() == SAFE
        assert calls == []
        assert client.get("/host?number=bad").json() == {"detail": "host validation"}
        assert calls == ["/host"]


def test_public_handler_ignores_unsafe_locations_messages_context_and_body(caplog):
    exc = RequestValidationError(
        [
            {
                "type": SECRET,
                "loc": ("body", SECRET),
                "msg": SECRET,
                "input": {"password": SECRET},
                "ctx": {"error": ValueError(SECRET)},
            }
        ],
        body={"token": SECRET},
    )
    response = request_validation_error_handler(None, exc)
    assert response.status_code == 422
    assert SECRET.encode() not in response.body
    assert SECRET not in caplog.text


def test_all_control_plane_routes_use_safe_validation_route():
    from fastapi.routing import APIRoute

    routes = api_with_header_validation().router.routes
    assert routes
    assert all(
        isinstance(route, RedactedValidationRoute)
        for route in routes
        if isinstance(route, APIRoute)
    )


def test_public_handler_can_be_registered_explicitly_without_body_logging(caplog):
    app = FastAPI()
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)

    @app.get("/host")
    def host(number: int):
        return {"number": number}

    with caplog.at_level(logging.WARNING, logger="httpx"), TestClient(app) as client:
        response = client.get("/host", params={"number": SECRET})
    assert response.status_code == 422 and response.json() == SAFE
    assert SECRET not in caplog.text
