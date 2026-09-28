# pyright: reportPrivateUsage=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Engine neutral source dispatch for schema inference."""

from __future__ import annotations

import inspect as _inspect
import math
import time
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from etlantic.diagnostics import Diagnostic, Severity
from etlantic.schema_drift import (
    NormalizedField,
    NormalizedSchema,
    normalize_logical_type,
    normalize_schema_from_fields,
)

from .records import (
    _estimate_size,
    estimate_materialized_row,
    infer_csv,
    infer_json,
    infer_records,
)
from .types import InferenceLimits, InferenceResult, SchemaEvidence

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


class _MaterializedLimitReached(RuntimeError):
    """A provider preview cannot be converted within the materialized-byte cap."""


class _InferenceTimeout(RuntimeError):
    """The shared inference deadline expired during provider inspection."""


@dataclass(frozen=True, slots=True)
class _BoundedView:
    value: Any
    truncated: bool
    source_rows: int | None
    preview_rows: int | None
    estimated_bytes: int | None


def _effective_deadline(
    limits: InferenceLimits, deadline: float | None
) -> float | None:
    if deadline is not None:
        return deadline
    if limits.timeout_seconds is None:
        return None
    return time.monotonic() + limits.timeout_seconds


def _check_deadline(deadline: float | None) -> None:
    if deadline is not None and time.monotonic() >= deadline:
        raise _InferenceTimeout


def _bounded_row_count(value: Any) -> int | None:
    try:
        return max(0, len(value))
    except Exception:
        pass
    try:
        rows = getattr(value, "rows", None)
    except Exception:
        return None
    if rows is None:
        return None
    try:
        return max(0, len(rows))
    except Exception:
        return None


def _provider_logical_type(value: Any) -> str:
    normalized = normalize_logical_type(value, preserve_decimal=True)
    return normalized if normalized in _KNOWN_LOGICAL_TYPES else "unknown"


def _schema_result(schema: NormalizedSchema) -> InferenceResult:
    return InferenceResult(
        schema,
        provenance={
            "source": "metadata",
            "method": "provider_schema",
            "provider_required_fields": [field.name for field in schema.fields],
            "provider_nullable_fields": [field.name for field in schema.fields],
        },
    )


def _provider_materialized_limit(limits: InferenceLimits) -> int | None:
    return (
        limits.max_materialized_bytes
        if limits.max_materialized_bytes is not None
        else limits.max_bytes
    )


def _provider_size_estimate(
    value: Any,
    *,
    byte_limit: int | None,
    deadline: float | None,
) -> int | None:
    """Use provider metadata to prove the view fits before converting its rows."""
    for attr in ("estimated_size", "nbytes", "byte_size", "memory_usage"):
        try:
            candidate = getattr(value, attr, None)
            estimate = (
                candidate(index=True)
                if attr == "memory_usage" and callable(candidate)
                else (candidate() if callable(candidate) else candidate)
            )
            if attr == "memory_usage":
                sum_method = getattr(estimate, "sum", None)
                if callable(sum_method):
                    estimate = sum_method()
            item_method = getattr(estimate, "item", None)
            if callable(item_method):
                estimate = item_method()
            if isinstance(estimate, (int, float)) and math.isfinite(estimate):
                return max(0, int(estimate))
        except Exception:
            continue
    try:
        rows = getattr(value, "rows", None)
        if rows is not None:
            return _estimate_size(
                rows,
                max_bytes=byte_limit,
                max_items=10_000,
                deadline=deadline,
            )
    except Exception:
        _check_deadline(deadline)
        if byte_limit is not None:
            return byte_limit + 1
    return None


def _bounded_materialization(
    value: Any,
    limits: InferenceLimits,
    *,
    deadline: float | None = None,
) -> _BoundedView | None:
    """Return a bounded provider view and proof metadata before row conversion."""
    deadline = _effective_deadline(limits, deadline)
    _check_deadline(deadline)
    head = getattr(value, "head", None)
    _check_deadline(deadline)
    if not callable(head):
        return None
    source_rows = _bounded_row_count(value)
    _check_deadline(deadline)
    module = type(value).__module__.split(".", 1)[0].casefold()
    probe_count = limits.max_rows
    if source_rows is None and module in {"pandas", "polars", "pyarrow", "duckdb"}:
        probe_count += 1
    try:
        bounded = head(probe_count)
    except Exception:
        _check_deadline(deadline)
        return None
    _check_deadline(deadline)
    # A provider that returns itself from ``head`` has not established a
    # bounded materialization boundary.  Calling its conversion method could
    # still consume the complete source.
    if bounded is value:
        return None
    row_count = _bounded_row_count(bounded)
    _check_deadline(deadline)
    truncated = source_rows > limits.max_rows if source_rows is not None else False
    if row_count is not None and row_count > limits.max_rows:
        truncated = True
        try:
            bounded = head(limits.max_rows)
        except Exception:
            _check_deadline(deadline)
            return None
        _check_deadline(deadline)
        if bounded is value:
            return None
        row_count = _bounded_row_count(bounded)
        if row_count is not None and row_count > limits.max_rows:
            return None
    elif source_rows is None and row_count is None:
        truncated = True
    elif source_rows is None and row_count == limits.max_rows:
        # Without a source count, a full head cannot prove whether additional
        # rows exist. Keep the result provisional at the exact boundary.
        truncated = True
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
    materialized_limit = _provider_materialized_limit(limits)
    estimate = _provider_size_estimate(
        bounded, byte_limit=materialized_limit, deadline=deadline
    )
    _check_deadline(deadline)
    if (
        materialized_limit is not None
        and estimate is not None
        and estimate > materialized_limit
    ):
        raise _MaterializedLimitReached
    return _BoundedView(
        bounded,
        truncated,
        source_rows,
        row_count,
        estimate,
    )


def _provider_name(value: Any) -> str:
    module = type(value).__module__.split(".", 1)[0].casefold()
    if module in {"pandas", "polars", "pyarrow", "duckdb", "datafusion"}:
        return module
    return type(value).__name__


def _provider_provenance(
    result: InferenceResult,
    value: Any,
    limits: InferenceLimits,
    method: str,
    preview: _BoundedView | None,
    *,
    limit_reason: str | None = None,
    inference_sampled: bool = False,
) -> dict[str, Any]:
    limitations: list[str] = []
    if preview is None:
        limitations.append("bounded_preview_unavailable")
    elif preview.truncated:
        limitations.append("provider_preview_truncated_or_unverified")
    elif result.provenance.get("sampled") is True or inference_sampled:
        limitations.append("provider_preview_limited")
    provenance = {
        **result.provenance,
        "source": _provider_name(value),
        "provider_name": _provider_name(value),
        "method": method,
        "inspection_method": method,
        "limits": limits.to_dict(),
        "sampled": (bool(preview.truncated) if preview is not None else False)
        or bool(result.provenance.get("sampled", False))
        or inference_sampled,
        "limitations": limitations,
        "effective_materialized_bytes_limit": _provider_materialized_limit(limits),
        **(
            {"preview_rows_observed": preview.preview_rows}
            if preview is not None and preview.preview_rows is not None
            else {}
        ),
        **(
            {"preview_estimated_bytes": preview.estimated_bytes}
            if preview is not None and preview.estimated_bytes is not None
            else {}
        ),
    }
    if limit_reason is not None:
        provenance.update(
            {
                "sampled": True,
                "limit_reason": limit_reason,
                "limit_reasons": [limit_reason],
                "limitations": [
                    "provider_timeout"
                    if limit_reason == "time"
                    else "provider_materialized_bytes_limit"
                ],
            }
        )
    return provenance


def _provider_failure(
    identity: str,
    value: Any,
    limits: InferenceLimits,
    method: str,
    code: str,
    message: str,
    *,
    limit_reason: str | None = None,
) -> InferenceResult:
    result = InferenceResult(
        NormalizedSchema(identity=identity, fields=()),
        (
            Diagnostic(
                code,
                Severity.ERROR,
                message,
                phase="inference",
            ),
        ),
        provenance={"source": _provider_name(value)},
    )
    provenance = _provider_provenance(
        result, value, limits, method, None, limit_reason=limit_reason
    )
    return result.replace(provenance=provenance)


def _mark_provider_evidence(
    evidence: tuple[SchemaEvidence, ...], *, truncated: bool
) -> tuple[SchemaEvidence, ...]:
    if not truncated:
        return evidence
    return tuple(
        SchemaEvidence(
            field=item.field,
            observed_values=item.observed_values,
            null_values=item.null_values,
            missing_values=item.missing_values,
            type_counts=dict(item.type_counts),
            sampled=True,
            method=item.method,
            confidence=min(item.confidence, 0.7)
            if item.confidence is not None
            else 0.7,
            limitations=tuple(
                dict.fromkeys(
                    (*item.limitations, "provider_preview_truncated_or_unverified")
                )
            ),
        )
        for item in evidence
    )


def _provider_schema_from_preview(
    schema: NormalizedSchema,
    preview_schema: NormalizedSchema,
    *,
    provisional: bool,
    conservative: bool,
    required_fields: tuple[str, ...] = (),
    nullable_fields: tuple[str, ...] = (),
) -> NormalizedSchema:
    preview_fields = {field.name: field for field in preview_schema.fields}
    if provisional:
        required = set(required_fields)
        nullable = set(nullable_fields)
        return NormalizedSchema(
            identity=schema.identity,
            fields=tuple(
                NormalizedField(
                    name=field.name,
                    logical_type=field.logical_type,
                    required=(
                        field.required and preview_fields[field.name].required
                        if (
                            field.name in required
                            and field.name in preview_fields
                            and not conservative
                        )
                        else False
                    ),
                    nullable=(
                        field.nullable or preview_fields[field.name].nullable
                        if (
                            field.name in nullable
                            and field.name in preview_fields
                            and not conservative
                        )
                        else True
                    ),
                    metadata=dict(field.metadata),
                )
                for field in schema.fields
            ),
            metadata=dict(schema.metadata),
        )
    if conservative:
        return schema
    if conservative:
        return schema
    fields = tuple(
        NormalizedField(
            name=field.name,
            logical_type=field.logical_type,
            required=(
                False
                if conservative
                else field.required and preview_fields.get(field.name, field).required
            ),
            nullable=(
                True
                if conservative
                else field.nullable or preview_fields.get(field.name, field).nullable
            ),
            metadata=dict(field.metadata),
        )
        for field in schema.fields
    )
    return NormalizedSchema(
        identity=schema.identity,
        fields=fields,
        metadata=dict(schema.metadata),
    )


def _infer_provider_records(
    records: list[Any],
    value: Any,
    preview: _BoundedView,
    *,
    limits: InferenceLimits,
    hints: Mapping[str, Any] | None,
    identity: str,
    method: str,
    deadline: float | None = None,
    extra_diagnostics: tuple[Diagnostic, ...] = (),
) -> InferenceResult:
    result = infer_records(
        records,
        hints=hints,
        limits=limits,
        identity=identity,
        retain_rows=True,
        _deadline=deadline,
    )
    sampled = preview.truncated or result.provenance.get("sampled") is True
    schema = _provider_schema_from_preview(
        result.schema,
        result.schema,
        provisional=sampled,
        conservative=True,
    )
    provenance = _provider_provenance(result, value, limits, method, preview)
    provenance.update(
        {
            "preview_bytes_observed": result.provenance.get(
                "materialized_bytes_observed", 0
            ),
            "preview_available": True,
        }
    )
    return result.replace(
        schema=schema,
        evidence=_mark_provider_evidence(result.evidence, truncated=sampled),
        diagnostics=(
            *extra_diagnostics,
            *result.diagnostics,
        )[: limits.max_diagnostics],
        provenance=provenance,
    )


def _provider_records(
    bounded: Any,
    limits: InferenceLimits,
    *,
    deadline: float | None = None,
) -> list[Any]:
    """Stream a bounded provider view and retain rows only within the byte cap."""
    deadline = _effective_deadline(limits, deadline)
    _check_deadline(deadline)
    module = type(bounded).__module__.split(".", 1)[0].casefold()
    row_iterator: Iterable[Any]
    if isinstance(bounded, Mapping):
        row_iterator = cast(Iterable[Any], (bounded,))
    elif callable(getattr(bounded, "iter_rows", None)):
        row_iterator = bounded.iter_rows(named=True)
    elif module == "pandas":
        columns = tuple(str(name) for name in bounded.columns)
        if len(set(columns)) != len(columns):
            raise _UnboundedProvider("provider columns are not unique")
        row_iterator = (
            dict(zip(columns, values, strict=True))
            for values in bounded.itertuples(index=False, name=None)
        )
    elif module == "pyarrow":
        row_count = _bounded_row_count(bounded)
        slice_rows = getattr(bounded, "slice", None)
        if row_count is None or not callable(slice_rows):
            raise _UnboundedProvider("provider has no bounded row iterator")

        def arrow_rows() -> Iterable[Any]:
            for index in range(row_count):
                row_values = cast(
                    list[Any], cast(Any, slice_rows(index, 1)).to_pylist()
                )
                if len(row_values) != 1:
                    raise _UnboundedProvider("provider row conversion is unbounded")
                yield row_values[0]

        row_iterator = arrow_rows()
    elif module == "datafusion":
        execute_stream = getattr(bounded, "execute_stream", None)
        if not callable(execute_stream):
            raise _UnboundedProvider("provider has no bounded row stream")
        stream = cast(Iterable[Any], execute_stream())

        def datafusion_rows() -> Iterable[Any]:
            for batch in stream:
                to_pyarrow = getattr(batch, "to_pyarrow", None)
                if not callable(to_pyarrow):
                    raise _UnboundedProvider("provider batch conversion is unsupported")
                arrow_batch = to_pyarrow()
                row_count = _bounded_row_count(arrow_batch)
                slice_rows = getattr(arrow_batch, "slice", None)
                if row_count is None or not callable(slice_rows):
                    raise _UnboundedProvider("provider batch conversion is unbounded")
                for index in range(row_count):
                    row_values = cast(
                        list[Any], cast(Any, slice_rows(index, 1)).to_pylist()
                    )
                    if len(row_values) != 1:
                        raise _UnboundedProvider("provider row conversion is unbounded")
                    yield row_values[0]

        row_iterator = datafusion_rows()
    elif callable(getattr(bounded, "fetchmany", None)) and isinstance(
        getattr(bounded, "columns", None), (list, tuple)
    ):
        columns = tuple(str(name) for name in bounded.columns)
        fetchmany = bounded.fetchmany

        def fetched_rows() -> Iterable[Any]:
            while True:
                batch = fetchmany(1)
                if not batch:
                    break
                if len(batch) != 1:
                    raise _UnboundedProvider("provider ignored the bounded fetch size")
                row = batch[0]
                if isinstance(row, Mapping):
                    yield row
                else:
                    yield dict(zip(columns, row, strict=True))

        row_iterator = fetched_rows()
    else:
        rows = getattr(bounded, "rows", None)
        if rows is not None:
            row_iterator = cast(Iterable[Any], rows)
        elif getattr(bounded, "__etlantic_bounded_view__", False):
            try:
                row_iterator = iter(bounded)
            except Exception:
                raise _UnboundedProvider(
                    "bounded provider view has no row iterator"
                ) from None
        else:
            # ``to_dicts`` and ``to_dict`` typically allocate the complete
            # converted table before inference can account for its byte size.
            raise _UnboundedProvider("provider exposes only materializing converters")

    _check_deadline(deadline)
    materialized_limit = _provider_materialized_limit(limits)
    records: list[Any] = []
    bytes_observed = 0
    try:
        iterator = iter(cast(Iterable[Any], row_iterator))
    except Exception:
        raise _UnboundedProvider("provider rows are not iterable") from None
    _check_deadline(deadline)
    for record in iterator:
        _check_deadline(deadline)
        if len(records) >= limits.max_rows:
            raise _UnboundedProvider("provider conversion exceeded max_rows")
        if not isinstance(record, Mapping):
            raise _UnboundedProvider("provider row is not a mapping")
        if materialized_limit is not None:
            try:
                record_bytes = estimate_materialized_row(
                    record,
                    bytes_observed=bytes_observed,
                    byte_limit=materialized_limit,
                    deadline=deadline,
                )
            except Exception:
                _check_deadline(deadline)
                raise _UnboundedProvider(
                    "provider row size could not be bounded"
                ) from None
            if record_bytes is None:
                raise _MaterializedLimitReached
            bytes_observed += record_bytes
        records.append(record)
        _check_deadline(deadline)
    _check_deadline(deadline)
    return records


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
            result,
            provenance={
                "source": "metadata",
                "method": method,
                "provider_required_fields": [field.name for field in result.fields],
                "provider_nullable_fields": [field.name for field in result.fields],
            },
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
    provider_required_fields: list[str] = []
    provider_nullable_fields: list[str] = []
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
                if "required" in item:
                    provider_required_fields.append(str(item["name"]))
                if "nullable" in item:
                    provider_nullable_fields.append(str(item["name"]))
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
                if hasattr(field, "required"):
                    provider_required_fields.append(str(field_name))
                if hasattr(field, "nullable"):
                    provider_nullable_fields.append(str(field_name))
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
        provenance={
            "source": "metadata",
            "method": method,
            "provider_required_fields": provider_required_fields,
            "provider_nullable_fields": provider_nullable_fields,
        },
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
    deadline: float | None = None,
) -> InferenceResult:
    """Retain a bounded preview when metadata-first providers expose one.

    Schema inspection must stay metadata first, but user-facing dataframe
    constructors promise a preview as well. The preview is obtained only
    through the same bounded head boundary. Provider logical types remain
    authoritative while observed nullability is refined from the bounded
    preview.
    """
    deadline = _effective_deadline(limits, deadline)
    method = str(result.provenance.get("method") or "provider_schema")
    try:
        bounded_preview = _bounded_materialization(value, limits, deadline=deadline)
    except _InferenceTimeout:
        return result.replace(
            diagnostics=(
                Diagnostic(
                    "INFER_LIMIT",
                    Severity.ERROR,
                    "Provider inference time limit reached",
                    phase="inference",
                ),
                *result.diagnostics,
            )[: limits.max_diagnostics],
            provenance=_provider_provenance(
                result, value, limits, method, None, limit_reason="time"
            ),
        )
    except _MaterializedLimitReached:
        return result.replace(
            diagnostics=(
                Diagnostic(
                    "INFER_LIMIT",
                    Severity.ERROR,
                    "Provider materialized-byte limit reached",
                    phase="inference",
                ),
                *result.diagnostics,
            ),
            provenance=_provider_provenance(
                result,
                value,
                limits,
                method,
                None,
                limit_reason="materialized_bytes",
            ),
        )
    if bounded_preview is None:
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
                ),
                provenance=_provider_provenance(result, value, limits, method, None),
            )
        return result.replace(
            provenance=_provider_provenance(result, value, limits, method, None)
        )
    try:
        records = _provider_records(bounded_preview.value, limits, deadline=deadline)
        preview = infer_records(
            records,
            hints=hints,
            limits=limits,
            identity=identity,
            retain_rows=True,
            _deadline=deadline,
        )
    except _InferenceTimeout:
        return result.replace(
            diagnostics=(
                Diagnostic(
                    "INFER_LIMIT",
                    Severity.ERROR,
                    "Provider inference time limit reached",
                    phase="inference",
                ),
                *result.diagnostics,
            )[: limits.max_diagnostics],
            provenance=_provider_provenance(
                result,
                value,
                limits,
                method,
                bounded_preview,
                limit_reason="time",
            ),
        )
    except _MaterializedLimitReached:
        return result.replace(
            diagnostics=(
                Diagnostic(
                    "INFER_LIMIT",
                    Severity.ERROR,
                    "Provider materialized-byte limit reached",
                    phase="inference",
                ),
                *result.diagnostics,
            )[: limits.max_diagnostics],
            provenance=_provider_provenance(
                result,
                value,
                limits,
                method,
                bounded_preview,
                limit_reason="materialized_bytes",
            ),
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
            ),
            provenance=_provider_provenance(
                result, value, limits, method, bounded_preview
            ),
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
            ),
            provenance=_provider_provenance(
                result, value, limits, method, bounded_preview
            ),
        )
    preview_sampled = bool(preview.provenance.get("sampled", False))
    observed_schema = _provider_schema_from_preview(
        result.schema,
        preview.schema,
        provisional=bounded_preview.truncated or preview_sampled,
        conservative=False,
        required_fields=tuple(result.provenance.get("provider_required_fields", ())),
        nullable_fields=tuple(result.provenance.get("provider_nullable_fields", ())),
    )
    provenance = _provider_provenance(
        result,
        value,
        limits,
        method,
        bounded_preview,
        inference_sampled=preview_sampled,
    )
    if preview_sampled:
        preview_limit_reason = preview.provenance.get("limit_reason")
        if preview_limit_reason is not None:
            provenance["limit_reason"] = preview_limit_reason
        limit_reasons = [
            *provenance.get("limit_reasons", ()),
            *preview.provenance.get("limit_reasons", ()),
        ]
        provenance["limit_reasons"] = list(dict.fromkeys(limit_reasons))
    provenance.update(
        {
            "preview_rows_observed": preview.provenance.get(
                "rows_observed", len(preview.rows)
            ),
            "preview_bytes_observed": preview.provenance.get("bytes_observed", 0),
            "preview_available": True,
        }
    )
    return result.replace(
        schema=observed_schema,
        rows=preview.rows,
        replay=preview.replay,
        evidence=_mark_provider_evidence(
            preview.evidence,
            truncated=bounded_preview.truncated or preview_sampled,
        ),
        diagnostics=(
            *result.diagnostics,
            *preview.diagnostics,
        )[: limits.max_diagnostics],
        provenance=provenance,
    )


def infer_source(
    value: Any,
    *,
    identity: str = "source",
    hints: Mapping[str, Any] | None = None,
    limits: InferenceLimits | None = None,
    _deadline: float | None = None,
) -> InferenceResult:
    """Infer a source using metadata first and bounded records as a fallback.

    Optional engines are detected by their public duck typed conversion hooks;
    importing an optional engine is never required by this function.
    """
    limits = limits or InferenceLimits()
    deadline = _effective_deadline(limits, _deadline)
    if isinstance(value, NormalizedSchema):
        return _schema_result(value)
    direct_schema = None
    if isinstance(value, Mapping):
        if not _looks_like_schema_mapping(value):
            result = infer_records(
                value,
                hints=hints,
                limits=limits,
                identity=identity,
                _deadline=deadline,
            )
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
            deadline=deadline,
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
                    result,
                    value,
                    limits=limits,
                    hints=hints,
                    identity=identity,
                    deadline=deadline,
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
                    result,
                    value,
                    limits=limits,
                    hints=hints,
                    identity=identity,
                    deadline=deadline,
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
                    deadline=deadline,
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
                deadline=deadline,
            )
    to_dicts = getattr(value, "to_dicts", None)
    if callable(to_dicts):
        method = "to_dicts"
        try:
            bounded_preview = _bounded_materialization(value, limits, deadline=deadline)
        except _InferenceTimeout:
            return _provider_failure(
                identity,
                value,
                limits,
                method,
                "INFER_LIMIT",
                "Provider inference time limit reached",
                limit_reason="time",
            )
        except _MaterializedLimitReached:
            return _provider_failure(
                identity,
                value,
                limits,
                method,
                "INFER_LIMIT",
                "Provider materialized-byte limit reached",
                limit_reason="materialized_bytes",
            )
        if bounded_preview is None:
            return _provider_failure(
                identity,
                value,
                limits,
                method,
                "INFER_SOURCE_UNBOUNDED",
                "Source exposes records but no provably bounded materialization",
            )
        try:
            records = _provider_records(
                bounded_preview.value, limits, deadline=deadline
            )
        except _InferenceTimeout:
            return _provider_failure(
                identity,
                value,
                limits,
                method,
                "INFER_LIMIT",
                "Provider inference time limit reached",
                limit_reason="time",
            )
        except _MaterializedLimitReached:
            return _provider_failure(
                identity,
                value,
                limits,
                method,
                "INFER_LIMIT",
                "Provider materialized-byte limit reached",
                limit_reason="materialized_bytes",
            )
        except _UnboundedProvider:
            return _provider_failure(
                identity,
                value,
                limits,
                method,
                "INFER_SOURCE_UNBOUNDED",
                "Provider conversion could not prove the configured bounds",
            )
        except Exception:
            return _provider_failure(
                identity,
                value,
                limits,
                method,
                "INFER_SOURCE_UNSUPPORTED",
                "Bounded provider conversion failed",
            )
        return _infer_provider_records(
            records,
            value,
            bounded_preview,
            limits=limits,
            hints=hints,
            identity=identity,
            method=method,
            deadline=deadline,
            extra_diagnostics=(schema_diagnostic,)
            if schema_diagnostic is not None
            else (),
        )
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        method = "to_dict"
        try:
            bounded_preview = _bounded_materialization(value, limits, deadline=deadline)
        except _InferenceTimeout:
            return _provider_failure(
                identity,
                value,
                limits,
                method,
                "INFER_LIMIT",
                "Provider inference time limit reached",
                limit_reason="time",
            )
        except _MaterializedLimitReached:
            return _provider_failure(
                identity,
                value,
                limits,
                method,
                "INFER_LIMIT",
                "Provider materialized-byte limit reached",
                limit_reason="materialized_bytes",
            )
        if bounded_preview is None:
            return _provider_failure(
                identity,
                value,
                limits,
                method,
                "INFER_SOURCE_UNBOUNDED",
                "Source exposes records but no provably bounded materialization",
            )
        try:
            converted = _provider_records(
                bounded_preview.value, limits, deadline=deadline
            )
        except _InferenceTimeout:
            return _provider_failure(
                identity,
                value,
                limits,
                method,
                "INFER_LIMIT",
                "Provider inference time limit reached",
                limit_reason="time",
            )
        except _MaterializedLimitReached:
            return _provider_failure(
                identity,
                value,
                limits,
                method,
                "INFER_LIMIT",
                "Provider materialized-byte limit reached",
                limit_reason="materialized_bytes",
            )
        except _UnboundedProvider:
            return _provider_failure(
                identity,
                value,
                limits,
                method,
                "INFER_SOURCE_UNBOUNDED",
                "Provider conversion could not prove the configured bounds",
            )
        except Exception:
            return _provider_failure(
                identity,
                value,
                limits,
                method,
                "INFER_SOURCE_UNSUPPORTED",
                "Bounded provider conversion failed",
            )
        result = infer_records(
            converted,
            hints=hints,
            limits=limits,
            identity=identity,
            retain_rows=True,
            _deadline=deadline,
        )
        if not converted and not result.schema.fields:
            column_schema = _schema_from_column_metadata(value, identity=identity)
            if column_schema is not None:
                result = column_schema.replace(
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
                return result.replace(
                    provenance=_provider_provenance(
                        result, value, limits, method, bounded_preview
                    )
                )
        return _infer_provider_records(
            converted,
            value,
            bounded_preview,
            limits=limits,
            hints=hints,
            identity=identity,
            method=method,
            deadline=deadline,
        )
    if isinstance(value, Mapping) or hasattr(value, "__iter__"):
        return infer_records(
            value,
            hints=hints,
            limits=limits,
            identity=identity,
            _deadline=deadline,
        )
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
    deadline = _effective_deadline(limits, None)
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
                    result,
                    value,
                    limits=limits,
                    hints=hints,
                    identity=identity,
                    deadline=deadline,
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
                        result,
                        value,
                        limits=limits,
                        hints=hints,
                        identity=identity,
                        deadline=deadline,
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
    return infer_source(
        value,
        identity=identity,
        hints=hints,
        limits=limits,
        _deadline=deadline,
    )
