"""Bounded schema-document inspection with optional registry identity checks."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, cast

from etlantic.diagnostics import Diagnostic, Severity
from etlantic.schema_drift import NormalizedSchema, normalize_schema_from_fields
from etlantic.streaming.registry import SchemaFormat, schema_fingerprint

from .types import InferenceLimits, InferenceResult, TargetObservation

_JSON_TYPES = {
    "null": "null",
    "boolean": "boolean",
    "integer": "integer",
    "number": "number",
    "string": "string",
    "object": "object",
    "array": "array",
}
_AVRO_TYPES = {
    "null": "null",
    "boolean": "boolean",
    "int": "integer",
    "long": "integer",
    "float": "number",
    "double": "number",
    "bytes": "binary",
    "string": "string",
    "record": "object",
    "array": "array",
    "map": "object",
}


def _exceeds_utf8_byte_limit(value: str, limit: int | None) -> bool:
    """Count encoded bytes in bounded chunks instead of copying the full text."""
    if limit is None:
        return False
    # UTF-8 uses at least one byte per code point, so this rejects oversized
    # ASCII and Unicode inputs without scanning or allocating an encoded copy.
    if len(value) > limit:
        return True
    encoded_bytes = 0
    for start in range(0, len(value), 4096):
        encoded_bytes += len(value[start : start + 4096].encode("utf-8"))
        if encoded_bytes > limit:
            return True
    return False


def _json_string_size(value: str, limit: int) -> int:
    """Count a JSONEncoder-compatible escaped string without encoding a copy."""
    size = 2  # surrounding quotes
    if size > limit:
        return size
    for character in value:
        codepoint = ord(character)
        if character in {'"', "\\", "\b", "\t", "\n", "\f", "\r"}:
            size += 2
        elif codepoint < 0x20 or codepoint > 0x7F:
            size += 12 if codepoint > 0xFFFF else 6
        else:
            size += 1
        if size > limit:
            return size
    return size


def _mapping_exceeds_serialization_limit(
    document: Mapping[str, Any], limit: int | None
) -> bool:
    """Preflight a mapping before JSONEncoder can allocate large scalar chunks."""
    if limit is None:
        return False

    encoded_bytes = 0
    visited_values = 0
    # Iterator frames keep wide arrays and objects from becoming pending lists.
    stack: list[tuple[str, Any, int]] = [("value", document, 0)]

    def add(size: int) -> bool:
        nonlocal encoded_bytes
        encoded_bytes += size
        return encoded_bytes > limit

    while stack:
        kind, value, depth = stack.pop()
        if depth > 512:
            return True
        if kind == "mapping":
            mapping, iterator, first = value
            try:
                key = next(iterator)
            except StopIteration:
                continue
            stack.append(("mapping", (mapping, iterator, False), depth))
            if not first and add(1):  # comma
                return True
            if add(1):  # colon
                return True
            stack.append(("value", mapping[key], depth + 1))
            stack.append(("key", key, depth + 1))
            continue
        if kind == "sequence":
            iterator, first = value
            try:
                item = next(iterator)
            except StopIteration:
                continue
            stack.append(("sequence", (iterator, False), depth))
            if not first and add(1):  # comma
                return True
            stack.append(("value", item, depth + 1))
            continue

        visited_values += 1
        if visited_values > limit:
            return True
        if isinstance(value, str):
            size = _json_string_size(value, limit)
            if size > limit or add(size):
                return True
            continue
        if isinstance(value, Mapping):
            try:
                mapping = cast(Mapping[Any, Any], value)
                if len(mapping) > limit:
                    return True
                iterator = iter(mapping)
            except Exception:
                # Let JSONEncoder produce its usual unsupported-payload error.
                continue
            if add(2):  # braces
                return True
            stack.append(("mapping", (mapping, iterator, True), depth))
            continue
        if isinstance(value, (list, tuple)):
            sequence = cast(list[Any] | tuple[Any, ...], value)
            if len(sequence) > limit:
                return True
            if add(2):  # brackets
                return True
            stack.append(("sequence", (iter(sequence), True), depth))
            continue
        if value is None or value is True:
            size = 4
        elif value is False:
            size = 5
        elif type(value) is int:
            if value.bit_length() > limit * 4:
                return True
            size = len(str(value))
        elif type(value) is float:
            size = len(repr(value))
        else:
            # Unsupported values are rejected by JSONEncoder below.
            size = 1
        if add(size):
            return True
    return False


def _failure(identity: str, code: str, message: str) -> InferenceResult:
    return InferenceResult(
        NormalizedSchema(identity, ()),
        (Diagnostic(code, Severity.ERROR, message, phase="inference"),),
        provenance={"source": "schema_document", "inspection": "failed"},
    )


def _field_type(raw: Any, *, avro: bool) -> tuple[str, bool]:
    nullable = False
    if isinstance(raw, list):
        variants = cast(list[Any], raw)
        nullable = "null" in variants
        nonnull: list[Any] = [item for item in variants if item != "null"]
        if len(nonnull) != 1:
            return "unknown", nullable
        raw = nonnull[0]
    if isinstance(raw, Mapping):
        declaration = cast(Mapping[str, Any], raw)
        declared = declaration.get("type")
        if avro and declaration.get("logicalType") == "decimal":
            return "decimal", nullable
        if avro and declaration.get("logicalType") in {
            "date",
            "timestamp-millis",
            "timestamp-micros",
        }:
            return (
                "date" if declaration["logicalType"] == "date" else "datetime",
                nullable,
            )
        if not avro and declaration.get("format") in {"date", "date-time"}:
            return ("date" if declaration["format"] == "date" else "datetime", nullable)
        logical, inner_nullable = _field_type(declared, avro=avro)
        return logical, nullable or inner_nullable
    if not isinstance(raw, str):
        return "unknown", nullable
    table = _AVRO_TYPES if avro else _JSON_TYPES
    return table.get(raw, "unknown"), nullable


def infer_schema_document(
    document: str | Mapping[str, Any],
    *,
    format: str,
    identity: str = "schema_document",
    limits: InferenceLimits | None = None,
    registry: Any | None = None,
    subject: str | None = None,
    version: int | None = None,
) -> InferenceResult:
    """Inspect JSON Schema or Avro record fields without retaining the document.

    A registry lookup pins the caller-supplied document to an existing
    subject/version fingerprint. This operation never registers or writes.
    """
    limits = limits or InferenceLimits()
    try:
        schema_format = SchemaFormat(format)
    except ValueError:
        return _failure(
            identity, "INFER_SOURCE_UNSUPPORTED", "Unknown schema document format"
        )
    if schema_format not in {SchemaFormat.JSON_SCHEMA, SchemaFormat.AVRO}:
        return _failure(
            identity,
            "INFER_SOURCE_UNSUPPORTED",
            "Schema document format has no qualified field adapter",
        )
    if registry is not None and not subject:
        return _failure(
            identity,
            "INFER_SOURCE_UNSUPPORTED",
            "Registry inspection requires a subject",
        )
    try:
        payload: Mapping[str, Any]
        if isinstance(document, str):
            if _exceeds_utf8_byte_limit(document, limits.max_bytes):
                return _failure(
                    identity, "INFER_LIMIT", "Schema document exceeds the byte limit"
                )
            parsed: Any = json.loads(document)
            if not isinstance(parsed, Mapping):
                raise ValueError("Schema document must be an object")
            payload = cast(Mapping[str, Any], parsed)
            fingerprint_document = document
        else:
            payload = document
            if _mapping_exceeds_serialization_limit(document, limits.max_bytes):
                return _failure(
                    identity,
                    "INFER_LIMIT",
                    "Schema document exceeds the byte limit",
                )
            parts: list[str] = []
            encoded_bytes = 0
            encoder = json.JSONEncoder(
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
                ensure_ascii=True,
            )
            for part in encoder.iterencode(document):
                encoded_bytes += len(part)
                if limits.max_bytes is not None and encoded_bytes > limits.max_bytes:
                    return _failure(
                        identity,
                        "INFER_LIMIT",
                        "Schema document exceeds the byte limit",
                    )
                parts.append(part)
            fingerprint_document = "".join(parts)
        fingerprint = schema_fingerprint(fingerprint_document, format=schema_format)
        registry_version: int | None = None
        if registry is not None:
            observed = registry.lookup(subject, version)
            if observed.format != schema_format or observed.fingerprint != fingerprint:
                return _failure(
                    identity,
                    "INFER_SOURCE_SCHEMA_MISMATCH",
                    "Registry identity does not match the schema document",
                )
            registry_version = observed.version
        avro = schema_format == SchemaFormat.AVRO
        if avro:
            if payload.get("type") != "record":
                raise ValueError("Avro root must be a record")
            raw_fields = payload.get("fields")
            if not isinstance(raw_fields, list):
                raise ValueError("Avro record fields must be an array")
            if len(cast(list[Any], raw_fields)) > limits.max_fields:
                return _failure(
                    identity, "INFER_LIMIT", "Schema document exceeds the field limit"
                )
            entries: list[dict[str, Any]] = []
            for raw_field in cast(list[Any], raw_fields):
                if not isinstance(raw_field, Mapping):
                    raise ValueError("Avro field is malformed")
                field = cast(Mapping[str, Any], raw_field)
                if not isinstance(field.get("name"), str):
                    raise ValueError("Avro field is malformed")
                logical, nullable = _field_type(field.get("type"), avro=True)
                entries.append(
                    {
                        "name": field["name"],
                        "logical_type": logical,
                        "required": True,
                        "nullable": nullable,
                    }
                )
        else:
            if payload.get("type") != "object":
                raise ValueError("JSON Schema root must be an object")
            properties = payload.get("properties")
            required = payload.get("required", [])
            if not isinstance(properties, Mapping) or not isinstance(required, list):
                raise ValueError("JSON Schema properties or required list is malformed")
            if len(cast(Mapping[str, Any], properties)) > limits.max_fields:
                return _failure(
                    identity, "INFER_LIMIT", "Schema document exceeds the field limit"
                )
            required_names = cast(list[Any], required)
            property_map = cast(Mapping[str, Any], properties)
            if not all(isinstance(item, str) for item in required_names):
                raise ValueError("JSON Schema required names are malformed")
            if any(item not in property_map for item in required_names):
                raise ValueError("JSON Schema required name is not a property")
            entries = []
            for name, raw_field in property_map.items():
                if type(name) is not str or not isinstance(raw_field, Mapping):
                    raise ValueError("JSON Schema property is malformed")
                field = cast(Mapping[str, Any], raw_field)
                logical, nullable = _field_type(field.get("type"), avro=False)
                entries.append(
                    {
                        "name": name,
                        "logical_type": logical,
                        "required": name in required_names,
                        "nullable": nullable,
                    }
                )
        if len(entries) > limits.max_fields:
            return _failure(
                identity, "INFER_LIMIT", "Schema document exceeds the field limit"
            )
        schema = normalize_schema_from_fields(
            entries, identity=identity, preserve_decimal=True
        )
    except (AttributeError, TypeError, ValueError, json.JSONDecodeError):
        return _failure(
            identity,
            "INFER_SOURCE_UNSUPPORTED",
            "Schema document could not be normalized",
        )
    except Exception:
        return _failure(identity, "INFER_SOURCE_UNSUPPORTED", "Registry lookup failed")
    diagnostics = tuple(
        Diagnostic(
            "INFER_UNKNOWN_TYPE",
            Severity.ERROR,
            f"Schema document type for field {field.name!r} is unsupported",
            path=(field.name,),
            phase="inference",
        )
        for field in schema.fields
        if field.logical_type == "unknown"
    )
    return InferenceResult(
        schema,
        diagnostics[: limits.max_diagnostics],
        provenance={
            "source": "schema_document",
            "method": schema_format.value,
            "fingerprint": fingerprint,
            "subject": subject,
            "version": registry_version,
            "rows_observed": 0,
            "sampled": False,
            "limits": limits.to_dict(),
        },
    )


def inspect_schema_document_target(
    document: str | Mapping[str, Any],
    *,
    format: str,
    identity: str,
    limits: InferenceLimits | None = None,
    registry: Any | None = None,
    subject: str | None = None,
    version: int | None = None,
) -> TargetObservation:
    """Pin a schema document as a read-only target constraint observation."""
    result = infer_schema_document(
        document,
        format=format,
        identity=identity,
        limits=limits,
        registry=registry,
        subject=subject,
        version=version,
    )
    metadata = {
        "identity": identity,
        "fingerprint": result.provenance.get("fingerprint"),
        "subject": result.provenance.get("subject"),
        "version": result.provenance.get("version"),
    }
    if not result.valid:
        return TargetObservation(
            None, "unknown", None, "schema_document", result.diagnostics, metadata
        )
    return TargetObservation(
        result.schema,
        "present",
        result.provenance.get("fingerprint"),
        "schema_document",
        result.diagnostics,
        metadata,
    )


def infer_registry_subject(
    registry: Any,
    subject: str,
    *,
    version: int | None = None,
    identity: str = "registry_subject",
    limits: InferenceLimits | None = None,
) -> InferenceResult:
    """Fetch one bounded registry version and normalize its document."""
    fetch = getattr(registry, "fetch_schema", None)
    if not callable(fetch):
        return _failure(
            identity,
            "INFER_SOURCE_UNSUPPORTED",
            "Registry provider does not expose bounded schema fetch",
        )
    try:
        entry = fetch(subject, version)
        if not isinstance(entry, Mapping):
            raise ValueError("invalid registry response")
        payload = cast(Mapping[str, Any], entry)
        document = payload.get("document")
        format_name = payload.get("format")
        observed_version = payload.get("version")
        if (
            not isinstance(document, str)
            or not isinstance(format_name, str)
            or type(observed_version) is not int
            or observed_version < 1
            or (version is not None and observed_version != version)
            or payload.get("subject") != subject
        ):
            raise ValueError("invalid registry schema metadata")
        result = infer_schema_document(
            document,
            format=format_name,
            identity=identity,
            limits=limits,
        )
        if not result.valid or payload.get("fingerprint") != result.provenance.get(
            "fingerprint"
        ):
            return _failure(
                identity,
                "INFER_SOURCE_SCHEMA_MISMATCH",
                "Registry document fingerprint could not be verified",
            )
        return result.replace(
            provenance={
                **result.provenance,
                "source": "schema_registry",
                "version": observed_version,
            }
        )
    except Exception:
        return _failure(
            identity, "INFER_SOURCE_UNSUPPORTED", "Registry schema lookup failed"
        )
