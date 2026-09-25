# pyright: reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Schema drift models: normalized schema, observations, changes, impact (0.3)."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Any

from etlantic.contracts import Data, is_data_contract_type

_SECRET_METADATA_KEYS = {
    "authorization",
    "api_key",
    "apikey",
    "credential",
    "password",
    "secret",
    "token",
}

_ROW_LIKE_METADATA_KEYS = {
    "row",
    "rows",
    "record",
    "records",
    "sample",
    "samples",
    "sample_row",
    "sample_rows",
    "source_value",
    "source_values",
    "values",
    "data",
}

# Metadata is not a general-purpose payload channel. Keep the control values
# inference needs to round-trip, while redacting unknown primitive values that
# may actually be provider row data.
_SAFE_METADATA_KEYS = {
    "version",
    "fingerprint",
    "code",
    "severity",
    "message",
    "phase",
    "path",
    "identity",
    "identity_unresolved",
    "target_identity",
    "revision",
    "target_revision",
    "source_logical_type",
    "target_logical_type",
    "row_index",
    "validated_prefix_rows",
    "validated_rows",
    "replay_status",
    "state",
    "source",
    "method",
    "inspector",
    "status",
    "exists",
    "empty",
    "sampled",
    "header_only",
    "rows_observed",
    "retained_rows",
    "bytes_observed",
    "preview_rows_observed",
    "preview_bytes_observed",
    "preview_available",
    "max_rows",
    "max_fields",
    "max_diagnostics",
    "max_bytes",
    "timeout_seconds",
    "fields",
    "field",
    "name",
    "logical_type",
    "required",
    "nullable",
    "schema",
    "observed_schema",
    "target_hypothesis",
    "target_observation",
    "observed_values",
    "null_values",
    "missing_values",
    "type_counts",
    "inference_evidence",
    "limitations",
    "inferred",
    "inference_diagnostics",
    "diagnostics",
    "keys",
    "partitions",
    "capabilities",
    "write_modes",
    "modes",
    "operations",
    "operation",
    "from",
    "to",
    "source_node",
    "source_nodes",
    "source_fields",
    "qualified_source_fields",
    "source_types",
    "target_type",
    "observed_type",
    "output_field",
    "constraints",
    "confidence",
    "lineage",
    "lineage_version",
    "lineage_fingerprint",
    "graph",
    "backward_constraints",
    "backfill_explanations",
    "target_validation",
    "target_validation_fields",
    "target_fingerprint",
    "observed_schema_fingerprint",
    "context",
    "provider_object",
    "provider_type",
    "adapter",
    "plugin",
    "create_required",
    "create_intent",
    "can_create",
    "mode",
    "compatible",
    "casts",
    "obligations",
    "target",
}
_STRUCTURAL_MAP_KEYS = {
    "casts",
    "type_counts",
    "source_types",
    "backward_constraints",
    "field_constraints",
    "graph",
    "capabilities",
    "limits",
}

_CSV_PARSER_OPTION_KEYS = {
    "encoding",
    "delimiter",
    "quotechar",
    "escapechar",
    "doublequote",
    "strict",
    "skipinitialspace",
    "quoting",
}
_CSV_QUOTING_MODES = frozenset(
    getattr(csv, name)
    for name in (
        "QUOTE_MINIMAL",
        "QUOTE_ALL",
        "QUOTE_NONNUMERIC",
        "QUOTE_NONE",
        "QUOTE_NOTNULL",
        "QUOTE_STRINGS",
    )
    if hasattr(csv, name)
)
_LINEAGE_ENTRY_KEYS = {
    "field",
    "source_node",
    "source_nodes",
    "source_fields",
    "qualified_source_fields",
    "source_types",
    "operations",
    "invertible",
}
_LINEAGE_GRAPH_KEYS = {"version", "fields"}
_LINEAGE_GRAPH_FIELD_KEYS = {
    "source_nodes",
    "source_fields",
    "qualified_source_fields",
    "operations",
    "invertible",
}
_PROVIDER_CAPABILITY_KEYS = {
    "write_modes",
    "modes",
    "operations",
    "create",
}
_PROVIDER_WRITE_MODES = {"append", "overwrite", "merge", "upsert", "partition_replace"}
_PROVIDER_OPERATIONS = _PROVIDER_WRITE_MODES | {"create"}


def _metadata_key_kind(key: str) -> str | None:
    """Classify metadata keys before values are traversed.

    Metadata is an untrusted provider boundary.  Exact-key checks are easy to
    bypass with wire aliases such as ``sampleRows`` or ``provider_payload``;
    normalize the spelling first and classify by stable tokens instead.
    """
    normalized = re.sub(r"[^a-z0-9]", "", key.casefold())
    if any(
        token in normalized
        for token in (
            "secret",
            "password",
            "credential",
            "authorization",
            "apikey",
            "token",
        )
    ):
        return "secret"
    # Match row-bearing aliases, not ordinary control fields such as
    # ``max_rows``, ``sampled`` or ``rows_observed``.  Those fields are
    # necessary inference metadata and redacting them corrupts round trips.
    if normalized in {
        "row",
        "rows",
        "record",
        "records",
        "sample",
        "samples",
        "samplerow",
        "samplerows",
        "sourcevalue",
        "sourcevalues",
        "value",
        "values",
        "data",
        "body",
        "content",
        "providerpayload",
        "providerdata",
    }:
        return "row"
    return None


def _looks_like_path(value: str) -> bool:
    """Return whether a string appears to contain a local or URI path."""
    if os.path.isabs(value) or value.startswith(
        ("~/", "file://", "s3://", "gs://", "az://")
    ):
        return True
    # Avoid leaking common temporary/home path fragments embedded in messages.
    return bool(re.search(r"(?:^|[\s=])/(?:Users|home|tmp|var|Volumes)/", value))


def _wire_identity(value: str) -> str:
    """Return a stable, path-private identity used by both wire and hashes."""
    if not _looks_like_path(value):
        return value
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return f"path-sha256:{digest}"


def _bounded_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or len(value) > 256:
        raise ValueError(f"{label} must be a bounded mapping")
    return value


def _safe_parser_options(value: Any) -> dict[str, Any]:
    options = _bounded_mapping(value, "parser_options")
    unknown = set(options) - _CSV_PARSER_OPTION_KEYS
    if unknown:
        raise ValueError("parser_options contains unsupported keys")
    safe: dict[str, Any] = {}
    for raw_key, item in options.items():
        key = str(raw_key)
        if key in {"doublequote", "strict", "skipinitialspace"}:
            if type(item) is not bool:
                raise ValueError(f"parser option {key} must be boolean")
        elif key == "quoting":
            if type(item) is not int or item not in _CSV_QUOTING_MODES:
                raise ValueError("parser option quoting must be a CSV quoting mode")
        elif key in {"delimiter", "quotechar", "escapechar"}:
            if item is not None and (
                not isinstance(item, str) or len(item) != 1 or _looks_like_path(item)
            ):
                raise ValueError(f"parser option {key} must be one safe character")
        elif key == "encoding" and (
            not isinstance(item, str)
            or not item
            or len(item) > 64
            or _looks_like_path(item)
        ):
            raise ValueError("parser option encoding must be a safe name")
        safe[key] = item
    return safe


def _safe_capabilities(value: Any) -> dict[str, Any] | list[str] | None:
    if value is None:
        return None
    if isinstance(value, Mapping):
        capabilities = _bounded_mapping(value, "provider capabilities")
        if set(capabilities) - _PROVIDER_CAPABILITY_KEYS:
            raise ValueError("provider capabilities contain unsupported keys")
        safe: dict[str, Any] = {}
        for raw_key, item in capabilities.items():
            key = str(raw_key)
            if key in {"write_modes", "modes", "operations"}:
                if (
                    not isinstance(item, (list, tuple, set, frozenset))
                    or len(item) > 64
                ):
                    raise ValueError(
                        f"provider capability {key} must be a bounded list"
                    )
                if any(not isinstance(mode, str) for mode in item):
                    raise ValueError(
                        f"provider capability {key} contains an invalid mode"
                    )
                values = sorted(item) if isinstance(item, (set, frozenset)) else item
                allowed_modes = (
                    _PROVIDER_WRITE_MODES
                    if key == "write_modes"
                    else _PROVIDER_OPERATIONS
                )
                if any(mode not in allowed_modes for mode in values):
                    raise ValueError(
                        f"provider capability {key} contains an invalid mode"
                    )
                safe[key] = list(values)
            elif key == "create" and type(item) is bool:
                safe[key] = item
            else:
                raise ValueError(f"provider capability {key} must be boolean")
        return safe
    if isinstance(value, (list, tuple, set, frozenset)):
        if len(value) > 64 or any(
            not isinstance(item, str) or item not in _PROVIDER_OPERATIONS
            for item in value
        ):
            raise ValueError("provider capabilities contain an unsupported operation")
        values = sorted(value) if isinstance(value, (set, frozenset)) else value
        return list(values)
    raise ValueError("provider capabilities must be a bounded map or operation list")


def _safe_lineage_entry(value: Any, allowed_keys: set[str]) -> dict[str, Any]:
    entry = _bounded_mapping(value, "lineage entry")
    if set(entry) - allowed_keys:
        raise ValueError("lineage entry contains unsupported keys")
    safe: dict[str, Any] = {}
    for raw_key, item in entry.items():
        key = str(raw_key)
        if key == "invertible":
            if type(item) is not bool:
                raise ValueError("lineage invertible must be boolean")
            safe[key] = item
        elif key in {"field", "source_node"}:
            if item is not None and not isinstance(item, str):
                raise ValueError(f"lineage {key} must be a string")
            safe[key] = (
                _wire_identity(item)
                if key == "source_node" and item
                else _json_safe(item, key=key)
            )
        elif key == "source_types":
            types = _bounded_mapping(item, "lineage source_types")
            if any(not isinstance(kind, str) for kind in types.values()):
                raise ValueError("lineage source_types must map names to types")
            safe[key] = {
                _json_safe(str(name), key="field"): _json_safe(kind, key="logical_type")
                for name, kind in sorted(types.items(), key=lambda pair: str(pair[0]))
            }
        elif key == "operations":
            if not isinstance(item, (list, tuple)) or len(item) > 256:
                raise ValueError("lineage operations must be a bounded list")
            operations: list[Any] = []
            for operation in item:
                if isinstance(operation, str):
                    operations.append(_json_safe(operation, key="operation"))
                elif (
                    isinstance(operation, Mapping)
                    and set(operation) in ({"operation"}, {"operation", "field"})
                    and isinstance(operation["operation"], str)
                    and (
                        "field" not in operation or isinstance(operation["field"], str)
                    )
                ):
                    safe_operation = {
                        "operation": _json_safe(operation["operation"], key="operation")
                    }
                    if "field" in operation:
                        safe_operation["field"] = _json_safe(
                            operation["field"], key="field"
                        )
                    operations.append(safe_operation)
                else:
                    raise ValueError("lineage operations contain an invalid entry")
            safe[key] = operations
        else:
            if (
                not isinstance(item, (list, tuple))
                or len(item) > 256
                or any(not isinstance(part, str) for part in item)
            ):
                raise ValueError(f"lineage {key} must be a bounded string list")
            safe[key] = [
                _wire_identity(part)
                if key == "source_nodes"
                else _json_safe(part, key=key)
                for part in item
            ]
    return safe


def _safe_lineage(value: Any, *, graph: bool) -> dict[str, Any]:
    lineage = _bounded_mapping(value, "lineage metadata")
    if graph:
        if set(lineage) - _LINEAGE_GRAPH_KEYS:
            raise ValueError("lineage graph contains unsupported keys")
        result: dict[str, Any] = {}
        if "version" in lineage:
            version = lineage["version"]
            if type(version) is not int or version < 1:
                raise ValueError("lineage graph version must be a positive integer")
            result["version"] = version
        if "fields" in lineage:
            fields = _bounded_mapping(lineage["fields"], "lineage graph fields")
            result["fields"] = {
                _json_safe(str(name), key="field"): _safe_lineage_entry(
                    item, _LINEAGE_GRAPH_FIELD_KEYS
                )
                for name, item in sorted(fields.items(), key=lambda pair: str(pair[0]))
            }
        return result
    return {
        _json_safe(str(name), key="field"): _safe_lineage_entry(
            item, _LINEAGE_ENTRY_KEYS
        )
        for name, item in sorted(lineage.items(), key=lambda pair: str(pair[0]))
    }


def _json_safe(
    value: Any,
    *,
    key: str | None = None,
    depth: int = 0,
    allow_unknown_primitive: bool = False,
) -> Any:
    """Bound metadata to JSON primitives without retaining provider objects."""
    if key is not None:
        normalized_key = re.sub(r"[^a-z0-9_]", "", key.casefold())
        if normalized_key == "parser_options":
            return _safe_parser_options(value)
        if normalized_key == "capabilities":
            return _safe_capabilities(value)
        if normalized_key in {"lineage", "lineage_graph"} and value is not None:
            return _safe_lineage(value, graph=normalized_key == "lineage_graph")
        key_kind = _metadata_key_kind(key)
        if key_kind in {"secret", "row"}:
            return "<redacted>"
        if normalized_key not in _SAFE_METADATA_KEYS and not allow_unknown_primitive:
            if isinstance(value, (str, int, float, bool, bytes, date, datetime)):
                return "<redacted>"
            if isinstance(value, (list, tuple, set, frozenset)):
                return "<redacted>"
    if depth > 6:
        return "<truncated>"
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else "<non-finite>"
    if isinstance(value, str):
        return "<path-redacted>" if _looks_like_path(value) else value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, bytes):
        return f"<bytes:{len(value)}>"
    if isinstance(value, Mapping):
        allow_children = key in _STRUCTURAL_MAP_KEYS
        return {
            str(k): _json_safe(
                v,
                key=str(k),
                depth=depth + 1,
                allow_unknown_primitive=allow_children,
            )
            for k, v in sorted(value.items(), key=lambda item: str(item[0]))[:256]
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        values = list(value)
        if isinstance(value, (set, frozenset)):
            values.sort(key=repr)
        return [_json_safe(v, depth=depth + 1) for v in values[:256]]
    return f"<{type(value).__module__}.{type(value).__qualname__}>"


def json_safe_metadata(value: Any, *, key: str | None = None, depth: int = 0) -> Any:
    """Return the bounded, redacted wire representation for metadata."""
    return _json_safe(value, key=key, depth=depth)


class DriftImpact(StrEnum):
    """Impact vocabulary for schema changes."""

    INFORMATIONAL = "informational"
    COMPATIBLE = "compatible"
    CONDITIONALLY_COMPATIBLE = "conditionally_compatible"
    BREAKING = "breaking"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class NormalizedField:
    """Normalized field definition."""

    name: str
    logical_type: str
    required: bool = True
    nullable: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize field."""
        return {
            "name": self.name,
            "logical_type": self.logical_type,
            "required": self.required,
            "nullable": self.nullable,
            "metadata": _json_safe(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class NormalizedSchema:
    """Versioned normalized schema representation."""

    identity: str
    fields: tuple[NormalizedField, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    def fingerprint(self) -> str:
        """Deterministic fingerprint of logical schema (ignores physical metadata)."""
        payload = {
            "identity": _wire_identity(self.identity),
            "fields": [
                {
                    "name": f.name,
                    "logical_type": f.logical_type,
                    "required": f.required,
                    "nullable": f.nullable,
                }
                for f in sorted(self.fields, key=lambda x: x.name)
            ],
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(raw).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Serialize schema."""
        return {
            "version": 1,
            "identity": _wire_identity(self.identity),
            "fields": [f.to_dict() for f in self.fields],
            "fingerprint": self.fingerprint(),
            "metadata": _json_safe(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NormalizedSchema:
        """Deserialize a normalized schema (fingerprint is recomputed)."""
        version = int(data.get("version", 1))
        if version != 1:
            raise ValueError(f"unsupported normalized schema version: {version}")
        fields = tuple(
            NormalizedField(
                name=str(item["name"]),
                logical_type=str(item.get("logical_type") or "unknown"),
                required=bool(item.get("required", True)),
                nullable=bool(item.get("nullable", False)),
                metadata=_json_safe(item.get("metadata") or {}),
            )
            for item in (data.get("fields") or ())
            if isinstance(item, dict)
        )
        return cls(
            identity=str(data.get("identity") or ""),
            fields=fields,
            metadata=_json_safe(data.get("metadata") or {}),
        )


@dataclass(frozen=True, slots=True)
class SchemaObservation:
    """Immutable schema observation (no row data or secrets)."""

    subject_id: str
    schema: NormalizedSchema
    observed_at: str | None = None
    profile: str | None = None
    environment: str | None = None
    pipeline_id: str | None = None
    plan_id: str | None = None
    inspector: str | None = None
    confidence: float | None = None
    security_domain: str = "default"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize observation."""
        return {
            "subject_id": self.subject_id,
            "schema": self.schema.to_dict(),
            "observed_at": self.observed_at,
            "profile": self.profile,
            "environment": self.environment,
            "pipeline_id": self.pipeline_id,
            "plan_id": self.plan_id,
            "inspector": self.inspector,
            "confidence": self.confidence,
            "security_domain": self.security_domain,
            "metadata": _json_safe(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class SchemaChange:
    """A semantic schema change between two states."""

    kind: str
    path: str
    previous: dict[str, Any] | None = None
    current: dict[str, Any] | None = None
    impact: DriftImpact = DriftImpact.UNKNOWN
    remediation: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize change."""
        return {
            "kind": self.kind,
            "path": self.path,
            "previous": self.previous,
            "current": self.current,
            "impact": self.impact.value,
            "remediation": self.remediation,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class SchemaChangeSet:
    """Comparison of two schema states."""

    baseline_fingerprint: str
    candidate_fingerprint: str
    changes: tuple[SchemaChange, ...]
    overall_impact: DriftImpact
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize change set."""
        return {
            "baseline_fingerprint": self.baseline_fingerprint,
            "candidate_fingerprint": self.candidate_fingerprint,
            "changes": [c.to_dict() for c in self.changes],
            "overall_impact": self.overall_impact.value,
            "metadata": dict(self.metadata),
        }


def normalize_schema_from_model(
    model: type[Data], *, identity: str | None = None
) -> NormalizedSchema:
    """Normalize a ContractModel/Data class into a logical schema."""
    if not is_data_contract_type(model):
        raise TypeError("Expected a Data / ContractModel subclass")
    fields: list[NormalizedField] = []
    for name, field_info in getattr(model, "model_fields", {}).items():
        annotation = field_info.annotation
        logical = _logical_type_name(annotation)
        required = field_info.is_required()
        nullable = _is_nullable(annotation)
        fields.append(
            NormalizedField(
                name=name,
                logical_type=logical,
                required=required,
                nullable=nullable,
            )
        )
    return NormalizedSchema(
        identity=identity or f"schema:{model.__module__}.{model.__qualname__}",
        fields=tuple(fields),
    )


def normalize_schema_from_fields(
    fields: list[dict[str, Any]],
    *,
    identity: str,
    preserve_decimal: bool = False,
) -> NormalizedSchema:
    """Normalize a list of field mappings (operational observation path)."""
    normalized = tuple(
        NormalizedField(
            name=str(f["name"]),
            logical_type=normalize_logical_type(
                f.get("logical_type") or f.get("type") or "unknown",
                preserve_decimal=preserve_decimal,
            ),
            required=bool(f.get("required", True)),
            nullable=bool(f.get("nullable", False)),
            metadata={
                str(k): _json_safe(v, key=str(k))
                for k, v in f.items()
                if k not in {"name", "logical_type", "type", "required", "nullable"}
            },
        )
        for f in fields
    )
    return NormalizedSchema(identity=identity, fields=normalized)


def diff_normalized_schemas(
    baseline: NormalizedSchema,
    candidate: NormalizedSchema,
) -> SchemaChangeSet:
    """Operational drift path: compare normalized schemas without ContractModel."""
    left = {f.name: f for f in baseline.fields}
    right = {f.name: f for f in candidate.fields}
    changes: list[SchemaChange] = []
    for name in sorted(set(left) - set(right)):
        changes.append(
            SchemaChange(
                kind="field_removed",
                path=name,
                previous=left[name].to_dict(),
                impact=DriftImpact.BREAKING,
                remediation="Restore the field or update downstream consumers.",
            )
        )
    for name in sorted(set(right) - set(left)):
        changes.append(
            SchemaChange(
                kind="field_added",
                path=name,
                current=right[name].to_dict(),
                impact=DriftImpact.COMPATIBLE,
            )
        )
    for name in sorted(set(left) & set(right)):
        a, b = left[name], right[name]
        if _canonicalize_logical_type(a.logical_type) != _canonicalize_logical_type(
            b.logical_type
        ):
            changes.append(
                SchemaChange(
                    kind="type_changed",
                    path=name,
                    previous=a.to_dict(),
                    current=b.to_dict(),
                    impact=DriftImpact.BREAKING,
                )
            )
        elif a.nullable != b.nullable or a.required != b.required:
            impact = (
                DriftImpact.CONDITIONALLY_COMPATIBLE
                if (not a.nullable and b.nullable) or (a.required and not b.required)
                else DriftImpact.BREAKING
            )
            changes.append(
                SchemaChange(
                    kind="nullability_changed",
                    path=name,
                    previous=a.to_dict(),
                    current=b.to_dict(),
                    impact=impact,
                )
            )
    overall = _overall_impact(changes)
    return SchemaChangeSet(
        baseline_fingerprint=baseline.fingerprint(),
        candidate_fingerprint=candidate.fingerprint(),
        changes=tuple(changes),
        overall_impact=overall,
    )


def diff_contract_schemas(
    previous: type[Data],
    current: type[Data],
) -> SchemaChangeSet:
    """Contract-drift path: delegate compatibility meaning to ContractModel diffs."""
    from etlantic.interchange.diff import diff_data_contracts

    baseline = normalize_schema_from_model(previous)
    candidate = normalize_schema_from_model(current)
    operational = diff_normalized_schemas(baseline, candidate)
    try:
        report = diff_data_contracts(previous, current)
        # Map toolkit findings into impact when available
        if getattr(report, "has_errors", False) or (
            hasattr(report, "errors") and report.errors
        ):
            overall = DriftImpact.BREAKING
        elif operational.changes:
            overall = operational.overall_impact
        else:
            overall = DriftImpact.INFORMATIONAL
    except Exception:
        # Fail closed: toolkit errors must not under-report breaking changes.
        overall = DriftImpact.BREAKING
    return SchemaChangeSet(
        baseline_fingerprint=baseline.fingerprint(),
        candidate_fingerprint=candidate.fingerprint(),
        changes=operational.changes,
        overall_impact=overall,
        metadata={"path": "contract"},
    )


def _overall_impact(changes: list[SchemaChange]) -> DriftImpact:
    if not changes:
        return DriftImpact.INFORMATIONAL
    order = [
        DriftImpact.BREAKING,
        DriftImpact.CONDITIONALLY_COMPATIBLE,
        DriftImpact.UNKNOWN,
        DriftImpact.COMPATIBLE,
        DriftImpact.INFORMATIONAL,
    ]
    for level in order:
        if any(c.impact is level for c in changes):
            return level
    return DriftImpact.UNKNOWN


def _logical_type_name(annotation: Any) -> str:
    origin = getattr(annotation, "__origin__", None)
    if origin is not None:
        args = getattr(annotation, "__args__", ())
        non_none = [a for a in args if a is not type(None)]
        if non_none:
            return _logical_type_name(non_none[0])
    name = getattr(annotation, "__name__", None)
    raw = str(name).lower() if name else str(annotation).replace("typing.", "").lower()
    return _canonicalize_logical_type(raw)


def _canonicalize_logical_type(name: str) -> str:
    """Normalize Python and JSON-schema style logical type aliases."""
    name = name.strip().lower()
    name = name.removesuffix("type()").removesuffix("type")
    aliases = {
        "int": "integer",
        "int_": "integer",
        "integer": "integer",
        "uint": "integer",
        "uint_": "integer",
        "str": "string",
        "str_": "string",
        "string": "string",
        "varchar": "string",
        "char": "string",
        "text": "string",
        "bool": "boolean",
        "bool_": "boolean",
        "boolean": "boolean",
        "tinyint": "integer",
        "smallint": "integer",
        "bigint": "integer",
        "long": "integer",
        "int8": "integer",
        "int16": "integer",
        "int32": "integer",
        "int64": "integer",
        "uint8": "integer",
        "uint16": "integer",
        "uint32": "integer",
        "uint64": "integer",
        "float": "number",
        "float_": "number",
        "number": "number",
        "real": "number",
        "float16": "number",
        "float32": "number",
        "float64": "number",
        "double precision": "number",
        # Keep the historical contract normalization.  Record inference can
        # retain Decimal separately without changing persisted fingerprints.
        "decimal": "number",
        "double": "number",
        "timestamp": "datetime",
        "datetime": "datetime",
        "date": "date",
        "null": "null",
        "none": "null",
        "na": "null",
        "nat": "null",
        "nulltype": "null",
        "nonetype": "null",
        "bytes": "binary",
        "bytes_": "binary",
        "bytearray": "binary",
        "memoryview": "binary",
        "binary": "binary",
        "dict": "object",
        "object": "object",
        "mapping": "object",
        "map": "object",
        "struct": "object",
        "list": "array",
        "tuple": "array",
        "array": "array",
        "utf8": "string",
        "largeutf8": "string",
        "stringtype": "string",
        "longtype": "integer",
        "integertype": "integer",
        "floattype": "number",
        "doubletype": "number",
        "booleantype": "boolean",
    }
    return aliases.get(name, name)


def normalize_logical_type(value: Any, *, preserve_decimal: bool = False) -> str:
    """Normalize Python and provider type values to a logical type name.

    ``normalize_schema_from_fields`` historically canonicalizes ``decimal`` to
    ``number`` for typed contract fingerprints. Inference callers can opt into
    preserving Decimal precision while continuing to use the same alias map.
    """
    if isinstance(value, str):
        raw = value
    elif isinstance(value, type):
        raw = value.__name__
    else:
        named = getattr(value, "__name__", None)
        if isinstance(named, str):
            raw = named
        else:
            rendered = str(value)
            # Provider datatype instances (for example Arrow decimal128) use
            # a useful stable spelling.  An arbitrary object repr contains a
            # memory address and must never become a logical type or fingerprint.
            raw = (
                rendered
                if " at 0x" not in rendered and not rendered.startswith("<")
                else "unknown"
            )
    raw = raw.replace("typing.", "").strip().lower()
    raw = raw.rsplit(".", 1)[-1]
    # Scalar and dtype wrappers are provider implementation details around the
    # same logical value. Strip only these known suffixes; arbitrary class
    # names still fall through as unknown rather than becoming strings.
    raw = raw.removesuffix("scalar").removesuffix("dtype")
    # Provider-qualified spellings such as ``int64[pyarrow]`` and
    # ``timestamp[us, tz=UTC]`` carry physical parameters that do not change
    # the logical inference type.  Normalize the common primitive prefix
    # before applying the alias table.
    raw = re.sub(r"\[(?:pyarrow|numpy|arrow|pandas)(?:[^]]*)\]$", "", raw)
    if re.fullmatch(r"(?:decimal|decimal128|decimal256|numeric)\s*(?:\([^)]*\))?", raw):
        return "decimal" if preserve_decimal else "number"
    if re.fullmatch(
        r"(?:timestamp|datetime|datetime64)\s*(?:\[[^]]*\]|\([^)]*\))?", raw
    ):
        return "datetime"
    if re.fullmatch(r"(?:date|date32|date64)\s*(?:\([^)]*\))?", raw):
        return "date"
    if raw in {"decimal", "decimal128", "numeric"} and preserve_decimal:
        return "decimal"
    return _canonicalize_logical_type(raw)


def _is_nullable(annotation: Any) -> bool:
    origin = getattr(annotation, "__origin__", None)
    args = getattr(annotation, "__args__", ())
    if origin is None:
        return False
    return any(a is type(None) for a in args)
