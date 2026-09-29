# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnnecessaryIsInstance=false
"""Public models used by optional schema and model inference.

The serialized inference observation stores schema evidence and counts only.
The data first facade may keep a bounded runtime preview and a single-use
replay handle, but those values are deliberately excluded from observations
used in plans, reports, and schema history.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Iterator, Mapping
from contextlib import suppress
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from itertools import chain, islice
from typing import Any, Literal, cast

from etlantic.diagnostics import Diagnostic, Severity
from etlantic.schema_drift import (
    NormalizedSchema,
    json_safe_metadata,
    restore_wire_revision_fingerprints,
)

TargetExistence = Literal["present", "absent", "unknown"]
TARGET_EXISTENCE_STATES = frozenset(("present", "absent", "unknown"))
_TARGET_LOGICAL_TYPES = frozenset(
    (
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
    )
)
_TARGET_OBSERVATION_METADATA_MAX_KEYS = 256


def _wire_value(value: Any, *, key: str | None = None, depth: int = 0) -> Any:
    """Return a bounded JSON-safe representation of provider metadata.

    Inference artifacts are metadata-only. Unknown provider objects are
    represented by their type name instead of being retained or stringified
    with potentially sensitive values.
    """
    # Keep one serializer for schema, observation, target, and diagnostic
    # metadata.  The key/depth arguments remain for source compatibility with
    # older callers that used this helper internally.
    return json_safe_metadata(value, key=key, depth=depth)


def _diagnostic_dict(value: Any) -> dict[str, Any]:
    typed_diagnostic = isinstance(value, Diagnostic)
    if hasattr(value, "to_dict"):
        value = value.to_dict()
    if isinstance(value, Mapping):
        if not typed_diagnostic:
            return provider_diagnostic(
                value, default_code="INFER_UNKNOWN_DIAGNOSTIC"
            ).to_dict()
        payload = _wire_value(value)
        if not isinstance(payload, dict):
            return {
                "code": "INFER_UNKNOWN_DIAGNOSTIC",
                "message": "Diagnostic payload was not a mapping",
            }
        return dict(payload)
    return {
        "code": "INFER_UNKNOWN_DIAGNOSTIC",
        "message": "Diagnostic payload was not a mapping",
    }


_SAFE_PROVIDER_DIAGNOSTIC_CODES = frozenset(
    {
        "INFER_BACKWARD_CONFLICT",
        "INFER_BACKWARD_NONCONVERGENT",
        "INFER_BACKWARD_UNSUPPORTED",
        "INFER_CSV_BYTE_LIMIT",
        "INFER_CSV_FIELD_LIMIT",
        "INFER_CSV_HEADER",
        "INFER_CSV_OPTIONS",
        "INFER_CSV_PARSE",
        "INFER_CSV_REPLAY_PARSE",
        "INFER_CSV_REPLAY_SOURCE",
        "INFER_CSV_ROW",
        "INFER_EMPTY",
        "INFER_EVALUATION_UNSUPPORTED",
        "INFER_HINT_CONFLICT",
        "INFER_HINT_UNOBSERVED",
        "INFER_HINT_UNSUPPORTED",
        "INFER_INVALID_KEY",
        "INFER_JSON_PARSE",
        "INFER_JSON_ROW",
        "INFER_LIMIT",
        "INFER_LINEAGE_COLLISION",
        "INFER_LINEAGE_MISSING",
        "INFER_MISSING_FIELD",
        "INFER_MIXED_TYPE",
        "INFER_NESTED_UNSUPPORTED",
        "INFER_RUNTIME_CONSTRAINT",
        "INFER_RUNTIME_CONVERSION",
        "INFER_RUNTIME_EVALUATION",
        "INFER_SOURCE_AMBIGUOUS",
        "INFER_SOURCE_ASYNC_SCHEMA",
        "INFER_SOURCE_BINDING",
        "INFER_SOURCE_INVALID",
        "INFER_SOURCE_REBIND",
        "INFER_SOURCE_SCHEMA_MISMATCH",
        "INFER_SOURCE_SCHEMA_UNKNOWN",
        "INFER_SOURCE_SCHEMA_UNVERIFIED",
        "INFER_SOURCE_UNBOUNDED",
        "INFER_SOURCE_UNKNOWN",
        "INFER_SOURCE_UNRESOLVABLE",
        "INFER_SOURCE_UNSUPPORTED",
        "INFER_TARGET_ABSENT",
        "INFER_TARGET_BINDING",
        "INFER_TARGET_CONFLICT",
        "INFER_TARGET_CREATE_UNSUPPORTED",
        "INFER_TARGET_IDENTITY_COLLISION",
        "INFER_TARGET_IDENTITY_UNKNOWN",
        "INFER_TARGET_REVISION_UNKNOWN",
        "INFER_TARGET_STALE",
        "INFER_TARGET_UNKNOWN",
        "INFER_TARGET_UNSUPPORTED",
        "INFER_TARGET_WRITE_UNQUALIFIED",
        "INFER_UNKNOWN_DIAGNOSTIC",
        "INFER_UNKNOWN_TYPE",
        "INFER_WRITE_INCOMPATIBLE",
        "INFER_WRITE_MODE_UNSUPPORTED",
        "PROVIDER_NAME",
        "PROVIDER_READ_FAILED",
        "PROVIDER_ROW_WARNING",
    }
)


def provider_diagnostic(value: Any, *, default_code: str) -> Diagnostic:
    """Keep provider diagnostic status while dropping untrusted text and paths."""
    code: Any = None
    severity: Any = Severity.WARNING
    if isinstance(value, Diagnostic):
        code = value.code
        severity = value.severity
    elif isinstance(value, Mapping):
        try:
            code = value.get("code")
            severity = value.get("severity", Severity.WARNING)
        except Exception:
            code = None
            severity = Severity.ERROR

    safe_code = (
        code
        if isinstance(code, str) and code in _SAFE_PROVIDER_DIAGNOSTIC_CODES
        else default_code
    )
    try:
        safe_severity = (
            severity
            if isinstance(severity, Severity)
            else Severity(str(getattr(severity, "value", severity)).lower())
        )
    except ValueError:
        safe_severity = Severity.ERROR
    return Diagnostic(
        safe_code,
        safe_severity,
        "Provider diagnostic details were omitted",
        phase="inference",
    )


def _wire_mapping(value: Any, *, key: str | None = None) -> dict[str, Any]:
    safe = _wire_value(restore_wire_revision_fingerprints(value, key=key), key=key)
    return dict(cast(Mapping[str, Any], safe)) if isinstance(safe, Mapping) else {}


def _wire_version(payload: Mapping[str, Any], model_name: str) -> int:
    version = payload.get("version", 1)
    if type(version) is not int:
        raise ValueError(f"{model_name} version must be an integer")
    if version != 1:
        raise ValueError(f"unsupported {model_name} version: {version}")
    return version


def _diagnostic_from_dict(value: Any) -> Any:
    if isinstance(value, Diagnostic):
        return value
    if not isinstance(value, Mapping):
        return Diagnostic(
            "INFER_UNKNOWN_DIAGNOSTIC",
            Severity.WARNING,
            "Diagnostic payload was not a mapping",
            phase="inference",
        )
    try:
        return Diagnostic(
            str(value.get("code") or "INFER_UNKNOWN_DIAGNOSTIC"),
            Severity(str(value.get("severity") or "warning").lower()),
            str(value.get("message") or "Inference diagnostic"),
            tuple(str(item) for item in value.get("path", ())),
            phase=(
                str(value["phase"]) if value.get("phase") is not None else "inference"
            ),
        )
    except (TypeError, ValueError):
        return Diagnostic(
            "INFER_UNKNOWN_DIAGNOSTIC",
            Severity.WARNING,
            "Invalid inference diagnostic payload",
            phase="inference",
        )


@dataclass(frozen=True, slots=True)
class InferenceLimits:
    """Bounds for inference and materialization.

    ``max_bytes`` bounds source bytes for file-backed readers (CSV accounts
    physical bytes returned by its binary reader). ``max_materialized_bytes``
    bounds estimated decoded/in-memory data; when omitted, in-memory record
    inference retains the historical behavior of using ``max_bytes`` for that
    estimate. CSV defaults its materialization estimate to the standard
    64 MiB inference budget. ``max_field_size`` is a separate per-field parser
    guard used by CSV; ``None`` removes that inference-specific cap, subject to
    the parser's platform maximum.
    """

    max_rows: int = 10_000
    max_fields: int = 1_000
    max_diagnostics: int = 100
    max_bytes: int | None = 64 * 1024 * 1024
    timeout_seconds: float | None = 30.0
    max_materialized_bytes: int | None = None
    max_field_size: int | None = 64 * 1024 * 1024

    def __post_init__(self) -> None:
        integer_limits = (
            ("max_rows", self.max_rows, 0),
            ("max_fields", self.max_fields, 1),
            ("max_diagnostics", self.max_diagnostics, 1),
        )
        for name, value, minimum in integer_limits:
            if type(value) is not int or value < minimum:
                raise ValueError(
                    f"{name} must be an integer greater than or equal to {minimum}"
                )
        optional_integer_limits = (
            ("max_bytes", self.max_bytes),
            ("max_materialized_bytes", self.max_materialized_bytes),
            ("max_field_size", self.max_field_size),
        )
        for name, value in optional_integer_limits:
            if value is not None and (type(value) is not int or value < 1):
                raise ValueError(f"{name} must be a positive integer when provided")
        if self.timeout_seconds is not None:
            if type(self.timeout_seconds) not in (int, float):
                raise ValueError(
                    "timeout_seconds must be positive and finite when provided"
                )
            try:
                finite = math.isfinite(self.timeout_seconds)
            except OverflowError:
                finite = False
            if not finite or self.timeout_seconds <= 0:
                raise ValueError(
                    "timeout_seconds must be positive and finite when provided"
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "max_rows": self.max_rows,
            "max_fields": self.max_fields,
            "max_diagnostics": self.max_diagnostics,
            "max_bytes": self.max_bytes,
            "timeout_seconds": self.timeout_seconds,
            "max_materialized_bytes": self.max_materialized_bytes,
            "max_field_size": self.max_field_size,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> InferenceLimits:
        _wire_version(payload, "inference limits")
        defaults = cls()

        def integer_limit(name: str, default: int | None = None) -> int | None:
            value = payload.get(name, default)
            if value is not None and type(value) is not int:
                raise ValueError(f"{name} must be an integer")
            return value

        raw_timeout = payload.get("timeout_seconds", defaults.timeout_seconds)
        if raw_timeout is not None and type(raw_timeout) not in (int, float):
            raise ValueError("timeout_seconds must be numeric")
        return cls(
            max_rows=cast(int, integer_limit("max_rows", defaults.max_rows)),
            max_fields=cast(int, integer_limit("max_fields", defaults.max_fields)),
            max_diagnostics=cast(
                int, integer_limit("max_diagnostics", defaults.max_diagnostics)
            ),
            max_bytes=integer_limit("max_bytes", defaults.max_bytes),
            timeout_seconds=raw_timeout,
            max_materialized_bytes=integer_limit("max_materialized_bytes"),
            max_field_size=integer_limit(
                "max_field_size",
                defaults.max_field_size if "max_field_size" not in payload else None,
            ),
        )


class InferenceReplayError(ValueError):
    """Raised when inference replay fails while consuming a replay.

    Replay is fail-closed: iteration stops at the first invalid row or source
    failure. The structured diagnostic is available on ``diagnostic`` and the
    zero-based position in the replay stream is available on ``row_index``.
    The exception message intentionally contains no source value.
    """

    def __init__(
        self,
        diagnostic: Diagnostic,
        row_index: int,
        *,
        diagnostics: Iterable[Diagnostic] = (),
    ) -> None:
        self.diagnostic = diagnostic
        self.diagnostics = tuple(diagnostics) or (diagnostic,)
        self.row_index = row_index
        super().__init__(
            f"{diagnostic.code}: inference replay failed at row {row_index}"
        )


class _ReplayLifecycle:
    """Coordinate durable status callbacks across derived replay handles."""

    __slots__ = (
        "_completed",
        "_failed",
        "_on_complete",
        "_on_failure",
    )

    def __init__(self) -> None:
        self._completed = False
        self._failed = False
        self._on_complete: Callable[[], None] | None = None
        self._on_failure: Callable[[InferenceReplayError], None] | None = None

    def bind(
        self,
        *,
        on_complete: Callable[[], None],
        on_failure: Callable[[InferenceReplayError], None],
    ) -> None:
        self._on_complete = on_complete
        self._on_failure = on_failure

    def fail(self, error: InferenceReplayError) -> None:
        if self._failed or self._completed:
            return
        self._failed = True
        if self._on_failure is not None:
            self._on_failure(error)

    def complete(self) -> None:
        if self._failed or self._completed:
            return
        self._completed = True
        if self._on_complete is not None:
            self._on_complete()


@dataclass(frozen=True, slots=True)
class SchemaEvidence:
    """Aggregate evidence supporting a field inference."""

    field: str
    observed_values: int = 0
    null_values: int = 0
    missing_values: int = 0
    type_counts: dict[str, int] = dataclass_field(default_factory=dict)
    sampled: bool = False
    method: str = "record_values"
    confidence: float | None = None
    limitations: tuple[str, ...] = ()

    @property
    def non_null_values(self) -> int:
        return max(0, self.observed_values - self.null_values)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "field": self.field,
            "observed_values": self.observed_values,
            "null_values": self.null_values,
            "missing_values": self.missing_values,
            "type_counts": _wire_value(self.type_counts, key="type_counts"),
            "sampled": self.sampled,
            "method": self.method,
            "confidence": self.confidence,
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True, slots=True)
class InferenceObservation:
    """Stable, row-free inference payload for plans and schema history."""

    schema: NormalizedSchema
    diagnostics: tuple[Any, ...] = ()
    evidence: tuple[SchemaEvidence, ...] = ()
    provenance: dict[str, Any] = dataclass_field(default_factory=dict)
    version: int = 1
    observed_schema: NormalizedSchema | None = None
    target_hypothesis: NormalizedSchema | None = None
    target_observation: TargetObservation | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "schema": self.schema.to_dict(),
            "observed_schema": (
                self.observed_schema.to_dict()
                if self.observed_schema is not None
                else None
            ),
            "target_hypothesis": (
                self.target_hypothesis.to_dict()
                if self.target_hypothesis is not None
                else None
            ),
            "target_observation": (
                self.target_observation.to_dict()
                if self.target_observation is not None
                else None
            ),
            "diagnostics": [_diagnostic_dict(d) for d in self.diagnostics],
            "evidence": [e.to_dict() for e in self.evidence],
            "provenance": _wire_value(self.provenance),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> InferenceObservation:
        payload = _wire_mapping(payload)
        version = _wire_version(payload, "inference observation")
        schema_payload = payload.get("schema")
        if not isinstance(schema_payload, dict):
            raise ValueError("inference observation schema is required")
        evidence = tuple(
            SchemaEvidence(
                field=str(item.get("field", "")),
                observed_values=int(item.get("observed_values", 0)),
                null_values=int(item.get("null_values", 0)),
                missing_values=int(item.get("missing_values", 0)),
                type_counts=dict(item.get("type_counts") or {}),
                sampled=bool(item.get("sampled", False)),
                method=str(item.get("method", "record_values")),
                confidence=item.get("confidence"),
                limitations=tuple(item.get("limitations") or ()),
            )
            for item in payload.get("evidence", ())
            if isinstance(item, dict)
        )
        return cls(
            NormalizedSchema.from_dict(schema_payload),
            tuple(
                _diagnostic_from_dict(item)
                for item in (payload.get("diagnostics") or ())
            ),
            evidence,
            _wire_mapping(payload.get("provenance") or {}),
            version,
            NormalizedSchema.from_dict(payload["observed_schema"])
            if isinstance(payload.get("observed_schema"), dict)
            else None,
            NormalizedSchema.from_dict(payload["target_hypothesis"])
            if isinstance(payload.get("target_hypothesis"), dict)
            else None,
            TargetObservation.from_dict(payload["target_observation"])
            if isinstance(payload.get("target_observation"), dict)
            else None,
        )


class ReplayHandle:
    """Single-use replay stream for a bounded inference prefix.

    Derived handles share a private lifecycle so a target conversion can
    report completion or a structured failure exactly once, even when callers
    compose ``map``, ``filter``, and ``limit``.
    """

    __slots__ = ("_lifecycle", "_prefix", "_remainder", "_used")

    def __init__(
        self,
        prefix: Iterable[dict[str, Any]],
        remainder: Iterator[Any],
        *,
        _lifecycle: _ReplayLifecycle | None = None,
    ):
        self._prefix = tuple(dict(row) for row in prefix)
        self._remainder = remainder
        self._used = False
        self._lifecycle = _lifecycle

    def take(self) -> Iterator[Any]:
        """Return the inspected prefix followed by the untouched remainder."""
        if self._used:
            raise RuntimeError("inference replay has already been consumed")
        self._used = True
        return chain(iter(self._prefix), self._remainder)

    @property
    def available(self) -> bool:
        """Whether this single-use replay can still be consumed."""
        return not self._used

    def map(
        self,
        transform: Any,
        *,
        _lifecycle: _ReplayLifecycle | None = None,
    ) -> ReplayHandle:
        """Return a replay with ``transform`` applied lazily to every row."""
        if self._used:
            raise RuntimeError("inference replay has already been consumed")
        stream = self.take()
        lifecycle = _lifecycle or self._lifecycle

        if lifecycle is None:
            mapped: Iterator[Any] = (transform(row) for row in stream)
        else:

            def mapped_stream() -> Iterator[Any]:
                try:
                    for row in stream:
                        yield transform(row)
                except InferenceReplayError as error:
                    lifecycle.fail(error)
                    raise
                else:
                    lifecycle.complete()

            mapped = mapped_stream()

        return ReplayHandle(
            (),
            mapped,
            _lifecycle=lifecycle,
        )

    def filter(self, predicate: Any) -> ReplayHandle:
        """Return a replay containing rows for which ``predicate`` is true."""
        if self._used:
            raise RuntimeError("inference replay has already been consumed")
        stream = self.take()
        return ReplayHandle(
            (),
            (row for row in stream if predicate(row)),
            _lifecycle=self._lifecycle,
        )

    def limit(self, count: int) -> ReplayHandle:
        """Return a replay bounded to the first ``count`` rows."""
        if self._used:
            raise RuntimeError("inference replay has already been consumed")
        return ReplayHandle(
            (),
            islice(self.take(), max(0, count)),
            _lifecycle=self._lifecycle,
        )


class InferenceResult:
    """Schema inference output with a row-free serialized observation.

    Preview rows and replay state are runtime-only attributes.  They are
    exposed through properties for the data-first facade, but are not fields
    that generic dataclass serializers can walk.
    """

    __slots__ = (
        "_replay",
        "_rows",
        "diagnostics",
        "evidence",
        "observed_schema",
        "provenance",
        "schema",
        "target_hypothesis",
        "target_observation",
    )

    def __init__(
        self,
        schema: NormalizedSchema,
        diagnostics: tuple[Any, ...] = (),
        evidence: tuple[SchemaEvidence, ...] = (),
        provenance: dict[str, Any] | None = None,
        rows: Iterable[dict[str, Any]] = (),
        replay: ReplayHandle | None = None,
        observed_schema: NormalizedSchema | None = None,
        target_hypothesis: NormalizedSchema | None = None,
        target_observation: TargetObservation | None = None,
    ) -> None:
        self.schema = schema
        self.diagnostics = tuple(diagnostics)
        self.evidence = tuple(evidence)
        self.provenance = dict(provenance or {})
        self._rows = tuple(dict(row) for row in rows)
        self._replay = replay
        self.observed_schema = observed_schema
        self.target_hypothesis = target_hypothesis
        self.target_observation = target_observation

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, InferenceResult):
            return NotImplemented
        return (
            self.schema == other.schema
            and self.diagnostics == other.diagnostics
            and self.evidence == other.evidence
            and self.provenance == other.provenance
            and self.observed_schema == other.observed_schema
            and self.target_hypothesis == other.target_hypothesis
            and self.target_observation == other.target_observation
        )

    def replace(self, **changes: Any) -> InferenceResult:
        """Return a copy with selected result attributes changed.

        This mirrors the useful part of ``dataclasses.replace`` while keeping
        runtime rows and replay state out of generic dataclass serialization.
        """
        allowed = {
            "schema",
            "diagnostics",
            "evidence",
            "provenance",
            "rows",
            "replay",
            "observed_schema",
            "target_hypothesis",
            "target_observation",
        }
        unknown = set(changes) - allowed
        if unknown:
            raise TypeError(f"Unknown inference result fields: {sorted(unknown)!r}")
        return InferenceResult(
            changes.get("schema", self.schema),
            changes.get("diagnostics", self.diagnostics),
            changes.get("evidence", self.evidence),
            changes.get("provenance", self.provenance),
            changes.get("rows", self.rows),
            changes.get("replay", self.replay),
            changes.get("observed_schema", self.observed_schema),
            changes.get("target_hypothesis", self.target_hypothesis),
            changes.get("target_observation", self.target_observation),
        )

    @property
    def rows(self) -> tuple[dict[str, Any], ...]:
        """Return the bounded runtime preview, never included in serialization."""
        return self._rows

    @property
    def replay(self) -> ReplayHandle | None:
        """Return the single-use runtime continuation, when available."""
        return self._replay

    @property
    def valid(self) -> bool:
        def is_error(diagnostic: Any) -> bool:
            severity = (
                diagnostic.get("severity")
                if isinstance(diagnostic, dict)
                else getattr(diagnostic, "severity", None)
            )
            return getattr(severity, "value", severity) == "error"

        return not any(is_error(diagnostic) for diagnostic in self.diagnostics)

    def to_dict(self, *, include_rows: bool = False) -> dict[str, Any]:
        """Serialize schema evidence without source rows.

        ``include_rows`` remains accepted for call-site compatibility but is
        intentionally ignored so observations cannot serialize source data.
        """
        # Results and observations use the same versioned wire envelope.  The
        # runtime preview remains deliberately absent from both forms.
        return self.to_observation().to_dict()

    def to_observation(self) -> InferenceObservation:
        """Return the serializable portion of this runtime result."""
        return InferenceObservation(
            self.schema,
            self.diagnostics,
            self.evidence,
            dict(self.provenance),
            1,
            self.observed_schema,
            self.target_hypothesis,
            self.target_observation,
        )


@dataclass(frozen=True, slots=True)
class TargetObservation:
    """Schema observed at an existing write target."""

    schema: NormalizedSchema | None
    exists: str
    revision: str | None = None
    inspector: str | None = None
    diagnostics: tuple[Any, ...] = ()
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.exists, str)
            or self.exists not in TARGET_EXISTENCE_STATES
        ):
            raise ValueError(
                "target observation exists must be one of: present, absent, unknown"
            )
        normalized_metadata: dict[str, Any] | None = None
        metadata_limit_hit = False
        if isinstance(self.metadata, Mapping):
            metadata_source = cast(Mapping[str, Any], self.metadata)
            with suppress(Exception):
                keys = list(
                    islice(
                        iter(metadata_source),
                        _TARGET_OBSERVATION_METADATA_MAX_KEYS + 1,
                    )
                )
                metadata_limit_hit = len(keys) > _TARGET_OBSERVATION_METADATA_MAX_KEYS
                normalized_metadata = {
                    key: metadata_source[key]
                    for key in keys[:_TARGET_OBSERVATION_METADATA_MAX_KEYS]
                }
        if normalized_metadata is None:
            object.__setattr__(
                self,
                "metadata",
                {},
            )
            object.__setattr__(
                self,
                "diagnostics",
                (
                    *self.diagnostics,
                    Diagnostic(
                        "INFER_TARGET_UNSUPPORTED",
                        Severity.WARNING,
                        "Target observation metadata must be a mapping",
                        phase="inference",
                    ),
                ),
            )
        else:
            object.__setattr__(self, "metadata", normalized_metadata)
            if metadata_limit_hit:
                object.__setattr__(
                    self,
                    "diagnostics",
                    (
                        *self.diagnostics,
                        Diagnostic(
                            "INFER_LIMIT",
                            Severity.ERROR,
                            "Target observation metadata exceeds the metadata limit",
                            phase="inference",
                        ),
                    ),
                )

    @property
    def identity(self) -> str | None:
        """Stable target identity when an inspected schema provides one."""
        if self.metadata.get("identity_unresolved") is True:
            return None
        schema_identity = self.schema.identity if self.schema is not None else None
        return (
            schema_identity
            if schema_identity is not None
            else self.metadata.get("identity")
        )

    def to_dict(self) -> dict[str, Any]:
        safe_metadata = _wire_value(self.metadata)
        metadata = (
            dict(cast(Mapping[str, Any], safe_metadata))
            if isinstance(safe_metadata, Mapping)
            else {}
        )
        schema = self.schema
        if self.exists != "present":
            if schema is not None:
                metadata.setdefault(
                    "untrusted_schema_fingerprint", schema.fingerprint()
                )
            schema = None
        return {
            "version": 1,
            "schema": schema.to_dict() if schema is not None else None,
            "identity": _wire_value(self.identity, key="identity"),
            "exists": self.exists,
            "revision": _wire_value(self.revision, key="revision"),
            "inspector": _wire_value(self.inspector, key="inspector"),
            "diagnostics": [_diagnostic_dict(d) for d in self.diagnostics],
            "metadata": metadata,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> TargetObservation:
        payload = _wire_mapping(payload)
        _wire_version(payload, "target observation")
        schema_payload = payload.get("schema")
        metadata = _wire_mapping(payload.get("metadata") or {})
        identity_unresolved = metadata.get("identity_unresolved") is True
        if payload.get("identity") is not None and not identity_unresolved:
            metadata.setdefault("identity", str(payload["identity"]))
        diagnostics = [
            _diagnostic_from_dict(item) for item in (payload.get("diagnostics") or ())
        ]
        raw_exists = payload.get("exists")
        if not isinstance(raw_exists, str) or raw_exists not in TARGET_EXISTENCE_STATES:
            diagnostics.append(
                Diagnostic(
                    "INFER_TARGET_UNKNOWN",
                    Severity.WARNING,
                    "Target existence state is missing or invalid",
                    phase="inference",
                )
            )
            exists: TargetExistence = "unknown"
        else:
            exists = raw_exists
        malformed_schema = False
        restored_schema = None
        if schema_payload is not None:
            if not isinstance(schema_payload, dict):
                malformed_schema = True
            else:
                if (
                    schema_payload.get("identity") is not None
                    and not identity_unresolved
                ):
                    metadata.setdefault("identity", str(schema_payload["identity"]))
                fields_payload = schema_payload.get("fields")
                field_names = (
                    [
                        item.get("name")
                        for item in fields_payload
                        if isinstance(item, dict) and isinstance(item.get("name"), str)
                    ]
                    if isinstance(fields_payload, list)
                    else []
                )
                malformed_schema = (
                    not isinstance(fields_payload, list)
                    or not isinstance(schema_payload.get("metadata", {}), Mapping)
                    or any(
                        not isinstance(item, dict)
                        or not isinstance(item.get("name"), str)
                        or not item.get("name")
                        or not isinstance(item.get("logical_type"), str)
                        or not item.get("logical_type")
                        or item.get("logical_type") not in _TARGET_LOGICAL_TYPES
                        or not isinstance(item.get("required", True), bool)
                        or not isinstance(item.get("nullable", False), bool)
                        or not isinstance(item.get("metadata", {}), Mapping)
                        for item in fields_payload
                    )
                    or len(field_names) != len(fields_payload or ())
                    or len(field_names) != len(set(field_names))
                )
                if not malformed_schema:
                    try:
                        restored_schema = NormalizedSchema.from_dict(schema_payload)
                    except (KeyError, TypeError, ValueError):
                        malformed_schema = True
        if malformed_schema:
            diagnostics.append(
                Diagnostic(
                    "INFER_TARGET_UNSUPPORTED",
                    Severity.WARNING,
                    "Target schema payload is malformed",
                    phase="inference",
                )
            )
            if exists == "present":
                exists = "unknown"
        if exists != "present" and restored_schema is not None:
            metadata["untrusted_schema_fingerprint"] = restored_schema.fingerprint()
            restored_schema = None
        elif (
            exists == "present"
            and restored_schema is not None
            and not restored_schema.fields
        ):
            metadata["empty"] = True
            restored_schema = None
        return cls(
            restored_schema,
            exists,
            payload.get("revision"),
            payload.get("inspector"),
            tuple(diagnostics),
            metadata,
        )


@dataclass(frozen=True, slots=True)
class OutputProposal:
    """Row-free proposal for creating an absent write target."""

    schema: NormalizedSchema
    identity: str
    create_required: bool = True
    capabilities: tuple[str, ...] = ()
    diagnostics: tuple[Any, ...] = ()
    version: int = 1
    create_intent: bool = False

    @property
    def can_create(self) -> bool:
        """Whether an explicit create intent and provider capability exist."""
        return (
            self.create_required
            and self.create_intent
            and "create" in self.capabilities
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "identity": _wire_value(self.identity, key="identity"),
            "schema": self.schema.to_dict(),
            "create_required": self.create_required,
            "capabilities": list(self.capabilities),
            "diagnostics": [_diagnostic_dict(d) for d in self.diagnostics],
            "create_intent": self.create_intent,
            "can_create": self.can_create,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> OutputProposal:
        version = _wire_version(payload, "output proposal")
        schema = payload.get("schema")
        if not isinstance(schema, Mapping):
            raise ValueError("output proposal schema is required")
        raw_identity = payload.get("identity")
        if raw_identity is not None and not isinstance(raw_identity, str):
            raise ValueError("output proposal identity must be a string")
        create_required = payload.get("create_required", True)
        create_intent = payload.get("create_intent", False)
        if type(create_required) is not bool or type(create_intent) is not bool:
            raise ValueError("output proposal create flags must be booleans")
        raw_capabilities = payload.get("capabilities", ())
        if not isinstance(raw_capabilities, (list, tuple)) or any(
            not isinstance(item, str) for item in raw_capabilities
        ):
            raise ValueError("output proposal capabilities must be strings")
        raw_diagnostics = payload.get("diagnostics", ())
        if not isinstance(raw_diagnostics, (list, tuple)):
            raise ValueError("output proposal diagnostics must be a sequence")
        return cls(
            NormalizedSchema.from_dict(dict(schema)),
            raw_identity or "proposal",
            create_required,
            tuple(raw_capabilities),
            tuple(_diagnostic_from_dict(item) for item in raw_diagnostics),
            version,
            create_intent,
        )


@dataclass(frozen=True, slots=True)
class FieldConstraint:
    """A constraint propagated backwards from a target field."""

    field: str
    logical_type: str
    source: str = "target"
    confidence: float = 1.0
    path: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "field": self.field,
            "logical_type": self.logical_type,
            "source": self.source,
            "confidence": self.confidence,
            "path": list(self.path),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> FieldConstraint:
        _wire_version(payload, "field constraint")
        return cls(
            str(payload.get("field", "")),
            str(payload.get("logical_type", "unknown")),
            str(payload.get("source", "target")),
            float(payload.get("confidence", 1.0)),
            tuple(str(item) for item in payload.get("path", ())),
        )


@dataclass(frozen=True, slots=True)
class WriteCompatibility:
    """Compatibility result for writing one inferred schema to a target."""

    compatible: bool
    casts: dict[str, str] = dataclass_field(default_factory=dict)
    incompatible_fields: tuple[str, ...] = ()
    diagnostics: tuple[Any, ...] = ()
    obligations: tuple[dict[str, Any], ...] = ()
    mode: str = "append"

    @property
    def status(self) -> str:
        """Wire-friendly tri-state compatibility status."""
        if not self.compatible or self.incompatible_fields:
            return "conflict"
        if self.casts or self.obligations:
            return "conditional"
        return "proven"

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "status": self.status,
            "compatible": self.compatible,
            "casts": _wire_value(self.casts, key="casts"),
            "incompatible_fields": list(self.incompatible_fields),
            "diagnostics": [_diagnostic_dict(d) for d in self.diagnostics],
            "obligations": [_wire_value(item) for item in self.obligations],
            "mode": self.mode,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> WriteCompatibility:
        _wire_version(payload, "write compatibility")
        compatible = payload.get("compatible", False)
        if type(compatible) is not bool:
            raise ValueError("write compatibility flag must be a boolean")
        return cls(
            compatible,
            _wire_mapping(payload.get("casts") or {}, key="casts"),
            tuple(str(item) for item in payload.get("incompatible_fields", ())),
            tuple(
                _diagnostic_from_dict(item)
                for item in (payload.get("diagnostics") or ())
            ),
            tuple(
                dict(_wire_value(item))
                for item in payload.get("obligations", ())
                if isinstance(item, dict)
            ),
            str(payload.get("mode", "append")),
        )
