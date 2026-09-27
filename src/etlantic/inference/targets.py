# pyright: reportPrivateUsage=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnnecessaryIsInstance=false
"""Target inspection, compatibility, and backward schema propagation."""

from __future__ import annotations

import hashlib
import inspect as _inspect
import json
import math
import re
import stat as _stat
from collections import OrderedDict
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from decimal import DecimalException
from pathlib import Path
from threading import Lock
from typing import Any, cast
from urllib.parse import unquote, urlsplit

from etlantic.diagnostics import Diagnostic, Severity
from etlantic.schema_drift import (
    NormalizedField,
    NormalizedSchema,
    normalize_logical_type,
    normalize_schema_from_fields,
)
from etlantic.transform.evaluation import coerce_value

from .durable import _safe_file_identity
from .records import infer_csv, infer_json, infer_records
from .types import (
    TARGET_EXISTENCE_STATES,
    FieldConstraint,
    InferenceLimits,
    InferenceReplayError,
    InferenceResult,
    TargetObservation,
    WriteCompatibility,
    _ReplayLifecycle,
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
_TARGET_IDENTITY_KEYS = frozenset(
    {"identity", "target_identity", "target_id", "resource_id"}
)
_TARGET_BINDING_KEYS = frozenset(
    {
        "bucket",
        "catalog",
        "database",
        "key",
        "location",
        "name",
        "namespace",
        "path",
        "provider",
        "resource",
        "schema",
        "table",
        "target",
        "uri",
        "url",
    }
)
_TARGET_URI = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")
_TARGET_BINDING_NESTED_KEYS = frozenset({"binding", "resource", "target"})
_TARGET_BINDING_ADDRESS_KEYS = _TARGET_BINDING_KEYS - {"provider"}
# Cache only fingerprints, never raw bindings, for process-local collision checks.
_TARGET_IDENTITY_BINDINGS: OrderedDict[str, str] = OrderedDict()
_TARGET_IDENTITY_BINDINGS_LOCK = Lock()
_TARGET_IDENTITY_BINDINGS_LIMIT = 4096


class _TargetIdentityCollision(ValueError):
    def __init__(self, identity: str) -> None:
        super().__init__(identity)
        self.identity = identity


def _identity_diagnostic(code: str, message: str) -> Diagnostic:
    return Diagnostic(
        code,
        Severity.ERROR,
        message,
        phase="inference",
    )


def _register_target_identity(identity: str, binding_fingerprint: str | None) -> None:
    """Reject reuse of one identity for a different observed binding."""
    if binding_fingerprint is None:
        return
    with _TARGET_IDENTITY_BINDINGS_LOCK:
        previous = _TARGET_IDENTITY_BINDINGS.get(identity)
        if previous is not None and previous != binding_fingerprint:
            raise _TargetIdentityCollision(identity)
        _TARGET_IDENTITY_BINDINGS[identity] = binding_fingerprint
        _TARGET_IDENTITY_BINDINGS.move_to_end(identity)
        if len(_TARGET_IDENTITY_BINDINGS) > _TARGET_IDENTITY_BINDINGS_LIMIT:
            _TARGET_IDENTITY_BINDINGS.popitem(last=False)


def _target_binding_value(key: str, value: Any) -> str | int | float | bool | None:
    """Normalize one allowlisted binding component for identity hashing."""
    if isinstance(value, Path):
        try:
            return str(value.expanduser().resolve())
        except (OSError, RuntimeError, ValueError):
            return None
    if isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if _TARGET_URI.match(text):
        try:
            parsed = urlsplit(text)
        except ValueError:
            return None
        host = (parsed.hostname or "").lower()
        try:
            port = parsed.port
        except ValueError:
            return None
        if port is not None:
            host = f"{host}:{port}"
        # Credentials, query parameters, and fragments are intentionally
        # omitted. The scheme, host, and resource path identify the binding.
        return f"{parsed.scheme.lower()}://{host}{unquote(parsed.path)}"
    if key in {"location", "path", "uri", "url"} or text.startswith(
        ("/", "~/", "./", "../")
    ):
        try:
            return str(Path(text).expanduser().resolve())
        except (OSError, RuntimeError, ValueError):
            return None
    return text


def _target_binding_fingerprint(binding: Mapping[str, Any]) -> str | None:
    """Hash only stable, non-secret address fields from a target binding."""
    normalized: dict[str, str | int | float | bool] = {}
    has_address = False

    def collect(values: Mapping[str, Any], *, prefix: str = "", depth: int = 0) -> None:
        nonlocal has_address
        if depth > 4:
            return
        try:
            items = cast(Any, values.items())
            for raw_key, value in items:
                key = str(raw_key).casefold().replace("-", "_")
                if (
                    key not in _TARGET_BINDING_KEYS
                    and key not in _TARGET_BINDING_NESTED_KEYS
                ):
                    continue
                qualified_key = f"{prefix}{key}"
                normalized_value = _target_binding_value(key, value)
                if normalized_value is not None:
                    normalized[qualified_key] = normalized_value
                    if key in _TARGET_BINDING_ADDRESS_KEYS:
                        has_address = True
                elif key in _TARGET_BINDING_NESTED_KEYS and isinstance(value, Mapping):
                    collect(
                        cast(Mapping[str, Any], value),
                        prefix=f"{qualified_key}.",
                        depth=depth + 1,
                    )
        except Exception:
            return

    collect(binding)
    if not normalized or not has_address:
        return None
    encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:20]
    return f"target:{digest}"


def _safe_target_identity(identity: str) -> str:
    """Return a wire-safe identity without exposing arbitrary URI contents."""
    value = str(identity).strip()
    if not value:
        return value
    if _TARGET_URI.match(value):
        normalized = _target_binding_value("uri", value)
        if normalized is not None:
            fingerprint = _target_binding_fingerprint({"uri": normalized})
            if fingerprint is not None:
                return fingerprint
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]
        return f"target:{digest}"
    return _safe_file_identity(value)


def _explicit_binding_identity(binding: Mapping[str, Any]) -> str | None:
    """Return a caller/provider identity carried by a bounded binding map."""
    for key in ("identity", "target_identity", "target_id", "resource_id"):
        try:
            value = binding.get(key)
        except Exception:
            value = None
        if isinstance(value, str) and value.strip():
            return _safe_target_identity(value.strip())
    for key in ("binding", "resource", "target"):
        try:
            nested = binding.get(key)
        except Exception:
            nested = None
        if isinstance(nested, Mapping):
            nested_mapping = cast(Mapping[str, Any], nested)
            for nested_key in (
                "identity",
                "target_identity",
                "target_id",
                "resource_id",
            ):
                try:
                    value = nested_mapping.get(nested_key)
                except Exception:
                    value = None
                if isinstance(value, str) and value.strip():
                    return _safe_target_identity(value.strip())
    return None


def _target_binding_fingerprint_for_target(
    target: Any, binding: Mapping[str, Any] | None = None
) -> str | None:
    if binding is not None:
        fingerprint = _target_binding_fingerprint(binding)
        if fingerprint is not None:
            return fingerprint

    if isinstance(target, Path):
        return _target_binding_fingerprint({"path": target})
    if isinstance(target, str):
        if _TARGET_URI.match(target):
            try:
                parsed = urlsplit(target)
            except ValueError:
                return None
            if parsed.scheme.casefold() == "file" and parsed.netloc.casefold() in {
                "",
                "localhost",
            }:
                return _target_binding_fingerprint({"path": Path(unquote(parsed.path))})
            return _target_binding_fingerprint({"uri": target})
        return _target_binding_fingerprint({"path": target})
    if isinstance(target, TargetObservation):
        return _target_binding_fingerprint(target.metadata)
    if isinstance(target, Mapping):
        target_mapping = cast(Mapping[str, Any], target)
        fingerprint = _target_binding_fingerprint(target_mapping)
        if fingerprint is not None:
            return fingerprint
        for key in _TARGET_BINDING_NESTED_KEYS:
            try:
                nested = target_mapping.get(key)
            except Exception:
                continue
            if isinstance(nested, Mapping):
                fingerprint = _target_binding_fingerprint(
                    cast(Mapping[str, Any], nested)
                )
                if fingerprint is not None:
                    return fingerprint
        return None
    try:
        nested = getattr(target, "binding", None)
    except Exception:
        nested = None
    if isinstance(nested, Mapping):
        fingerprint = _target_binding_fingerprint(cast(Mapping[str, Any], nested))
        if fingerprint is not None:
            return fingerprint
    attributes: dict[str, Any] = {}
    for key in _TARGET_BINDING_KEYS - {"schema"}:
        try:
            value = getattr(target, key, _MISSING)
        except Exception:
            continue
        if value is not _MISSING:
            attributes[key] = value
    return _target_binding_fingerprint(attributes)


def _target_identity(
    target: Any,
    identity: str | None = None,
    *,
    binding: Mapping[str, Any] | None = None,
) -> str | None:
    """Resolve a stable, privacy-preserving identity for an inspected target.

    Explicit caller or provider identities take precedence. Local paths and
    provider bindings without an explicit identity use a deterministic digest;
    raw paths, URI credentials, query strings, and fragments never enter the
    returned identity. Objects with no usable identity or binding stay
    unresolved instead of sharing a type-wide identity.
    """
    binding_fingerprint = _target_binding_fingerprint_for_target(target, binding)

    def accept(candidate: str) -> str:
        resolved = _safe_target_identity(candidate)
        _register_target_identity(resolved, binding_fingerprint)
        return resolved

    if identity is not None and str(identity).strip():
        return accept(str(identity).strip())
    if binding is not None:
        candidate_identity = _explicit_binding_identity(binding)
        if candidate_identity is not None:
            return accept(candidate_identity)

    if isinstance(target, TargetObservation):
        schema_identity = target.schema.identity if target.schema is not None else None
        metadata_identity = target.metadata.get("identity")
        if (
            isinstance(metadata_identity, str)
            and metadata_identity.strip()
            and metadata_identity.strip() not in {"target", "<path-redacted>"}
            and target.metadata.get("identity_unresolved") is not True
        ):
            return accept(metadata_identity.strip())
        if target.metadata.get("identity_unresolved") is not True:
            for candidate in (metadata_identity, schema_identity):
                if (
                    isinstance(candidate, str)
                    and candidate.strip()
                    and candidate.strip() not in {"target", "<path-redacted>"}
                ):
                    return accept(candidate.strip())

    if isinstance(target, NormalizedSchema):
        return (
            accept(target.identity)
            if target.identity.strip() not in {"target", "<path-redacted>"}
            else None
        )

    if isinstance(target, (str, Path)):
        text = str(target)
        if _TARGET_URI.match(text):
            try:
                parsed = urlsplit(text)
            except ValueError:
                parsed = None
            if (
                parsed is not None
                and parsed.scheme.casefold() == "file"
                and parsed.netloc.casefold() in {"", "localhost"}
                and binding_fingerprint is not None
            ):
                return accept(binding_fingerprint)
            normalized_uri = _target_binding_value("uri", text)
            if normalized_uri is not None:
                fingerprint = _target_binding_fingerprint({"uri": normalized_uri})
                if fingerprint is not None:
                    return accept(fingerprint)
        if binding_fingerprint is not None:
            return accept(binding_fingerprint)
        try:
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:20]
            return accept(f"target:{digest}")
        except (OSError, RuntimeError, ValueError):
            return None

    for key in ("identity", "target_identity", "target_id", "resource_id"):
        try:
            target_mapping = cast(Mapping[str, Any], target)
            candidate = (
                target_mapping.get(key, _MISSING)
                if isinstance(target, Mapping)
                else getattr(target, key, _MISSING)
            )
        except Exception:
            candidate = _MISSING
        if isinstance(candidate, str) and candidate.strip() not in {
            "target",
            "<path-redacted>",
        }:
            return accept(candidate.strip())

    if isinstance(target, Mapping):
        candidate_identity = _explicit_binding_identity(cast(Mapping[str, Any], target))
        if candidate_identity is not None:
            return accept(candidate_identity)
    else:
        try:
            attributes = vars(target)
        except (TypeError, AttributeError):
            attributes = {}
        schema = attributes.get("schema")
        if isinstance(schema, NormalizedSchema) and schema.identity.strip():
            return accept(schema.identity)
        try:
            nested = getattr(target, "binding", None)
        except Exception:
            nested = None
        if isinstance(nested, Mapping):
            candidate_identity = _explicit_binding_identity(
                cast(Mapping[str, Any], nested)
            )
            if candidate_identity is not None:
                return accept(candidate_identity)

    if binding_fingerprint is not None:
        return accept(binding_fingerprint)
    return None


def _unknown_target(
    code: str = "INFER_TARGET_UNKNOWN",
    *,
    identity: str = "target",
    inspector: str | None = None,
    message: str = "Target schema could not be inspected",
    metadata: Mapping[str, Any] | None = None,
) -> TargetObservation:
    safe_metadata = {
        "identity": _safe_target_identity(identity),
        **dict(metadata or {}),
    }
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
    identity = _safe_target_identity(identity)
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
        names: set[str] = {field.name for field in values}
        if any(not isinstance(name, str) or not name for name in names):
            raise ValueError("target field names must be non-empty strings")
        if len(names) != len(values):
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
    observation: TargetObservation, *, identity: str | None = None
) -> TargetObservation:
    """Validate schema fields carried by a provider-created observation."""
    try:
        resolved_identity = _target_identity(observation, identity)
    except _TargetIdentityCollision as collision:
        return _target_identity_collision_observation(
            collision.identity, inspector=observation.inspector
        )
    identity_missing = resolved_identity is None
    resolved_identity = resolved_identity or "target"
    metadata = dict(observation.metadata)
    if identity_missing:
        metadata.pop("identity", None)
        metadata["identity_unresolved"] = True
    else:
        metadata["identity"] = resolved_identity
        metadata.pop("identity_unresolved", None)
    diagnostics = observation.diagnostics
    if observation.schema is None:
        if observation.exists == "present":
            metadata.setdefault("empty", True)
        return TargetObservation(
            None,
            observation.exists,
            observation.revision,
            observation.inspector,
            diagnostics,
            metadata,
        )
    try:
        schema = _validated_normalized_schema(observation.schema)
    except (AttributeError, KeyError, TypeError, ValueError):
        diagnostics = (
            *diagnostics,
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
            metadata,
        )
    schema = NormalizedSchema(resolved_identity, schema.fields, schema.metadata)
    metadata["empty"] = not bool(schema.fields)
    schema_metadata = metadata
    if identity_missing:
        # The unresolved marker belongs to the observation envelope. Keeping it
        # in schema metadata makes a second normalization change the value and
        # breaks observation round trips.
        schema_metadata = dict(metadata)
        schema_metadata.pop("identity_unresolved", None)
    schema = _attach_target_metadata(schema, schema_metadata, observation.revision)
    return TargetObservation(
        schema if schema.fields else None,
        observation.exists,
        observation.revision,
        observation.inspector,
        (*diagnostics, *_unknown_type_diagnostics(schema)),
        metadata,
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
        {"empty": True, "identity": _safe_target_identity(identity)},
    )


def _target_identity_collision_observation(
    identity: str, *, inspector: str | None
) -> TargetObservation:
    return TargetObservation(
        None,
        "unknown",
        None,
        inspector,
        (
            _identity_diagnostic(
                "INFER_TARGET_IDENTITY_COLLISION",
                "Target identity is already bound to a different target address",
            ),
        ),
        {"identity": _safe_target_identity(identity)},
    )


def _mark_target_identity_unknown(
    observation: TargetObservation,
) -> TargetObservation:
    metadata = dict(observation.metadata)
    if metadata.get("identity") == "target":
        metadata.pop("identity", None)
    metadata["identity_unresolved"] = True
    return TargetObservation(
        observation.schema,
        observation.exists,
        observation.revision,
        observation.inspector,
        observation.diagnostics,
        metadata,
    )


def _register_observation_identity(
    target: Any,
    observation: TargetObservation,
    *,
    binding: Mapping[str, Any] | None = None,
) -> TargetObservation:
    identity = observation.identity
    if not isinstance(identity, str) or identity.strip() in {
        "",
        "target",
        "<path-redacted>",
    }:
        return observation
    try:
        _register_target_identity(
            _safe_target_identity(identity.strip()),
            _target_binding_fingerprint_for_target(target, binding),
        )
    except _TargetIdentityCollision as collision:
        return _target_identity_collision_observation(
            collision.identity, inspector=observation.inspector
        )
    return observation


def _provider_payload_value(payload: Any, key: str, default: Any = _MISSING) -> Any:
    if isinstance(payload, Mapping):
        return payload.get(key, default)
    return getattr(payload, key, default)


def _register_payload_identity(
    payload: Any, identity: str, *, inspector: str
) -> TargetObservation | None:
    """Register address fields carried by a provider response itself."""
    try:
        _register_target_identity(
            _safe_target_identity(identity),
            _target_binding_fingerprint_for_target(payload),
        )
    except _TargetIdentityCollision as collision:
        return _target_identity_collision_observation(
            collision.identity, inspector=inspector
        )
    return None


def _normalize_provider_payload(
    payload: Any,
    *,
    identity: str,
    inspector: str,
    max_diagnostics: int = 100,
    direct_mapping: bool = False,
    fallback_exists: str | None = None,
    provider_exists: tuple[str | None, Diagnostic | None] | None = None,
    caller_identity: str | None = None,
) -> TargetObservation | None:
    """Normalize every provider response through the same tri-state path."""
    if isinstance(payload, TargetObservation):
        payload_identity = payload.identity
        fallback_identity = caller_identity or (
            identity
            if payload_identity is None
            or str(payload_identity).strip() in {"", "target"}
            else None
        )
        return _normalize_target_observation(payload, identity=fallback_identity)
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
        schema_identity = _safe_target_identity(schema.identity)
        if schema_identity in {"", "target"}:
            schema_identity = (
                _safe_target_identity(caller_identity)
                if caller_identity is not None
                else _safe_target_identity(identity)
            )
        if schema_identity == "target" and identity == "target":
            return TargetObservation(
                schema,
                "present",
                None,
                inspector,
                _unknown_type_diagnostics(schema),
                metadata=dict(schema.metadata),
            )
        schema = NormalizedSchema(schema_identity, schema.fields, schema.metadata)
        metadata = {**schema.metadata, "identity": schema_identity}
        metadata["empty"] = not bool(schema.fields)
        schema = _attach_target_metadata(schema, metadata)
        return TargetObservation(
            schema if schema.fields else None,
            "present",
            None,
            inspector,
            _unknown_type_diagnostics(schema),
            metadata=metadata,
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
        target_identity = _safe_target_identity(identity)
        revision = None
        metadata: dict[str, Any] = {
            "identity": target_identity,
        }
    else:
        payload_binding_fingerprint = _target_binding_fingerprint_for_target(payload)
        provider_identity = _provider_payload_value(payload, "identity", _MISSING)
        if (
            provider_identity is _MISSING
            or provider_identity is None
            or not str(provider_identity).strip()
            or str(provider_identity).strip() == "target"
        ):
            provider_identity = caller_identity
        if (
            provider_identity is None
            or not str(provider_identity).strip()
            or str(provider_identity).strip() == "target"
        ):
            provider_identity = payload_binding_fingerprint or identity
        target_identity = _safe_target_identity(str(provider_identity))
        revision = _provider_payload_value(payload, "revision")
        if revision is _MISSING:
            revision = None
        metadata = {
            "identity": target_identity,
        }
        for key in ("keys", "partitions", "capabilities"):
            value = _provider_payload_value(payload, key)
            if value is not _MISSING:
                metadata[key] = value

    collision = _register_payload_identity(
        payload, target_identity, inspector=inspector
    )
    if collision is not None:
        return collision

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
    caller_identity: str | None = None,
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
        caller_identity=caller_identity,
    )


def inspect_target(
    target: Any, *, identity: str | None = None, max_diagnostics: int = 100
) -> TargetObservation:
    """Inspect an existing target when its adapter exposes a schema."""
    if isinstance(target, TargetObservation):
        return _normalize_target_observation(target, identity=identity)
    try:
        resolved_identity = _target_identity(target, identity)
    except _TargetIdentityCollision as collision:
        return _target_identity_collision_observation(
            collision.identity, inspector=type(target).__name__
        )
    unresolved = resolved_identity is None
    observation = _inspect_target_with_identity(
        target,
        identity=resolved_identity or "target",
        max_diagnostics=max_diagnostics,
        caller_identity=(
            str(identity).strip()
            if identity is not None and str(identity).strip()
            else None
        ),
    )
    observation = _register_observation_identity(target, observation)
    collision_detected = any(
        getattr(item, "code", None) == "INFER_TARGET_IDENTITY_COLLISION"
        for item in observation.diagnostics
    )
    identity_from_observation = isinstance(observation.identity, str) and (
        observation.identity.strip() not in {"", "target", "<path-redacted>"}
    )
    if not unresolved or collision_detected or identity_from_observation:
        return observation
    return _mark_target_identity_unknown(observation)


def _inspect_target_with_identity(
    target: Any,
    *,
    identity: str,
    max_diagnostics: int = 100,
    caller_identity: str | None = None,
) -> TargetObservation:
    """Inspect a target after resolving or assigning a diagnostic placeholder ID."""
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
        schema = NormalizedSchema(identity, schema.fields, schema.metadata)
        metadata = {**schema.metadata, "identity": identity}
        metadata["empty"] = not bool(schema.fields)
        schema = _attach_target_metadata(schema, metadata)
        return TargetObservation(
            schema if schema.fields else None,
            "present",
            None,
            "normalized",
            _unknown_type_diagnostics(schema),
            metadata,
        )
    if isinstance(target, Mapping):
        try:
            observation = _normalize_provider_payload(
                target,
                identity=identity,
                inspector="mapping",
                max_diagnostics=max_diagnostics,
                direct_mapping=True,
                caller_identity=caller_identity,
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
    if isinstance(target, (list, tuple)) and not target:
        return TargetObservation(
            None,
            "present",
            None,
            "sequence",
            (),
            {"empty": True, "identity": _safe_target_identity(identity)},
        )
    if isinstance(target, bytes):
        return _unknown_target(
            "INFER_TARGET_UNSUPPORTED", identity=identity, inspector="bytes"
        )
    if isinstance(target, (str, Path)):
        target_text = str(target)
        if isinstance(target, str) and _TARGET_URI.match(target_text):
            try:
                parsed = urlsplit(target_text)
            except ValueError:
                return _unknown_target(
                    "INFER_TARGET_UNSUPPORTED",
                    identity=identity,
                    inspector="uri",
                    message="Target URI is malformed",
                )
            if parsed.scheme.casefold() != "file" or parsed.netloc.casefold() not in {
                "",
                "localhost",
            }:
                return _unknown_target(
                    "INFER_TARGET_UNSUPPORTED",
                    identity=identity,
                    inspector="uri",
                    message="Remote target URIs require a provider inspector",
                )
            path = Path(unquote(parsed.path))
        else:
            path = Path(target)
        try:
            path_stat = path.stat()
        except FileNotFoundError:
            return TargetObservation(
                None,
                "absent",
                None,
                "filesystem",
                metadata={"identity": _safe_target_identity(identity)},
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
        if not result.schema.fields and (
            path_stat.st_size == 0
            or all(getattr(item, "code", None) == "INFER_EMPTY" for item in diagnostics)
        ):
            return TargetObservation(
                None,
                "present",
                None,
                inspector,
                diagnostics,
                {
                    "empty": True,
                    "identity": _safe_target_identity(identity),
                },
            )
        if diagnostics:
            metadata: dict[str, Any] = {
                "identity": _safe_target_identity(identity),
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
                "identity": _safe_target_identity(identity),
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
                caller_identity=caller_identity,
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
            caller_identity=caller_identity,
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
    identity: str | None = None,
    binding: Mapping[str, Any] | None = None,
    context: Mapping[str, Any] | None = None,
    max_diagnostics: int = 100,
) -> TargetObservation:
    """Inspect synchronous or asynchronous target adapters safely."""
    if isinstance(target, TargetObservation):
        try:
            resolved_identity = _target_identity(target, identity, binding=binding)
        except _TargetIdentityCollision as collision:
            return _target_identity_collision_observation(
                collision.identity, inspector=target.inspector
            )
        observation = _normalize_target_observation(target, identity=resolved_identity)
        return (
            observation
            if resolved_identity is not None
            else _mark_target_identity_unknown(observation)
        )
    try:
        resolved_identity = _target_identity(target, identity, binding=binding)
    except _TargetIdentityCollision as collision:
        return _target_identity_collision_observation(
            collision.identity, inspector=type(target).__name__
        )
    unresolved = resolved_identity is None
    observation = await _inspect_target_async_with_identity(
        target,
        identity=resolved_identity or "target",
        binding=binding,
        context=context,
        max_diagnostics=max_diagnostics,
        caller_identity=(
            str(identity).strip()
            if identity is not None and str(identity).strip()
            else None
        ),
    )
    observation = _register_observation_identity(target, observation, binding=binding)
    collision_detected = any(
        getattr(item, "code", None) == "INFER_TARGET_IDENTITY_COLLISION"
        for item in observation.diagnostics
    )
    identity_from_observation = isinstance(observation.identity, str) and (
        observation.identity.strip() not in {"", "target", "<path-redacted>"}
    )
    if not unresolved or collision_detected or identity_from_observation:
        return observation
    return _mark_target_identity_unknown(observation)


async def _inspect_target_async_with_identity(
    target: Any,
    *,
    identity: str,
    binding: Mapping[str, Any] | None = None,
    context: Mapping[str, Any] | None = None,
    max_diagnostics: int = 100,
    caller_identity: str | None = None,
) -> TargetObservation:
    """Inspect an async adapter after identity resolution."""
    if isinstance(target, (NormalizedSchema, str, Path, bytes, Mapping, list, tuple)):
        return _inspect_target_with_identity(
            target,
            identity=identity,
            max_diagnostics=max_diagnostics,
            caller_identity=caller_identity,
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
                    caller_identity=caller_identity,
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
                    caller_identity=caller_identity,
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
        if not callable(schema_method):
            return _unknown_target(
                "INFER_TARGET_UNSUPPORTED",
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
                caller_identity=caller_identity,
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
            caller_identity=caller_identity,
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
                caller_identity=caller_identity,
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
                caller_identity=caller_identity,
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
    target_identity: str | None = None,
    retain_rows: bool = False,
    expected_revision: str | None = None,
    revision_reader: Callable[[], Any] | None = None,
) -> InferenceResult:
    """Infer records and apply constraints from an existing target schema.

    ``target_identity`` supplies the stable identity used for durable target
    bindings when the inspected target is otherwise unbound.
    """
    # Keep the bounded prefix while validating conversions, even when the
    # caller only requested a schema.  Rows are removed after validation.
    source = infer_records(
        records, hints=hints, limits=limits, identity=identity, retain_rows=True
    )
    limits = limits or InferenceLimits()
    observation = (
        _normalize_target_observation(target, identity=target_identity)
        if isinstance(target, TargetObservation)
        else inspect_target(
            target,
            identity=target_identity,
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
    return _backfill_observation(source, observation, retain_rows=retain_rows)


async def infer_records_for_target_async(
    records: Any,
    target: Any,
    *,
    hints: Mapping[str, Any] | None = None,
    limits: InferenceLimits | None = None,
    identity: str = "records",
    target_identity: str | None = None,
    retain_rows: bool = False,
    binding: Mapping[str, Any] | None = None,
    context: Mapping[str, Any] | None = None,
    expected_revision: str | None = None,
    revision_reader: Callable[[], Any] | None = None,
) -> InferenceResult:
    """Async counterpart for connector-backed target schema inspection.

    ``target_identity`` supplies a stable identity for an otherwise unbound
    target when the result must be exported durably.
    """
    source = infer_records(
        records, hints=hints, limits=limits, identity=identity, retain_rows=True
    )
    limits = limits or InferenceLimits()
    observation = (
        _normalize_target_observation(target, identity=target_identity)
        if isinstance(target, TargetObservation)
        else await inspect_target_async(
            target,
            identity=target_identity,
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
    return _backfill_observation(source, observation, retain_rows=retain_rows)


@dataclass(frozen=True, slots=True)
class _TargetConversionOutcome:
    """Row conversion result shared by prefix validation and replay."""

    row: Any
    diagnostics: tuple[Diagnostic, ...] = ()
    failed_fields: frozenset[str] = frozenset()


def _target_conversion_diagnostic(
    *,
    field_name: str,
    source_type: str,
    target_type: str,
    target_identity: str | None,
    target_revision: str | None,
    row_index: int,
    unsafe: bool,
) -> Diagnostic:
    return Diagnostic(
        "INFER_RUNTIME_CONVERSION",
        Severity.ERROR,
        (
            f"Field {field_name!r} cannot be safely converted to {target_type!r}"
            if unsafe
            else f"Field {field_name!r} could not be converted to {target_type!r}"
        ),
        path=(field_name,),
        metadata={
            "source_logical_type": source_type,
            "target_logical_type": target_type,
            "target_identity": target_identity,
            "target_revision": target_revision,
            "row_index": row_index,
        },
        phase="inference",
    )


def _convert_target_row(
    row: Any,
    *,
    source_fields: Mapping[str, NormalizedField],
    target_fields: Mapping[str, NormalizedField],
    target_identity: str | None,
    target_revision: str | None,
    row_index: int,
) -> _TargetConversionOutcome:
    """Apply the target cast policy without retaining any source values."""
    if not isinstance(row, Mapping):
        return _TargetConversionOutcome(row)

    converted = dict(row)
    diagnostics: list[Diagnostic] = []
    failed_fields: set[str] = set()
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
        source_type = source_field.logical_type
        target_type = target_field.logical_type
        if (source_type, target_type) not in _LOSSLESS_CASTS:
            failed_fields.add(name)
            diagnostics.append(
                _target_conversion_diagnostic(
                    field_name=name,
                    source_type=source_type,
                    target_type=target_type,
                    target_identity=target_identity,
                    target_revision=target_revision,
                    row_index=row_index,
                    unsafe=True,
                )
            )
            continue
        try:
            converted[name] = _coerce_value(value, target_type)
        except (TypeError, ValueError, OverflowError, DecimalException):
            failed_fields.add(name)
            diagnostics.append(
                _target_conversion_diagnostic(
                    field_name=name,
                    source_type=source_type,
                    target_type=target_type,
                    target_identity=target_identity,
                    target_revision=target_revision,
                    row_index=row_index,
                    unsafe=False,
                )
            )
    return _TargetConversionOutcome(
        converted,
        tuple(diagnostics),
        frozenset(failed_fields),
    )


def _backfill_observation(
    source: InferenceResult,
    observation: TargetObservation,
    *,
    retain_rows: bool = True,
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
                "retained_rows": bool(retain_rows),
            },
            source.rows if retain_rows else (),
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
                "retained_rows": bool(retain_rows),
            },
            source.rows if retain_rows else (),
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
                "retained_rows": bool(retain_rows),
            },
            source.rows if retain_rows else (),
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
                "retained_rows": bool(retain_rows),
            },
            source.rows if retain_rows else (),
            source.replay,
            source.observed_schema,
            source.target_hypothesis,
            observation,
        )
    backfilled = backfill_schema(source.schema, observation.schema)
    rows = list(source.rows)
    runtime_diagnostics: list[Diagnostic] = []
    failed_fields: set[str] = set()
    source_fields = {field.name: field for field in source.schema.fields}
    target_fields = {field.name: field for field in observation.schema.fields}
    target_identity = observation.identity
    target_revision = observation.revision
    if rows:
        for row_index, row in enumerate(rows):
            outcome = _convert_target_row(
                row,
                source_fields=source_fields,
                target_fields=target_fields,
                target_identity=target_identity,
                target_revision=target_revision,
                row_index=row_index,
            )
            if isinstance(outcome.row, Mapping):
                rows[row_index] = dict(outcome.row)
            runtime_diagnostics.extend(outcome.diagnostics)
            failed_fields.update(outcome.failed_fields)
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
    if failed_fields:
        validation_state = "failed"
    elif cast_fields and rows and replay is None:
        validation_state = "complete"
    elif cast_fields and replay is not None:
        validation_state = "prefix_only"
    elif cast_fields:
        validation_state = "not_performed"
    replay_lifecycle: _ReplayLifecycle | None = None
    if replay is not None and (cast_fields or failed_fields):
        replay_lifecycle = _ReplayLifecycle()
        replay_row_index = 0

        def replay_convert(row: Any) -> Any:
            nonlocal replay_row_index
            row_index = replay_row_index
            replay_row_index += 1
            outcome = _convert_target_row(
                row,
                source_fields=source_fields,
                target_fields=target_fields,
                target_identity=target_identity,
                target_revision=target_revision,
                row_index=row_index,
            )
            if outcome.diagnostics:
                raise InferenceReplayError(
                    outcome.diagnostics[0],
                    row_index,
                    diagnostics=outcome.diagnostics,
                )
            return outcome.row

        replay = replay.map(replay_convert, _lifecycle=replay_lifecycle)
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
    diagnostics = tuple(unique_diagnostics[: max(1, max_diagnostics)])
    provenance = {
        **source.provenance,
        **backfilled.provenance,
        "target_exists": observation.exists,
        "target_validation": validation_state,
        "target_validation_fields": sorted(cast_fields),
        "retained_rows": bool(retain_rows),
    }
    if replay_lifecycle is not None:
        replay_status: dict[str, Any] = {
            "state": validation_state,
            "target_identity": target_identity,
            "target_revision": target_revision,
            "validated_prefix_rows": len(rows),
        }
        conversion_diagnostics = [
            diagnostic.to_dict()
            for diagnostic in runtime_diagnostics
            if diagnostic.code == "INFER_RUNTIME_CONVERSION"
        ]
        if conversion_diagnostics:
            replay_status["diagnostics"] = conversion_diagnostics
        provenance["replay_status"] = replay_status

    result = InferenceResult(
        resolved_schema,
        diagnostics,
        source.evidence,
        provenance,
        tuple(rows) if retain_rows else (),
        replay,
        source.observed_schema or source.schema,
        resolved_schema,
        observation,
    )
    if replay_lifecycle is not None:
        replay_status = result.provenance["replay_status"]

        def on_replay_failure(error: InferenceReplayError) -> None:
            replay_status.update(
                {
                    "state": "failed",
                    "row_index": error.row_index,
                    "diagnostics": [
                        diagnostic.to_dict() for diagnostic in error.diagnostics
                    ],
                }
            )
            result.provenance["target_validation"] = "failed"
            existing = list(result.diagnostics)
            existing_keys = {
                (
                    diagnostic.code,
                    tuple(diagnostic.path),
                    diagnostic.message,
                )
                for diagnostic in existing
                if isinstance(diagnostic, Diagnostic)
            }
            for diagnostic in error.diagnostics:
                key = (diagnostic.code, tuple(diagnostic.path), diagnostic.message)
                if key not in existing_keys:
                    existing.append(diagnostic)
                    existing_keys.add(key)
            result.diagnostics = tuple(existing[: max(1, max_diagnostics)])

        def on_replay_complete() -> None:
            if validation_state != "failed":
                replay_status["state"] = "complete"
                replay_status["validated_rows"] = replay_row_index
                result.provenance["target_validation"] = "complete"

        replay_lifecycle.bind(
            on_complete=on_replay_complete,
            on_failure=on_replay_failure,
        )
    return result


def _coerce_value(value: Any, logical_type: str) -> Any:
    return coerce_value(value, logical_type)


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
            target_guided_unknown = (
                source_field.logical_type == "unknown"
                and source_field.metadata.get("inference_evidence")
                in {"null_only", "no_observed_values"}
            )
            compatible = target_guided_unknown or (
                source_field.logical_type,
                target_field.logical_type,
            ) in {
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
            target_schema = _validated_normalized_schema(
                cast(NormalizedSchema, target_schema)
            )
        except (AttributeError, KeyError, TypeError, ValueError):
            base_diagnostics = (
                tuple(target_observation.diagnostics)
                if target_observation is not None
                else ()
            )
            return WriteCompatibility(
                False,
                mode=mode,
                diagnostics=(
                    *base_diagnostics,
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
            base_diagnostics = (
                tuple(target_observation.diagnostics)
                if target_observation is not None
                else ()
            )
            return WriteCompatibility(
                False,
                mode=mode,
                diagnostics=(*base_diagnostics, *unknown_type_diagnostics),
            )
        assert target_schema is not None
        assert isinstance(target_schema, NormalizedSchema)
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
        assert isinstance(target_schema, NormalizedSchema)
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
