"""Problem Details exception handlers for control-plane errors."""

from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse

from etlantic.control_plane import ControlPlaneError
from fastapi import FastAPI, Request


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
    "control_plane_error_handler",
    "install_exception_handlers",
    "problem_from_exception",
]
