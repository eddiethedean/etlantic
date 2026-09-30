"""Typed, secret-free requests for isolated connector action workers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal, TypeAlias

from etlantic.control_plane.errors import ControlPlaneError

ConnectorActionKind: TypeAlias = Literal[
    "connector.test",
    "connector.catalog",
    "connector.schema.inspect",
    "connector.preflight",
]
CatalogConnectorKind: TypeAlias = Literal["source", "sink", "storage"]
_SAFE_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}\Z")
_SAFE_PROVIDER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
_SAFE_CURSOR = re.compile(r"[A-Za-z0-9_-]{1,256}\Z")


def _fields(
    payload: dict[str, Any], *, required: set[str], optional: set[str]
) -> None:
    unknown = set(payload) - required - optional
    missing = required - set(payload)
    if unknown or missing:
        raise ControlPlaneError(
            "Connector action request has missing or unsupported fields",
            code="PMCP400",
            status=400,
            title="Bad Request",
            type="etlantic.control_plane/bad_request",
            extensions={"missing": sorted(missing), "unsupported": sorted(unknown)},
        )


def _identifier(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not _SAFE_IDENTIFIER.fullmatch(value):
        raise ControlPlaneError(
            f"Connector action field {field!r} is invalid",
            code="PMCP400",
            status=400,
            title="Bad Request",
            type="etlantic.control_plane/bad_request",
        )
    return value


def _provider(value: Any) -> str:
    if not isinstance(value, str) or not _SAFE_PROVIDER.fullmatch(value):
        raise ControlPlaneError(
            "Connector action provider is invalid",
            code="PMCP400",
            status=400,
            title="Bad Request",
            type="etlantic.control_plane/bad_request",
        )
    return value


@dataclass(frozen=True, slots=True)
class ConnectorTestRequest:
    """Test a named server-side connection without accepting credentials."""

    provider: str
    connection_id: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ConnectorTestRequest:
        _fields(payload, required={"provider", "connection_id"}, optional=set())
        return cls(
            _provider(payload["provider"]),
            _identifier(payload["connection_id"], field="connection_id"),
        )

    def to_dict(self) -> dict[str, str]:
        return {"provider": self.provider, "connection_id": self.connection_id}


@dataclass(frozen=True, slots=True)
class ConnectorCatalogRequest:
    """Read one bounded page of the installed, profile-authorized catalog."""

    limit: int = 50
    cursor: str | None = None
    kind: CatalogConnectorKind | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ConnectorCatalogRequest:
        _fields(payload, required=set(), optional={"limit", "cursor", "kind"})
        limit = payload.get("limit", 50)
        cursor = payload.get("cursor")
        kind = payload.get("kind")
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ControlPlaneError(
                "Connector catalog page limit must be between 1 and 100",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        if cursor is not None and (
            not isinstance(cursor, str) or not _SAFE_CURSOR.fullmatch(cursor)
        ):
            raise ControlPlaneError(
                "Connector catalog cursor is invalid",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        if kind is not None and kind not in {"source", "sink", "storage"}:
            raise ControlPlaneError(
                "Connector catalog kind is invalid",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        return cls(limit, cursor, kind)

    def to_dict(self) -> dict[str, Any]:
        return {"limit": self.limit, "cursor": self.cursor, "kind": self.kind}


@dataclass(frozen=True, slots=True)
class ConnectorSchemaInspectionRequest:
    """Inspect a server-side connection with a hard field-count limit."""

    provider: str
    connection_id: str
    max_fields: int = 100

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ConnectorSchemaInspectionRequest:
        _fields(
            payload,
            required={"provider", "connection_id"},
            optional={"max_fields"},
        )
        max_fields = payload.get("max_fields", 100)
        if type(max_fields) is not int or not 1 <= max_fields <= 100:
            raise ControlPlaneError(
                "Schema inspection field limit must be between 1 and 100",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        return cls(
            _provider(payload["provider"]),
            _identifier(payload["connection_id"], field="connection_id"),
            max_fields,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "connection_id": self.connection_id,
            "max_fields": self.max_fields,
        }


@dataclass(frozen=True, slots=True)
class ConnectorPreflightRequest:
    """Run explicitly requested bounded live preflight on a saved definition."""

    definition_id: str
    revision_selector: str = "current"

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ConnectorPreflightRequest:
        _fields(
            payload,
            required={"definition_id"},
            optional={"revision_selector"},
        )
        return cls(
            _identifier(payload["definition_id"], field="definition_id"),
            _identifier(payload.get("revision_selector", "current"), field="revision_selector"),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "definition_id": self.definition_id,
            "revision_selector": self.revision_selector,
        }


ConnectorActionRequest: TypeAlias = (
    ConnectorTestRequest
    | ConnectorCatalogRequest
    | ConnectorSchemaInspectionRequest
    | ConnectorPreflightRequest
)


def parse_connector_action_request(
    action: ConnectorActionKind, payload: dict[str, Any]
) -> ConnectorActionRequest:
    """Validate an action discriminator and normalize its typed payload."""
    if action == "connector.test":
        return ConnectorTestRequest.from_dict(payload)
    if action == "connector.catalog":
        return ConnectorCatalogRequest.from_dict(payload)
    if action == "connector.schema.inspect":
        return ConnectorSchemaInspectionRequest.from_dict(payload)
    if action == "connector.preflight":
        return ConnectorPreflightRequest.from_dict(payload)
    raise ControlPlaneError(
        "Unsupported connector action",
        code="PMCP400",
        status=400,
        title="Bad Request",
        type="etlantic.control_plane/bad_request",
    )


def connector_action_resources(
    action: ConnectorActionKind, request: ConnectorActionRequest
) -> tuple[str, ...]:
    """Return every object reference a worker must authorize before provider IO."""
    if isinstance(request, ConnectorTestRequest | ConnectorSchemaInspectionRequest):
        return (f"connector:{request.provider}", f"connection:{request.connection_id}")
    if isinstance(request, ConnectorPreflightRequest):
        return (f"definition:{request.definition_id}",)
    if action == "connector.catalog":
        return ("connector:*",)
    return ("connector:*",)


__all__ = [
    "CatalogConnectorKind",
    "ConnectorActionKind",
    "ConnectorActionRequest",
    "ConnectorCatalogRequest",
    "ConnectorPreflightRequest",
    "ConnectorSchemaInspectionRequest",
    "ConnectorTestRequest",
    "connector_action_resources",
    "parse_connector_action_request",
]
