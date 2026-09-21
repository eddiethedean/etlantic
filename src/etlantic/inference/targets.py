"""Target inspection, compatibility, and backward schema propagation."""

from __future__ import annotations

import datetime as _dt
import inspect as _inspect
import math
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path
from typing import Any

from etlantic.diagnostics import Diagnostic, Severity
from etlantic.schema_drift import (
    NormalizedField,
    NormalizedSchema,
    normalize_logical_type,
    normalize_schema_from_fields,
)

from .records import infer_csv, infer_json, infer_records
from .types import (
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


def _unknown_target(code: str = "INFER_TARGET_UNKNOWN") -> TargetObservation:
    return TargetObservation(
        None,
        "unknown",
        None,
        None,
        (
            Diagnostic(
                code,
                Severity.WARNING,
                "Target schema could not be inspected",
                phase="inference",
            ),
        ),
    )


def _diagnostics_from_payload(value: Any) -> tuple[Diagnostic, ...]:
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
                    Severity(str(item.get("severity") or "warning")),
                    str(item.get("message") or "Target inspection diagnostic"),
                    tuple(str(path) for path in item.get("path", ())),
                    phase="inference",
                )
            )
        except (TypeError, ValueError):
            continue
    return tuple(diagnostics)


def _schema_from_inspection(identity: str, fields: Any) -> NormalizedSchema:
    if isinstance(fields, Mapping):
        fields = [
            {"name": name, "logical_type": logical_type}
            for name, logical_type in fields.items()
        ]
    elif fields is None:
        fields = []
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
        return NormalizedSchema(identity=identity, fields=tuple(values))
    normalized: list[Any] = []
    for field in values:
        if isinstance(field, Mapping):
            item = dict(field)
            if "logical_type" not in item and "type" in item:
                item["logical_type"] = item["type"]
            if not item.get("name") or item.get("logical_type") is None:
                raise ValueError("target field requires name and logical type")
            item["logical_type"] = normalize_logical_type(
                item["logical_type"], preserve_decimal=True
            )
            normalized.append(item)
            continue
        field_name = getattr(field, "name", None)
        logical_type = getattr(field, "logical_type", None)
        if logical_type is None:
            logical_type = getattr(field, "type", None)
        if field_name is not None and logical_type is not None:
            normalized.append(
                {
                    "name": str(field_name),
                    "logical_type": normalize_logical_type(
                        logical_type, preserve_decimal=True
                    ),
                    "required": bool(getattr(field, "required", True)),
                    "nullable": bool(getattr(field, "nullable", False)),
                }
            )
            continue
        raise TypeError("target fields must contain field mappings or objects")
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


def inspect_target(target: Any, *, identity: str = "target") -> TargetObservation:
    """Inspect an existing target when its adapter exposes a schema."""
    if isinstance(target, NormalizedSchema):
        return TargetObservation(target, "present", target.fingerprint(), "normalized")
    if isinstance(target, Mapping):
        if not target:
            return TargetObservation(
                None,
                "present",
                None,
                "mapping",
                metadata={"empty": True, "identity": identity},
            )
        if "fields" in target:
            fields = target["fields"]
            target_identity = str(target.get("identity") or identity)
        elif target and all(
            isinstance(value, (str, type)) for value in target.values()
        ):
            fields = target
            target_identity = identity
        else:
            fields = None
            target_identity = identity
        if fields is not None:
            try:
                schema = _schema_from_inspection(target_identity, fields)
            except (KeyError, TypeError, ValueError):
                return _unknown_target("INFER_TARGET_UNSUPPORTED")
            revision = target.get("revision")
            metadata = {
                "empty": not bool(schema.fields),
                "identity": target_identity,
            }
            for key in ("keys", "partitions", "capabilities"):
                if key in target:
                    metadata[key] = target[key]
            schema = _attach_target_metadata(schema, metadata, revision)
            return TargetObservation(
                schema if schema.fields else None,
                "present",
                str(revision) if revision is not None else (
                    schema.fingerprint() if schema.fields else None
                ),
                "mapping",
                _diagnostics_from_payload(target.get("diagnostics")),
                metadata=metadata,
            )
    if hasattr(target, "names"):
        try:
            schema = _schema_from_inspection(identity, target)
            return TargetObservation(
                schema if schema.fields else None,
                "present",
                schema.fingerprint() if schema.fields else None,
                type(target).__name__,
                metadata={"empty": not bool(schema.fields), "identity": identity},
            )
        except (KeyError, TypeError, ValueError):
            return _unknown_target("INFER_TARGET_UNSUPPORTED")
    if isinstance(target, bytes):
        return _unknown_target("INFER_TARGET_UNSUPPORTED")
    if isinstance(target, (str, Path)):
        path = Path(target)
        if not path.exists():
            return TargetObservation(None, "absent", None, "filesystem")
        if not path.is_file():
            return _unknown_target("INFER_TARGET_UNSUPPORTED")
        suffix = path.suffix.lower()
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
            return _unknown_target("INFER_TARGET_UNSUPPORTED")
        return TargetObservation(
            result.schema if result.schema.fields else None,
            "present",
            result.schema.fingerprint() if result.schema.fields else None,
            inspector,
            result.diagnostics,
            {"empty": not bool(result.schema.fields)},
        )
    inspect = getattr(target, "inspect_schema", None)
    if callable(inspect):
        try:
            result = inspect()
            if _inspect.isawaitable(result):
                close = getattr(result, "close", None)
                if callable(close):
                    close()
                return _unknown_target("INFER_TARGET_UNSUPPORTED")
            if isinstance(result, NormalizedSchema):
                return TargetObservation(
                    result, "present", result.fingerprint(), type(target).__name__
                )
            fields = (
                result.get("fields", result)
                if isinstance(result, Mapping)
                else getattr(result, "fields", None)
            )
            if fields is not None:
                schema = _schema_from_inspection(identity, fields)
                payload_diagnostics = (
                    _diagnostics_from_payload(result.get("diagnostics"))
                    if isinstance(result, Mapping)
                    else ()
                )
                revision = result.get("revision") if isinstance(result, Mapping) else None
                metadata = {"empty": not bool(schema.fields), "identity": identity}
                if isinstance(result, Mapping):
                    for key in ("keys", "partitions", "capabilities"):
                        if key in result:
                            metadata[key] = result[key]
                schema = _attach_target_metadata(schema, metadata, revision)
                return TargetObservation(
                    schema if schema.fields else None,
                    "present",
                    str(revision) if revision is not None else (
                        schema.fingerprint() if schema.fields else None
                    ),
                    type(target).__name__,
                    payload_diagnostics,
                    metadata,
                )
        except Exception:
            return _unknown_target("INFER_TARGET_UNKNOWN")
    schema_attr = getattr(target, "schema", None)
    if callable(schema_attr):
        try:
            schema_attr = schema_attr()
            if _inspect.isawaitable(schema_attr):
                close = getattr(schema_attr, "close", None)
                if callable(close):
                    close()
                return _unknown_target("INFER_TARGET_UNSUPPORTED")
        except Exception:
            schema_attr = None
    if isinstance(schema_attr, NormalizedSchema):
        return TargetObservation(
            schema_attr, "present", schema_attr.fingerprint(), type(target).__name__
        )
    if isinstance(schema_attr, Mapping):
        fields = schema_attr.get("fields", schema_attr)
        try:
            schema = _schema_from_inspection(
                str(schema_attr.get("identity") or identity), fields
            )
        except (KeyError, TypeError, ValueError):
            return _unknown_target("INFER_TARGET_UNSUPPORTED")
        metadata = {"empty": not bool(schema.fields), "identity": identity}
        if isinstance(schema_attr, Mapping):
            for key in ("keys", "partitions", "capabilities"):
                if key in schema_attr:
                    metadata[key] = schema_attr[key]
        schema = _attach_target_metadata(schema, metadata, schema_attr.get("revision") if isinstance(schema_attr, Mapping) else None)
        revision = schema_attr.get("revision")
        return TargetObservation(
            schema if schema.fields else None,
            "present",
            str(revision) if revision is not None else (schema.fingerprint() if schema.fields else None),
            type(target).__name__,
            _diagnostics_from_payload(schema_attr.get("diagnostics")),
            metadata,
        )
    return _unknown_target()


async def inspect_target_async(
    target: Any,
    *,
    identity: str = "target",
    binding: Mapping[str, Any] | None = None,
    context: Mapping[str, Any] | None = None,
) -> TargetObservation:
    """Inspect synchronous or asynchronous target adapters safely."""
    if isinstance(target, (NormalizedSchema, str, Path, bytes, Mapping)):
        return inspect_target(target, identity=identity)
    inspect_schema = getattr(target, "inspect_schema", None)
    if not callable(inspect_schema):
        if not callable(getattr(target, "schema", None)):
            return inspect_target(target, identity=identity)
        try:
            schema_attr = target.schema()
            if _inspect.isawaitable(schema_attr):
                schema_attr = await schema_attr
            if isinstance(schema_attr, NormalizedSchema):
                return TargetObservation(
                    schema_attr,
                    "present",
                    schema_attr.fingerprint(),
                    type(target).__name__,
                )
            fields = (
                schema_attr.get("fields", schema_attr)
                if isinstance(schema_attr, Mapping)
                else getattr(schema_attr, "fields", None)
            )
            if fields is not None:
                try:
                    schema = _schema_from_inspection(identity, fields)
                except (KeyError, TypeError, ValueError):
                    return _unknown_target("INFER_TARGET_UNSUPPORTED")
                revision = schema_attr.get("revision") if isinstance(schema_attr, Mapping) else None
                metadata = {"empty": not bool(schema.fields), "identity": identity}
                if isinstance(schema_attr, Mapping):
                    for key in ("keys", "partitions", "capabilities"):
                        if key in schema_attr:
                            metadata[key] = schema_attr[key]
                schema = _attach_target_metadata(schema, metadata, revision)
                return TargetObservation(
                    schema if schema.fields else None,
                    "present",
                    str(revision) if revision is not None else (
                        schema.fingerprint() if schema.fields else None
                    ),
                    type(target).__name__,
                    _diagnostics_from_payload(
                        schema_attr.get("diagnostics")
                        if isinstance(schema_attr, Mapping)
                        else None
                    ),
                    metadata,
                )
        except Exception:
            return _unknown_target("INFER_TARGET_UNKNOWN")
        return _unknown_target("INFER_TARGET_UNSUPPORTED")
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
        if isinstance(result, NormalizedSchema):
            return TargetObservation(
                result, "present", result.fingerprint(), type(target).__name__
            )
        fields = (
            result.get("fields", result)
            if isinstance(result, Mapping)
            else getattr(result, "fields", None)
        )
        if fields is not None:
            try:
                schema = _schema_from_inspection(identity, fields)
            except (KeyError, TypeError, ValueError):
                return _unknown_target("INFER_TARGET_UNSUPPORTED")
            payload_diagnostics = (
                _diagnostics_from_payload(result.get("diagnostics"))
                if isinstance(result, Mapping)
                else ()
            )
            revision = result.get("revision") if isinstance(result, Mapping) else None
            metadata = {"empty": not bool(schema.fields), "identity": identity}
            if isinstance(result, Mapping):
                for key in ("keys", "partitions", "capabilities"):
                    if key in result:
                        metadata[key] = result[key]
            schema = _attach_target_metadata(schema, metadata, revision)
            return TargetObservation(
                schema if schema.fields else None,
                "present",
                str(revision) if revision is not None else (
                    schema.fingerprint() if schema.fields else None
                ),
                type(target).__name__,
                payload_diagnostics,
                metadata,
            )
    except Exception:
        return _unknown_target("INFER_TARGET_UNKNOWN")
    schema_attr = getattr(target, "schema", None)
    if callable(schema_attr):
        try:
            schema_attr = schema_attr()
            if _inspect.isawaitable(schema_attr):
                schema_attr = await schema_attr
            if isinstance(schema_attr, NormalizedSchema):
                return TargetObservation(
                    schema_attr,
                    "present",
                    schema_attr.fingerprint(),
                    type(target).__name__,
                )
            fields = (
                schema_attr.get("fields", schema_attr)
                if isinstance(schema_attr, Mapping)
                else getattr(schema_attr, "fields", None)
            )
            if fields is not None:
                try:
                    schema = _schema_from_inspection(identity, fields)
                except (KeyError, TypeError, ValueError):
                    return _unknown_target("INFER_TARGET_UNSUPPORTED")
                revision = schema_attr.get("revision") if isinstance(schema_attr, Mapping) else None
                metadata = {"empty": not bool(schema.fields), "identity": identity}
                if isinstance(schema_attr, Mapping):
                    for key in ("keys", "partitions", "capabilities"):
                        if key in schema_attr:
                            metadata[key] = schema_attr[key]
                schema = _attach_target_metadata(schema, metadata, revision)
                return TargetObservation(
                    schema if schema.fields else None,
                    "present",
                    str(revision) if revision is not None else (
                        schema.fingerprint() if schema.fields else None
                    ),
                    type(target).__name__,
                    _diagnostics_from_payload(
                        schema_attr.get("diagnostics")
                        if isinstance(schema_attr, Mapping)
                        else None
                    ),
                    metadata,
                )
        except Exception:
            return _unknown_target("INFER_TARGET_UNKNOWN")
    return _unknown_target("INFER_TARGET_UNSUPPORTED")


def infer_records_for_target(
    records: Any,
    target: Any,
    *,
    hints: Mapping[str, Any] | None = None,
    limits: InferenceLimits | None = None,
    identity: str = "records",
    retain_rows: bool = False,
    expected_revision: str | None = None,
) -> InferenceResult:
    """Infer records and apply constraints from an existing target schema."""
    # Keep the bounded prefix while validating conversions, even when the
    # caller only requested a schema.  Rows are removed after validation.
    source = infer_records(
        records, hints=hints, limits=limits, identity=identity, retain_rows=True
    )
    observation = inspect_target(target, identity=f"target:{identity}")
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
) -> InferenceResult:
    """Async counterpart for connector-backed target schema inspection."""
    source = infer_records(
        records, hints=hints, limits=limits, identity=identity, retain_rows=True
    )
    observation = await inspect_target_async(
        target, identity=f"target:{identity}", binding=binding, context=context
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
    )


def _backfill_observation(
    source: InferenceResult, observation: TargetObservation
) -> InferenceResult:
    if any(
        getattr(diagnostic, "code", None) == "INFER_TARGET_STALE"
        or (isinstance(diagnostic, Mapping) and diagnostic.get("code") == "INFER_TARGET_STALE")
        for diagnostic in observation.diagnostics
    ):
        return InferenceResult(
            source.schema,
            tuple(source.diagnostics) + tuple(observation.diagnostics),
            source.evidence,
            {**source.provenance, "target_exists": observation.exists, "target_validation": "stale"},
            source.rows,
            source.replay,
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
                try:
                    row[name] = _coerce_value(value, target_field.logical_type)
                except (TypeError, ValueError, OverflowError):
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
                try:
                    converted[name] = _coerce_value(value, target_field.logical_type)
                except (TypeError, ValueError, OverflowError):
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
    )


def _coerce_value(value: Any, logical_type: str) -> Any:
    if logical_type == "integer":
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
            if len(source_fields) != 1 or not invertible:
                backward_constraints[source_field.name] = {
                    "target_type": target_field.logical_type,
                    "source_fields": list(source_fields),
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
                        if isinstance(item, Mapping) and item.get("target_type") is not None
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
                            if isinstance(item, Mapping) and item.get("target_type") is not None
                        )
                    if previous_types and target_field.logical_type not in previous_types:
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
            for key in ("default", "has_default", "generated", "identity", "auto_increment")
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
    target_items = tuple(targets) if not isinstance(targets, (NormalizedSchema, TargetObservation)) else (targets,)
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
        for item in target_items:
            observation = item if isinstance(item, TargetObservation) else TargetObservation(item, "present", item.fingerprint(), "provided")
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
    if target_observation is not None:
        # A schema accompanied by an inspector error is not a qualified
        # observation.  Do not let a useful-looking partial payload turn into
        # a proven write result.
        inspector_errors = tuple(
            diagnostic
            for diagnostic in target_observation.diagnostics
            if getattr(getattr(diagnostic, "severity", None), "value", getattr(diagnostic, "severity", None))
            == Severity.ERROR.value
            or (isinstance(diagnostic, Mapping) and str(diagnostic.get("severity", "")).lower() == "error")
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
        target = target_observation.schema
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
                field.name
                for field in target.fields
                if field.metadata.get("partition")
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
        if not isinstance(supported_modes, (list, tuple, set)) or mode not in supported_modes:
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
    elif target_observation is not None and "capabilities" in target_metadata:
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
        and not any(diagnostic.severity == Severity.ERROR for diagnostic in diagnostics),
        casts,
        tuple(incompatible),
        tuple(diagnostics),
        obligations,
        mode,
    )
