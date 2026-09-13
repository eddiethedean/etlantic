"""Versioned execution contracts for adaptive physical units.

The records in this module deliberately separate wire-safe execution summaries
from process-local values.  They are independent of the ``etlantic.plan/2``
document schema so a consumer can negotiate both versions explicitly.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from etlantic.plan.physical import PHYSICAL_UNIT_SCHEMA, PhysicalUnit, PhysicalUnitKind

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


_SAFE_NUMERIC_KEYS = frozenset(
    {
        "attempts",
        "max_attempts",
        "records_in",
        "records_out",
        "row_count",
        "byte_count",
        "rows_processed",
        "bytes_processed",
        "duration_seconds",
        "elapsed_ms",
        "max_rows",
        "max_bytes",
    }
)


def _count(value: Any) -> int | None:
    return value if type(value) is int and 0 <= value < 2**63 else None


def _status(value: Any) -> str:
    return (
        value
        if type(value) is str
        and value
        in {
            "succeeded",
            "skipped",
            "failed",
            "cancelled",
            "timed_out",
            "abandoned",
            "pending",
            "committed",
            "rolled_back",
            "unknown",
        }
        else "<redacted>"
    )


def _code(value: Any) -> str | None:
    return (
        value
        if type(value) is str and re.fullmatch(r"PM[A-Z]+[0-9]{3}", value)
        else None
    )


def _identifier(value: Any) -> str | None:
    if value is None:
        return None
    if (
        type(value) is str
        and len(value) <= 256
        and re.fullmatch(r"[A-Za-z0-9_.:/-]+", value)
    ):
        return value
    if type(value) is str:
        return "sha256:" + hashlib.sha256(value.encode()).hexdigest()
    return "opaque"


def _safe_wire_value(value: Any, *, key: str | None = None, depth: int = 0) -> Any:
    """Bounded numeric metadata projection; arbitrary text/native values stay local."""
    if depth > 8 or (key is not None and key.lower() in _SENSITIVE_KEYS):
        return "<redacted>"
    if isinstance(value, Mapping):
        return {
            str(k): _safe_wire_value(v, key=str(k), depth=depth + 1)
            for k, v in list(value.items())[:64]
            if isinstance(k, str)
            and len(k) <= 128
            and re.fullmatch(r"[A-Za-z][A-Za-z0-9_.:-]*", k)
            and k.lower() not in _SENSITIVE_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_safe_wire_value(item, depth=depth + 1) for item in value[:64]]
    if value is None:
        return None
    if isinstance(value, (bool, int, float)):
        metric = (key or "").rsplit(".", 1)[-1]
        if metric not in _SAFE_NUMERIC_KEYS:
            return "<redacted>"
        return value if not isinstance(value, float) or math.isfinite(value) else None
    if (
        isinstance(value, str)
        and key == "code"
        and re.fullmatch(r"PM[A-Z]+[0-9]{3}", value)
    ):
        return value
    if (
        isinstance(value, str)
        and key in {"status", "severity", "ownership"}
        and value
        in {
            "succeeded",
            "failed",
            "cancelled",
            "timed_out",
            "abandoned",
            "committed",
            "rolled_back",
            "unknown",
            "error",
            "warning",
            "info",
            "owned",
            "borrowed",
            "shared",
            "copied",
        }
    ):
        return value
    return "<redacted>"


def _safe_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return _safe_wire_value(value or {})


def safe_receipt(receipt: Any) -> dict[str, Any] | None:
    """Project known receipts without calling provider-controlled serializers."""
    from etlantic.connectors.models import CommitReceipt

    if receipt is None:
        return None
    if type(receipt) is not CommitReceipt:
        return {"type": "opaque"}
    result = {"status": _status(receipt.status)}
    for name in ("publication_id", "session_id", "provider"):
        value = getattr(receipt, name)
        if (
            isinstance(value, str)
            and len(value) <= 256
            and re.fullmatch(r"[A-Za-z0-9_:.-]+", value)
        ):
            result[name] = value
    return result


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
            "identity": _identifier(self.identity),
            "package": _identifier(self.package),
            "version": _identifier(self.version),
            "plan_versions": [_identifier(v) for v in self.plan_versions[:8]],
            "unit_protocol_versions": [
                _identifier(v) for v in self.unit_protocol_versions[:8]
            ],
            "unit_kinds": [_identifier(v) for v in self.unit_kinds[:8]],
            "capability_fingerprint": _identifier(self.capability_fingerprint),
            "evidence_refs": [_identifier(v) for v in self.evidence_refs[:16]],
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
            "code": _code(self.code),
            "unit_id": _identifier(self.unit_id),
            "target_identity": _identifier(self.target_identity),
            "path": [_identifier(part) for part in self.path[:16]],
            "reason": "Physical unit support requirement is not satisfied."
            if self.reason
            else "",
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
            "executor_identity": _identifier(self.executor_identity),
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
        from etlantic.plan.artifacts import ArtifactRef

        ref = (
            {"identity": "sha256:" + hashlib.sha256(str(self.ref).encode()).hexdigest()}
            if isinstance(self.ref, (str, int, float, bool)) or self.ref is None
            else {
                "identity": _identifier(self.ref.identity),
                "logical_output": _identifier(self.ref.logical_output),
                "strategy": self.ref.strategy.value,
            }
            if type(self.ref) is ArtifactRef
            else {"identity": "opaque"}
        )
        return {
            "schema": PHYSICAL_EXECUTION_SCHEMA,
            "ref": ref,
            "target_identity": _identifier(self.target_identity),
            "ownership": _identifier(self.ownership),
            "cleanup_token": "sha256:"
            + hashlib.sha256(self.cleanup_token.encode()).hexdigest()
            if self.cleanup_token
            else None,
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
            "logical_name": _identifier(self.logical_name),
            "status": _status(self.status),
            "attempts": _count(self.attempts),
            "implementation": _identifier(self.implementation),
            "records_in": _count(self.records_in),
            "records_out": _count(self.records_out),
            "failure_stage": _identifier(self.failure_stage),
            "code": _code(self.code),
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
            "unit_id": _identifier(self.unit_id),
            "target_identity": _identifier(self.target_identity),
            "status": _status(self.status),
            "outputs": [output.to_dict() for output in self.outputs],
            "logical_outcomes": [
                outcome.to_dict() for outcome in self.logical_outcomes
            ],
            "diagnostics": [_safe_mapping(item) for item in self.diagnostics[:64]],
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
        safe_unknown_receipt = safe_receipt(self.unknown_receipt)
        return {
            "schema": PHYSICAL_EXECUTION_SCHEMA,
            "unit_id": _identifier(self.unit_id),
            "target_identity": _identifier(self.target_identity),
            "code": _code(self.code),
            "stage": _identifier(self.stage),
            "logical_names": [_identifier(name) for name in self.logical_names[:256]],
            "message": _safe_failure_message(str(self)),
            "unknown_receipt": safe_unknown_receipt,
        }


def _safe_failure_message(message: str) -> str:
    # Exception messages are unrestricted data. Attribution belongs to the
    # closed code/unit/target/stage fields, never an arbitrary backend repr.
    return "Physical unit execution failed." if message else ""


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
