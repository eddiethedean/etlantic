"""Versioned execution contracts for adaptive physical units.

The records in this module deliberately separate wire-safe execution summaries
from process-local values.  They are independent of the ``etlantic.plan/2``
document schema so a consumer can negotiate both versions explicitly.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from etlantic.plan.physical import PHYSICAL_UNIT_SCHEMA, PhysicalUnit, PhysicalUnitKind
from etlantic.runtime.logging import redact_message

PHYSICAL_EXECUTION_SCHEMA = "etlantic.physical_execution/1"


_SENSITIVE_KEYS = frozenset(
    {
        "secret",
        "password",
        "token",
        "credential",
        "authorization",
        "rows",
        "records",
        "data",
        "payload",
        "value",
        "frame",
        "table",
        "native",
        "handle",
        "ref",
    }
)


def _safe_wire_value(value: Any, *, key: str | None = None) -> Any:
    """Project protocol metadata without traversing row/native payloads."""
    if key is not None and key.lower() in _SENSITIVE_KEYS:
        return "<redacted>"
    if isinstance(value, Mapping):
        return {
            str(item_key): _safe_wire_value(item_value, key=str(item_key))
            for item_key, item_value in value.items()
            if str(item_key).lower() not in _SENSITIVE_KEYS
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [
            item
            if item is None or isinstance(item, (str, int, float, bool))
            else f"<{type(item).__name__}>"
            for item in value
        ]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return f"<{type(value).__name__}>"


def _safe_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return _safe_wire_value(value or {})


@dataclass(frozen=True, slots=True)
class PhysicalExecutorInfo:
    identity: str
    package: str
    version: str
    plan_versions: tuple[str, ...] = ("etlantic.plan/2",)
    unit_protocol_versions: tuple[str, ...] = (PHYSICAL_UNIT_SCHEMA,)
    unit_kinds: tuple[str, ...] = tuple(kind.value for kind in PhysicalUnitKind)
    capability_fingerprint: str = ""
    evidence_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": PHYSICAL_EXECUTION_SCHEMA,
            "identity": self.identity,
            "package": self.package,
            "version": self.version,
            "plan_versions": list(self.plan_versions),
            "unit_protocol_versions": list(self.unit_protocol_versions),
            "unit_kinds": list(self.unit_kinds),
            "capability_fingerprint": self.capability_fingerprint,
            "evidence_refs": list(self.evidence_refs),
        }


@dataclass(frozen=True, slots=True)
class PhysicalUnitFinding:
    code: str
    unit_id: str
    target_identity: str
    path: tuple[str, ...] = ()
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "unit_id": self.unit_id,
            "target_identity": self.target_identity,
            "path": list(self.path),
            "reason": self.reason[:1024],
        }


@dataclass(frozen=True, slots=True)
class PhysicalUnitSupport:
    supported: bool
    executor_identity: str
    protocol_version: str = PHYSICAL_UNIT_SCHEMA
    findings: tuple[PhysicalUnitFinding, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": PHYSICAL_EXECUTION_SCHEMA,
            "supported": self.supported,
            "executor_identity": self.executor_identity,
            "protocol_version": self.protocol_version,
            "findings": [finding.to_dict() for finding in self.findings[:8]],
        }


@dataclass(frozen=True, slots=True)
class PhysicalArtifactHandle:
    """A process-local artifact; ``value`` is intentionally not serializable."""

    ref: Any
    value: Any = field(repr=False, compare=False)
    target_identity: str = ""
    ownership: str = "owned"
    cleanup_token: str | None = None

    def to_dict(self) -> dict[str, Any]:
        # ``ref`` is process-local. Never invoke arbitrary provider
        # serialization hooks; expose only a bounded type/scalar identity.
        ref = (
            {"identity": str(self.ref)}
            if self.ref is None or isinstance(self.ref, (str, int, float, bool))
            else {"identity": type(self.ref).__name__}
        )
        return {
            "schema": PHYSICAL_EXECUTION_SCHEMA,
            "ref": ref,
            "target_identity": self.target_identity,
            "ownership": self.ownership,
            "cleanup_token": self.cleanup_token,
        }


@dataclass(frozen=True, slots=True)
class PhysicalLogicalOutcome:
    logical_name: str
    status: str
    attempts: int = 1
    implementation: str | None = None
    records_in: int | None = None
    records_out: int | None = None
    failure_stage: str | None = None
    code: str | None = None
    metrics: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "logical_name": self.logical_name,
            "status": self.status,
            "attempts": self.attempts,
            "implementation": self.implementation,
            "records_in": self.records_in,
            "records_out": self.records_out,
            "failure_stage": self.failure_stage,
            "code": self.code,
            "metrics": _safe_mapping(self.metrics),
        }


@dataclass(frozen=True, slots=True)
class PhysicalUnitContext:
    plan: Any
    unit: PhysicalUnit
    run_id: str
    unit_attempt: int
    member_attempts: Mapping[str, int] = field(default_factory=dict)
    adapters: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)
    effective_policy: Mapping[str, Any] = field(default_factory=dict)
    inputs: Mapping[str, PhysicalArtifactHandle] = field(
        default_factory=dict, repr=False, compare=False
    )
    services: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class PhysicalUnitResult:
    unit_id: str
    target_identity: str
    status: str
    outputs: tuple[PhysicalArtifactHandle, ...] = field(
        default_factory=tuple, repr=False, compare=False
    )
    logical_outcomes: tuple[PhysicalLogicalOutcome, ...] = ()
    diagnostics: tuple[Mapping[str, Any], ...] = ()
    commit_receipt: Any | None = field(default=None, repr=False, compare=False)
    cleanup_receipts: tuple[Any, ...] = field(
        default_factory=tuple, repr=False, compare=False
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": PHYSICAL_EXECUTION_SCHEMA,
            "unit_id": self.unit_id,
            "target_identity": self.target_identity,
            "status": self.status,
            "outputs": [output.to_dict() for output in self.outputs],
            "logical_outcomes": [
                outcome.to_dict() for outcome in self.logical_outcomes
            ],
            "diagnostics": [_safe_mapping(item) for item in self.diagnostics],
        }


class PhysicalUnitFailure(Exception):
    """Safe, attributed physical-unit failure."""

    def __init__(
        self,
        message: str,
        *,
        unit_id: str,
        target_identity: str,
        code: str = "PMADP520",
        stage: str = "execute",
        logical_names: tuple[str, ...] = (),
        unknown_receipt: Any | None = None,
    ) -> None:
        super().__init__(message[:1024])
        self.unit_id = unit_id
        self.target_identity = target_identity
        self.code = code
        self.stage = stage
        self.logical_names = logical_names
        self.unknown_receipt = unknown_receipt

    def to_dict(self) -> dict[str, Any]:
        receipt = self.unknown_receipt
        return {
            "schema": PHYSICAL_EXECUTION_SCHEMA,
            "unit_id": self.unit_id,
            "target_identity": self.target_identity,
            "code": self.code,
            "stage": self.stage,
            "logical_names": list(self.logical_names),
            "message": _safe_failure_message(str(self)),
            "unknown_receipt": (
                receipt.to_dict()
                if receipt is not None and hasattr(receipt, "to_dict")
                else None
            ),
        }


def _safe_failure_message(message: str) -> str:
    cleaned = redact_message(message)
    lowered = cleaned.lower()
    if any(marker in lowered for marker in ("rows", "records", "payload")) or any(
        marker in cleaned for marker in ("{", "[")
    ):
        return "Physical unit failure details were redacted."
    return cleaned[:1024]


def validate_unit_result(result: PhysicalUnitResult, unit: PhysicalUnit) -> None:
    """Validate executor identity attribution before a result is registered."""
    if result.unit_id != unit.identity:
        raise PhysicalUnitFailure(
            "Physical executor returned a result for a different unit",
            unit_id=unit.identity,
            target_identity=unit.target_identity,
            code="PMADP400",
        )
    if result.target_identity != unit.target_identity:
        raise PhysicalUnitFailure(
            "Physical executor returned a result for a different target",
            unit_id=unit.identity,
            target_identity=unit.target_identity,
            code="PMADP400",
        )
    if result.status not in {
        "succeeded",
        "failed",
        "cancelled",
        "timed_out",
        "abandoned",
    }:
        raise PhysicalUnitFailure(
            "Physical executor returned an unknown status",
            unit_id=unit.identity,
            target_identity=unit.target_identity,
            code="PMADP400",
        )
    if any(
        output.target_identity not in {"", unit.target_identity}
        for output in result.outputs
    ):
        raise PhysicalUnitFailure(
            "Physical executor returned an output owned by another target",
            unit_id=unit.identity,
            target_identity=unit.target_identity,
            code="PMADP400",
        )


@runtime_checkable
class PhysicalUnitExecutor(Protocol):
    @property
    def info(self) -> PhysicalExecutorInfo: ...

    def analyze(self, plan: Any, unit: PhysicalUnit) -> PhysicalUnitSupport: ...

    async def execute(self, context: PhysicalUnitContext) -> PhysicalUnitResult: ...

    async def cancel(self, context: PhysicalUnitContext) -> None: ...

    async def cleanup(
        self, context: PhysicalUnitContext, result: PhysicalUnitResult | None
    ) -> tuple[Any, ...]: ...


__all__ = [
    "PHYSICAL_EXECUTION_SCHEMA",
    "PhysicalArtifactHandle",
    "PhysicalExecutorInfo",
    "PhysicalLogicalOutcome",
    "PhysicalUnitContext",
    "PhysicalUnitExecutor",
    "PhysicalUnitFailure",
    "PhysicalUnitFinding",
    "PhysicalUnitResult",
    "PhysicalUnitSupport",
    "validate_unit_result",
]
