"""Versioned control-plane error envelopes (Problem Details-shaped, no FastAPI)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from etlantic.control_plane.redaction import (
    redact_control_plane_payload,
    redact_control_plane_text,
)
from etlantic.exceptions import ETLanticError

CONTROL_PLANE_ERROR_SCHEMA = "etlantic.control_plane.error/1"

ErrorDisclosure = Literal["not_found", "forbidden", "conflict", "unauthorized", "error"]


@dataclass(frozen=True, slots=True)
class ProblemDetails:
    """Transport-neutral problem document (RFC 7807-shaped).

    Adapters (for example ``etlantic-fastapi``) may map ``status`` to HTTP
    without importing FastAPI here.
    """

    type: str
    title: str
    status: int
    detail: str
    code: str
    instance: str | None = None
    extensions: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema": CONTROL_PLANE_ERROR_SCHEMA,
            "type": self.type,
            "title": redact_control_plane_text(self.title),
            "status": self.status,
            "detail": redact_control_plane_text(self.detail),
            "code": self.code,
        }
        if self.instance is not None:
            payload["instance"] = self.instance
        if self.extensions:
            payload["extensions"] = redact_control_plane_payload(dict(self.extensions))
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ProblemDetails:
        return cls(
            type=str(data["type"]),
            title=str(data["title"]),
            status=int(data["status"]),
            detail=str(data["detail"]),
            code=str(data["code"]),
            instance=(
                str(data["instance"]) if data.get("instance") is not None else None
            ),
            extensions=dict(data.get("extensions") or {}),
        )


class ControlPlaneError(ETLanticError):
    """Raised for control-plane authorization, scope, and durability failures."""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        status: int,
        type: str = "about:blank",
        title: str | None = None,
        instance: str | None = None,
        extensions: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.type = type
        self.title = title or message
        self.detail = message
        self.instance = instance
        self.extensions = dict(extensions or {})

    def to_problem_details(self) -> ProblemDetails:
        return ProblemDetails(
            type=self.type,
            title=self.title,
            status=self.status,
            detail=self.detail,
            code=self.code,
            instance=self.instance,
            extensions=dict(self.extensions),
        )

    def to_dict(self) -> dict[str, Any]:
        return self.to_problem_details().to_dict()

    @classmethod
    def not_found(
        cls,
        detail: str = "Resource not found",
        *,
        code: str = "PMCP404",
        instance: str | None = None,
        extensions: Mapping[str, Any] | None = None,
    ) -> ControlPlaneError:
        return cls(
            detail,
            code=code,
            status=404,
            type="etlantic.control_plane/not_found",
            title="Not Found",
            instance=instance,
            extensions=extensions,
        )

    @classmethod
    def forbidden(
        cls,
        detail: str = "Forbidden",
        *,
        code: str = "PMCP403",
        instance: str | None = None,
        extensions: Mapping[str, Any] | None = None,
    ) -> ControlPlaneError:
        return cls(
            detail,
            code=code,
            status=403,
            type="etlantic.control_plane/forbidden",
            title="Forbidden",
            instance=instance,
            extensions=extensions,
        )

    @classmethod
    def conflict(
        cls,
        detail: str,
        *,
        code: str = "PMCP409",
        instance: str | None = None,
        extensions: Mapping[str, Any] | None = None,
    ) -> ControlPlaneError:
        return cls(
            detail,
            code=code,
            status=409,
            type="etlantic.control_plane/conflict",
            title="Conflict",
            instance=instance,
            extensions=extensions,
        )

    @classmethod
    def gone(
        cls,
        detail: str = "Cursor expired or unknown",
        *,
        code: str = "PMCP410",
        instance: str | None = None,
        extensions: Mapping[str, Any] | None = None,
    ) -> ControlPlaneError:
        """SSE resume failure: reconnect without cursor to replay from start."""
        return cls(
            detail,
            code=code,
            status=410,
            type="etlantic.control_plane/gone",
            title="Gone",
            instance=instance,
            extensions=extensions,
        )

    @classmethod
    def unauthorized(
        cls,
        detail: str = "Unauthorized",
        *,
        code: str = "PMCP401",
        instance: str | None = None,
        extensions: Mapping[str, Any] | None = None,
    ) -> ControlPlaneError:
        return cls(
            detail,
            code=code,
            status=401,
            type="etlantic.control_plane/unauthorized",
            title="Unauthorized",
            instance=instance,
            extensions=extensions,
        )


__all__ = [
    "CONTROL_PLANE_ERROR_SCHEMA",
    "ControlPlaneError",
    "ErrorDisclosure",
    "ProblemDetails",
]
