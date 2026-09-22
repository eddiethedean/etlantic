"""Target inspection, compatibility, and backward schema propagation."""

from __future__ import annotations

import datetime as _dt
import inspect as _inspect
import math
import stat as _stat
from collections.abc import Callable, Mapping
from contextlib import suppress
from decimal import Decimal, DecimalException
from pathlib import Path
from typing import Any

from etlantic.diagnostics import Diagnostic, Severity
from etlantic.schema_drift import (
    NormalizedField,
    NormalizedSchema,
    normalize_logical_type,
    normalize_schema_from_fields,
)

from .durable import _safe_file_identity
from .records import infer_csv, infer_json, infer_records
from .types import (
    TARGET_EXISTENCE_STATES,
    FieldConstraint,
    InferenceLimits,
    InferenceResult,
    TargetObservation,
    WriteCompatibility,
)

_LOSSLESS_CASTS = {
    ("string", "integer"),
    ("string", "number"),
    ("string", "decimal"),
    ("integer", "number"),
    ("integer", "decimal"),
    ("decimal", "number"),
    ("decimal", "decimal"),
    ("date", "datetime"),
}

_KNOWN_LOGICAL_TYPES = {
    "unknown",
    "null",
    "boolean",
    "integer",
    "number",
    "decimal",
    "string",
    "binary",
    "date",
    "datetime",
    "object",
    "array",
}


def _target_logical_type(value: Any) -> str:
    """Normalize provider types without inventing a new logical type."""
    normalized = normalize_logical_type(value, preserve_decimal=True)
    return normalized if normalized in _KNOWN_LOGICAL_TYPES else "unknown"


def _unknown_type_diagnostics(schema: NormalizedSchema) -> tuple[Diagnostic, ...]:
    return tuple(
        Diagnostic(
            "INFER_UNKNOWN_TYPE",
            Severity.WARNING,
            f"Target type for field {field.name!r} is unknown",
            path=(field.name,),
            phase="inference",
        )
        for field in schema.fields
        if field.logical_type == "unknown"
    )


_MISSING = object()
_MALFORMED = object()


def _unknown_target(
    code: str = "INFER_TARGET_UNKNOWN",
    *,
    identity: str = "target",
    inspector: str | None = None,
    message: str = "Target schema could not be inspected",
    metadata: Mapping[str, Any] | None = None,
) -> TargetObservation:
    safe_metadata = {"identity": _safe_file_identity(identity), **dict(metadata or {})}
    return TargetObservation(
        None,
        "unknown",
        None,
        inspector,
        (
            Diagnostic(
                code,
                Severity.WARNING,
                message,
                phase="inference",
            ),
        ),
        safe_metadata,
    )


def _with_target_diagnostic(
    observation: TargetObservation, diagnostic: Diagnostic
) -> TargetObservation:
    return TargetObservation(
        observation.schema,
        observation.exists,
        observation.revision,
        observation.inspector,
        (*observation.diagnostics, diagnostic),
        observation.metadata,
    )


def _diagnostics_from_payload(
    value: Any, *, max_diagnostics: int = 100
) -> tuple[Diagnostic, ...]:
    """Normalize provider diagnostics without retaining arbitrary objects."""
    if not isinstance(value, (list, tuple)):
        return ()
    diagnostics: list[Diagnostic] = []
    for item in value:
        if isinstance(item, Diagnostic):
            diagnostics.append(item)
            continue
        if not isinstance(item, Mapping):
            continue
        try:
            diagnostics.append(
                Diagnostic(
                    str(item.get("code") or "INFER_TARGET_UNKNOWN"),
                    Severity(str(item.get("severity") or "warning").lower()),
                    str(item.get("message") or "Target inspection diagnostic"),
                    tuple(str(path) for path in item.get("path", ())),
                    phase="inference",
                )
            )
        except (TypeError, ValueError):
            continue
    return tuple(diagnostics[:max_diagnostics])


def _schema_from_inspection(identity: str, fields: Any) -> NormalizedSchema:
    identity = _safe_file_identity(identity)
    if isinstance(fields, Mapping):
        fields = [
            {"name": name, "logical_type": logical_type}
            for name, logical_type in fields.items()
        ]
    elif fields is None:
        raise TypeError("target fields must be a mapping or sequence")
    elif hasattr(fields, "names") and isinstance(
        getattr(fields, "names", None), (list, tuple)
    ):
        try:
            fields = list(fields)
        except TypeError:
            raise TypeError("target schema is not iterable") from None
    elif not isinstance(fields, (list, tuple)):
        raise TypeError("target fields must be a mapping or sequence")
    values = list(fields)
    if all(isinstance(field, NormalizedField) for field in values):
        names = [field.name for field in values]
        if any(not isinstance(name, str) or not name for name in names):
            raise ValueError("target field names must be non-empty strings")
        if len(names) != len(set(names)):
            raise ValueError("target field names must be unique")
        if any(
            not isinstance(flag, bool)
            for field in values
            for flag in (field.required, field.nullable)
        ):
            raise TypeError("target field required and nullable flags must be booleans")
        normalized_fields: list[NormalizedField] = []
        for field in values:
            if not isinstance(field.logical_type, str):
                raise TypeError("target field logical types must be strings")
            if not isinstance(field.metadata, Mapping):
                raise TypeError("target field metadata must be a mapping")
            normalized_fields.append(
                NormalizedField(
                    field.name,
                    _target_logical_type(field.logical_type),
                    field.required,
                    field.nullable,
                    dict(field.metadata),
                )
            )
        return NormalizedSchema(identity=identity, fields=tuple(normalized_fields))
    normalized: list[Any] = []
    names: set[str] = set()
    for field in values:
        if isinstance(field, Mapping):
            item = dict(field)
            if "logical_type" not in item and "type" in item:
                item["logical_type"] = item["type"]
            field_name = item.get("name")
            if not isinstance(field_name, str) or not field_name:
                raise ValueError("target field name must be a non-empty string")
            if field_name in names:
                raise ValueError("target field names must be unique")
            names.add(field_name)
            if item.get("logical_type") is None:
                raise ValueError("target field requires name and logical type")
            if any(
                flag in item and not isinstance(item[flag], bool)
                for flag in ("required", "nullable")
            ):
                raise TypeError(
                    "target field required and nullable flags must be booleans"
                )
            item["logical_type"] = _target_logical_type(item["logical_type"])
            normalized.append(item)
            continue
        field_name = getattr(field, "name", None)
        logical_type = getattr(field, "logical_type", None)
        if logical_type is None:
            logical_type = getattr(field, "type", None)
        if not isinstance(field_name, str) or not field_name or logical_type is None:
            raise TypeError(
                "target fields must contain named fields with logical types"
            )
        if field_name in names:
            raise ValueError("target field names must be unique")
        names.add(field_name)
        required = getattr(field, "required", True)
        nullable = getattr(field, "nullable", False)
        if not isinstance(required, bool) or not isinstance(nullable, bool):
            raise TypeError("target field required and nullable flags must be booleans")
        normalized.append(
            {
                "name": field_name,
                "logical_type": _target_logical_type(logical_type),
                "required": required,
                "nullable": nullable,
            }
        )
    return normalize_schema_from_fields(
        normalized, identity=identity, preserve_decimal=True
    )


def _attach_target_metadata(
    schema: NormalizedSchema, metadata: Mapping[str, Any], revision: Any = None
) -> NormalizedSchema:
    """Keep provider capabilities and revision attached to the observed schema."""
    merged = {**schema.metadata, **dict(metadata)}
    if revision is not None:
        merged["revision"] = str(revision)
    return NormalizedSchema(schema.identity, schema.fields, merged)


def _validated_normalized_schema(schema: NormalizedSchema) -> NormalizedSchema:
    """Revalidate even normalized schemas at an untrusted inspection boundary."""
    if not isinstance(schema, NormalizedSchema):
        raise TypeError("target schema must be normalized")
    if not isinstance(schema.metadata, Mapping):
        raise TypeError("target schema metadata must be a mapping")
    normalized = _schema_from_inspection(schema.identity, schema.fields)
    return NormalizedSchema(
        normalized.identity, normalized.fields, dict(schema.metadata)
    )


def _normalize_target_observation(
    observation: TargetObservation,
) -> TargetObservation:
    """Validate schema fields carried by a provider-created observation."""
    if observation.schema is None:
        return observation
    try:
        schema = _validated_normalized_schema(observation.schema)
    except (AttributeError, KeyError, TypeError, ValueError):
        diagnostics = (
            *observation.diagnostics,
            Diagnostic(
                "INFER_TARGET_UNSUPPORTED",
                Severity.WARNING,
                "Target fields are malformed",
                phase="inference",
            ),
        )
        exists = "unknown" if observation.exists == "present" else observation.exists
        return TargetObservation(
            None,
            exists,
            observation.revision,
            observation.inspector,
            diagnostics,
            observation.metadata,
        )
    return TargetObservation(
        schema,
        observation.exists,
        observation.revision,
        observation.inspector,
        (*observation.diagnostics, *_unknown_type_diagnostics(schema)),
        observation.metadata,
    )


def _provider_exists(
    payload: Any,
) -> tuple[str | None, Diagnostic | None]:
    """Read an explicit provider existence state without inferring one."""
    try:
        if isinstance(payload, Mapping):
            raw = payload.get("exists", _MISSING)
        else:
            raw = getattr(payload, "exists", _MISSING)
            if callable(raw):
                raw = raw()
    except Exception:
        return (
            "unknown",
            Diagnostic(
                "INFER_TARGET_UNKNOWN",
                Severity.WARNING,
                "Provider target existence could not be established",
                phase="inference",
            ),
        )
    if raw is _MISSING:
        return None, None
    if _inspect.isawaitable(raw):
        close = getattr(raw, "close", None)
        if callable(close):
            with suppress(Exception):
                close()
        return (
            "unknown",
            Diagnostic(
                "INFER_TARGET_UNKNOWN",
                Severity.WARNING,
                "Provider returned an awaitable target existence state",
                phase="inference",
            ),
        )
    if isinstance(raw, str) and raw in TARGET_EXISTENCE_STATES:
        return raw, None
    return (
        "unknown",
        Diagnostic(
            "INFER_TARGET_UNKNOWN",
            Severity.WARNING,
            "Provider returned an invalid target existence state",
            phase="inference",
        ),
    )


async def _provider_exists_async(
    payload: Any,
) -> tuple[str | None, Diagnostic | None]:
    """Read an explicit provider existence state in an async context."""
    try:
        if isinstance(payload, Mapping):
            raw = payload.get("exists", _MISSING)
        else:
            raw = getattr(payload, "exists", _MISSING)
            if callable(raw):
                raw = raw()
        if _inspect.isawaitable(raw):
            raw = await raw
    except Exception:
        return (
            "unknown",
            Diagnostic(
                "INFER_TARGET_UNKNOWN",
                Severity.WARNING,
                "Provider target existence could not be established",
                phase="inference",
            ),
        )
    if raw is _MISSING:
        return None, None
    if isinstance(raw, str) and raw in TARGET_EXISTENCE_STATES:
        return raw, None
    return (
        "unknown",
        Diagnostic(
            "INFER_TARGET_UNKNOWN",
            Severity.WARNING,
            "Provider returned an invalid target existence state",
            phase="inference",
        ),
    )


def _provider_state_observation(
    state: str,
    *,
    identity: str,
    inspector: str,
    diagnostic: Diagnostic | None = None,
) -> TargetObservation:
    diagnostics: list[Diagnostic] = []
    if diagnostic is not None:
        diagnostics.append(diagnostic)
    if state == "unknown" and not any(
        item.code == "INFER_TARGET_UNKNOWN" for item in diagnostics
    ):
        diagnostics.append(
            Diagnostic(
                "INFER_TARGET_UNKNOWN",
                Severity.WARNING,
                "Target existence could not be established",
                phase="inference",
            )
        )
    return TargetObservation(
        None,
        state,
        None,
        inspector,
        tuple(diagnostics),
        {"empty": True, "identity": _safe_file_identity(identity)},
    )


def _provider_payload_value(payload: Any, key: str, default: Any = _MISSING) -> Any:
    if isinstance(payload, Mapping):
        return payload.get(key, default)
    return getattr(payload, key, default)


def _normalize_provider_payload(
    payload: Any,
    *,
    identity: str,
    inspector: str,
    max_diagnostics: int = 100,
    direct_mapping: bool = False,
    fallback_exists: str | None = None,
    provider_exists: tuple[str | None, Diagnostic | None] | None = None,
) -> TargetObservation | None:
    """Normalize every provider response through the same tri-state path."""
    if isinstance(payload, TargetObservation):
        return _normalize_target_observation(payload)
    if isinstance(payload, NormalizedSchema):
        try:
            schema = _validated_normalized_schema(payload)
        except (AttributeError, KeyError, TypeError, ValueError):
            return _unknown_target(
                "INFER_TARGET_UNSUPPORTED",
                identity=payload.identity,
                inspector=inspector,
                message="Target fields are malformed",
            )
        return TargetObservation(
            schema,
            "present",
            None,
            inspector,
            _unknown_type_diagnostics(schema),
            metadata={"identity": _safe_file_identity(payload.identity)},
        )

    if provider_exists is None:
        explicit_exists, exists_diagnostic = _provider_exists(payload)
    else:
        explicit_exists, exists_diagnostic = provider_exists
    raw_schema_mapping = False
    if direct_mapping and isinstance(payload, Mapping):
        schema_payload = payload.get("schema", _MISSING)
        schema_is_envelope = schema_payload is not _MISSING and not isinstance(
            schema_payload, (str, type)
        )
        raw_schema_mapping = (
            "exists" not in payload
            and "fields" not in payload
            and not schema_is_envelope
            and all(isinstance(value, (str, type)) for value in payload.values())
        )
        if raw_schema_mapping:
            # Raw schema mappings remain supported when they cannot be
            # confused with an existence-state envelope.
            explicit_exists = None
            exists_diagnostic = None

    fields = (
        payload if raw_schema_mapping else _provider_payload_value(payload, "fields")
    )
    schema_payload = _provider_payload_value(payload, "schema")
    if fields is _MISSING and schema_payload is not _MISSING:
        if isinstance(schema_payload, Mapping):
            nested_fields = _provider_payload_value(schema_payload, "fields")
            if nested_fields is not _MISSING:
                fields = nested_fields
            elif not schema_payload:
                fields = []
            elif all(
                isinstance(value, (str, type)) for value in schema_payload.values()
            ):
                fields = schema_payload
            else:
                fields = _MALFORMED
        else:
            fields = schema_payload
    if fields is _MISSING and hasattr(payload, "names"):
        fields = payload

    if explicit_exists is None and fields is _MISSING:
        return None

    if raw_schema_mapping:
        target_identity = identity
        revision = None
        metadata: dict[str, Any] = {
            "identity": _safe_file_identity(identity),
        }
    else:
        target_identity = _provider_payload_value(payload, "identity", identity)
        if target_identity is _MISSING or target_identity is None:
            target_identity = identity
        target_identity = str(target_identity)
        revision = _provider_payload_value(payload, "revision")
        if revision is _MISSING:
            revision = None
        metadata = {
            "identity": _safe_file_identity(target_identity),
        }
        for key in ("keys", "partitions", "capabilities"):
            value = _provider_payload_value(payload, key)
            if value is not _MISSING:
                metadata[key] = value

    if explicit_exists is None and fallback_exists is not None:
        explicit_exists = fallback_exists

    diagnostics: list[Diagnostic] = []
    if exists_diagnostic is not None:
        diagnostics.append(exists_diagnostic)
    payload_diagnostics = _provider_payload_value(payload, "diagnostics")
    diagnostics.extend(
        _diagnostics_from_payload(
            payload_diagnostics,
            max_diagnostics=max_diagnostics,
        )
    )

    schema: NormalizedSchema | None = None
    schema_error: str | None = None
    if fields is not _MISSING:
        try:
            schema = _schema_from_inspection(target_identity, fields)
        except (AttributeError, KeyError, TypeError, ValueError):
            schema_error = "Target fields are malformed"

    if schema_error is not None:
        diagnostics.append(
            Diagnostic(
                "INFER_TARGET_UNSUPPORTED",
                Severity.WARNING,
                schema_error,
                phase="inference",
            )
        )
        # An explicit absent/unknown state remains authoritative, but a
        # malformed present payload cannot prove a usable target contract.
        if explicit_exists == "present" or explicit_exists is None:
            explicit_exists = "unknown"
    if schema is not None:
        metadata["empty"] = not bool(schema.fields)
        schema = _attach_target_metadata(schema, metadata, revision)
        if explicit_exists in {"absent", "unknown"}:
            # Keep only bounded provenance for untrusted schema-shaped data.
            metadata["untrusted_schema_fingerprint"] = schema.fingerprint()
            schema = None
    elif explicit_exists is not None:
        metadata["empty"] = True

    if explicit_exists is None:
        explicit_exists = (
            "present" if schema is not None and schema.fields else "unknown"
        )
    if explicit_exists == "unknown" and not any(
        diagnostic.code == "INFER_TARGET_UNKNOWN" for diagnostic in diagnostics
    ):
        diagnostics.append(
            Diagnostic(
                "INFER_TARGET_UNKNOWN",
                Severity.WARNING,
                "Target existence could not be established",
                phase="inference",
            )
        )
    if explicit_exists != "present":
        schema = None
    return TargetObservation(
        schema if schema is not None and schema.fields else None,
        explicit_exists,
        str(revision) if revision is not None else None,
        inspector,
        tuple(diagnostics[:max_diagnostics]),
        metadata,
    )


async def _normalize_provider_payload_async(
    payload: Any,
    *,
    identity: str,
    inspector: str,
    max_diagnostics: int = 100,
    direct_mapping: bool = False,
    fallback_exists: str | None = None,
    provider_exists: tuple[str | None, Diagnostic | None] | None = None,
) -> TargetObservation | None:
    """Normalize a provider response after awaiting its existence state."""
    if provider_exists is None:
        provider_exists = await _provider_exists_async(payload)
    return _normalize_provider_payload(
        payload,
        identity=identity,
        inspector=inspector,
        max_diagnostics=max_diagnostics,
        direct_mapping=direct_mapping,
        fallback_exists=fallback_exists,
        provider_exists=provider_exists,
    )


def inspect_target(
    target: Any, *, identity: str = "target", max_diagnostics: int = 100
) -> TargetObservation:
    """Inspect an existing target when its adapter exposes a schema."""
    if isinstance(target, TargetObservation):
        return _normalize_target_observation(target)
    if isinstance(target, NormalizedSchema):
        try:
            schema = _validated_normalized_schema(target)
        except (AttributeError, KeyError, TypeError, ValueError):
            return _unknown_target(
                "INFER_TARGET_UNSUPPORTED",
                identity=target.identity,
                inspector="normalized",
                message="Target fields are malformed",
            )
        return TargetObservation(
            schema,
            "present",
            None,
            "normalized",
            _unknown_type_diagnostics(schema),
        )
    if isinstance(target, Mapping):
        try:
            observation = _normalize_provider_payload(
                target,
                identity=identity,
                inspector="mapping",
                max_diagnostics=max_diagnostics,
                direct_mapping=True,
            )
        except Exception:
            return _unknown_target(
                "INFER_TARGET_UNKNOWN",
                identity=identity,
                inspector="mapping",
                message="Target mapping could not be inspected",
            )
        if observation is not None:
            if observation.schema is not None:
                observation = TargetObservation(
                    observation.schema,
                    observation.exists,
                    observation.revision,
                    observation.inspector,
                    (
                        *_unknown_type_diagnostics(observation.schema),
                        *observation.diagnostics,
                    ),
                    observation.metadata,
                )
            return observation
    if isinstance(target, bytes):
        return _unknown_target(
            "INFER_TARGET_UNSUPPORTED", identity=identity, inspector="bytes"
        )
    if isinstance(target, (str, Path)):
        path = Path(target)
        try:
            path_stat = path.stat()
        except FileNotFoundError:
            return TargetObservation(
                None,
                "absent",
                None,
                "filesystem",
                metadata={"identity": _safe_file_identity(identity)},
            )
        except (OSError, ValueError):
            return _unknown_target(
                "INFER_TARGET_UNKNOWN",
                identity=identity,
                inspector="filesystem",
                message="Target filesystem state could not be established",
            )
        if not _stat.S_ISREG(path_stat.st_mode):
            return _unknown_target("INFER_TARGET_UNSUPPORTED", identity=identity)
        suffix = path.suffix.lower()
        try:
            if suffix in {".json", ".jsonl"}:
                result = infer_json(path, identity=identity)
                inspector = "json"
            elif suffix in {".csv", ".tsv"}:
                result = infer_csv(
                    path,
                    options={"delimiter": "\t"} if suffix == ".tsv" else None,
                    identity=identity,
                )
                inspector = "csv"
            else:
                return _unknown_target("INFER_TARGET_UNSUPPORTED", identity=identity)
        except OSError:
            return _unknown_target(
                "INFER_TARGET_UNKNOWN",
                identity=identity,
                inspector="filesystem",
                message="Target file could not be read",
            )
        diagnostics = tuple(result.diagnostics) + _unknown_type_diagnostics(
            result.schema
        )
        if diagnostics:
            metadata: dict[str, Any] = {
                "identity": _safe_file_identity(identity),
            }
            if result.schema.fields:
                metadata["untrusted_schema_fingerprint"] = result.schema.fingerprint()
            return TargetObservation(
                None,
                "unknown",
                None,
                inspector,
                diagnostics,
                metadata,
            )
        return TargetObservation(
            result.schema if result.schema.fields else None,
            "present",
            None,
            inspector,
            (),
            {
                "empty": not bool(result.schema.fields),
                "identity": _safe_file_identity(identity),
            },
        )
    try:
        adapter_exists, adapter_diagnostic = _provider_exists(target)
    except Exception:
        return _unknown_target(
            "INFER_TARGET_UNKNOWN", identity=identity, inspector=type(target).__name__
        )
    if adapter_exists in {"absent", "unknown"}:
        return _provider_state_observation(
            adapter_exists,
            identity=identity,
            inspector=type(target).__name__,
            diagnostic=adapter_diagnostic,
        )
    try:
        inspect = getattr(target, "inspect_schema", None)
    except Exception:
        return _unknown_target(
            "INFER_TARGET_UNKNOWN", identity=identity, inspector=type(target).__name__
        )
    if callable(inspect):
        try:
            result = inspect()
            if _inspect.isawaitable(result):
                close = getattr(result, "close", None)
                if callable(close):
                    close()
                return _unknown_target(
                    "INFER_TARGET_UNSUPPORTED",
                    identity=identity,
                    inspector=type(target).__name__,
                )
            observation = _normalize_provider_payload(
                result,
                identity=identity,
                inspector=type(target).__name__,
                max_diagnostics=max_diagnostics,
                direct_mapping=True,
                fallback_exists=adapter_exists,
            )
            if observation is not None:
                if observation.schema is not None:
                    observation = TargetObservation(
                        observation.schema,
                        observation.exists,
                        observation.revision,
                        observation.inspector,
                        (
                            *_unknown_type_diagnostics(observation.schema),
                            *observation.diagnostics,
                        ),
                        observation.metadata,
                    )
                return observation
        except Exception:
            return _unknown_target(
                "INFER_TARGET_UNKNOWN",
                identity=identity,
                inspector=type(target).__name__,
            )
    try:
        schema_attr = getattr(target, "schema", _MISSING)
    except Exception:
        return _unknown_target(
            "INFER_TARGET_UNKNOWN", identity=identity, inspector=type(target).__name__
        )
    if callable(schema_attr):
        try:
            schema_attr = schema_attr()
            if _inspect.isawaitable(schema_attr):
                close = getattr(schema_attr, "close", None)
                if callable(close):
                    close()
                return _unknown_target(
                    "INFER_TARGET_UNSUPPORTED",
                    identity=identity,
                    inspector=type(target).__name__,
                )
            if schema_attr is None:
                return _unknown_target(
                    "INFER_TARGET_UNSUPPORTED",
                    identity=identity,
                    inspector=type(target).__name__,
                )
        except Exception:
            return _unknown_target(
                "INFER_TARGET_UNKNOWN",
                identity=identity,
                inspector=type(target).__name__,
            )
    payload = target if schema_attr is _MISSING or schema_attr is None else schema_attr
    try:
        observation = _normalize_provider_payload(
            payload,
            identity=identity,
            inspector=type(target).__name__,
            max_diagnostics=max_diagnostics,
            direct_mapping=payload is not target,
            fallback_exists=adapter_exists,
            provider_exists=(adapter_exists, adapter_diagnostic)
            if payload is target
            else None,
        )
    except Exception:
        return _unknown_target(
            "INFER_TARGET_UNKNOWN", identity=identity, inspector=type(target).__name__
        )
    if observation is not None:
        if observation.schema is not None:
            observation = TargetObservation(
                observation.schema,
                observation.exists,
                observation.revision,
                observation.inspector,
                (
                    *_unknown_type_diagnostics(observation.schema),
                    *observation.diagnostics,
                ),
                observation.metadata,
            )
        return observation
    return _unknown_target(
        identity=identity,
        inspector=type(target).__name__,
    )


async def inspect_target_async(
    target: Any,
    *,
    identity: str = "target",
    binding: Mapping[str, Any] | None = None,
    context: Mapping[str, Any] | None = None,
    max_diagnostics: int = 100,
) -> TargetObservation:
    """Inspect synchronous or asynchronous target adapters safely."""
    if isinstance(target, TargetObservation):
        return _normalize_target_observation(target)
    if isinstance(target, (NormalizedSchema, str, Path, bytes, Mapping)):
        return inspect_target(
            target, identity=identity, max_diagnostics=max_diagnostics
        )
    try:
        adapter_exists, adapter_diagnostic = await _provider_exists_async(target)
    except Exception:
        return _unknown_target(
            "INFER_TARGET_UNKNOWN", identity=identity, inspector=type(target).__name__
        )
    if adapter_exists in {"absent", "unknown"}:
        return _provider_state_observation(
            adapter_exists,
            identity=identity,
            inspector=type(target).__name__,
            diagnostic=adapter_diagnostic,
        )
    try:
        inspect_schema = getattr(target, "inspect_schema", None)
    except Exception:
        return _unknown_target(
            "INFER_TARGET_UNKNOWN", identity=identity, inspector=type(target).__name__
        )
    if not callable(inspect_schema):
        try:
            schema_method = getattr(target, "schema", _MISSING)
        except Exception:
            return _unknown_target(
                "INFER_TARGET_UNKNOWN",
                identity=identity,
                inspector=type(target).__name__,
            )
        if (
            schema_method is not _MISSING
            and schema_method is not None
            and not callable(schema_method)
        ):
            try:
                schema_attr = schema_method
                if _inspect.isawaitable(schema_attr):
                    schema_attr = await schema_attr
                if schema_attr is None:
                    return _unknown_target(
                        "INFER_TARGET_UNSUPPORTED",
                        identity=identity,
                        inspector=type(target).__name__,
                    )
                observation = await _normalize_provider_payload_async(
                    schema_attr,
                    identity=identity,
                    inspector=type(target).__name__,
                    max_diagnostics=max_diagnostics,
                    direct_mapping=True,
                    fallback_exists=adapter_exists,
                )
                if observation is not None:
                    if observation.schema is not None:
                        observation = TargetObservation(
                            observation.schema,
                            observation.exists,
                            observation.revision,
                            observation.inspector,
                            (
                                *_unknown_type_diagnostics(observation.schema),
                                *observation.diagnostics,
                            ),
                            observation.metadata,
                        )
                    return observation
            except Exception:
                return _unknown_target(
                    "INFER_TARGET_UNKNOWN",
                    identity=identity,
                    inspector=type(target).__name__,
                )
            return _unknown_target(
                "INFER_TARGET_UNSUPPORTED",
                identity=identity,
                inspector=type(target).__name__,
            )
        if schema_method is _MISSING or schema_method is None:
            try:
                observation = await _normalize_provider_payload_async(
                    target,
                    identity=identity,
                    inspector=type(target).__name__,
                    max_diagnostics=max_diagnostics,
                    fallback_exists=adapter_exists,
                    provider_exists=(adapter_exists, adapter_diagnostic),
                )
            except Exception:
                return _unknown_target(
                    "INFER_TARGET_UNKNOWN",
                    identity=identity,
                    inspector=type(target).__name__,
                )
            if observation is not None:
                if observation.schema is not None:
                    observation = TargetObservation(
                        observation.schema,
                        observation.exists,
                        observation.revision,
                        observation.inspector,
                        (
                            *_unknown_type_diagnostics(observation.schema),
                            *observation.diagnostics,
                        ),
                        observation.metadata,
                    )
                return observation
            return _unknown_target(
                identity=identity,
                inspector=type(target).__name__,
            )
        try:
            schema_attr = schema_method()
            if _inspect.isawaitable(schema_attr):
                schema_attr = await schema_attr
            if schema_attr is None:
                return _unknown_target(
                    "INFER_TARGET_UNSUPPORTED",
                    identity=identity,
                    inspector=type(target).__name__,
                )
            observation = await _normalize_provider_payload_async(
                schema_attr,
                identity=identity,
                inspector=type(target).__name__,
                max_diagnostics=max_diagnostics,
                direct_mapping=True,
                fallback_exists=adapter_exists,
            )
            if observation is not None:
                if observation.schema is not None:
                    observation = TargetObservation(
                        observation.schema,
                        observation.exists,
                        observation.revision,
                        observation.inspector,
                        (
                            *_unknown_type_diagnostics(observation.schema),
                            *observation.diagnostics,
                        ),
                        observation.metadata,
                    )
                return observation
        except Exception:
            return _unknown_target(
                "INFER_TARGET_UNKNOWN",
                identity=identity,
                inspector=type(target).__name__,
            )
        return _unknown_target(
            "INFER_TARGET_UNSUPPORTED",
            identity=identity,
            inspector=type(target).__name__,
        )
    kwargs: dict[str, Any] = {}
    if binding is not None:
        kwargs["binding"] = binding
    if context is not None:
        kwargs["context"] = context
    try:
        try:
            result = inspect_schema(**kwargs)
        except TypeError:
            result = inspect_schema()
        if _inspect.isawaitable(result):
            result = await result
        observation = await _normalize_provider_payload_async(
            result,
            identity=identity,
            inspector=type(target).__name__,
            max_diagnostics=max_diagnostics,
            direct_mapping=True,
            fallback_exists=adapter_exists,
        )
        if observation is not None:
            if observation.schema is not None:
                observation = TargetObservation(
                    observation.schema,
                    observation.exists,
                    observation.revision,
                    observation.inspector,
                    (
                        *_unknown_type_diagnostics(observation.schema),
                        *observation.diagnostics,
                    ),
                    observation.metadata,
                )
            return observation
    except Exception:
        return _unknown_target(
            "INFER_TARGET_UNKNOWN",
            identity=identity,
            inspector=type(target).__name__,
        )
    try:
        schema_attr = getattr(target, "schema", _MISSING)
    except Exception:
        return _unknown_target(
            "INFER_TARGET_UNKNOWN", identity=identity, inspector=type(target).__name__
        )
    if callable(schema_attr):
        try:
            schema_attr = schema_attr()
            if _inspect.isawaitable(schema_attr):
                schema_attr = await schema_attr
            if schema_attr is None:
                return _unknown_target(
                    "INFER_TARGET_UNSUPPORTED",
                    identity=identity,
                    inspector=type(target).__name__,
                )
            observation = await _normalize_provider_payload_async(
                schema_attr,
                identity=identity,
                inspector=type(target).__name__,
                max_diagnostics=max_diagnostics,
                direct_mapping=True,
                fallback_exists=adapter_exists,
            )
            if observation is not None:
                if observation.schema is not None:
                    observation = TargetObservation(
                        observation.schema,
                        observation.exists,
                        observation.revision,
                        observation.inspector,
                        (
                            *_unknown_type_diagnostics(observation.schema),
                            *observation.diagnostics,
                        ),
                        observation.metadata,
                    )
                return observation
        except Exception:
            return _unknown_target(
                "INFER_TARGET_UNKNOWN",
                identity=identity,
                inspector=type(target).__name__,
            )
    elif schema_attr is not _MISSING:
        try:
            observation = await _normalize_provider_payload_async(
                schema_attr,
                identity=identity,
                inspector=type(target).__name__,
                max_diagnostics=max_diagnostics,
                direct_mapping=True,
                fallback_exists=adapter_exists,
            )
            if observation is not None:
                if observation.schema is not None:
                    observation = TargetObservation(
                        observation.schema,
                        observation.exists,
                        observation.revision,
                        observation.inspector,
                        (
                            *_unknown_type_diagnostics(observation.schema),
                            *observation.diagnostics,
                        ),
                        observation.metadata,
                    )
                return observation
        except Exception:
            return _unknown_target(
                "INFER_TARGET_UNKNOWN",
                identity=identity,
                inspector=type(target).__name__,
            )
    return _unknown_target(
        "INFER_TARGET_UNSUPPORTED",
        identity=identity,
        inspector=type(target).__name__,
    )


def infer_records_for_target(
    records: Any,
    target: Any,
    *,
    hints: Mapping[str, Any] | None = None,
    limits: InferenceLimits | None = None,
    identity: str = "records",
    retain_rows: bool = False,
    expected_revision: str | None = None,
    revision_reader: Callable[[], Any] | None = None,
) -> InferenceResult:
    """Infer records and apply constraints from an existing target schema."""
    # Keep the bounded prefix while validating conversions, even when the
    # caller only requested a schema.  Rows are removed after validation.
    source = infer_records(
        records, hints=hints, limits=limits, identity=identity, retain_rows=True
    )
    limits = limits or InferenceLimits()
    observation = (
        _normalize_target_observation(target)
        if isinstance(target, TargetObservation)
        else inspect_target(
            target,
            identity=f"target:{identity}",
            max_diagnostics=limits.max_diagnostics,
        )
    )
    if revision_reader is not None:
        try:
            current_revision = revision_reader()
            if hasattr(current_revision, "__await__"):
                raise TypeError("revision_reader returned an awaitable; use async API")
        except Exception:
            observation = _with_target_diagnostic(
                observation,
                Diagnostic(
                    "INFER_TARGET_REVISION_UNKNOWN",
                    Severity.ERROR,
                    "Target revision could not be rechecked before planning",
                    phase="inference",
                ),
            )
        else:
            current_revision = (
                str(current_revision) if current_revision is not None else None
            )
            if current_revision is None or observation.revision is None:
                observation = _with_target_diagnostic(
                    observation,
                    Diagnostic(
                        "INFER_TARGET_REVISION_UNKNOWN",
                        Severity.ERROR,
                        "Target revision is missing; publication cannot be fenced",
                        phase="inference",
                    ),
                )
            elif current_revision != observation.revision:
                observation = _with_target_diagnostic(
                    observation,
                    Diagnostic(
                        "INFER_TARGET_STALE",
                        Severity.ERROR,
                        "Target revision changed after schema inspection",
                        phase="inference",
                    ),
                )
    if expected_revision is not None and observation.revision != expected_revision:
        observation = TargetObservation(
            observation.schema,
            observation.exists,
            observation.revision,
            observation.inspector,
            (
                *observation.diagnostics,
                Diagnostic(
                    "INFER_TARGET_STALE",
                    Severity.ERROR,
                    "Inspected target revision does not match expected revision",
                    phase="inference",
                ),
            ),
            observation.metadata,
        )
    result = _backfill_observation(source, observation)
    if retain_rows:
        return result
    return InferenceResult(
        result.schema,
        result.diagnostics,
        result.evidence,
        {**result.provenance, "retained_rows": False},
        (),
        result.replay,
        result.observed_schema,
        result.target_hypothesis,
        result.target_observation,
    )


async def infer_records_for_target_async(
    records: Any,
    target: Any,
    *,
    hints: Mapping[str, Any] | None = None,
    limits: InferenceLimits | None = None,
    identity: str = "records",
    retain_rows: bool = False,
    binding: Mapping[str, Any] | None = None,
    context: Mapping[str, Any] | None = None,
    expected_revision: str | None = None,
    revision_reader: Callable[[], Any] | None = None,
) -> InferenceResult:
    """Async counterpart for connector-backed target schema inspection."""
    source = infer_records(
        records, hints=hints, limits=limits, identity=identity, retain_rows=True
    )
    limits = limits or InferenceLimits()
    observation = (
        _normalize_target_observation(target)
        if isinstance(target, TargetObservation)
        else await inspect_target_async(
            target,
            identity=f"target:{identity}",
            binding=binding,
            context=context,
            max_diagnostics=limits.max_diagnostics,
        )
    )
    if revision_reader is not None:
        try:
            current_revision = revision_reader()
            if hasattr(current_revision, "__await__"):
                current_revision = await current_revision
        except Exception:
            observation = _with_target_diagnostic(
                observation,
                Diagnostic(
                    "INFER_TARGET_REVISION_UNKNOWN",
                    Severity.ERROR,
                    "Target revision could not be rechecked before planning",
                    phase="inference",
                ),
            )
        else:
            current_revision = (
                str(current_revision) if current_revision is not None else None
            )
            if current_revision is None or observation.revision is None:
                observation = _with_target_diagnostic(
                    observation,
                    Diagnostic(
                        "INFER_TARGET_REVISION_UNKNOWN",
                        Severity.ERROR,
                        "Target revision is missing; publication cannot be fenced",
                        phase="inference",
                    ),
                )
            elif current_revision != observation.revision:
                observation = _with_target_diagnostic(
                    observation,
                    Diagnostic(
                        "INFER_TARGET_STALE",
                        Severity.ERROR,
                        "Target revision changed after schema inspection",
                        phase="inference",
                    ),
                )
    if expected_revision is not None and observation.revision != expected_revision:
        observation = TargetObservation(
            observation.schema,
            observation.exists,
            observation.revision,
            observation.inspector,
            (
                *observation.diagnostics,
                Diagnostic(
                    "INFER_TARGET_STALE",
                    Severity.ERROR,
                    "Inspected target revision does not match expected revision",
                    phase="inference",
                ),
            ),
            observation.metadata,
        )
    result = _backfill_observation(source, observation)
    if retain_rows:
        return result
    return InferenceResult(
        result.schema,
        result.diagnostics,
        result.evidence,
        {**result.provenance, "retained_rows": False},
        (),
        result.replay,
        result.observed_schema,
        result.target_hypothesis,
        result.target_observation,
    )


def _backfill_observation(
    source: InferenceResult, observation: TargetObservation
) -> InferenceResult:
    if observation.exists != "present":
        state = observation.exists
        code = "INFER_TARGET_ABSENT" if state == "absent" else "INFER_TARGET_UNKNOWN"
        return InferenceResult(
            source.schema,
            tuple(source.diagnostics)
            + tuple(observation.diagnostics)
            + (
                Diagnostic(
                    code,
                    Severity.ERROR,
                    (
                        "Target is absent; target constraints were not applied"
                        if state == "absent"
                        else "Target existence is unknown; target constraints were not applied"
                    ),
                    phase="inference",
                ),
            ),
            source.evidence,
            {
                **source.provenance,
                "target_exists": state,
                "target_validation": "not_performed",
            },
            source.rows,
            source.replay,
            source.observed_schema,
            source.target_hypothesis,
            observation,
        )
    # Any target-side diagnostic means the target state is not qualified for
    # constraint propagation.  A warning is still a provider assertion that
    # the inspected schema may be incomplete or stale, so accepting it would
    # turn partial target evidence into a durable source fact.
    if observation.diagnostics:
        return InferenceResult(
            source.schema,
            tuple(source.diagnostics) + tuple(observation.diagnostics),
            source.evidence,
            {
                **source.provenance,
                "target_exists": observation.exists,
                "target_validation": "failed",
            },
            source.rows,
            source.replay,
            source.observed_schema,
            source.target_hypothesis,
            observation,
        )
    inspection_errors = tuple(
        diagnostic
        for diagnostic in observation.diagnostics
        if getattr(
            getattr(diagnostic, "severity", None),
            "value",
            getattr(diagnostic, "severity", None),
        )
        == Severity.ERROR.value
        or (
            isinstance(diagnostic, Mapping)
            and str(diagnostic.get("severity", "")).lower() == "error"
        )
    )
    if inspection_errors:
        return InferenceResult(
            source.schema,
            tuple(source.diagnostics) + tuple(observation.diagnostics),
            source.evidence,
            {
                **source.provenance,
                "target_exists": observation.exists,
                "target_validation": "failed",
            },
            source.rows,
            source.replay,
            source.observed_schema,
            source.target_hypothesis,
            observation,
        )
    if any(
        getattr(diagnostic, "code", None) == "INFER_TARGET_STALE"
        or (
            isinstance(diagnostic, Mapping)
            and diagnostic.get("code") == "INFER_TARGET_STALE"
        )
        for diagnostic in observation.diagnostics
    ):
        return InferenceResult(
            source.schema,
            tuple(source.diagnostics) + tuple(observation.diagnostics),
            source.evidence,
            {
                **source.provenance,
                "target_exists": observation.exists,
                "target_validation": "stale",
            },
            source.rows,
            source.replay,
            source.observed_schema,
            source.target_hypothesis,
            observation,
        )
    if observation.schema is None:
        return InferenceResult(
            source.schema,
            tuple(source.diagnostics) + tuple(observation.diagnostics),
            source.evidence,
            {
                **source.provenance,
                "target_exists": observation.exists,
                "target_validation": "not_performed",
            },
            source.rows,
            source.replay,
            source.observed_schema,
            source.target_hypothesis,
            observation,
        )
    backfilled = backfill_schema(source.schema, observation.schema)
    rows = list(source.rows)
    runtime_diagnostics: list[Diagnostic] = []
    failed_fields: set[str] = set()
    if rows:
        source_fields = {field.name: field for field in source.schema.fields}
        target_fields = {field.name: field for field in observation.schema.fields}
        for row in rows:
            for name, value in list(row.items()):
                source_field = source_fields.get(name)
                target_field = target_fields.get(name)
                if source_field is None or target_field is None or value is None:
                    continue
                if source_field.logical_type == target_field.logical_type:
                    continue
                if (
                    source_field.logical_type,
                    target_field.logical_type,
                ) not in _LOSSLESS_CASTS:
                    failed_fields.add(name)
                    runtime_diagnostics.append(
                        Diagnostic(
                            "INFER_RUNTIME_CONVERSION",
                            Severity.ERROR,
                            f"Field {name!r} cannot be safely converted to {target_field.logical_type!r}",
                            path=(name,),
                            phase="inference",
                        )
                    )
                    continue
                try:
                    row[name] = _coerce_value(value, target_field.logical_type)
                except (TypeError, ValueError, OverflowError, DecimalException):
                    failed_fields.add(name)
                    runtime_diagnostics.append(
                        Diagnostic(
                            "INFER_RUNTIME_CONVERSION",
                            Severity.ERROR,
                            f"Field {name!r} could not be converted to {target_field.logical_type!r}",
                            path=(name,),
                            phase="inference",
                        )
                    )
    resolved_schema = backfilled.schema
    cast_fields = {
        source_field.name: target_field.logical_type
        for source_field in source.schema.fields
        for target_field in observation.schema.fields
        if target_field.name == source_field.name
        and target_field.logical_type != source_field.logical_type
        and (source_field.logical_type, target_field.logical_type) in _LOSSLESS_CASTS
    }
    if failed_fields:
        source_fields = {field.name: field for field in source.schema.fields}
        resolved_schema = NormalizedSchema(
            identity=backfilled.schema.identity,
            fields=tuple(
                source_fields.get(field.name, field)
                if field.name in failed_fields
                else field
                for field in backfilled.schema.fields
            ),
            metadata={
                **backfilled.schema.metadata,
                "runtime_conversion_failed": sorted(failed_fields),
            },
        )
    if rows:
        for field in resolved_schema.fields:
            if field.required and any(row.get(field.name) is None for row in rows):
                runtime_diagnostics.append(
                    Diagnostic(
                        "INFER_RUNTIME_EVALUATION",
                        Severity.ERROR,
                        f"Required field {field.name!r} evaluated to null",
                        path=(field.name,),
                        phase="inference",
                    )
                )
    replay = source.replay
    validation_state = "not_required"
    if cast_fields and rows and replay is None:
        validation_state = "complete"
    elif cast_fields and replay is not None:
        validation_state = "prefix_only"
    elif cast_fields:
        validation_state = "not_performed"
    if replay is not None:
        source_fields = {field.name: field for field in source.schema.fields}
        target_fields = {field.name: field for field in observation.schema.fields}

        def replay_convert(row: Any) -> Any:
            if not isinstance(row, Mapping):
                return row
            converted = dict(row)
            for name, value in list(converted.items()):
                source_field = source_fields.get(name)
                target_field = target_fields.get(name)
                if (
                    source_field is None
                    or target_field is None
                    or value is None
                    or source_field.logical_type == target_field.logical_type
                ):
                    continue
                if (
                    source_field.logical_type,
                    target_field.logical_type,
                ) not in _LOSSLESS_CASTS:
                    raise ValueError(
                        f"Field {name!r} cannot be safely converted to target type "
                        f"{target_field.logical_type!r}"
                    )
                try:
                    converted[name] = _coerce_value(value, target_field.logical_type)
                except (TypeError, ValueError, OverflowError, DecimalException):
                    raise ValueError(
                        f"Field {name!r} contains a value that cannot be converted "
                        f"to target type {target_field.logical_type!r}"
                    ) from None
            return converted

        replay = replay.map(replay_convert)
    all_diagnostics = (
        tuple(source.diagnostics)
        + tuple(backfilled.diagnostics)
        + tuple(observation.diagnostics)
        + tuple(runtime_diagnostics)
    )
    unique_diagnostics: list[Any] = []
    seen_diagnostics: set[tuple[Any, ...]] = set()
    for diagnostic in all_diagnostics:
        if isinstance(diagnostic, Diagnostic):
            key = (diagnostic.code, tuple(diagnostic.path), diagnostic.message)
        elif isinstance(diagnostic, Mapping):
            key = (
                diagnostic.get("code"),
                tuple(diagnostic.get("path", ())),
                diagnostic.get("message"),
            )
        else:
            key = (str(diagnostic),)
        if key in seen_diagnostics:
            continue
        seen_diagnostics.add(key)
        unique_diagnostics.append(diagnostic)
    max_diagnostics = int(
        source.provenance.get("limits", {}).get("max_diagnostics", 100)
        if isinstance(source.provenance.get("limits", {}), Mapping)
        else 100
    )
    return InferenceResult(
        resolved_schema,
        tuple(unique_diagnostics[: max(1, max_diagnostics)]),
        source.evidence,
        {
            **source.provenance,
            **backfilled.provenance,
            "target_exists": observation.exists,
            "target_validation": validation_state,
            "target_validation_fields": sorted(cast_fields),
        },
        tuple(rows),
        replay,
        source.observed_schema or source.schema,
        resolved_schema,
        observation,
    )


def _coerce_value(value: Any, logical_type: str) -> Any:
    if logical_type == "integer":
        if isinstance(value, bool):
            raise ValueError("boolean is not an integer value")
        if isinstance(value, float) and not value.is_integer():
            raise ValueError("integer conversion would lose the fractional part")
        if isinstance(value, Decimal) and value != value.to_integral_value():
            raise ValueError("integer conversion would lose the fractional part")
        return int(value)
    if logical_type == "number":
        converted = float(value)
        if not math.isfinite(converted):
            raise ValueError("number conversion produced a non-finite value")
        if isinstance(value, (Decimal, int)):
            if Decimal(str(converted)) != Decimal(value):
                raise ValueError("number conversion would lose precision")
        elif isinstance(value, str):
            try:
                original = Decimal(value.strip())
            except (ArithmeticError, ValueError):
                if not value.strip():
                    raise ValueError("invalid number spelling") from None
            else:
                if Decimal(str(converted)) != original:
                    raise ValueError("number conversion would lose precision")
        return converted
    if logical_type == "decimal":
        return value if isinstance(value, Decimal) else Decimal(str(value))
    if logical_type == "binary":
        if isinstance(value, bytes):
            return value
        if isinstance(value, str):
            return value.encode()
        return bytes(value)
    if logical_type == "boolean":
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes"}:
                return True
            if lowered in {"false", "0", "no"}:
                return False
            raise ValueError("invalid boolean spelling")
        return bool(value)
    if logical_type == "string":
        return str(value)
    if logical_type == "date":
        return (
            value if isinstance(value, _dt.date) else _dt.date.fromisoformat(str(value))
        )
    if logical_type == "datetime":
        return (
            value
            if isinstance(value, _dt.datetime)
            else _dt.datetime.fromisoformat(str(value))
        )
    raise TypeError(f"unsupported conversion to {logical_type}")


def backfill_schema(
    source: NormalizedSchema, target: NormalizedSchema
) -> InferenceResult:
    """Apply target constraints through qualified source lineage.

    The output schema records the target-compatible type for direct fields,
    while ``backward_constraints`` retains the observed source type and the
    qualified path used to derive the constraint.
    """
    try:
        target = _validated_normalized_schema(target)
    except (AttributeError, KeyError, TypeError, ValueError):
        return InferenceResult(
            source,
            (
                Diagnostic(
                    "INFER_TARGET_UNSUPPORTED",
                    Severity.ERROR,
                    "Target fields are malformed; backward constraints were not applied",
                    phase="inference",
                ),
            ),
            provenance={
                "source": "target_backfill",
                "target_validation": "failed",
            },
            observed_schema=source,
            target_hypothesis=source,
        )
    unknown_type_diagnostics = _unknown_type_diagnostics(target)
    if unknown_type_diagnostics:
        return InferenceResult(
            source,
            unknown_type_diagnostics,
            provenance={
                "source": "target_backfill",
                "target_validation": "failed",
            },
            observed_schema=source,
            target_hypothesis=source,
        )
    target_fields = {field.name: field for field in target.fields}
    fields: list[NormalizedField] = []
    diagnostics: list[Diagnostic] = []
    conditional_casts: dict[str, str] = {}
    field_constraints: list[dict[str, Any]] = [
        dict(item)
        for item in source.metadata.get("field_constraints", ())
        if isinstance(item, Mapping)
    ]
    lineage = source.metadata.get("lineage", {})
    backward_constraints = dict(source.metadata.get("backward_constraints", {}))
    explanations: list[dict[str, Any]] = []
    for source_field in source.fields:
        target_field = target_fields.get(source_field.name)
        if target_field is None:
            fields.append(source_field)
            continue
        if target_field.required and not source_field.required:
            diagnostics.append(
                Diagnostic(
                    "INFER_TARGET_CONFLICT",
                    Severity.ERROR,
                    f"Target field {target_field.name!r} is required but source may omit it",
                    path=(target_field.name,),
                    phase="inference",
                )
            )
        if not target_field.nullable and source_field.nullable:
            diagnostics.append(
                Diagnostic(
                    "INFER_TARGET_CONFLICT",
                    Severity.ERROR,
                    f"Target field {target_field.name!r} is non-nullable but source may contain nulls",
                    path=(target_field.name,),
                    phase="inference",
                )
            )
        if source_field.logical_type != target_field.logical_type:
            lineage_entry = (
                lineage.get(source_field.name) if isinstance(lineage, Mapping) else None
            )
            source_fields = (
                tuple(lineage_entry.get("source_fields", ()))
                if isinstance(lineage_entry, Mapping)
                else (source_field.name,)
            )
            invertible = bool(
                lineage_entry.get("invertible", True)
                if isinstance(lineage_entry, Mapping)
                else True
            )
            qualified_source_fields = (
                tuple(lineage_entry.get("qualified_source_fields", ()))
                if isinstance(lineage_entry, Mapping)
                else (f"{source.identity}.{source_field.name}",)
            )
            if len(source_fields) != 1 or not invertible:
                backward_constraints[source_field.name] = {
                    "target_type": target_field.logical_type,
                    "source_fields": list(source_fields),
                    "qualified_source_fields": list(qualified_source_fields),
                    "operations": list(
                        lineage_entry.get("operations", ())
                        if isinstance(lineage_entry, Mapping)
                        else ()
                    ),
                    "status": "blocked",
                }
                diagnostics.append(
                    Diagnostic(
                        "INFER_BACKWARD_UNSUPPORTED",
                        Severity.WARNING,
                        f"Target type for derived field {source_field.name!r} cannot be propagated to its source",
                        path=(source_field.name,),
                        phase="inference",
                    )
                )
                fields.append(
                    NormalizedField(
                        source_field.name,
                        source_field.logical_type,
                        source_field.required,
                        source_field.nullable,
                        {**source_field.metadata, "backfill_blocked": True},
                    )
                )
                explanations.append(
                    {
                        "field": source_field.name,
                        "status": "blocked",
                        "target_type": target_field.logical_type,
                        "source_fields": list(source_fields),
                        "qualified_source_fields": list(qualified_source_fields),
                    }
                )
                continue
            compatible = (source_field.logical_type, target_field.logical_type) in {
                ("string", "integer"),
                ("string", "number"),
                ("string", "decimal"),
                ("integer", "number"),
                ("integer", "decimal"),
                ("decimal", "number"),
                ("decimal", "decimal"),
                ("date", "datetime"),
            }
            if not compatible:
                prior = backward_constraints.get(source_field.name)
                prior_types: set[str] = set()
                if isinstance(prior, Mapping):
                    if prior.get("target_type") is not None:
                        prior_types.add(str(prior["target_type"]))
                    prior_types.update(
                        str(item.get("target_type"))
                        for item in prior.get("constraints", ())
                        if isinstance(item, Mapping)
                        and item.get("target_type") is not None
                    )
                if prior_types and target_field.logical_type not in prior_types:
                    backward_constraints[source_field.name] = {
                        "constraints": [
                            prior,
                            {
                                "target_type": target_field.logical_type,
                                "observed_type": source_field.metadata.get(
                                    "observed_type", source_field.logical_type
                                ),
                                "qualified_source_fields": list(
                                    qualified_source_fields
                                ),
                                "status": "conflict",
                            },
                        ]
                    }
                diagnostics.append(
                    Diagnostic(
                        "INFER_BACKWARD_CONFLICT",
                        Severity.WARNING,
                        f"Source field {source_field.name!r} conflicts with target type {target_field.logical_type!r}",
                        path=(source_field.name,),
                        phase="inference",
                    )
                )
                fields.append(
                    NormalizedField(
                        source_field.name,
                        source_field.logical_type,
                        source_field.required,
                        source_field.nullable,
                        {**source_field.metadata, "backfill_conflict": True},
                    )
                )
                continue
            else:
                conditional_casts[source_field.name] = target_field.logical_type
                for source_name in source_fields:
                    field_constraints.append(
                        FieldConstraint(
                            source_name,
                            target_field.logical_type,
                            source="target",
                            confidence=1.0 if invertible else 0.0,
                            path=tuple(
                                str(item)
                                for item in (
                                    lineage_entry.get("operations", ())
                                    if isinstance(lineage_entry, Mapping)
                                    else ()
                                )
                            ),
                        ).to_dict()
                    )
                    constraint = {
                        "target_type": target_field.logical_type,
                        "observed_type": source_field.metadata.get(
                            "observed_type", source_field.logical_type
                        ),
                        "output_field": source_field.name,
                        "source_fields": [source_name],
                        "qualified_source_fields": list(qualified_source_fields),
                        "operations": list(
                            lineage_entry.get("operations", ())
                            if isinstance(lineage_entry, Mapping)
                            else ()
                        ),
                        "status": "conditional",
                    }
                    previous = backward_constraints.get(source_name)
                    previous_types: set[str] = set()
                    if isinstance(previous, Mapping):
                        if previous.get("target_type") is not None:
                            previous_types.add(str(previous["target_type"]))
                        previous_types.update(
                            str(item.get("target_type"))
                            for item in previous.get("constraints", ())
                            if isinstance(item, Mapping)
                            and item.get("target_type") is not None
                        )
                    if (
                        previous_types
                        and target_field.logical_type not in previous_types
                    ):
                        diagnostics.append(
                            Diagnostic(
                                "INFER_BACKWARD_CONFLICT",
                                Severity.ERROR,
                                f"Conflicting target constraints for source field {source_name!r}",
                                path=(source_name,),
                                phase="inference",
                            )
                        )
                        constraint["status"] = "conflict"
                        backward_constraints[source_name] = {
                            "constraints": [previous, constraint]
                        }
                    else:
                        backward_constraints[source_name] = constraint
                explanations.append(
                    {
                        "field": source_field.name,
                        "status": "constrained",
                        "observed_type": source_field.logical_type,
                        "target_type": target_field.logical_type,
                        "source_fields": list(source_fields),
                        "qualified_source_fields": list(qualified_source_fields),
                    }
                )
                diagnostics.append(
                    Diagnostic(
                        "INFER_TARGET_CONFLICT",
                        Severity.INFO,
                        f"Target type {target_field.logical_type!r} constrained source field {source_field.name!r}",
                        path=(source_field.name,),
                        phase="inference",
                    )
                )
            fields.append(
                NormalizedField(
                    source_field.name,
                    target_field.logical_type,
                    source_field.required,
                    source_field.nullable,
                    {
                        **source_field.metadata,
                        "backfilled_from_target": True,
                        "observed_type": source_field.logical_type,
                    },
                )
            )
            continue
        else:
            fields.append(source_field)
            explanations.append(
                {
                    "field": source_field.name,
                    "status": "observed",
                    "observed_type": source_field.logical_type,
                }
            )
    source_names = {field.name for field in source.fields}
    for target_field in target.fields:
        if target_field.name in source_names or not target_field.required:
            continue
        if any(
            target_field.metadata.get(key)
            for key in (
                "default",
                "has_default",
                "generated",
                "identity",
                "auto_increment",
            )
        ):
            continue
        diagnostics.append(
            Diagnostic(
                "INFER_TARGET_CONFLICT",
                Severity.ERROR,
                f"Required target field {target_field.name!r} is absent from source schema",
                path=(target_field.name,),
                phase="inference",
            )
        )
    schema = NormalizedSchema(
        identity=source.identity,
        fields=tuple(fields),
        metadata={
            **source.metadata,
            "target_backfilled": target.identity,
            "conditional_casts": conditional_casts,
            "backward_constraints": backward_constraints,
            "field_constraints": field_constraints,
            "backfill_explanations": explanations,
            "observed_schema_fingerprint": source.fingerprint(),
        },
    )
    return InferenceResult(
        schema,
        tuple(diagnostics),
        provenance={
            "source": "target_backfill",
            "target_fingerprint": target.fingerprint(),
        },
        observed_schema=source,
        target_hypothesis=schema,
    )


def solve_backward_constraints(
    source: NormalizedSchema,
    targets: Any,
    *,
    max_iterations: int = 8,
) -> InferenceResult:
    """Solve bounded target constraints to a fixed point.

    ``targets`` may contain normalized schemas or ``TargetObservation``
    instances. Each pass preserves the prior diagnostics and stops when the
    schema and constraint payload stabilize. A changing cycle is reported as
    nonconvergent instead of returning an arbitrary final type.
    """
    current = InferenceResult(source)
    target_items = (
        tuple(targets)
        if not isinstance(targets, (NormalizedSchema, TargetObservation))
        else (targets,)
    )
    observations: list[TargetObservation] = []
    for item in target_items:
        if isinstance(item, TargetObservation):
            observations.append(_normalize_target_observation(item))
            continue
        try:
            schema = _validated_normalized_schema(item)
        except (AttributeError, KeyError, TypeError, ValueError):
            identity = getattr(item, "identity", "target")
            observations.append(
                _unknown_target(
                    "INFER_TARGET_UNSUPPORTED",
                    identity=identity,
                    inspector="provided",
                    message="Target fields are malformed",
                )
            )
            continue
        observations.append(
            TargetObservation(
                schema,
                "present",
                None,
                "provided",
                _unknown_type_diagnostics(schema),
            )
        )
    seen: set[tuple[str, str]] = set()
    all_diagnostics: list[Any] = []
    for _iteration in range(max(1, max_iterations)):
        before = (
            current.schema.fingerprint(),
            repr(current.schema.metadata.get("backward_constraints", {})),
        )
        if before in seen:
            all_diagnostics.append(
                Diagnostic(
                    "INFER_BACKWARD_NONCONVERGENT",
                    Severity.ERROR,
                    "Backward target constraints did not converge",
                    phase="inference",
                )
            )
            break
        seen.add(before)
        changed = False
        for observation in observations:
            result = _backfill_observation(current, observation)
            all_diagnostics.extend(result.diagnostics)
            changed = changed or result.schema != current.schema
            current = result
        after = (
            current.schema.fingerprint(),
            repr(current.schema.metadata.get("backward_constraints", {})),
        )
        if not changed or after == before:
            break
    else:
        all_diagnostics.append(
            Diagnostic(
                "INFER_BACKWARD_NONCONVERGENT",
                Severity.ERROR,
                f"Backward target constraints exceeded {max_iterations} iterations",
                phase="inference",
            )
        )
    unique: list[Any] = []
    keys: set[tuple[str, tuple[str, ...], str]] = set()
    for diagnostic in all_diagnostics:
        key = (
            getattr(diagnostic, "code", str(diagnostic)),
            tuple(getattr(diagnostic, "path", ())),
            getattr(diagnostic, "message", str(diagnostic)),
        )
        if key not in keys:
            keys.add(key)
            unique.append(diagnostic)
    return current.replace(diagnostics=tuple(unique))


def check_write_compatibility(
    source: NormalizedSchema,
    target: NormalizedSchema | TargetObservation,
    *,
    mode: str = "append",
    expected_revision: str | None = None,
) -> WriteCompatibility:
    """Check a source against every target field and target constraint."""
    target_observation = target if isinstance(target, TargetObservation) else None
    observation_metadata: dict[str, Any] = {}
    observed_revision: str | None = None
    target_schema = (
        target_observation.schema if target_observation is not None else target
    )
    if target_schema is not None:
        try:
            target_schema = _validated_normalized_schema(target_schema)
        except (AttributeError, KeyError, TypeError, ValueError):
            diagnostics = (
                tuple(target_observation.diagnostics)
                if target_observation is not None
                else ()
            )
            return WriteCompatibility(
                False,
                mode=mode,
                diagnostics=(
                    *diagnostics,
                    Diagnostic(
                        "INFER_TARGET_UNSUPPORTED",
                        Severity.ERROR,
                        "Target fields are malformed",
                        phase="inference",
                    ),
                ),
            )
        unknown_type_diagnostics = _unknown_type_diagnostics(target_schema)
        if unknown_type_diagnostics:
            diagnostics = (
                tuple(target_observation.diagnostics)
                if target_observation is not None
                else ()
            )
            return WriteCompatibility(
                False,
                mode=mode,
                diagnostics=(*diagnostics, *unknown_type_diagnostics),
            )
        target = target_schema
    if target_observation is not None:
        if target_observation.exists != "present":
            state = target_observation.exists
            diagnostics = list(target_observation.diagnostics)
            diagnostics.append(
                Diagnostic(
                    "INFER_TARGET_ABSENT"
                    if state == "absent"
                    else "INFER_TARGET_UNKNOWN",
                    Severity.ERROR,
                    (
                        "Target is absent; compatibility is not qualified"
                        if state == "absent"
                        else "Target existence is unknown; compatibility is not qualified"
                    ),
                    phase="inference",
                )
            )
            return WriteCompatibility(
                False,
                mode=mode,
                diagnostics=tuple(diagnostics),
            )
        # A schema accompanied by an inspector error is not a qualified
        # observation.  Do not let a useful-looking partial payload turn into
        # a proven write result.
        if target_observation.diagnostics:
            return WriteCompatibility(
                False,
                mode=mode,
                diagnostics=(
                    *target_observation.diagnostics,
                    Diagnostic(
                        "INFER_TARGET_UNKNOWN",
                        Severity.ERROR,
                        "Target inspection reported diagnostics; compatibility is unqualified",
                        phase="inference",
                    ),
                ),
            )
        inspector_errors = tuple(
            diagnostic
            for diagnostic in target_observation.diagnostics
            if getattr(
                getattr(diagnostic, "severity", None),
                "value",
                getattr(diagnostic, "severity", None),
            )
            == Severity.ERROR.value
            or (
                isinstance(diagnostic, Mapping)
                and str(diagnostic.get("severity", "")).lower() == "error"
            )
        )
        if inspector_errors:
            return WriteCompatibility(
                False,
                mode=mode,
                diagnostics=(
                    *target_observation.diagnostics,
                    Diagnostic(
                        "INFER_TARGET_UNKNOWN",
                        Severity.ERROR,
                        "Target inspection reported an error; compatibility is unqualified",
                        phase="inference",
                    ),
                ),
            )
        if target_observation.schema is None:
            return WriteCompatibility(
                False,
                mode=mode,
                diagnostics=(
                    *target_observation.diagnostics,
                    Diagnostic(
                        "INFER_TARGET_UNKNOWN",
                        Severity.ERROR,
                        "Target has no normalized schema for compatibility checking",
                        phase="inference",
                    ),
                ),
            )
        if not isinstance(target_observation.metadata, Mapping):
            return WriteCompatibility(
                False,
                mode=mode,
                diagnostics=(
                    *target_observation.diagnostics,
                    Diagnostic(
                        "INFER_TARGET_UNSUPPORTED",
                        Severity.ERROR,
                        "Target observation metadata is malformed",
                        phase="inference",
                    ),
                ),
            )
        target = target_schema
        observation_metadata = dict(target_observation.metadata)
        observed_revision = target_observation.revision
    assert isinstance(target, NormalizedSchema)
    target_metadata = {**target.metadata, **observation_metadata}
    source_fields = {field.name: field for field in source.fields}
    target_fields = {field.name: field for field in target.fields}
    casts: dict[str, str] = {}
    incompatible: list[str] = []
    diagnostics: list[Diagnostic] = []
    modes = {"append", "overwrite", "merge", "upsert", "partition_replace"}
    if mode not in modes:
        diagnostics.append(
            Diagnostic(
                "INFER_WRITE_MODE_UNSUPPORTED",
                Severity.ERROR,
                f"Write mode {mode!r} is not supported by inference",
                phase="inference",
            )
        )
    target_revision = observed_revision or target_metadata.get("revision")
    if expected_revision is not None and target_revision != expected_revision:
        diagnostics.append(
            Diagnostic(
                "INFER_TARGET_STALE",
                Severity.ERROR,
                "Target revision changed before compatibility checking",
                phase="inference",
            )
        )
    widening = _LOSSLESS_CASTS
    for field in source.fields:
        target_field = target_fields.get(field.name)
        if target_field is None:
            incompatible.append(field.name)
            diagnostics.append(
                Diagnostic(
                    "INFER_WRITE_INCOMPATIBLE",
                    Severity.ERROR,
                    f"Source field {field.name!r} is not present in target schema",
                    path=(field.name,),
                    phase="inference",
                )
            )
            continue
        if target_field.required and not field.required:
            incompatible.append(field.name)
            diagnostics.append(
                Diagnostic(
                    "INFER_WRITE_INCOMPATIBLE",
                    Severity.ERROR,
                    f"Source field {field.name!r} may be missing from required target field",
                    path=(field.name,),
                    phase="inference",
                )
            )
            continue
        if field.nullable and not target_field.nullable:
            incompatible.append(field.name)
            diagnostics.append(
                Diagnostic(
                    "INFER_WRITE_INCOMPATIBLE",
                    Severity.ERROR,
                    f"Source field {field.name!r} may contain nulls for a non-nullable target field",
                    path=(field.name,),
                    phase="inference",
                )
            )
            continue
        if field.logical_type != target_field.logical_type:
            if (field.logical_type, target_field.logical_type) in widening:
                casts[field.name] = target_field.logical_type
            else:
                incompatible.append(field.name)
                diagnostics.append(
                    Diagnostic(
                        "INFER_WRITE_INCOMPATIBLE",
                        Severity.ERROR,
                        f"Field {field.name!r} cannot be written as {target_field.logical_type}",
                        path=(field.name,),
                        phase="inference",
                    )
                )
    for field in target.fields:
        if field.name in source_fields or not field.required:
            continue
        metadata = field.metadata
        if any(
            metadata.get(key)
            for key in (
                "default",
                "has_default",
                "generated",
                "identity",
                "auto_increment",
            )
        ):
            continue
        incompatible.append(field.name)
        diagnostics.append(
            Diagnostic(
                "INFER_WRITE_INCOMPATIBLE",
                Severity.ERROR,
                f"Required target field {field.name!r} is absent from source schema",
                path=(field.name,),
                phase="inference",
            )
        )
    # Merge/upsert operations need stable keys; partition replacement needs a
    # complete partition predicate. Providers may declare capabilities in
    # target metadata, and absent declarations fail closed for these modes.
    if mode in {"merge", "upsert"}:
        keys = target_metadata.get("keys")
        if not isinstance(keys, (list, tuple)):
            keys = [
                field.name
                for field in target.fields
                if field.metadata.get("key") or field.metadata.get("primary_key")
            ]
        missing_keys = [key for key in keys if key not in source_fields]
        if not keys or missing_keys:
            incompatible.extend(str(key) for key in missing_keys or ["<keys>"])
            diagnostics.append(
                Diagnostic(
                    "INFER_WRITE_INCOMPATIBLE",
                    Severity.ERROR,
                    "Merge/upsert requires source fields for every target key",
                    phase="inference",
                )
            )
    if mode == "partition_replace":
        partitions = target_metadata.get("partitions")
        if not isinstance(partitions, (list, tuple)):
            partitions = [
                field.name for field in target.fields if field.metadata.get("partition")
            ]
        missing_partitions = [name for name in partitions if name not in source_fields]
        if not partitions or missing_partitions:
            incompatible.extend(
                str(name) for name in missing_partitions or ["<partitions>"]
            )
            diagnostics.append(
                Diagnostic(
                    "INFER_WRITE_INCOMPATIBLE",
                    Severity.ERROR,
                    "Partition replacement requires source partition fields",
                    phase="inference",
                )
            )
    capabilities = target_metadata.get("capabilities")
    supported_modes: Any = None
    if isinstance(capabilities, Mapping):
        supported_modes = capabilities.get("write_modes", capabilities.get("modes"))
        if (
            not isinstance(supported_modes, (list, tuple, set))
            or mode not in supported_modes
        ):
            diagnostics.append(
                Diagnostic(
                    "INFER_WRITE_MODE_UNSUPPORTED",
                    Severity.ERROR,
                    f"Target does not advertise write mode {mode!r}",
                    phase="inference",
                )
            )
    elif isinstance(capabilities, (list, tuple, set)):
        supported_modes = capabilities
        if mode not in capabilities:
            diagnostics.append(
                Diagnostic(
                    "INFER_WRITE_MODE_UNSUPPORTED",
                    Severity.ERROR,
                    f"Target does not advertise write mode {mode!r}",
                    phase="inference",
                )
            )
    elif target_observation is not None:
        # Existing targets are qualified only when their adapter explicitly
        # advertises the requested operation.  Plain NormalizedSchema values
        # retain the legacy append behavior for class-authored contracts.
        diagnostics.append(
            Diagnostic(
                "INFER_WRITE_MODE_UNSUPPORTED",
                Severity.ERROR,
                f"Target does not advertise write mode {mode!r}",
                phase="inference",
            )
        )
    obligations_list: list[dict[str, Any]] = []
    for name, target_type in sorted(casts.items()):
        obligation = {
            "field": name,
            "cast": target_type,
            "validation": "all_values",
            "on_failure": "error",
        }
        if target_type == "number":
            obligation["precision_policy"] = "lossless_or_error"
        obligations_list.append(obligation)
    obligations = tuple(obligations_list)
    return WriteCompatibility(
        not incompatible
        and mode in modes
        and not any(
            diagnostic.severity == Severity.ERROR for diagnostic in diagnostics
        ),
        casts,
        tuple(incompatible),
        tuple(diagnostics),
        obligations,
        mode,
    )
