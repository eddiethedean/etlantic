"""Dataframe plugin protocol and execution types."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from pipelantic.capabilities import PluginCapabilities

DATAFRAME_PROTOCOL_VERSION = "pipelantic.dataframe/1"

# Engines that execute through the dataframe protocol (not local record callables).
DATAFRAME_ENGINES = frozenset({"polars", "pandas"})


class DataframePhase(StrEnum):
    """Reportable phases of a dataframe step execution."""

    MATERIALIZE = "materialize"
    INVOKE = "invoke"
    NORMALIZE = "normalize"
    VALIDATE = "validate"
    METRICS = "metrics"
    CLEANUP = "cleanup"


class ArtifactOwnership(StrEnum):
    """Ownership state for a dataframe artifact handle."""

    BORROWED = "borrowed"
    SHARED = "shared"
    COPIED = "copied"
    CONSUMED = "consumed"


class DataframeValidationOutcome(StrEnum):
    """Configured outcome when invalid rows are identified."""

    FAIL = "fail"
    REJECT = "reject"
    QUARANTINE = "quarantine"
    WARN = "warn"
    OBSERVE_ONLY = "observe_only"


class ValidationDecision(StrEnum):
    """Decision applied during a validation phase."""

    PASSED = "passed"
    FAILED = "failed"
    REJECTED = "rejected"
    QUARANTINED = "quarantined"
    WARNED = "warned"
    OBSERVED = "observed"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class DataframeValidationPolicy:
    """Input/output validation policy for a dataframe step."""

    input_outcome: DataframeValidationOutcome = DataframeValidationOutcome.FAIL
    output_outcome: DataframeValidationOutcome = DataframeValidationOutcome.FAIL

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_outcome": self.input_outcome.value,
            "output_outcome": self.output_outcome.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> DataframeValidationPolicy:
        data = data or {}
        return cls(
            input_outcome=DataframeValidationOutcome(
                str(data.get("input_outcome") or "fail")
            ),
            output_outcome=DataframeValidationOutcome(
                str(data.get("output_outcome") or "fail")
            ),
        )


@dataclass(frozen=True, slots=True)
class DataframePluginInfo:
    """Installed dataframe plugin metadata."""

    name: str
    engine: str
    version: str
    protocol_version: str = DATAFRAME_PROTOCOL_VERSION
    capabilities: PluginCapabilities | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "engine": self.engine,
            "version": self.version,
            "protocol_version": self.protocol_version,
            "capabilities": (
                self.capabilities.to_dict() if self.capabilities is not None else None
            ),
        }


@dataclass(frozen=True, slots=True)
class DataframeExecutionContext:
    """Caller identity and plan-resolved settings for one step invocation."""

    run_id: str
    pipeline_id: str
    plan_id: str
    step_name: str
    engine: str
    attempt: int = 1
    collect: bool = False
    ownership: ArtifactOwnership = ArtifactOwnership.SHARED
    validation_policy: DataframeValidationPolicy = field(
        default_factory=DataframeValidationPolicy
    )
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass
class DataframeMetrics:
    """Structured metrics emitted by a dataframe step."""

    rows_in: int | None = None
    rows_out: int | None = None
    invalid_count: int | None = None
    rejected_count: int | None = None
    collected: bool = False
    converted: bool = False
    conversion_kind: str | None = None
    ownership: str | None = None
    memory_bytes_estimate: int | None = None
    phases: list[str] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rows_in": self.rows_in,
            "rows_out": self.rows_out,
            "invalid_count": self.invalid_count,
            "rejected_count": self.rejected_count,
            "collected": self.collected,
            "converted": self.converted,
            "conversion_kind": self.conversion_kind,
            "ownership": self.ownership,
            "memory_bytes_estimate": self.memory_bytes_estimate,
            "phases": list(self.phases),
            "extras": dict(self.extras),
        }


@dataclass
class DataframeOutputBundle:
    """Normalized outputs from a dataframe plugin invocation."""

    valid: dict[str, Any]
    invalid: dict[str, Any] = field(default_factory=dict)
    side: dict[str, Any] = field(default_factory=dict)
    metrics: DataframeMetrics = field(default_factory=DataframeMetrics)
    validation_decision: ValidationDecision = ValidationDecision.PASSED
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
    schema_observations: list[dict[str, Any]] = field(default_factory=list)


@runtime_checkable
class DataframePlugin(Protocol):
    """Protocol for in-process dataframe execution backends."""

    @property
    def info(self) -> DataframePluginInfo: ...

    def materialize_input(
        self,
        value: Any,
        *,
        contract_type: type[Any] | None,
        context: DataframeExecutionContext,
        port_name: str,
    ) -> Any:
        """Convert a logical/runtime value into a native frame for this engine."""
        ...

    def invoke(
        self,
        *,
        callable_: Any,
        inputs: Mapping[str, Any],
        parameters: Mapping[str, Any],
        context: DataframeExecutionContext,
    ) -> Any:
        """Invoke a registered transformation implementation."""
        ...

    def normalize_output(
        self,
        result: Any,
        *,
        output_ports: tuple[str, ...],
        context: DataframeExecutionContext,
    ) -> DataframeOutputBundle:
        """Normalize a callable result into valid/invalid/side outputs."""
        ...

    def validate_frame(
        self,
        value: Any,
        *,
        contract_type: type[Any] | None,
        context: DataframeExecutionContext,
        boundary: str,
        port_name: str | None = None,
    ) -> tuple[Any, ValidationDecision, list[dict[str, Any]]]:
        """Validate a frame (or records) against a contract."""
        ...

    def inspect_schema(
        self,
        value: Any,
        *,
        identity: str,
    ) -> dict[str, Any] | None:
        """Return a NormalizedSchema-compatible mapping, if inspectable."""
        ...

    def ensure_ownership(
        self,
        value: Any,
        *,
        ownership: ArtifactOwnership,
        context: DataframeExecutionContext,
    ) -> Any:
        """Return a handle that respects ownership / mutation isolation."""
        ...

    def collect_if_needed(
        self,
        value: Any,
        *,
        context: DataframeExecutionContext,
    ) -> Any:
        """Collect lazy values when the plan declares a collection boundary."""
        ...

    def to_records(
        self,
        value: Any,
        *,
        contract_type: type[Any] | None,
    ) -> list[Any]:
        """Convert a native frame to Python records for storage/publication."""
        ...

    def row_count(self, value: Any) -> int | None:
        """Best-effort row count without forcing a full materialization when possible."""
        ...
