"""Engine neutral source dispatch for schema inference."""

from __future__ import annotations

import inspect as _inspect
import time
from collections.abc import Mapping
from itertools import islice
from pathlib import Path
from typing import Any, cast

from etlantic.diagnostics import Diagnostic, Severity
from etlantic.schema_drift import (
    NormalizedField,
    NormalizedSchema,
    normalize_logical_type,
    normalize_schema_from_fields,
)

from .records import _estimate_size, infer_csv, infer_json, infer_records
from .types import InferenceLimits, InferenceResult

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


class _UnboundedProvider(RuntimeError):
    """Provider conversion cannot prove the configured materialization bound."""


def _bounded_row_count(value: Any) -> int | None:
    try:
        return max(0, len(value))
    except (TypeError, ValueError, OverflowError):
        pass
    rows = getattr(value, "rows", None)
    if rows is None:
        return None
    try:
        return max(0, len(rows))
    except (TypeError, ValueError, OverflowError):
        return None


def _provider_logical_type(value: Any) -> str:
    normalized = normalize_logical_type(value, preserve_decimal=True)
    return normalized if normalized in _KNOWN_LOGICAL_TYPES else "unknown"


def _schema_result(schema: NormalizedSchema) -> InferenceResult:
    return InferenceResult(
        schema,
        provenance={"source": "metadata", "method": "provider_schema"},
    )


def _bounded_materialization(value: Any, limits: InferenceLimits) -> Any | None:
    """Return a bounded provider view, or ``None`` when it cannot be bounded."""
    head = getattr(value, "head", None)
    if not callable(head):
        return None
    started = time.monotonic()
    try:
        bounded = head(limits.max_rows)
    except Exception:
        return None
    if (
        limits.timeout_seconds is not None
        and time.monotonic() - started >= limits.timeout_seconds
    ):
        return None
    # A provider that returns itself from ``head`` has not established a
    # bounded materialization boundary.  Calling its conversion method could
    # still consume the complete source.
    if bounded is value:
        return None
    row_count = _bounded_row_count(bounded)
    if row_count is not None and row_count > limits.max_rows:
        return None
    if row_count is None:
        module = type(bounded).__module__.split(".", 1)[0].casefold()
        if not getattr(bounded, "__etlantic_bounded_view__", False) and module not in {
            "pandas",
            "polars",
            "duckdb",
            "pyarrow",
            "datafusion",
        }:
            return None
    if limits.max_bytes is not None:
        estimate: Any = None
        for attr in ("estimated_size", "nbytes", "byte_size", "memory_usage"):
            candidate = getattr(bounded, attr, None)
            try:
                estimate = (
                    candidate(index=True)
                    if attr == "memory_usage" and callable(candidate)
                    else (candidate() if callable(candidate) else candidate)
                )
                if attr == "memory_usage" and hasattr(estimate, "sum"):
                    estimate = estimate.sum()
            except Exception:
                estimate = None
            item_method = getattr(estimate, "item", None)
            if isinstance(estimate, (int, float)) or callable(item_method):
                try:
                    estimate = float(
                        cast(Any, item_method() if callable(item_method) else estimate)
                    )
                except (TypeError, ValueError):
                    estimate = None
                break
        if estimate is None and hasattr(bounded, "rows"):
            try:
                estimate = _estimate_size(cast(Any, bounded).rows)
            except Exception:
                estimate = None
        if isinstance(estimate, (int, float)) and estimate > limits.max_bytes:
            return None
    return bounded


def _provider_records(bounded: Any, limits: InferenceLimits) -> list[Any]:
    """Convert a proven bounded provider view without retaining extra rows."""
    started = time.monotonic()
    to_dicts = getattr(bounded, "to_dicts", None)
    to_dict = getattr(bounded, "to_dict", None)
    if callable(to_dicts):
        records = to_dicts()
    elif callable(to_dict):
        try:
            records = to_dict(orient="records")
        except TypeError:
            records = to_dict()
    else:
        raise _UnboundedProvider("bounded provider view has no record conversion")
    if (
        limits.timeout_seconds is not None
        and time.monotonic() - started >= limits.timeout_seconds
    ):
        raise _UnboundedProvider("provider conversion exceeded the time budget")
    if isinstance(records, Mapping):
        records = [records]
    elif not isinstance(records, (list, tuple)):
        try:
            records = list(islice(cast(Any, records), limits.max_rows + 1))
        except TypeError as exc:
            raise _UnboundedProvider("provider records are not iterable") from exc
    if len(records) > limits.max_rows:
        raise _UnboundedProvider("provider conversion exceeded max_rows")
    return list(records)


def _looks_like_schema_mapping(value: Mapping[str, Any]) -> bool:
    """Disambiguate explicit provider schemas from one record mapping."""
    if "fields" in value or "schema" in value:
        return True
    if not value:
        return False
    # A plain mapping of lower-case strings is just as likely to be one record
    # (``{"status": "string"}``) as a shorthand provider schema.  Require an
    # explicit envelope or provider-style/type values for the schema path.
    if all(isinstance(raw, str) and raw == raw.casefold() for raw in value.values()):
        return False
    for raw_type in value.values():
        if isinstance(raw_type, type):
            continue
        normalized = normalize_logical_type(raw_type, preserve_decimal=True)
        if normalized not in _KNOWN_LOGICAL_TYPES:
            return False
    return True


def _source_failure(identity: str, source_name: str) -> InferenceResult:
    return InferenceResult(
        NormalizedSchema(identity=identity, fields=()),
        (
            Diagnostic(
                "INFER_SOURCE_UNKNOWN",
                Severity.ERROR,
                "Source schema inspection failed",
                phase="inference",
            ),
        ),
        provenance={"source": source_name, "inspection": "failed"},
    )


def _schema_from_provider_result(
    result: Any, *, identity: str, method: str, max_diagnostics: int = 100
) -> InferenceResult | None:
    """Normalize a provider schema payload without importing its package."""
    if isinstance(result, NormalizedSchema):
        return InferenceResult(
            result, provenance={"source": "metadata", "method": method}
        )
    if isinstance(result, Mapping):
        fields = result.get("fields")
        if fields is None and isinstance(result.get("schema"), Mapping):
            nested = result["schema"]
            fields = nested.get("fields", nested)
        if fields is None:
            fields = result
    else:
        fields = getattr(result, "fields", None)
        if fields is None and isinstance(getattr(result, "names", None), (list, tuple)):
            try:
                fields = tuple(result)
            except TypeError:
                fields = None
    if fields is None:
        return None
    if isinstance(fields, Mapping):
        field_items = [
            {
                "name": str(name),
                "logical_type": _provider_logical_type(logical_type),
            }
            for name, logical_type in fields.items()
        ]
    elif isinstance(fields, (list, tuple)):
        field_items = []
        for field in fields:
            if isinstance(field, Mapping):
                item = dict(field)
                if "logical_type" not in item and "type" in item:
                    item["logical_type"] = item["type"]
                if not item.get("name") or item.get("logical_type") is None:
                    return InferenceResult(
                        NormalizedSchema(identity=identity, fields=()),
                        (
                            Diagnostic(
                                "INFER_SOURCE_UNSUPPORTED",
                                Severity.ERROR,
                                "Provider schema fields are malformed",
                                phase="inference",
                            ),
                        ),
                        provenance={"source": "metadata", "method": method},
                    )
                item["logical_type"] = _provider_logical_type(item["logical_type"])
                field_items.append(item)
            else:
                field_type = getattr(field, "logical_type", None)
                if field_type is None:
                    field_type = getattr(field, "type", None)
                field_name = getattr(field, "name", None)
                if field_name is None or field_type is None:
                    return InferenceResult(
                        NormalizedSchema(identity=identity, fields=()),
                        (
                            Diagnostic(
                                "INFER_SOURCE_UNSUPPORTED",
                                Severity.ERROR,
                                "Provider schema fields are malformed",
                                phase="inference",
                            ),
                        ),
                        provenance={"source": "metadata", "method": method},
                    )
                field_items.append(
                    {
                        "name": str(field_name),
                        "logical_type": _provider_logical_type(field_type),
                        "nullable": bool(getattr(field, "nullable", True)),
                    }
                )
    else:
        return InferenceResult(
            NormalizedSchema(identity=identity, fields=()),
            (
                Diagnostic(
                    "INFER_SOURCE_UNSUPPORTED",
                    Severity.ERROR,
                    "Provider schema fields must be a mapping or sequence",
                    phase="inference",
                ),
            ),
            provenance={"source": "metadata", "method": method},
        )
    if not field_items:
        explicit_envelope = isinstance(result, Mapping) and (
            "fields" in result or "schema" in result
        )
        if explicit_envelope:
            return InferenceResult(
                NormalizedSchema(identity=identity, fields=()),
                provenance={"source": "metadata", "method": method},
            )
        return None
    diagnostics_list: list[Any] = []
    if isinstance(result, Mapping):
        raw_diagnostics = result.get("diagnostics", ())
        if isinstance(raw_diagnostics, (list, tuple)):
            diagnostics_list.extend(
                item
                for item in raw_diagnostics
                if isinstance(item, (Diagnostic, Mapping))
            )
    for item in field_items:
        if str(item.get("logical_type", "unknown")) == "unknown":
            diagnostics_list.append(
                Diagnostic(
                    "INFER_UNKNOWN_TYPE",
                    Severity.WARNING,
                    f"Provider type for field {item.get('name', '')!r} is unknown",
                    path=(str(item.get("name", "")),),
                    phase="inference",
                )
            )
    try:
        schema = normalize_schema_from_fields(
            field_items, identity=identity, preserve_decimal=True
        )
    except (KeyError, TypeError, ValueError):
        return InferenceResult(
            NormalizedSchema(identity=identity, fields=()),
            (
                Diagnostic(
                    "INFER_SOURCE_UNSUPPORTED",
                    Severity.ERROR,
                    "Provider schema fields are malformed",
                    phase="inference",
                ),
            ),
            provenance={"source": "metadata", "method": method},
        )
    return InferenceResult(
        schema,
        tuple(diagnostics_list[:max_diagnostics]),
        provenance={"source": "metadata", "method": method},
    )


def _schema_from_column_metadata(
    value: Any, *, identity: str
) -> InferenceResult | None:
    """Recover a schema from dataframe columns when no rows are available."""
    columns = getattr(value, "columns", None)
    dtypes = getattr(value, "dtypes", None)
    if columns is None or dtypes is None:
        return None
    try:
        names = list(columns)
        dtype_values = (
            list(dtypes.values()) if isinstance(dtypes, Mapping) else list(dtypes)
        )
    except (TypeError, ValueError):
        return None
    if not names or len(names) != len(dtype_values):
        return None
    try:
        schema = normalize_schema_from_fields(
            [
                {
                    "name": str(name),
                    "logical_type": _provider_logical_type(dtype),
                }
                for name, dtype in zip(names, dtype_values, strict=True)
            ],
            identity=identity,
            preserve_decimal=True,
        )
    except (TypeError, ValueError):
        return None
    return InferenceResult(
        schema,
        provenance={"source": "metadata", "method": "provider_columns"},
    )


def _attach_provider_preview(
    result: InferenceResult,
    value: Any,
    *,
    limits: InferenceLimits,
    hints: Mapping[str, Any] | None,
    identity: str,
) -> InferenceResult:
    """Retain a bounded preview when metadata-first providers expose one.

    Schema inspection must stay metadata first, but user-facing dataframe
    constructors promise a preview as well. The preview is obtained only
    through the same bounded head boundary. Provider logical types remain
    authoritative while observed nullability is refined from the bounded
    preview.
    """
    bounded = _bounded_materialization(value, limits)
    if bounded is None:
        if callable(getattr(value, "head", None)):
            return result.replace(
                diagnostics=(
                    Diagnostic(
                        "INFER_SOURCE_UNBOUNDED",
                        Severity.ERROR,
                        "Provider head view could not prove the configured bounds",
                        phase="inference",
                    ),
                    *result.diagnostics,
                )
            )
        return result
    try:
        records = _provider_records(bounded, limits)
        preview = infer_records(
            records,
            hints=hints,
            limits=limits,
            identity=identity,
            retain_rows=True,
        )
    except _UnboundedProvider:
        return result.replace(
            diagnostics=(
                Diagnostic(
                    "INFER_SOURCE_UNBOUNDED",
                    Severity.ERROR,
                    "Provider preview conversion could not prove the configured bounds",
                    phase="inference",
                ),
                *result.diagnostics,
            )
        )
    except Exception:
        return result.replace(
            diagnostics=(
                Diagnostic(
                    "INFER_SOURCE_UNSUPPORTED",
                    Severity.WARNING,
                    "Bounded provider preview conversion failed",
                    phase="inference",
                ),
                *result.diagnostics,
            )
        )
    preview_fields = {field.name: field for field in preview.schema.fields}
    merged_fields = tuple(
        NormalizedField(
            name=field.name,
            logical_type=field.logical_type,
            required=field.required and preview_fields.get(field.name, field).required,
            nullable=field.nullable or preview_fields.get(field.name, field).nullable,
            metadata=dict(field.metadata),
        )
        for field in result.schema.fields
    )
    observed_schema = NormalizedSchema(
        identity=result.schema.identity,
        fields=merged_fields,
        metadata=dict(result.schema.metadata),
    )
    return result.replace(
        schema=observed_schema,
        rows=preview.rows,
        replay=preview.replay,
        diagnostics=(
            *result.diagnostics,
            *preview.diagnostics,
        )[: limits.max_diagnostics],
        provenance={
            **result.provenance,
            "preview_rows_observed": preview.provenance.get(
                "rows_observed", len(preview.rows)
            ),
            "preview_bytes_observed": preview.provenance.get("bytes_observed", 0),
            "preview_available": True,
        },
    )


def infer_source(
    value: Any,
    *,
    identity: str = "source",
    hints: Mapping[str, Any] | None = None,
    limits: InferenceLimits | None = None,
) -> InferenceResult:
    """Infer a source using metadata first and bounded records as a fallback.

    Optional engines are detected by their public duck typed conversion hooks;
    importing an optional engine is never required by this function.
    """
    limits = limits or InferenceLimits()
    if isinstance(value, NormalizedSchema):
        return _schema_result(value)
    direct_schema = None
    if isinstance(value, Mapping):
        if not _looks_like_schema_mapping(value):
            result = infer_records(value, hints=hints, limits=limits, identity=identity)
            if value and all(isinstance(raw, str) for raw in value.values()):
                result = result.replace(
                    diagnostics=(
                        Diagnostic(
                            "INFER_SOURCE_AMBIGUOUS",
                            Severity.WARNING,
                            "Mapping was treated as one record; use a fields/schema envelope for provider schemas",
                            phase="inference",
                        ),
                        *result.diagnostics,
                    )
                )
            return result
        direct_schema = _schema_from_provider_result(
            value,
            identity=identity,
            method="provider_schema",
            max_diagnostics=limits.max_diagnostics,
        )
        if direct_schema is None and ("fields" in value or "schema" in value):
            return InferenceResult(
                NormalizedSchema(identity=identity, fields=()),
                (
                    Diagnostic(
                        "INFER_SOURCE_UNSUPPORTED",
                        Severity.ERROR,
                        "Provider schema envelope is malformed",
                        phase="inference",
                    ),
                ),
                provenance={"source": "metadata", "inspection": "failed"},
            )
    else:
        direct_schema = _schema_from_provider_result(
            value,
            identity=identity,
            method="provider_schema",
            max_diagnostics=limits.max_diagnostics,
        )
    if direct_schema is not None:
        return _attach_provider_preview(
            direct_schema,
            value,
            limits=limits,
            hints=hints,
            identity=identity,
        )
    if isinstance(value, (str, Path)):
        suffix = str(value).lower()
        if suffix.endswith((".json", ".jsonl")):
            return infer_json(
                value,
                lines=suffix.endswith(".jsonl"),
                hints=hints,
                limits=limits,
                identity=identity,
            )
        if suffix.endswith((".csv", ".tsv")):
            options = {"delimiter": "\t"} if suffix.endswith(".tsv") else None
            return infer_csv(
                value, options=options, hints=hints, limits=limits, identity=identity
            )
        return InferenceResult(
            NormalizedSchema(identity=identity, fields=()),
            (
                Diagnostic(
                    "INFER_SOURCE_UNSUPPORTED",
                    Severity.ERROR,
                    "File suffix is not a supported inference format",
                    phase="inference",
                ),
            ),
            provenance={"source": "path"},
        )
    inspect_schema = getattr(value, "inspect_schema", None)
    if callable(inspect_schema):
        try:
            inspected = inspect_schema()
            if _inspect.isawaitable(inspected):
                close = getattr(inspected, "close", None)
                if callable(close):
                    close()
                return InferenceResult(
                    NormalizedSchema(identity=identity, fields=()),
                    (
                        Diagnostic(
                            "INFER_SOURCE_ASYNC_SCHEMA",
                            Severity.WARNING,
                            "Source schema inspection is asynchronous; use infer_source_async",
                            phase="inference",
                        ),
                    ),
                    provenance={"source": type(value).__name__},
                )
            result = _schema_from_provider_result(
                inspected,
                identity=identity,
                method="inspect_schema",
                max_diagnostics=limits.max_diagnostics,
            )
            if result is not None:
                return _attach_provider_preview(
                    result, value, limits=limits, hints=hints, identity=identity
                )
        except Exception:
            return InferenceResult(
                NormalizedSchema(identity=identity, fields=()),
                (
                    Diagnostic(
                        "INFER_SOURCE_UNKNOWN",
                        Severity.ERROR,
                        "Source schema inspection failed",
                        phase="inference",
                    ),
                ),
                provenance={"source": type(value).__name__, "inspection": "failed"},
            )
    schema = getattr(value, "schema", None)
    schema_diagnostic: Diagnostic | None = None
    if callable(schema):
        try:
            schema = schema()
            if _inspect.isawaitable(schema):
                close = getattr(schema, "close", None)
                if callable(close):
                    close()
                schema = None
                schema_diagnostic = Diagnostic(
                    "INFER_SOURCE_ASYNC_SCHEMA",
                    Severity.WARNING,
                    "Source schema inspection is asynchronous; use infer_source_async",
                    phase="inference",
                )
        except Exception:
            return InferenceResult(
                NormalizedSchema(identity=identity, fields=()),
                (
                    Diagnostic(
                        "INFER_SOURCE_UNKNOWN",
                        Severity.ERROR,
                        "Source schema inspection failed",
                        phase="inference",
                    ),
                ),
                provenance={"source": type(value).__name__, "inspection": "failed"},
            )
    if schema is not None:
        if isinstance(schema, Mapping) and "fields" in schema:
            result = _schema_from_provider_result(
                schema,
                identity=identity,
                method="schema",
                max_diagnostics=limits.max_diagnostics,
            )
            if result is not None:
                return _attach_provider_preview(
                    result, value, limits=limits, hints=hints, identity=identity
                )
            return InferenceResult(
                NormalizedSchema(identity=identity, fields=()),
                (
                    Diagnostic(
                        "INFER_SOURCE_UNSUPPORTED",
                        Severity.ERROR,
                        "Provider schema envelope is malformed",
                        phase="inference",
                    ),
                ),
                provenance={"source": type(value).__name__, "inspection": "failed"},
            )
        elif not isinstance(schema, Mapping):
            provider_schema = _schema_from_provider_result(
                schema,
                identity=identity,
                method="schema",
                max_diagnostics=limits.max_diagnostics,
            )
            if provider_schema is not None:
                return _attach_provider_preview(
                    provider_schema,
                    value,
                    limits=limits,
                    hints=hints,
                    identity=identity,
                )
        fields: list[dict[str, Any]] = []
        if isinstance(schema, Mapping):
            fields = [
                {
                    "name": str(name),
                    "logical_type": _provider_logical_type(dtype),
                }
                for name, dtype in schema.items()
            ]
        elif hasattr(schema, "names") and isinstance(
            getattr(schema, "names", None), (list, tuple)
        ):
            schema_fields = getattr(schema, "fields", ())
            if not isinstance(schema_fields, (list, tuple)):
                try:
                    schema_fields = tuple(cast(Any, schema))
                except TypeError:
                    schema_fields = ()
            for field in schema_fields:
                fields.append(
                    {
                        "name": str(getattr(field, "name", "")),
                        "logical_type": _provider_logical_type(
                            getattr(field, "type", "unknown")
                        ),
                        "nullable": bool(getattr(field, "nullable", True)),
                    }
                )
        if fields:
            normalized = normalize_schema_from_fields(
                fields, identity=identity, preserve_decimal=True
            )
            unknown_diagnostics = tuple(
                Diagnostic(
                    "INFER_UNKNOWN_TYPE",
                    Severity.WARNING,
                    f"Provider type for field {field.name!r} is unknown",
                    path=(field.name,),
                    phase="inference",
                )
                for field in normalized.fields
                if field.logical_type == "unknown"
            )
            return _attach_provider_preview(
                InferenceResult(
                    normalized,
                    unknown_diagnostics,
                    provenance={"source": "metadata", "method": "provider_schema"},
                ),
                value,
                limits=limits,
                hints=hints,
                identity=identity,
            )
    to_dicts = getattr(value, "to_dicts", None)
    if callable(to_dicts):
        bounded = _bounded_materialization(value, limits)
        if bounded is None:
            return InferenceResult(
                NormalizedSchema(identity=identity, fields=()),
                (
                    Diagnostic(
                        "INFER_SOURCE_UNBOUNDED",
                        Severity.ERROR,
                        "Source exposes records but no bounded head operation",
                        phase="inference",
                    ),
                ),
                provenance={"source": type(value).__name__},
            )
        try:
            records = _provider_records(bounded, limits)
        except _UnboundedProvider:
            return InferenceResult(
                NormalizedSchema(identity=identity, fields=()),
                (
                    Diagnostic(
                        "INFER_SOURCE_UNBOUNDED",
                        Severity.ERROR,
                        "Provider conversion could not prove the configured bounds",
                        phase="inference",
                    ),
                ),
                provenance={"source": type(value).__name__},
            )
        except Exception:
            return InferenceResult(
                NormalizedSchema(identity=identity, fields=()),
                (
                    Diagnostic(
                        "INFER_SOURCE_UNSUPPORTED",
                        Severity.ERROR,
                        "Bounded provider conversion failed",
                        phase="inference",
                    ),
                ),
                provenance={"source": type(value).__name__},
            )
        result = infer_records(
            records, hints=hints, limits=limits, identity=identity, retain_rows=True
        )
        if schema_diagnostic is not None:
            result = InferenceResult(
                result.schema,
                (schema_diagnostic, *result.diagnostics),
                result.evidence,
                result.provenance,
                result.rows,
                result.replay,
            )
        return result
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        bounded = _bounded_materialization(value, limits)
        if bounded is None:
            return InferenceResult(
                NormalizedSchema(identity=identity, fields=()),
                (
                    Diagnostic(
                        "INFER_SOURCE_UNBOUNDED",
                        Severity.ERROR,
                        "Source exposes records but no bounded head operation",
                        phase="inference",
                    ),
                ),
                provenance={"source": type(value).__name__},
            )
        try:
            converted = _provider_records(bounded, limits)
        except _UnboundedProvider:
            return InferenceResult(
                NormalizedSchema(identity=identity, fields=()),
                (
                    Diagnostic(
                        "INFER_SOURCE_UNBOUNDED",
                        Severity.ERROR,
                        "Provider conversion could not prove the configured bounds",
                        phase="inference",
                    ),
                ),
                provenance={"source": type(value).__name__},
            )
        except Exception:
            return InferenceResult(
                NormalizedSchema(identity=identity, fields=()),
                (
                    Diagnostic(
                        "INFER_SOURCE_UNSUPPORTED",
                        Severity.ERROR,
                        "Bounded provider conversion failed",
                        phase="inference",
                    ),
                ),
                provenance={"source": type(value).__name__},
            )
        result = infer_records(
            converted,
            hints=hints,
            limits=limits,
            identity=identity,
            retain_rows=True,
        )
        if not converted and not result.schema.fields:
            column_schema = _schema_from_column_metadata(value, identity=identity)
            if column_schema is not None:
                return column_schema.replace(
                    diagnostics=(
                        *column_schema.diagnostics,
                        *result.diagnostics,
                    )[: limits.max_diagnostics],
                    provenance={
                        **column_schema.provenance,
                        **{
                            key: item
                            for key, item in result.provenance.items()
                            if key != "source"
                        },
                    },
                    rows=result.rows,
                    replay=result.replay,
                )
        return result
    if isinstance(value, Mapping) or hasattr(value, "__iter__"):
        return infer_records(value, hints=hints, limits=limits, identity=identity)
    return InferenceResult(
        NormalizedSchema(identity=identity, fields=()),
        (
            Diagnostic(
                "INFER_SOURCE_UNSUPPORTED",
                Severity.ERROR,
                "Source does not expose schema metadata or records",
                phase="inference",
            ),
        ),
        provenance={"source": type(value).__name__},
    )


async def infer_source_async(
    value: Any,
    *,
    identity: str = "source",
    hints: Mapping[str, Any] | None = None,
    limits: InferenceLimits | None = None,
) -> InferenceResult:
    """Infer a source while allowing connector schema inspection to be awaited."""
    limits = limits or InferenceLimits()
    inspect_schema = getattr(value, "inspect_schema", None)
    if callable(inspect_schema):
        try:
            inspected = inspect_schema()
            if _inspect.isawaitable(inspected):
                inspected = await inspected
            result = _schema_from_provider_result(
                inspected,
                identity=identity,
                method="inspect_schema",
                max_diagnostics=limits.max_diagnostics,
            )
            if result is not None:
                return _attach_provider_preview(
                    result, value, limits=limits, hints=hints, identity=identity
                )
        except Exception:
            return _source_failure(identity, type(value).__name__)
    schema = getattr(value, "schema", None)
    if isinstance(schema, NormalizedSchema):
        return _schema_result(schema)
    if callable(schema):
        try:
            schema = schema()
            if _inspect.isawaitable(schema):
                schema = await schema
            fields: list[dict[str, Any]] = []
            if isinstance(schema, Mapping) and "fields" in schema:
                result = _schema_from_provider_result(
                    schema,
                    identity=identity,
                    method="schema",
                    max_diagnostics=limits.max_diagnostics,
                )
                if result is not None:
                    return _attach_provider_preview(
                        result, value, limits=limits, hints=hints, identity=identity
                    )
            if isinstance(schema, Mapping):
                fields = [
                    {
                        "name": str(name),
                        "logical_type": normalize_logical_type(
                            dtype, preserve_decimal=True
                        ),
                    }
                    for name, dtype in schema.items()
                ]
            if fields:
                return _schema_result(
                    normalize_schema_from_fields(
                        fields, identity=identity, preserve_decimal=True
                    )
                )
        except Exception:
            return _source_failure(identity, type(value).__name__)
    return infer_source(value, identity=identity, hints=hints, limits=limits)
