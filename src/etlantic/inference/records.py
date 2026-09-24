# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnnecessaryIsInstance=false
"""Bounded schema inference for mappings, iterables, and CSV files."""

from __future__ import annotations

import csv
import datetime as _dt
import hashlib
import json
import math
import re
import sys
import time
from collections.abc import Iterable, Mapping
from contextlib import contextmanager
from decimal import Decimal
from itertools import chain
from pathlib import Path
from typing import Any

from etlantic.diagnostics import Diagnostic, Severity
from etlantic.schema_drift import (
    NormalizedField,
    NormalizedSchema,
    normalize_logical_type,
    normalize_schema_from_fields,
)

from .types import InferenceLimits, InferenceResult, ReplayHandle, SchemaEvidence

_INT = re.compile(r"^[+-]?\d+$")
_NUMBER = re.compile(r"^[+-]?(?:\d+\.\d*|\d*\.\d+|\d+)(?:[eE][+-]?\d+)?$")
_DATE_ONLY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_KNOWN_LOGICAL_TYPES = frozenset(
    {
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
)
_APPROVED_PROVIDER_MODULES = frozenset(
    {
        "arrow",
        "datafusion",
        "duckdb",
        "numpy",
        "pandas",
        "polars",
        "pyarrow",
        "pyspark",
    }
)


def _path_identity(kind: str, path: str | Path) -> str:
    """Return a stable identity without placing an absolute path in metadata."""
    resolved = str(Path(path).expanduser().resolve())
    digest = hashlib.sha256(resolved.encode("utf-8")).hexdigest()[:20]
    return f"{kind}:{digest}"


def _diag(
    code: str,
    message: str,
    *,
    severity: Severity = Severity.WARNING,
    path: tuple[str, ...] = (),
) -> Diagnostic:
    return Diagnostic(
        code=code, severity=severity, message=message, path=path, phase="inference"
    )


def _append_diag(
    diagnostics: list[Diagnostic], diagnostic: Diagnostic, limit: int
) -> None:
    """Keep diagnostic collection bounded while retaining the first findings."""
    if len(diagnostics) < limit:
        diagnostics.append(diagnostic)


def _guarded_iterator(
    iterator: Iterable[Any], diagnostics: list[Diagnostic], limit: int
) -> Iterable[Any]:
    """Turn provider iterator failures into bounded inference diagnostics."""
    try:
        yield from iterator
    except Exception as exc:
        _append_diag(
            diagnostics,
            _diag(
                "INFER_SOURCE_UNSUPPORTED",
                f"Record provider failed during iteration: {type(exc).__name__}",
                severity=Severity.ERROR,
            ),
            limit,
        )


def _csv_row(
    row: Mapping[str | None, Any],
    *,
    fieldnames: list[str],
    null_values: set[str],
    diagnostics: list[Diagnostic],
    max_diagnostics: int,
) -> dict[str, Any]:
    """Normalize one DictReader row and diagnose ragged records."""
    extras = row.get(None)
    if extras:
        _append_diag(
            diagnostics,
            _diag("INFER_CSV_ROW", "CSV row contains more values than the header"),
            max_diagnostics,
        )
    if any(row.get(name) is None for name in fieldnames):
        _append_diag(
            diagnostics,
            _diag("INFER_CSV_ROW", "CSV row contains fewer values than the header"),
            max_diagnostics,
        )
    return {name: _parse_csv_value(row.get(name), null_values) for name in fieldnames}


@contextmanager
def _csv_field_limit(max_bytes: int | None):
    """Bound csv's internal field buffer and restore its process-global setting."""
    previous = csv.field_size_limit()
    try:
        if max_bytes is not None:
            csv.field_size_limit(max(1, min(previous, max_bytes)))
        yield
    finally:
        csv.field_size_limit(previous)


def _type_of(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, float) and math.isnan(value):
        return "null"
    module = type(value).__module__.split(".", 1)[0].casefold()
    provider_type = (
        normalize_logical_type(type(value), preserve_decimal=True)
        if module in _APPROVED_PROVIDER_MODULES
        else "unknown"
    )
    if provider_type in _KNOWN_LOGICAL_TYPES:
        if provider_type == "number":
            try:
                if math.isnan(value):
                    return "null"
            except (TypeError, ValueError, OverflowError):
                pass
        elif provider_type in {"date", "datetime"}:
            try:
                if value != value:
                    return "null"
            except Exception:
                pass
        if provider_type == "null":
            return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, Decimal):
        return "decimal"
    if isinstance(value, _dt.datetime):
        return "datetime"
    if isinstance(value, _dt.date):
        return "date"
    if isinstance(value, (bytes, bytearray, memoryview)):
        return "binary"
    if isinstance(value, str):
        return "string"
    if isinstance(value, Mapping):
        return "object"
    if isinstance(value, (list, tuple, set, frozenset)):
        return "array"
    if provider_type in _KNOWN_LOGICAL_TYPES:
        return provider_type
    return "unknown"


def _qualified_type_name(value: Any) -> str:
    """Return a stable type token without invoking provider value reprs."""
    value_type: type[Any] = type(value)
    module = getattr(value_type, "__module__", "")
    qualname = getattr(value_type, "__qualname__", value_type.__name__)
    if isinstance(module, str) and module and isinstance(qualname, str) and qualname:
        return f"{module}.{qualname}"
    return str(qualname) if isinstance(qualname, str) else "unknown"


def _parse_csv_value(value: str | None, null_values: set[str] | None = None) -> Any:
    if value is None or value in (null_values or {""}):
        return None
    text = value.strip()
    if text.lower() in {"true", "false"}:
        return text.lower() == "true"
    if _INT.fullmatch(text):
        try:
            return int(text)
        except ValueError:
            pass
    if _NUMBER.fullmatch(text):
        try:
            # Keep the coefficient and scale intact.  Converting through
            # binary float here would corrupt large identifiers and money-like
            # values before schema inference or preview materialization.
            return Decimal(text)
        except ValueError:
            pass
    if _DATE_ONLY.fullmatch(text):
        try:
            return _dt.date.fromisoformat(text)
        except ValueError:
            pass
    try:
        return _dt.datetime.fromisoformat(text)
    except ValueError:
        try:
            return _dt.date.fromisoformat(text)
        except ValueError:
            return value


def _promote(types: set[str]) -> tuple[str, bool]:
    non_null = types - {"null"}
    if not non_null:
        return "unknown", False
    if "unknown" in non_null:
        return "unknown", len(non_null) > 1
    if len(non_null) == 1:
        return next(iter(non_null)), False
    if non_null <= {"integer", "number"}:
        return "number", False
    if non_null <= {"integer", "decimal"}:
        return "decimal", False
    if non_null <= {"integer", "decimal", "number"}:
        # Decimal is the lossless common representation.  Promoting this
        # mixture to binary number silently loses precision for large values.
        return "decimal", False
    if non_null <= {"date", "datetime"}:
        return "datetime", False
    # Heterogeneous values are representable as strings only when all values
    # are scalar.  Keep a diagnostic so callers can choose strict handling.
    if non_null <= {
        "boolean",
        "integer",
        "number",
        "decimal",
        "string",
        "date",
        "datetime",
        "binary",
    }:
        return "string", True
    return "object", True


def _hint_type(hint: Any) -> str | None:
    if hint is None:
        return None
    if isinstance(hint, str):
        aliases = {
            "int": "integer",
            "integer": "integer",
            "float": "number",
            "double": "number",
            "number": "number",
            "decimal": "decimal",
            "str": "string",
            "string": "string",
            "bool": "boolean",
            "boolean": "boolean",
            "bytes": "binary",
            "binary": "binary",
            "date": "date",
            "datetime": "datetime",
            "object": "object",
            "dict": "object",
            "array": "array",
            "list": "array",
        }
        return aliases.get(hint.lower())
    mapping = {
        bool: "boolean",
        int: "integer",
        float: "number",
        Decimal: "decimal",
        bytes: "binary",
        str: "string",
        _dt.date: "date",
        _dt.datetime: "datetime",
        dict: "object",
        list: "array",
    }
    return mapping.get(hint)


def _estimate_size(value: Any, *, depth: int = 0) -> int:
    """Estimate bounded input bytes without serializing or emitting values."""
    if depth > 4:
        return sys.getsizeof(value)
    if value is None:
        return 4
    if isinstance(value, str):
        return len(value.encode("utf-8"))
    if isinstance(value, (bytes, bytearray, memoryview)):
        return len(value)
    if isinstance(value, Mapping):
        return sum(
            _estimate_size(key, depth=depth + 1) + _estimate_size(item, depth=depth + 1)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple, set, frozenset)):
        return sum(_estimate_size(item, depth=depth + 1) for item in value)
    return sys.getsizeof(value)


def infer_records(
    records: Iterable[Mapping[str, Any]] | Mapping[str, Any],
    *,
    hints: Mapping[str, Any] | None = None,
    limits: InferenceLimits | None = None,
    identity: str = "records",
    retain_rows: bool = False,
) -> InferenceResult:
    """Infer a normalized schema from an iterable of dictionaries.

    The iterable is consumed once and bounded by ``limits.max_rows``.  A
    bounded copy is retained only for the data first facade; callers that only
    need a schema can set ``retain_rows=False``.
    """
    limits = limits or InferenceLimits()
    diagnostics: list[Diagnostic] = []
    rows: list[dict[str, Any]] = []
    if isinstance(records, Mapping):
        iterator: Iterable[Any] = [records]
    else:
        iterator = records
    try:
        iterator = _guarded_iterator(
            iter(iterator), diagnostics, limits.max_diagnostics
        )
    except TypeError:
        _append_diag(
            diagnostics,
            _diag(
                "INFER_SOURCE_UNSUPPORTED",
                "Expected a mapping or iterable of mappings",
                severity=Severity.ERROR,
            ),
            limits.max_diagnostics,
        )
        return InferenceResult(
            NormalizedSchema(identity=identity, fields=()),
            tuple(diagnostics),
            provenance={"source": "records", "limits": limits.to_dict()},
        )
    names: list[str] = []
    stats: dict[str, dict[str, Any]] = {}
    sampled = False
    sampled_reason: str | None = None
    replay_remainder: Iterable[Any] | None = None
    started_at = time.monotonic()
    bytes_observed = 0
    for index, item in enumerate(iterator):
        if index >= limits.max_rows:
            sampled = True
            sampled_reason = "rows"
            replay_remainder = chain((item,), iterator)
            break
        if limits.timeout_seconds is not None and (
            limits.timeout_seconds <= 1e-9
            or time.monotonic() - started_at >= limits.timeout_seconds
        ):
            sampled = True
            sampled_reason = "time"
            replay_remainder = chain((item,), iterator)
            _append_diag(
                diagnostics,
                _diag("INFER_LIMIT", "Inference time limit reached"),
                limits.max_diagnostics,
            )
            break
        item_bytes = _estimate_size(item)
        if (
            limits.max_bytes is not None
            and bytes_observed + item_bytes > limits.max_bytes
        ):
            sampled = True
            sampled_reason = "bytes"
            replay_remainder = chain((item,), iterator)
            _append_diag(
                diagnostics,
                _diag("INFER_LIMIT", "Inference byte limit reached"),
                limits.max_diagnostics,
            )
            break
        bytes_observed += item_bytes
        if not isinstance(item, Mapping):
            _append_diag(
                diagnostics,
                _diag(
                    "INFER_INVALID_KEY",
                    f"Record {index} is not a mapping",
                    severity=Severity.ERROR,
                    path=(str(index),),
                ),
                limits.max_diagnostics,
            )
            continue
        row: dict[str, Any] = {}
        for raw_name, value in item.items():
            if not isinstance(raw_name, str) or not raw_name:
                _append_diag(
                    diagnostics,
                    _diag(
                        "INFER_INVALID_KEY",
                        f"Record {index} contains a non-string or empty field name",
                        path=(str(index),),
                    ),
                    limits.max_diagnostics,
                )
                continue
            if raw_name not in stats:
                if len(names) >= limits.max_fields:
                    _append_diag(
                        diagnostics,
                        _diag(
                            "INFER_LIMIT",
                            "Maximum inferred field count reached",
                            path=(raw_name,),
                        ),
                        limits.max_diagnostics,
                    )
                    continue
                names.append(raw_name)
                stats[raw_name] = {
                    "types": set(),
                    "unknown_types": set(),
                    "observed": 0,
                    "null": 0,
                    "missing": 0,
                }
            if isinstance(value, float) and math.isnan(value):
                value = None
            entry = stats[raw_name]
            entry["observed"] += 1
            logical = _type_of(value)
            if logical == "null":
                value = None
            row[raw_name] = value
            entry["types"].add(logical)
            if logical == "unknown":
                entry["unknown_types"].add(_qualified_type_name(value))
            if logical == "null":
                entry["null"] += 1
        rows.append(row)
    for name in names:
        stats[name]["missing"] = len(rows) - stats[name]["observed"]
        if stats[name]["missing"]:
            _append_diag(
                diagnostics,
                _diag(
                    "INFER_MISSING_FIELD",
                    f"Field {name!r} is absent from some records",
                    path=(name,),
                ),
                limits.max_diagnostics,
            )
    if sampled and sampled_reason == "rows":
        _append_diag(
            diagnostics,
            _diag("INFER_LIMIT", f"Inference stopped after {limits.max_rows} rows"),
            limits.max_diagnostics,
        )
    if not rows:
        _append_diag(
            diagnostics,
            _diag(
                "INFER_EMPTY",
                "No records were available for inference",
                severity=Severity.INFO,
            ),
            limits.max_diagnostics,
        )
    validated_hints: dict[str, str] = {}
    for hint_name, raw_hint in (hints or {}).items():
        parsed_hint = _hint_type(raw_hint)
        if parsed_hint is None:
            _append_diag(
                diagnostics,
                _diag(
                    "INFER_HINT_UNSUPPORTED",
                    f"Hint for field {hint_name!r} is not a supported logical type",
                    severity=Severity.ERROR,
                    path=(str(hint_name),),
                ),
                limits.max_diagnostics,
            )
        else:
            validated_hints[str(hint_name)] = parsed_hint
    fields: list[NormalizedField] = []
    evidence: list[SchemaEvidence] = []
    mixed_fields: set[str] = set()
    decimal_fields: set[str] = set()
    for name in names:
        entry = stats[name]
        logical, mixed = _promote(set(entry["types"]))
        hint = validated_hints.get(name)
        if hint:
            if logical == "unknown":
                logical = hint
            elif logical not in {hint} and not (
                {logical, hint} <= {"integer", "number"}
            ):
                _append_diag(
                    diagnostics,
                    _diag(
                        "INFER_HINT_CONFLICT",
                        f"Hint for field {name!r} differs from observed type {logical!r}",
                        severity=Severity.ERROR,
                        path=(name,),
                    ),
                    limits.max_diagnostics,
                )
            else:
                logical = hint
        if logical == "unknown":
            unknown_types = tuple(sorted(entry["unknown_types"]))
            if unknown_types:
                type_summary = ", ".join(unknown_types[:3])
                if len(unknown_types) > 3:
                    type_summary += ", ..."
                message = (
                    f"Field {name!r} contains unsupported value type(s): {type_summary}"
                )
            elif set(entry["types"]) == {"null"}:
                message = f"Field {name!r} contains only null values"
            else:
                message = f"Field {name!r} has no observed typed values"
            _append_diag(
                diagnostics,
                _diag(
                    "INFER_UNKNOWN_TYPE",
                    message,
                    path=(name,),
                ),
                limits.max_diagnostics,
            )
        if mixed:
            _append_diag(
                diagnostics,
                _diag(
                    "INFER_MIXED_TYPE",
                    f"Field {name!r} contains mixed value types; promoted to {logical}",
                    path=(name,),
                ),
                limits.max_diagnostics,
            )
            if logical == "string":
                mixed_fields.add(name)
        if logical in {"object", "array"}:
            _append_diag(
                diagnostics,
                _diag(
                    "INFER_NESTED_UNSUPPORTED",
                    f"Field {name!r} contains nested values; using {logical}",
                    path=(name,),
                ),
                limits.max_diagnostics,
            )
        if logical == "decimal":
            decimal_fields.add(name)
        nullable = entry["null"] > 0 or entry["missing"] > 0
        field_metadata: dict[str, Any] = {"inferred": True}
        if logical == "unknown" and not entry["unknown_types"]:
            field_metadata["inference_evidence"] = (
                "null_only" if set(entry["types"]) == {"null"} else "no_observed_values"
            )
        fields.append(
            NormalizedField(
                name=name,
                logical_type=logical,
                required=not nullable,
                nullable=nullable,
                metadata=field_metadata,
            )
        )
        evidence.append(
            SchemaEvidence(
                name,
                entry["observed"],
                entry["null"],
                entry["missing"],
                {
                    k: sum(
                        1 for row in rows if name in row and k == _type_of(row[name])
                    )
                    for k in entry["types"]
                },
                sampled,
                confidence=0.7 if sampled else 0.95,
            )
        )
    if mixed_fields:
        for row in rows:
            for name in mixed_fields:
                if name in row and row[name] is not None:
                    row[name] = str(row[name])
    if decimal_fields:
        for row in rows:
            for name in decimal_fields:
                value = row.get(name)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    row[name] = Decimal(str(value))
    schema = NormalizedSchema(
        identity=identity,
        fields=tuple(sorted(fields, key=lambda field: field.name)),
    )
    provenance = {
        "source": "records",
        "limits": limits.to_dict(),
        "sampled": sampled,
        "rows_observed": len(rows),
        "retained_rows": bool(retain_rows),
        "bytes_observed": bytes_observed,
    }
    replay = (
        ReplayHandle(rows, iter(replay_remainder))
        if replay_remainder is not None
        else None
    )
    if replay is not None and (mixed_fields or decimal_fields):

        def normalize_replay_row(row: Any) -> Any:
            if not isinstance(row, Mapping):
                return row
            normalized = dict(row)
            for name in mixed_fields:
                if name in normalized and normalized[name] is not None:
                    normalized[name] = str(normalized[name])
            for name in decimal_fields:
                value = normalized.get(name)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    normalized[name] = Decimal(str(value))
            return normalized

        replay = replay.map(normalize_replay_row)
    return InferenceResult(
        schema,
        tuple(diagnostics[: limits.max_diagnostics]),
        tuple(evidence),
        provenance,
        tuple(rows) if retain_rows else (),
        replay,
    )


def infer_csv(
    path: str | Path,
    *,
    options: Mapping[str, Any] | None = None,
    hints: Mapping[str, Any] | None = None,
    limits: InferenceLimits | None = None,
    identity: str | None = None,
    retain_rows: bool = False,
) -> InferenceResult:
    """Infer a CSV schema, parsing common scalar spellings before inference."""
    limits = limits or InferenceLimits()
    try:
        if options is not None and not isinstance(options, Mapping):
            raise TypeError("CSV options must be a mapping")
        opts = dict(options or {})
        null_values = {str(value) for value in opts.pop("null_values", {""})}
        encoding = opts.pop("encoding", "utf-8")
    except (TypeError, ValueError):
        return InferenceResult(
            NormalizedSchema(identity or _path_identity("csv", path), fields=()),
            (
                _diag(
                    "INFER_CSV_OPTIONS",
                    "CSV options are malformed",
                    severity=Severity.ERROR,
                ),
            ),
            provenance={"source": "csv", "limits": limits.to_dict()},
        )
    parser_options = {"encoding": encoding}
    parser_options.update(
        {
            key: opts[key]
            for key in (
                "delimiter",
                "quotechar",
                "escapechar",
                "doublequote",
                "strict",
            )
            if key in opts
        }
    )
    try:
        with (
            _csv_field_limit(limits.max_bytes),
            Path(path).open("r", newline="", encoding=encoding) as handle,
        ):
            reader = csv.DictReader(handle, **opts)
            if reader.fieldnames is None:
                return InferenceResult(
                    NormalizedSchema(
                        identity or _path_identity("csv", path), fields=()
                    ),
                    (
                        _diag(
                            "INFER_CSV_HEADER",
                            "CSV has no header",
                            severity=Severity.ERROR,
                        ),
                    ),
                    provenance={
                        "source": "csv",
                        "limits": limits.to_dict(),
                        "parser_options": parser_options,
                    },
                )
            fieldnames = list(reader.fieldnames)
            if any(not name for name in fieldnames) or len(set(fieldnames)) != len(
                fieldnames
            ):
                return InferenceResult(
                    NormalizedSchema(
                        identity or _path_identity("csv", path), fields=()
                    ),
                    (
                        _diag(
                            "INFER_CSV_HEADER",
                            "CSV header contains empty or duplicate field names",
                            severity=Severity.ERROR,
                        ),
                    ),
                    provenance={
                        "source": "csv",
                        "limits": limits.to_dict(),
                        "parser_options": parser_options,
                    },
                )

            row_diagnostics: list[Diagnostic] = []
            rows = (
                _csv_row(
                    row,
                    fieldnames=fieldnames,
                    null_values=null_values,
                    diagnostics=row_diagnostics,
                    max_diagnostics=limits.max_diagnostics,
                )
                for row in reader
            )
            result = infer_records(
                rows,
                hints=hints,
                limits=limits,
                identity=identity or _path_identity("csv", path),
                retain_rows=retain_rows,
            )
            header_hints = {
                name: _hint_type((hints or {}).get(name)) for name in fieldnames
            }
            header_diagnostics = [
                _diag(
                    "INFER_UNKNOWN_TYPE",
                    f"Field {name!r} has no observed typed values",
                    path=(name,),
                )
                for name in fieldnames
                if header_hints[name] is None
            ]
            diagnostics = tuple(
                (row_diagnostics + list(result.diagnostics) + header_diagnostics)[
                    : limits.max_diagnostics
                ]
            )
            if not result.schema.fields and result.provenance.get("rows_observed") == 0:
                result = InferenceResult(
                    normalize_schema_from_fields(
                        [
                            {
                                "name": name,
                                "logical_type": header_hints[name] or "unknown",
                                "required": False,
                                "nullable": True,
                                "header_only": True,
                                **(
                                    {"inference_evidence": "no_observed_values"}
                                    if header_hints[name] is None
                                    else {}
                                ),
                            }
                            for name in fieldnames
                        ],
                        identity=identity or _path_identity("csv", path),
                    ),
                    diagnostics,
                    result.evidence,
                    {
                        **result.provenance,
                        "source": "csv",
                        "header_only": True,
                        "limits": limits.to_dict(),
                        "parser_options": parser_options,
                    },
                    result.rows,
                    result.replay,
                )
            else:
                result = InferenceResult(
                    result.schema,
                    diagnostics,
                    result.evidence,
                    {
                        **result.provenance,
                        "source": "csv",
                        "limits": limits.to_dict(),
                        "parser_options": parser_options,
                    },
                    result.rows,
                    result.replay,
                )
            return result
    except (OSError, csv.Error, UnicodeError, TypeError, ValueError) as exc:
        return InferenceResult(
            NormalizedSchema(identity or _path_identity("csv", path), fields=()),
            (
                _diag(
                    "INFER_CSV_PARSE",
                    f"Unable to parse CSV: {type(exc).__name__}",
                    severity=Severity.ERROR,
                ),
            ),
            provenance={
                "source": "csv",
                "limits": limits.to_dict(),
                "parser_options": parser_options,
            },
        )


def _read_json_array(
    path: str | Path, limits: InferenceLimits
) -> tuple[list[Mapping[str, Any]], list[Diagnostic], bool, int]:
    """Read a JSON array incrementally under the inference budgets."""
    decoder = json.JSONDecoder()
    rows: list[Mapping[str, Any]] = []
    diagnostics: list[Diagnostic] = []
    buffer = ""
    bytes_observed = 0
    started_at = time.monotonic()
    sampled = False
    eof = False
    stopped = False
    items_seen = 0
    after_comma = False

    with Path(path).open("r", encoding="utf-8") as handle:

        def refill() -> bool:
            nonlocal buffer, bytes_observed, eof, sampled, stopped
            if (
                limits.timeout_seconds is not None
                and time.monotonic() - started_at >= limits.timeout_seconds
            ):
                sampled = True
                stopped = True
                _append_diag(
                    diagnostics,
                    _diag("INFER_LIMIT", "JSON inference time limit reached"),
                    limits.max_diagnostics,
                )
                return False
            chunk_size = 64 * 1024
            if limits.max_bytes is not None:
                chunk_size = min(
                    chunk_size,
                    max(1, limits.max_bytes - bytes_observed + 1),
                )
            chunk = handle.read(chunk_size)
            if not chunk:
                eof = True
                return False
            chunk_bytes = len(chunk.encode("utf-8"))
            bytes_observed += chunk_bytes
            if limits.max_bytes is not None and bytes_observed > limits.max_bytes:
                sampled = True
                stopped = True
                _append_diag(
                    diagnostics,
                    _diag("INFER_LIMIT", "JSON source byte limit reached"),
                    limits.max_diagnostics,
                )
                return False
            buffer += chunk
            return True

        def trailing_content() -> bool:
            """Return whether non-whitespace content follows the array."""
            nonlocal buffer
            while True:
                if buffer.strip():
                    return True
                buffer = ""
                if eof or stopped or not refill():
                    return False

        if not refill():
            return rows, diagnostics, sampled, bytes_observed
        buffer = buffer.lstrip()
        if not buffer.startswith("["):
            _append_diag(
                diagnostics,
                _diag(
                    "INFER_SOURCE_UNSUPPORTED",
                    "JSON root must be an array of objects",
                    severity=Severity.ERROR,
                ),
                limits.max_diagnostics,
            )
            return rows, diagnostics, sampled, bytes_observed
        buffer = buffer[1:]

        while True:
            if (
                limits.timeout_seconds is not None
                and time.monotonic() - started_at >= limits.timeout_seconds
            ):
                sampled = True
                _append_diag(
                    diagnostics,
                    _diag("INFER_LIMIT", "JSON inference time limit reached"),
                    limits.max_diagnostics,
                )
                break
            buffer = buffer.lstrip()
            if not buffer and not eof and not stopped and refill():
                continue
            if stopped:
                break
            if buffer.startswith("]"):
                if after_comma:
                    _append_diag(
                        diagnostics,
                        _diag(
                            "INFER_JSON_PARSE",
                            "JSON array has a trailing comma",
                            severity=Severity.ERROR,
                        ),
                        limits.max_diagnostics,
                    )
                else:
                    buffer = buffer[1:]
                    if trailing_content():
                        _append_diag(
                            diagnostics,
                            _diag(
                                "INFER_JSON_PARSE",
                                "JSON source contains trailing content",
                                severity=Severity.ERROR,
                            ),
                            limits.max_diagnostics,
                        )
                break
            if items_seen >= limits.max_rows:
                sampled = True
                _append_diag(
                    diagnostics,
                    _diag(
                        "INFER_LIMIT",
                        f"Inference stopped after {limits.max_rows} rows",
                    ),
                    limits.max_diagnostics,
                )
                break
            try:
                value, consumed = decoder.raw_decode(buffer)
            except json.JSONDecodeError:
                if eof or not refill():
                    _append_diag(
                        diagnostics,
                        _diag(
                            "INFER_JSON_PARSE",
                            "Unable to parse JSON array",
                            severity=Severity.ERROR,
                        ),
                        limits.max_diagnostics,
                    )
                    break
                continue
            buffer = buffer[consumed:]
            items_seen += 1
            after_comma = False
            if isinstance(value, Mapping):
                rows.append(value)
            else:
                _append_diag(
                    diagnostics,
                    _diag(
                        "INFER_JSON_ROW",
                        "JSON array item must be an object",
                        path=(str(items_seen - 1),),
                    ),
                    limits.max_diagnostics,
                )
            while not buffer and not eof and not stopped and refill():
                pass
            if stopped:
                break
            buffer = buffer.lstrip()
            if buffer.startswith(","):
                buffer = buffer[1:]
                after_comma = True
                continue
            if buffer.startswith("]"):
                buffer = buffer[1:]
                if trailing_content():
                    _append_diag(
                        diagnostics,
                        _diag(
                            "INFER_JSON_PARSE",
                            "JSON source contains trailing content",
                            severity=Severity.ERROR,
                        ),
                        limits.max_diagnostics,
                    )
                break
            if not buffer and eof:
                _append_diag(
                    diagnostics,
                    _diag(
                        "INFER_JSON_PARSE",
                        "JSON array is not terminated",
                        severity=Severity.ERROR,
                    ),
                    limits.max_diagnostics,
                )
                break
            if buffer:
                _append_diag(
                    diagnostics,
                    _diag(
                        "INFER_JSON_PARSE",
                        "JSON array separator is invalid",
                        severity=Severity.ERROR,
                    ),
                    limits.max_diagnostics,
                )
                break
    return rows, diagnostics, sampled, bytes_observed


def _infer_jsonl_bounded(
    path: str | Path,
    *,
    limits: InferenceLimits,
    hints: Mapping[str, Any] | None,
    identity: str,
    retain_rows: bool,
) -> InferenceResult:
    """Read JSON Lines through a byte-bounded binary boundary."""
    rows: list[Mapping[str, Any]] = []
    diagnostics: list[Diagnostic] = []
    bytes_observed = 0
    sampled = False
    started_at = time.monotonic()
    try:
        with Path(path).open("rb") as handle:
            line_number = 0
            loop_completed = True
            for line_number in range(1, limits.max_rows + 1):
                if (
                    limits.timeout_seconds is not None
                    and time.monotonic() - started_at >= limits.timeout_seconds
                ):
                    sampled = True
                    loop_completed = False
                    _append_diag(
                        diagnostics,
                        _diag("INFER_LIMIT", "JSONL inference time limit reached"),
                        limits.max_diagnostics,
                    )
                    break
                remaining = (
                    limits.max_bytes - bytes_observed
                    if limits.max_bytes is not None
                    else None
                )
                read_size = remaining + 1 if remaining is not None else -1
                raw = handle.readline(read_size)
                if not raw:
                    loop_completed = False
                    break
                if remaining is not None and len(raw) > remaining:
                    sampled = True
                    loop_completed = False
                    _append_diag(
                        diagnostics,
                        _diag("INFER_LIMIT", "JSONL inference byte limit reached"),
                        limits.max_diagnostics,
                    )
                    break
                bytes_observed += len(raw)
                try:
                    line = raw.decode("utf-8")
                except UnicodeDecodeError:
                    _append_diag(
                        diagnostics,
                        _diag(
                            "INFER_JSON_ROW",
                            "JSONL row is not valid UTF-8",
                            path=(str(line_number),),
                        ),
                        limits.max_diagnostics,
                    )
                    continue
                if not line.strip():
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    _append_diag(
                        diagnostics,
                        _diag(
                            "INFER_JSON_ROW",
                            "JSONL row could not be parsed",
                            path=(str(line_number),),
                        ),
                        limits.max_diagnostics,
                    )
                    continue
                if not isinstance(value, Mapping):
                    _append_diag(
                        diagnostics,
                        _diag(
                            "INFER_JSON_ROW",
                            "JSONL row must be an object",
                            path=(str(line_number),),
                        ),
                        limits.max_diagnostics,
                    )
                    continue
                rows.append(value)
            if loop_completed and line_number >= limits.max_rows:
                probe = handle.readline(1)
                if probe:
                    sampled = True
                    _append_diag(
                        diagnostics,
                        _diag("INFER_LIMIT", "JSONL inference row limit reached"),
                        limits.max_diagnostics,
                    )
            else:
                # The loop ended because the file was exhausted.  A full
                # boundary sample is therefore not a sampled result.
                pass
    except (OSError, UnicodeError) as exc:
        return InferenceResult(
            NormalizedSchema(identity=identity, fields=()),
            (
                _diag(
                    "INFER_JSON_PARSE",
                    f"Unable to parse JSON: {type(exc).__name__}",
                    severity=Severity.ERROR,
                ),
            ),
            provenance={"source": "jsonl", "limits": limits.to_dict()},
        )
    result = infer_records(
        rows,
        hints=hints,
        limits=InferenceLimits(
            max_rows=max(len(rows), 1),
            max_fields=limits.max_fields,
            max_diagnostics=limits.max_diagnostics,
            max_bytes=None,
            timeout_seconds=limits.timeout_seconds,
        ),
        identity=identity,
        retain_rows=retain_rows,
    )
    return InferenceResult(
        result.schema,
        tuple((diagnostics + list(result.diagnostics))[: limits.max_diagnostics]),
        result.evidence,
        {
            **result.provenance,
            "source": "jsonl",
            "limits": limits.to_dict(),
            "sampled": sampled,
            "bytes_observed": bytes_observed,
        },
        result.rows,
        result.replay,
    )


def infer_json(
    path: str | Path,
    *,
    lines: bool = False,
    limits: InferenceLimits | None = None,
    hints: Mapping[str, Any] | None = None,
    identity: str | None = None,
    retain_rows: bool = False,
) -> InferenceResult:
    """Infer a bounded JSON array or JSON Lines source."""
    source_id = identity or _path_identity("json", path)
    limits = limits or InferenceLimits()
    if lines:
        return _infer_jsonl_bounded(
            path,
            limits=limits,
            hints=hints,
            identity=source_id,
            retain_rows=retain_rows,
        )
    try:
        with Path(path).open("r", encoding="utf-8") as handle:
            if lines:
                rows: list[Mapping[str, Any]] = []
                diagnostics: list[Diagnostic] = []
                bytes_observed = 0
                started_at = time.monotonic()
                sampled = False
                processed_rows = 0
                for line_number, line in enumerate(handle, 1):
                    if not line.strip():
                        continue
                    if processed_rows >= limits.max_rows:
                        sampled = True
                        break
                    processed_rows += 1
                    line_bytes = len(line.encode("utf-8"))
                    if (
                        limits.timeout_seconds is not None
                        and time.monotonic() - started_at >= limits.timeout_seconds
                    ):
                        sampled = True
                        _append_diag(
                            diagnostics,
                            _diag("INFER_LIMIT", "JSONL inference time limit reached"),
                            limits.max_diagnostics,
                        )
                        break
                    if (
                        limits.max_bytes is not None
                        and bytes_observed + line_bytes > limits.max_bytes
                    ):
                        sampled = True
                        _append_diag(
                            diagnostics,
                            _diag("INFER_LIMIT", "JSONL inference byte limit reached"),
                            limits.max_diagnostics,
                        )
                        break
                    bytes_observed += line_bytes
                    try:
                        value = json.loads(line)
                    except json.JSONDecodeError:
                        _append_diag(
                            diagnostics,
                            _diag(
                                "INFER_JSON_ROW",
                                "JSONL row could not be parsed",
                                path=(str(line_number),),
                            ),
                            limits.max_diagnostics,
                        )
                        continue
                    if not isinstance(value, Mapping):
                        _append_diag(
                            diagnostics,
                            _diag(
                                "INFER_JSON_ROW",
                                "JSONL row must be an object",
                                path=(str(line_number),),
                            ),
                            limits.max_diagnostics,
                        )
                        continue
                    rows.append(value)
                result = infer_records(
                    rows,
                    hints=hints,
                    limits=InferenceLimits(
                        max_rows=max(len(rows), 1),
                        max_fields=limits.max_fields,
                        max_diagnostics=limits.max_diagnostics,
                    ),
                    identity=source_id,
                    retain_rows=retain_rows,
                )
                if sampled:
                    _append_diag(
                        diagnostics,
                        _diag(
                            "INFER_LIMIT",
                            "JSONL inference stopped at the configured limit",
                        ),
                        limits.max_diagnostics,
                    )
                return InferenceResult(
                    result.schema,
                    tuple(
                        (diagnostics + list(result.diagnostics))[
                            : limits.max_diagnostics
                        ]
                    ),
                    result.evidence,
                    {
                        **result.provenance,
                        "source": "jsonl",
                        "limits": limits.to_dict(),
                        "sampled": sampled,
                        "bytes_observed": bytes_observed,
                    },
                    result.rows,
                    result.replay,
                )
        rows, diagnostics, sampled, bytes_observed = _read_json_array(path, limits)
        result = infer_records(
            rows,
            hints=hints,
            limits=InferenceLimits(
                max_rows=max(len(rows), 1),
                max_fields=limits.max_fields,
                max_diagnostics=limits.max_diagnostics,
            ),
            identity=source_id,
            retain_rows=retain_rows,
        )
        return InferenceResult(
            result.schema,
            tuple((diagnostics + list(result.diagnostics))[: limits.max_diagnostics]),
            result.evidence,
            {
                **result.provenance,
                "source": "json",
                "limits": limits.to_dict(),
                "sampled": sampled,
                "bytes_observed": bytes_observed,
            },
            result.rows,
            result.replay,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return InferenceResult(
            NormalizedSchema(identity=source_id, fields=()),
            (
                _diag(
                    "INFER_JSON_PARSE",
                    f"Unable to parse JSON: {type(exc).__name__}",
                    severity=Severity.ERROR,
                ),
            ),
            provenance={"source": "json", "limits": limits.to_dict()},
        )
