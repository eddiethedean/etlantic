"""Problem Details exception handlers for control-plane errors."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.responses import Response

from etlantic.control_plane import ControlPlaneError
from fastapi import FastAPI, Request


def request_validation_error_handler(
    _request: Request, _exc: RequestValidationError
) -> JSONResponse:
    """Return a fixed 422 envelope without inspecting or logging invalid input.

    Locations, messages and validation context can also contain user input, so
    none of the original exception's fields are rendered.
    """
    return JSONResponse(
        status_code=422,
        content={
            "detail": [
                {"type": "request_validation", "loc": [], "msg": "Invalid request"}
            ]
        },
    )


class RedactedValidationRoute(APIRoute):
    """Route-scoped validation safety, independent of host exception handlers."""

    def get_route_handler(self) -> Callable[[Request], Awaitable[Response]]:
        handler = super().get_route_handler()

        async def safe_handler(request: Request) -> Response:
            try:
                return await handler(request)
            except RequestValidationError as exc:
                return request_validation_error_handler(request, exc)

        return safe_handler


def control_plane_error_handler(
    _request: Request, exc: ControlPlaneError
) -> JSONResponse:
    """Map :class:`ControlPlaneError` to an RFC 7807-shaped JSON body."""
    problem = exc.to_problem_details()
    payload = problem.to_dict()
    return JSONResponse(
        status_code=exc.status,
        content=payload,
        media_type="application/problem+json",
    )


def install_exception_handlers(app: FastAPI) -> None:
    """Install CP error handlers on a standalone app (not used by include_router)."""
    app.add_exception_handler(ControlPlaneError, control_plane_error_handler)


def problem_from_exception(exc: BaseException) -> dict[str, Any] | None:
    if isinstance(exc, ControlPlaneError):
        return exc.to_dict()
    return None


__all__ = [
    "RedactedValidationRoute",
    "control_plane_error_handler",
    "install_exception_handlers",
    "problem_from_exception",
    "request_validation_error_handler",
]
