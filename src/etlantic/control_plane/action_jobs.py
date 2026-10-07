"""Typed, secret-free requests for isolated connector action workers."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, TypeAlias, cast

from etlantic.control_plane.durable_models import ActionJobRecord
from etlantic.control_plane.errors import ControlPlaneError
from etlantic.control_plane.models import ControlPlaneContext

ConnectorActionKind: TypeAlias = Literal[
    "connector.test",
    "connector.catalog",
    "connector.schema.inspect",
    "connector.preflight",
    "connector.preview",
    "connector.provision",
    "connector.provision.cleanup",
]
CatalogConnectorKind: TypeAlias = Literal["source", "sink", "storage"]
ProvisionColumnType: TypeAlias = Literal[
    "string",
    "integer",
    "number",
    "boolean",
    "decimal",
    "date",
    "timestamp",
    "json",
]
_SAFE_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}\Z")
_SAFE_PROVIDER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
_SAFE_CURSOR = re.compile(r"[A-Za-z0-9_-]{1,256}\Z")
MIN_PREVIEW_RESULT_TTL_SECONDS = 60
MAX_PREVIEW_RESULT_TTL_SECONDS = 24 * 60 * 60
_PROVISION_RECEIPT_FIELDS = frozenset(
    {
        "action_id",
        "effect_id",
        "resource_id",
        "schema_fingerprint",
        "created",
        "cleanup_supported",
    }
)


def _fields(payload: dict[str, Any], *, required: set[str], optional: set[str]) -> None:
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
    """Read installed connector metadata or one saved connection's resources."""

    limit: int = 50
    cursor: str | None = None
    kind: CatalogConnectorKind | None = None
    provider: str | None = None
    connection_id: str | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ConnectorCatalogRequest:
        _fields(
            payload,
            required=set(),
            optional={"limit", "cursor", "kind", "provider", "connection_id"},
        )
        limit = payload.get("limit", 50)
        cursor = payload.get("cursor")
        kind = payload.get("kind")
        provider = payload.get("provider")
        connection_id = payload.get("connection_id")
        if (provider is None) != (connection_id is None):
            raise ControlPlaneError(
                "Live catalog requests require both provider and connection_id",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        if provider is not None:
            provider = _provider(provider)
            connection_id = _identifier(connection_id, field="connection_id")
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
        if kind is not None and (
            not isinstance(kind, str) or kind not in {"source", "sink", "storage"}
        ):
            raise ControlPlaneError(
                "Connector catalog kind is invalid",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        kind = cast(CatalogConnectorKind | None, kind)
        return cls(limit, cursor, kind, provider, connection_id)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "limit": self.limit,
            "cursor": self.cursor,
            "kind": self.kind,
        }
        # Preserve the historical canonical request for installed-catalog jobs.
        # These fields were added later, and explicit nulls change the persisted
        # idempotency fingerprint for older accepted requests.
        if self.provider is not None and self.connection_id is not None:
            payload["provider"] = self.provider
            payload["connection_id"] = self.connection_id
        return payload


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
            _identifier(
                payload.get("revision_selector", "current"), field="revision_selector"
            ),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "definition_id": self.definition_id,
            "revision_selector": self.revision_selector,
        }


@dataclass(frozen=True, slots=True)
class ConnectorPreviewRequest:
    """Read a bounded sample from a saved provider resource reference."""

    provider: str
    connection_id: str
    resource_id: str
    max_rows: int = 20
    max_bytes: int = 16 * 1024
    redact_fields: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ConnectorPreviewRequest:
        _fields(
            payload,
            required={"provider", "connection_id", "resource_id"},
            optional={"max_rows", "max_bytes", "redact_fields"},
        )
        max_rows = payload.get("max_rows", 20)
        max_bytes = payload.get("max_bytes", 16 * 1024)
        fields_value = payload.get("redact_fields", [])
        if type(max_rows) is not int or not 1 <= max_rows <= 100:
            raise ControlPlaneError(
                "Preview row limit must be between 1 and 100",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        if type(max_bytes) is not int or not 256 <= max_bytes <= 64 * 1024:
            raise ControlPlaneError(
                "Preview byte limit must be between 256 and 65536",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        if not isinstance(fields_value, list):
            raise ControlPlaneError(
                "Preview redaction fields are invalid",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        fields_list = cast(list[Any], fields_value)
        if len(fields_list) > 100:
            raise ControlPlaneError(
                "Preview redaction fields are invalid",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        fields = tuple(
            _identifier(value, field="redact_fields") for value in fields_list
        )
        if len(set(fields)) != len(fields):
            raise ControlPlaneError(
                "Preview redaction fields must be unique",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        return cls(
            _provider(payload["provider"]),
            _identifier(payload["connection_id"], field="connection_id"),
            _identifier(payload["resource_id"], field="resource_id"),
            max_rows,
            max_bytes,
            fields,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "connection_id": self.connection_id,
            "resource_id": self.resource_id,
            "max_rows": self.max_rows,
            "max_bytes": self.max_bytes,
            "redact_fields": list(self.redact_fields),
        }


@dataclass(frozen=True, slots=True)
class ProvisionColumn:
    """Provider-neutral column declaration for explicit create-only actions."""

    name: str
    logical_type: ProvisionColumnType
    nullable: bool = True
    primary_key: bool = False

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ProvisionColumn:
        _fields(
            payload,
            required={"name", "logical_type"},
            optional={"nullable", "primary_key"},
        )
        logical_type = payload["logical_type"]
        allowed_types = {
            "string",
            "integer",
            "number",
            "boolean",
            "decimal",
            "date",
            "timestamp",
            "json",
        }
        if not isinstance(logical_type, str) or logical_type not in allowed_types:
            raise ControlPlaneError(
                "Provision column logical_type is unsupported",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        typed_logical_type = cast(ProvisionColumnType, logical_type)
        nullable = payload.get("nullable", True)
        primary_key = payload.get("primary_key", False)
        if type(nullable) is not bool or type(primary_key) is not bool:
            raise ControlPlaneError(
                "Provision column flags must be boolean",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        if primary_key and nullable:
            raise ControlPlaneError(
                "Provision primary key columns cannot be nullable",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        return cls(
            _identifier(payload["name"], field="column name"),
            typed_logical_type,
            nullable,
            primary_key,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "logical_type": self.logical_type,
            "nullable": self.nullable,
            "primary_key": self.primary_key,
        }


@dataclass(frozen=True, slots=True)
class ConnectorProvisionRequest:
    """Explicit create-only provisioning with a canonical typed schema."""

    provider: str
    connection_id: str
    resource_id: str
    columns: tuple[ProvisionColumn, ...]
    target_kind: Literal["table", "dataset"] = "table"

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ConnectorProvisionRequest:
        _fields(
            payload,
            required={"provider", "connection_id", "resource_id", "columns"},
            optional={"target_kind"},
        )
        kind = payload.get("target_kind", "table")
        if not isinstance(kind, str) or kind not in {"table", "dataset"}:
            raise ControlPlaneError(
                "Provision target_kind is invalid",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        raw_columns = payload["columns"]
        if not isinstance(raw_columns, list):
            raise ControlPlaneError(
                "Provision requires between 1 and 100 columns",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        raw_column_list = cast(list[Any], raw_columns)
        if not 1 <= len(raw_column_list) <= 100:
            raise ControlPlaneError(
                "Provision requires between 1 and 100 columns",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        columns = tuple(
            ProvisionColumn.from_dict(cast(dict[str, Any], value))
            for value in raw_column_list
            if isinstance(value, dict)
        )
        if len(columns) != len(raw_column_list):
            raise ControlPlaneError(
                "Provision column declarations are invalid",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        names = [column.name for column in columns]
        if len(set(names)) != len(names):
            raise ControlPlaneError(
                "Provision column names must be unique",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        typed_kind = cast(Literal["table", "dataset"], kind)
        return cls(
            _provider(payload["provider"]),
            _identifier(payload["connection_id"], field="connection_id"),
            _identifier(payload["resource_id"], field="resource_id"),
            columns,
            typed_kind,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "connection_id": self.connection_id,
            "resource_id": self.resource_id,
            "target_kind": self.target_kind,
            "columns": [column.to_dict() for column in self.columns],
        }

    def schema_fingerprint(self) -> str:
        """Return the backend-derived digest of the canonical target schema."""
        return hashlib.sha256(
            json.dumps(
                {"target_kind": self.target_kind, "columns": self.to_dict()["columns"]},
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()


@dataclass(frozen=True, slots=True)
class ConnectorProvisionCleanupRequest:
    """Compensate only a target created by a verified provision action."""

    provider: str
    connection_id: str
    resource_id: str
    provision_action_id: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ConnectorProvisionCleanupRequest:
        _fields(
            payload,
            required={
                "provider",
                "connection_id",
                "resource_id",
                "provision_action_id",
            },
            optional=set(),
        )
        return cls(
            _provider(payload["provider"]),
            _identifier(payload["connection_id"], field="connection_id"),
            _identifier(payload["resource_id"], field="resource_id"),
            _identifier(payload["provision_action_id"], field="provision_action_id"),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "provider": self.provider,
            "connection_id": self.connection_id,
            "resource_id": self.resource_id,
            "provision_action_id": self.provision_action_id,
        }


def verify_provision_parent(
    ctx: ControlPlaneContext,
    request: ConnectorProvisionCleanupRequest,
    parent: ActionJobRecord,
) -> tuple[ConnectorProvisionRequest, Mapping[str, Any]]:
    """Verify the cleanup command names a live receipt for an owned create."""
    if (
        parent.action_id != request.provision_action_id
        or parent.action != "connector.provision"
        or parent.status not in {"succeeded", "timed_out", "cancelled"}
        or parent.result_json is None
        or parent.tenant_id != ctx.tenant.tenant_id
        or parent.workspace_id != ctx.workspace.workspace_id
        or parent.owner_id != (ctx.resource_owner_id or ctx.principal.identity_key)
        or parent.environment != ctx.environment.name
        or parent.security_domain_id != ctx.security_domain.domain_id
    ):
        raise ControlPlaneError.not_found("Provision effect not found")
    try:
        raw_request = json.loads(parent.request_json)
        raw_result = json.loads(parent.result_json)
    except (TypeError, ValueError) as exc:
        raise ControlPlaneError.conflict("Provision receipt is not verifiable") from exc
    if not isinstance(raw_request, dict) or not isinstance(raw_result, dict):
        raise ControlPlaneError.conflict("Provision receipt is not verifiable")
    request_payload = cast(dict[str, Any], raw_request)
    result_payload = cast(dict[str, Any], raw_result)
    provision = ConnectorProvisionRequest.from_dict(request_payload)
    effect_id = result_payload.get("effect_id")
    if (
        frozenset(result_payload) != _PROVISION_RECEIPT_FIELDS
        or provision.provider != request.provider
        or provision.connection_id != request.connection_id
        or provision.resource_id != request.resource_id
        or result_payload.get("action_id") != parent.action_id
        or result_payload.get("resource_id") != provision.resource_id
        or result_payload.get("schema_fingerprint") != provision.schema_fingerprint()
        or result_payload.get("created") is not True
        or result_payload.get("cleanup_supported") is not True
        or not isinstance(effect_id, str)
        or not _SAFE_IDENTIFIER.fullmatch(effect_id)
    ):
        raise ControlPlaneError.conflict(
            "Provision receipt does not authorize this cleanup"
        )
    return provision, result_payload


ConnectorActionRequest: TypeAlias = (
    ConnectorTestRequest
    | ConnectorCatalogRequest
    | ConnectorSchemaInspectionRequest
    | ConnectorPreflightRequest
    | ConnectorPreviewRequest
    | ConnectorProvisionRequest
    | ConnectorProvisionCleanupRequest
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
    if action == "connector.preview":
        return ConnectorPreviewRequest.from_dict(payload)
    if action == "connector.provision":
        return ConnectorProvisionRequest.from_dict(payload)
    if action == "connector.provision.cleanup":
        return ConnectorProvisionCleanupRequest.from_dict(payload)
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
    if isinstance(request, ConnectorCatalogRequest) and request.provider is not None:
        return (
            f"connector:{request.provider}",
            f"connection:{request.connection_id}",
        )
    if isinstance(
        request,
        ConnectorPreviewRequest
        | ConnectorProvisionRequest
        | ConnectorProvisionCleanupRequest,
    ):
        resources = [
            f"connector:{request.provider}",
            f"connection:{request.connection_id}",
            f"connector-resource:{request.provider}:{request.resource_id}",
        ]
        if isinstance(request, ConnectorProvisionCleanupRequest):
            resources.append(f"connector-action:{request.provision_action_id}")
        return tuple(resources)
    if isinstance(request, ConnectorPreflightRequest):
        return (f"definition:{request.definition_id}",)
    if action == "connector.catalog":
        return ("connector:*",)
    return ("connector:*",)


__all__ = [
    "MAX_PREVIEW_RESULT_TTL_SECONDS",
    "MIN_PREVIEW_RESULT_TTL_SECONDS",
    "CatalogConnectorKind",
    "ConnectorActionKind",
    "ConnectorActionRequest",
    "ConnectorCatalogRequest",
    "ConnectorPreflightRequest",
    "ConnectorPreviewRequest",
    "ConnectorProvisionCleanupRequest",
    "ConnectorProvisionRequest",
    "ConnectorSchemaInspectionRequest",
    "ConnectorTestRequest",
    "ProvisionColumn",
    "ProvisionColumnType",
    "connector_action_resources",
    "parse_connector_action_request",
    "verify_provision_parent",
]
