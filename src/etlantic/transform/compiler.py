"""Portable transform compiler protocol (`etlantic.transform-compiler/1`)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

COMPILER_PROTOCOL = "etlantic.transform-compiler/1"
SUPPORT_STATES = frozenset(
    {
        "supported_exact",
        "supported_with_lowering",
        "unsupported",
        "unavailable",
        "unknown",
    }
)
OBLIGATIONS = frozenset({"required", "preferred", "informational"})


@dataclass(frozen=True, slots=True)
class TransformCapabilities:
    """Advertised compiler capabilities over DTCS profiles and operators."""

    profiles: frozenset[str] = frozenset()
    actions: frozenset[str] = frozenset()
    functions: frozenset[str] = frozenset()
    operators: frozenset[str] = frozenset()
    types: frozenset[str] = frozenset()
    semantic_modes: frozenset[str] = frozenset()
    lazy: bool = True
    eager: bool = True
    max_plan_nodes: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "profiles": sorted(self.profiles),
            "actions": sorted(self.actions),
            "functions": sorted(self.functions),
            "operators": sorted(self.operators),
            "types": sorted(self.types),
            "semantic_modes": sorted(self.semantic_modes),
            "lazy": self.lazy,
            "eager": self.eager,
            "max_plan_nodes": self.max_plan_nodes,
        }


@dataclass(frozen=True, slots=True)
class TransformCompilerInfo:
    """Installed transform compiler metadata."""

    name: str
    version: str
    engine: str
    compiler_protocol: str = COMPILER_PROTOCOL
    dtcs_plan_versions: tuple[str, ...] = (
        "dtcs.transform-plan/2",
        "dtcs.transform-plan/1",
    )
    capabilities: TransformCapabilities = field(default_factory=TransformCapabilities)
    # Optional evidence identity.  This is deliberately additive so existing
    # /1 compiler implementations remain valid and serializable.
    evidence_fingerprint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "name": self.name,
            "version": self.version,
            "engine": self.engine,
            "compiler_protocol": self.compiler_protocol,
            "dtcs_plan_versions": list(self.dtcs_plan_versions),
            "capabilities": self.capabilities.to_dict(),
        }
        if self.evidence_fingerprint is not None:
            payload["evidence_fingerprint"] = self.evidence_fingerprint
        return payload


@dataclass(frozen=True, slots=True)
class TransformSupportFinding:
    """One unsupported or conditional requirement from analyze()."""

    code: str
    requirement: str
    reason: str
    expression_path: str | None = None
    # /1-compatible optional evidence fields.  ``support`` is intentionally a
    # string rather than a new enum so third-party compilers can add a state
    # without requiring a protocol-major change.
    obligation: str | None = None
    support: str | None = None
    lowering_id: str | None = None
    conditions: tuple[str, ...] = ()
    physical_effects: tuple[str, ...] = ()
    evidence_fingerprint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "code": self.code,
            "requirement": self.requirement,
            "reason": self.reason,
            "expression_path": self.expression_path,
        }
        if self.obligation is not None:
            payload["obligation"] = self.obligation
        if self.support is not None:
            payload["support"] = self.support
        if self.lowering_id is not None:
            payload["lowering_id"] = self.lowering_id
        if self.conditions:
            payload["conditions"] = list(self.conditions)
        if self.physical_effects:
            payload["physical_effects"] = list(self.physical_effects)
        if self.evidence_fingerprint is not None:
            payload["evidence_fingerprint"] = self.evidence_fingerprint
        return payload


@dataclass(frozen=True, slots=True)
class TransformPushdownFinding:
    """Boundary-scoped pushdown outcome kept separate from support failures."""

    boundary: str
    outcome: str
    reason: str
    physical_effects: tuple[str, ...] = ()
    evidence_fingerprint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "boundary": self.boundary,
            "outcome": self.outcome,
            "reason": self.reason,
            "physical_effects": list(self.physical_effects),
        }
        if self.evidence_fingerprint is not None:
            payload["evidence_fingerprint"] = self.evidence_fingerprint
        return payload


@dataclass(frozen=True, slots=True)
class TransformSupportReport:
    """Deterministic support analysis for a transformation plan."""

    supported: bool
    findings: tuple[TransformSupportFinding, ...] = ()
    evidence_fingerprint: str | None = None
    pushdown: tuple[TransformPushdownFinding, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "supported": self.supported,
            "findings": [f.to_dict() for f in self.findings],
        }
        if self.evidence_fingerprint is not None:
            payload["evidence_fingerprint"] = self.evidence_fingerprint
        if self.pushdown:
            payload["pushdown"] = [p.to_dict() for p in self.pushdown]
        return payload

    def to_requirement_support(
        self, *, target: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        """Serialize the additive requirement-level support protocol."""
        return {
            "schema": "etlantic.portable-requirement-support/1",
            "target": dict(target or {}),
            "requirements": [],
            "findings": [
                {
                    "requirement": finding.requirement,
                    "support": finding.support
                    or ("unsupported" if not self.supported else "supported_exact"),
                    "reason": finding.reason,
                    "evidence": finding.evidence_fingerprint
                    or self.evidence_fingerprint,
                    "path": finding.expression_path,
                    "obligation": finding.obligation or "required",
                }
                for finding in self.findings
            ],
            "evidence": [],
        }


@dataclass(frozen=True, slots=True)
class TransformPlanningContext:
    """Caller identity for analyze() (no data access)."""

    pipeline_id: str
    step_name: str
    profile_name: str
    engine: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TransformCompileContext:
    """Caller identity for compile() (no data access)."""

    pipeline_id: str
    plan_id: str
    step_name: str
    profile_name: str
    engine: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TransformExecutionContext:
    """Runtime identity for execute()."""

    run_id: str
    pipeline_id: str
    plan_id: str
    step_name: str
    engine: str
    attempt: int = 1
    collect: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CompiledTransform:
    """In-memory compiled artifact (never serialize backend objects into plans)."""

    compiler_name: str
    compiler_version: str
    engine: str
    ir_fingerprint: str
    output_ports: tuple[str, ...] = ("result",)
    parameter_names: tuple[str, ...] = ()
    explain: dict[str, Any] = field(default_factory=dict)
    # Opaque backend handle kept only in process memory.
    native_plan: Any = None


@dataclass(frozen=True, slots=True)
class TransformOutputBundle:
    """Normalized compiler execution outputs."""

    valid: Mapping[str, Any]
    invalid: Mapping[str, Any] = field(default_factory=dict)
    side: Mapping[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    diagnostics: Sequence[dict[str, Any]] = ()


@runtime_checkable
class PortableTransformCompiler(Protocol):
    """Plugin protocol for analyzing, compiling, and executing portable IR."""

    @property
    def info(self) -> TransformCompilerInfo: ...

    def analyze(
        self,
        definition: Mapping[str, Any],
        *,
        context: TransformPlanningContext,
        requirements: Mapping[str, Sequence[str]] | None = None,
    ) -> TransformSupportReport: ...

    def compile(
        self,
        definition: Mapping[str, Any],
        *,
        context: TransformCompileContext,
        requirements: Mapping[str, Sequence[str]] | None = None,
    ) -> CompiledTransform: ...

    async def execute(
        self,
        compiled: CompiledTransform,
        *,
        inputs: Mapping[str, Any],
        parameters: Mapping[str, Any],
        context: TransformExecutionContext,
    ) -> TransformOutputBundle: ...
