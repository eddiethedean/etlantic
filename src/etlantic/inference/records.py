# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnnecessaryIsInstance=false
"""Bounded schema inference for mappings, iterables, and CSV files."""

from __future__ import annotations

import codecs
import csv
import datetime as _dt
import hashlib
import io
import json
import math
import os
import re
import sys
import threading
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

from .types import (
    InferenceLimits,
    InferenceReplayError,
    InferenceResult,
    ReplayHandle,
    SchemaEvidence,
)

_INT = re.compile(r"^[+-]?\d+$")
_NUMBER = re.compile(r"^[+-]?(?:\d+\.\d*|\d*\.\d+|\d+)(?:[eE][+-]?\d+)?$")
_DATE_ONLY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_CSV_FIELD_LIMIT_LOCK = threading.RLock()
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


class _CSVByteLimitReached(Exception):
    """Internal signal that the CSV raw-byte budget stopped the reader."""


class _BoundedCSVRaw(io.RawIOBase):
    """Count bytes returned by a CSV source and enforce its raw-read budget."""

    def __init__(self, source: Any, max_bytes: int | None):
        super().__init__()
        self._source = source
        self._max_bytes = max_bytes
        self.bytes_observed = 0

    def readable(self) -> bool:
        return True

    def _has_remaining_bytes(self) -> bool:
        try:
            return self._source.tell() < os.fstat(self._source.fileno()).st_size
        except (OSError, AttributeError):
            return False

    def readinto(self, buffer: Any) -> int:
        if self.closed:
            raise ValueError("I/O operation on closed CSV source")
        requested = len(buffer)
        if requested == 0:
            return 0
        if self._max_bytes is not None:
            remaining = self._max_bytes - self.bytes_observed
            if remaining <= 0:
                if self._has_remaining_bytes():
                    raise _CSVByteLimitReached
                return 0
            requested = min(requested, remaining)
        data = self._source.read(requested)
        size = len(data)
        if size:
            buffer[:size] = data
            self.bytes_observed += size
        return size


def _csv_source_signature(
    stat_result: os.stat_result,
) -> tuple[int, int, int, int, int]:
    """Identify a source version without serializing its path or contents."""
    return (
        stat_result.st_dev,
        stat_result.st_ino,
        stat_result.st_size,
        stat_result.st_mtime_ns,
        stat_result.st_ctime_ns,
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
def _csv_field_limit(max_field_size: int | None):
    """Bound csv's global field buffer while serializing parser access."""
    # csv.field_size_limit is interpreter-global, so parser contexts must not
    # overlap or restore another inference's setting.
    with _CSV_FIELD_LIMIT_LOCK:
        previous = csv.field_size_limit()
        try:
            if max_field_size is not None:
                # Honor the inference limit even when it is larger than csv's
                # process default. Clamp only to the largest size accepted by
                # the platform's C-backed csv parser.
                csv.field_size_limit(min(max_field_size, sys.maxsize))
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
    materialized_limit = (
        limits.max_materialized_bytes
        if limits.max_materialized_bytes is not None
        else limits.max_bytes
    )
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
            materialized_limit is not None
            and bytes_observed + item_bytes > materialized_limit
        ):
            sampled = True
            sampled_reason = "materialized_bytes"
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
        fields=tuple(fields),
    )
    provenance = {
        "source": "records",
        "limits": limits.to_dict(),
        "sampled": sampled,
        "rows_observed": len(rows),
        "retained_rows": bool(retain_rows),
        "bytes_observed": bytes_observed,
        "materialized_bytes_observed": bytes_observed,
        "raw_bytes_observed": None,
        "raw_byte_limit_applies": False,
        "effective_materialized_bytes_limit": materialized_limit,
        "limit_reason": sampled_reason,
        "limit_reasons": [sampled_reason] if sampled_reason else [],
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
    # Replay reopens the source after this call returns, so pin relative paths
    # to the directory in which inference began.
    source_identity = identity or "csv:unresolved"
    try:
        csv_path = Path(path).expanduser().resolve()
        source_identity = identity or _path_identity("csv", csv_path)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        return InferenceResult(
            NormalizedSchema(identity=source_identity, fields=()),
            (
                _diag(
                    "INFER_CSV_PARSE",
                    f"Unable to parse CSV: {type(exc).__name__}",
                    severity=Severity.ERROR,
                ),
            ),
            provenance={
                "source": "csv",
                "source_identity": source_identity,
                "limits": limits.to_dict(),
                "replay_status": {"state": "not_available"},
            },
        )
    try:
        if options is not None and not isinstance(options, Mapping):
            raise TypeError("CSV options must be a mapping")
        opts = dict(options or {})
        null_values = {str(value) for value in opts.pop("null_values", {""})}
        encoding = opts.pop("encoding", "utf-8")
        if not isinstance(encoding, str) or not encoding:
            raise ValueError("CSV encoding must be a non-empty string")
        codecs.lookup(encoding)
        supported_options = {
            "delimiter",
            "quotechar",
            "escapechar",
            "doublequote",
            "strict",
            "skipinitialspace",
            "quoting",
        }
        if set(opts) - supported_options:
            raise ValueError("CSV options contain unsupported parser settings")
        csv.reader((), **opts)
    except (TypeError, ValueError, LookupError, csv.Error):
        return InferenceResult(
            NormalizedSchema(identity=source_identity, fields=()),
            (
                _diag(
                    "INFER_CSV_OPTIONS",
                    "CSV options are malformed",
                    severity=Severity.ERROR,
                ),
            ),
            provenance={
                "source": "csv",
                "source_identity": source_identity,
                "limits": limits.to_dict(),
                "raw_byte_limit_applies": False,
                "replay_status": {"state": "not_required"},
            },
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
                "skipinitialspace",
                "quoting",
            )
            if key in opts
        }
    )
    materialized_limit = (
        limits.max_materialized_bytes
        if limits.max_materialized_bytes is not None
        else InferenceLimits().max_bytes
    )
    record_limits = InferenceLimits(
        max_rows=limits.max_rows,
        max_fields=limits.max_fields,
        max_diagnostics=limits.max_diagnostics,
        max_bytes=None,
        timeout_seconds=limits.timeout_seconds,
        max_materialized_bytes=materialized_limit,
        max_field_size=limits.max_field_size,
    )
    bounded_reader: _BoundedCSVRaw | None = None
    source_signature: tuple[int, int, int, int, int] | None = None
    fieldnames: list[str] = []
    row_diagnostics: list[Diagnostic] = []
    parser_diagnostics: list[Diagnostic] = []
    result: InferenceResult | None = None
    reader_state = {"raw_limit_hit": False, "field_limit_hit": False}
    try:
        with csv_path.open("rb") as raw_source:
            source_signature = _csv_source_signature(os.fstat(raw_source.fileno()))
            bounded_reader = _BoundedCSVRaw(raw_source, limits.max_bytes)
            buffered = io.BufferedReader(bounded_reader)
            with io.TextIOWrapper(buffered, encoding=encoding, newline="") as handle:
                reader = csv.DictReader(handle, **opts)
                with _csv_field_limit(limits.max_field_size):
                    raw_fieldnames = reader.fieldnames
                if raw_fieldnames is None:
                    return InferenceResult(
                        NormalizedSchema(identity=source_identity, fields=()),
                        (
                            _diag(
                                "INFER_CSV_HEADER",
                                "CSV has no header",
                                severity=Severity.ERROR,
                            ),
                        ),
                        provenance={
                            "source": "csv",
                            "source_identity": source_identity,
                            "limits": limits.to_dict(),
                            "parser_options": parser_options,
                            "raw_byte_limit_applies": limits.max_bytes is not None,
                            "raw_bytes_observed": bounded_reader.bytes_observed,
                            "materialized_bytes_observed": 0,
                            "bytes_observed": 0,
                            "limit_reason": None,
                            "replay_status": {"state": "not_required"},
                        },
                    )
                fieldnames = list(raw_fieldnames)
                if any(not name for name in fieldnames) or len(set(fieldnames)) != len(
                    fieldnames
                ):
                    return InferenceResult(
                        NormalizedSchema(identity=source_identity, fields=()),
                        (
                            _diag(
                                "INFER_CSV_HEADER",
                                "CSV header contains empty or duplicate field names",
                                severity=Severity.ERROR,
                            ),
                        ),
                        provenance={
                            "source": "csv",
                            "source_identity": source_identity,
                            "limits": limits.to_dict(),
                            "parser_options": parser_options,
                            "raw_byte_limit_applies": limits.max_bytes is not None,
                            "raw_bytes_observed": bounded_reader.bytes_observed,
                            "materialized_bytes_observed": 0,
                            "bytes_observed": 0,
                            "limit_reason": None,
                            "replay_status": {"state": "not_required"},
                        },
                    )

                def rows() -> Iterable[dict[str, Any]]:
                    try:
                        while True:
                            try:
                                with _csv_field_limit(limits.max_field_size):
                                    row = next(reader)
                            except StopIteration:
                                break
                            yield _csv_row(
                                row,
                                fieldnames=fieldnames,
                                null_values=null_values,
                                diagnostics=row_diagnostics,
                                max_diagnostics=limits.max_diagnostics,
                            )
                    except _CSVByteLimitReached:
                        reader_state["raw_limit_hit"] = True
                    except csv.Error as exc:
                        field_limit_hit = (
                            "field larger than field limit" in str(exc).casefold()
                        )
                        reader_state["field_limit_hit"] = field_limit_hit
                        diagnostic = _diag(
                            "INFER_CSV_FIELD_LIMIT"
                            if field_limit_hit
                            else "INFER_CSV_PARSE",
                            "CSV field exceeds the configured per-field limit"
                            if field_limit_hit
                            else "Unable to parse CSV records",
                            severity=Severity.ERROR,
                        )
                        _append_diag(
                            parser_diagnostics,
                            diagnostic,
                            limits.max_diagnostics,
                        )
                    except (OSError, UnicodeError, LookupError) as exc:
                        _append_diag(
                            parser_diagnostics,
                            _diag(
                                "INFER_CSV_PARSE",
                                f"Unable to parse CSV records: {type(exc).__name__}",
                                severity=Severity.ERROR,
                            ),
                            limits.max_diagnostics,
                        )

                result = infer_records(
                    rows(),
                    hints=hints,
                    limits=record_limits,
                    identity=source_identity,
                    retain_rows=retain_rows,
                )

                file_size = os.fstat(raw_source.fileno()).st_size
                raw_limit_hit = bool(reader_state["raw_limit_hit"])
                raw_limit_hit = raw_limit_hit or (
                    limits.max_bytes is not None
                    and bounded_reader.bytes_observed >= limits.max_bytes
                    and file_size > limits.max_bytes
                )

        assert (
            result is not None
            and bounded_reader is not None
            and source_signature is not None
        )
        sampled = bool(result.provenance.get("sampled", False))
        limit_reasons: list[str] = [
            str(reason) for reason in result.provenance.get("limit_reasons", ())
        ]
        if reader_state["field_limit_hit"]:
            sampled = True
            limit_reasons.append("field_size")
        if raw_limit_hit:
            sampled = True
            limit_reasons.append("raw_bytes")
            _append_diag(
                parser_diagnostics,
                _diag(
                    "INFER_CSV_BYTE_LIMIT",
                    "CSV raw input byte limit reached",
                ),
                limits.max_diagnostics,
            )

        if len(set(limit_reasons)) > 1:
            limit_reason = "multiple"
        elif limit_reasons:
            limit_reason = limit_reasons[0]
        else:
            limit_reason = None

        materialized_bytes = int(
            result.provenance.get(
                "materialized_bytes_observed",
                result.provenance.get("bytes_observed", 0),
            )
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
            if result.provenance.get("rows_observed") == 0
            and header_hints[name] is None
        ]
        diagnostics = tuple(
            (
                row_diagnostics
                + parser_diagnostics
                + list(result.diagnostics)
                + header_diagnostics
            )[: limits.max_diagnostics]
        )
        schema = result.schema
        if not result.schema.fields and result.provenance.get("rows_observed") == 0:
            schema = normalize_schema_from_fields(
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
                identity=source_identity,
            )

        replay_status: dict[str, Any] = {
            "state": "pending" if sampled else "not_required",
            "rows_observed": 0,
            "raw_bytes_observed": 0,
        }
        replay: ReplayHandle | None = None
        if sampled:
            string_fields = {
                field.name
                for field in result.schema.fields
                if field.logical_type == "string"
            }
            # Diagnostics are deliberately capped, so they cannot be the
            # source of truth for replay normalization decisions.
            mixed_fields = {
                evidence.field
                for evidence in result.evidence
                if evidence.field in string_fields
                and len(
                    {
                        type_name
                        for type_name, count in evidence.type_counts.items()
                        if type_name != "null" and count > 0
                    }
                )
                > 1
            }
            decimal_fields = {
                field.name
                for field in result.schema.fields
                if field.logical_type == "decimal"
            }

            def replay_rows() -> Iterable[dict[str, Any]]:
                row_index = 0
                replay_reader: _BoundedCSVRaw | None = None

                def fail(code: str, message: str) -> InferenceReplayError:
                    diagnostic = _diag(
                        code,
                        message,
                        severity=Severity.ERROR,
                    )
                    replay_status.update(
                        {
                            "state": "failed",
                            "rows_observed": row_index,
                            "diagnostic": diagnostic.to_dict(),
                            "raw_bytes_observed": (
                                replay_reader.bytes_observed
                                if replay_reader is not None
                                else 0
                            ),
                        }
                    )
                    return InferenceReplayError(diagnostic, row_index)

                replay_status["state"] = "in_progress"
                try:
                    with csv_path.open("rb") as replay_source:
                        if (
                            _csv_source_signature(os.fstat(replay_source.fileno()))
                            != source_signature
                        ):
                            raise fail(
                                "INFER_CSV_REPLAY_SOURCE",
                                "CSV source changed or disappeared before replay",
                            )
                        replay_reader = _BoundedCSVRaw(replay_source, None)
                        with io.TextIOWrapper(
                            io.BufferedReader(replay_reader),
                            encoding=encoding,
                            newline="",
                        ) as replay_handle:
                            replay_parser = csv.DictReader(replay_handle, **opts)
                            with _csv_field_limit(limits.max_field_size):
                                replay_fieldnames = list(replay_parser.fieldnames or ())
                            if replay_fieldnames != fieldnames:
                                raise fail(
                                    "INFER_CSV_REPLAY_SOURCE",
                                    "CSV header changed before replay",
                                )
                            while True:
                                try:
                                    with _csv_field_limit(limits.max_field_size):
                                        raw_row = next(replay_parser)
                                except StopIteration:
                                    break
                                replay_row = _csv_row(
                                    raw_row,
                                    fieldnames=fieldnames,
                                    null_values=null_values,
                                    diagnostics=[],
                                    max_diagnostics=limits.max_diagnostics,
                                )
                                for name in mixed_fields:
                                    if (
                                        name in replay_row
                                        and replay_row[name] is not None
                                    ):
                                        replay_row[name] = str(replay_row[name])
                                for name in decimal_fields:
                                    value = replay_row.get(name)
                                    if isinstance(
                                        value, (int, float)
                                    ) and not isinstance(value, bool):
                                        replay_row[name] = Decimal(str(value))
                                row_index += 1
                                replay_status.update(
                                    {
                                        "state": "in_progress",
                                        "rows_observed": row_index,
                                        "raw_bytes_observed": replay_reader.bytes_observed,
                                    }
                                )
                                yield replay_row
                    replay_status.update(
                        {
                            "state": "complete",
                            "rows_observed": row_index,
                            "raw_bytes_observed": replay_reader.bytes_observed,
                        }
                    )
                except InferenceReplayError:
                    raise
                except csv.Error as exc:
                    field_limit_hit = (
                        "field larger than field limit" in str(exc).casefold()
                    )
                    raise fail(
                        "INFER_CSV_FIELD_LIMIT"
                        if field_limit_hit
                        else "INFER_CSV_REPLAY_PARSE",
                        "CSV field exceeds the configured per-field limit"
                        if field_limit_hit
                        else "Unable to parse CSV during replay",
                    ) from None
                except (OSError, UnicodeError, LookupError, TypeError, ValueError):
                    raise fail(
                        "INFER_CSV_REPLAY_SOURCE",
                        "CSV source could not be reopened or parsed for replay",
                    ) from None

            replay = ReplayHandle((), iter(replay_rows()))

        effective_limits = limits.to_dict()
        effective_limits["max_materialized_bytes"] = materialized_limit
        provenance = {
            **result.provenance,
            "source": "csv",
            "source_identity": source_identity,
            "limits": effective_limits,
            "parser_options": parser_options,
            "sampled": sampled,
            "limit_reason": limit_reason,
            "limit_reasons": list(dict.fromkeys(limit_reasons)),
            "rows_observed": result.provenance.get("rows_observed", 0),
            "bytes_observed": materialized_bytes,
            "materialized_bytes_observed": materialized_bytes,
            "raw_bytes_observed": bounded_reader.bytes_observed,
            "raw_byte_limit_applies": limits.max_bytes is not None,
            "byte_accounting": {
                "raw_bytes": "physical bytes returned by the bounded binary reader",
                "materialized_bytes": "estimated decoded Python record size",
            },
            "replay_status": replay_status,
        }
        return InferenceResult(
            schema,
            diagnostics,
            result.evidence,
            provenance,
            result.rows,
            replay,
        )
    except _CSVByteLimitReached:
        raw_bytes = bounded_reader.bytes_observed if bounded_reader else 0
        diagnostic = _diag("INFER_CSV_BYTE_LIMIT", "CSV raw input byte limit reached")
        return InferenceResult(
            NormalizedSchema(identity=source_identity, fields=()),
            (diagnostic,),
            provenance={
                "source": "csv",
                "source_identity": source_identity,
                "limits": limits.to_dict(),
                "parser_options": parser_options,
                "sampled": True,
                "limit_reason": "raw_bytes",
                "limit_reasons": ["raw_bytes"],
                "bytes_observed": 0,
                "materialized_bytes_observed": 0,
                "raw_bytes_observed": raw_bytes,
                "raw_byte_limit_applies": limits.max_bytes is not None,
                "replay_status": {"state": "not_available"},
            },
        )
    except (
        OSError,
        csv.Error,
        UnicodeError,
        LookupError,
        TypeError,
        ValueError,
    ) as exc:
        field_limit_hit = isinstance(exc, csv.Error) and (
            "field larger than field limit" in str(exc).casefold()
        )
        code = "INFER_CSV_FIELD_LIMIT" if field_limit_hit else "INFER_CSV_PARSE"
        message = (
            "CSV field exceeds the configured per-field limit"
            if field_limit_hit
            else f"Unable to parse CSV: {type(exc).__name__}"
        )
        return InferenceResult(
            NormalizedSchema(identity=source_identity, fields=()),
            (
                _diag(
                    code,
                    message,
                    severity=Severity.ERROR,
                ),
            ),
            provenance={
                "source": "csv",
                "source_identity": source_identity,
                "limits": limits.to_dict(),
                "parser_options": parser_options,
                "sampled": field_limit_hit,
                "limit_reason": "field_size" if field_limit_hit else None,
                "bytes_observed": 0,
                "materialized_bytes_observed": 0,
                "raw_bytes_observed": (
                    bounded_reader.bytes_observed if bounded_reader else 0
                ),
                "raw_byte_limit_applies": (
                    bounded_reader is not None and limits.max_bytes is not None
                ),
                "replay_status": {"state": "not_available"},
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
