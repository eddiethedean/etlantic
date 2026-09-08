"""Portable transform compiler protocol (`etlantic.transform-compiler/1`)."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Protocol, runtime_checkable
from urllib.parse import quote

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
PUSHDOWN_OUTCOMES = frozenset(
    {"pushed_exact", "pushed_with_lowering", "not_pushed", "not_applicable", "unknown"}
)
MAX_REQUIREMENTS = 100_000
MAX_FINDINGS = 100_000
MAX_REPORT_BYTES = 8 * 1024 * 1024
MAX_CONDITIONS = 64
MAX_REASON_BYTES = 1_024


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
    proof_reference: str | None = None
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
        if self.proof_reference is not None:
            payload["proof_reference"] = self.proof_reference
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
    # Normalized requirement records are additive to the /1 aggregate fields.
    # Keep this last so existing positional construction remains compatible.
    requirements: tuple[Mapping[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "supported": self.supported,
            "findings": [f.to_dict() for f in self.findings],
        }
        if self.evidence_fingerprint is not None:
            payload["evidence_fingerprint"] = self.evidence_fingerprint
        if self.pushdown:
            payload["pushdown"] = [p.to_dict() for p in self.pushdown]
        if self.requirements:
            payload["requirements"] = [dict(item) for item in self.requirements]
        return payload

    def to_requirement_support(
        self, *, target: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        """Serialize the additive requirement-level support protocol."""
        requirements = [dict(item) for item in self.requirements]
        findings = []
        used_ids: set[str] = set()
        for index, finding in enumerate(self.findings):
            item = finding.to_dict()
            requirement_id = item.get("requirement")
            if requirement_id not in {r.get("id") for r in requirements}:
                remaining = [
                    r.get("id") for r in requirements if r.get("id") not in used_ids
                ]
                if remaining:
                    requirement_id = remaining[0]
            if requirement_id is None:
                requirement_id = _canonical_requirement_id(
                    "legacy", f"finding-{index}", "findings"
                )
                requirements.append(
                    {
                        "id": requirement_id,
                        "scope": "legacy",
                        "path": "findings",
                        "obligation": finding.obligation or "required",
                        "applicability": "applicable",
                        "parameters": {},
                    }
                )
            item["requirement"] = requirement_id
            item["support"] = finding.support or (
                "unsupported" if not self.supported else "supported_exact"
            )
            item["obligation"] = finding.obligation or "required"
            fingerprint = finding.evidence_fingerprint or self.evidence_fingerprint
            item["evidence_fingerprint"] = fingerprint
            item["evidence"] = ["compiler"] if fingerprint else []
            item["reason_code"] = finding.code
            item["path"] = finding.expression_path or "findings"
            used_ids.add(requirement_id)
            findings.append(item)
        # Legacy compilers may only provide aggregate findings. Preserve those
        # records while making successful reports explicit about their target.
        if not requirements:
            requirements = [
                {
                    "id": _canonical_requirement_id(
                        "legacy", finding.requirement, "findings"
                    ),
                    "scope": "legacy",
                    "path": finding.expression_path or "",
                    "obligation": finding.obligation or "required",
                    "applicability": "applicable",
                    "parameters": {},
                }
                for finding in self.findings
            ]
        finding_ids = {item.get("requirement") for item in findings}
        if self.supported and requirements:
            evidence = self.evidence_fingerprint
            findings.extend(
                {
                    "requirement": item.get("id") or item.get("requirement"),
                    "support": "supported_exact",
                    "reason": "supported by the analyzed compiler target",
                    "reason_code": "PMXFORM000",
                    "evidence": ["compiler"] if evidence else [],
                    "evidence_fingerprint": evidence,
                    "path": item.get("path") or "requirements",
                    "obligation": item.get("obligation", "required"),
                }
                for item in requirements
                if (item.get("id") or item.get("requirement")) not in finding_ids
            )
        elif requirements:
            # An aggregate unsupported/unknown report still needs one explicit
            # fail-closed finding for every applicable requirement.
            represented = {item.get("requirement") for item in findings}
            findings.extend(
                {
                    "requirement": item.get("id") or item.get("requirement"),
                    "support": "unknown",
                    "reason": "requirement has no independently verified support result",
                    "reason_code": "PMXFORM999",
                    "evidence": [],
                    "evidence_fingerprint": None,
                    "path": item.get("path") or "requirements",
                    "obligation": item.get("obligation", "required"),
                }
                for item in requirements
                if (item.get("id") or item.get("requirement")) not in represented
            )
        evidence = []
        if self.evidence_fingerprint:
            evidence.append(
                {
                    "id": "compiler",
                    "kind": "compiler_capability",
                    "fingerprint": self.evidence_fingerprint,
                }
            )
        payload = {
            "schema": "etlantic.portable-requirement-support/1",
            "target": {
                "engine": "unknown",
                "compiler": "unknown",
                "version": "unknown",
                "protocol": COMPILER_PROTOCOL,
                **dict(target or {}),
            },
            "requirements": requirements,
            "findings": findings,
            "evidence": evidence,
        }
        payload["fingerprint"] = _support_fingerprint(payload)
        validate_requirement_support_payload(payload)
        return payload


def requirement_records_from_mapping(
    requirements: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], ...]:
    """Convert legacy requirement lists into stable bounded protocol records."""
    records: list[dict[str, Any]] = []
    for scope in sorted((requirements or {}).keys()):
        value = (requirements or {}).get(scope)
        values = (
            value
            if isinstance(value, Sequence) and not isinstance(value, (str, bytes))
            else [value]
        )
        for item in values:
            if item is None:
                continue
            semantic_id = str(item)
            requirement_id = _canonical_requirement_id(scope, semantic_id, scope)
            records.append(
                {
                    "id": requirement_id,
                    "vocabulary": "dtcs",
                    "version": "1",
                    "scope": scope,
                    "path": scope,
                    "obligation": "required",
                    "applicability": "applicable",
                    "parameters": {"value": semantic_id},
                }
            )
    return tuple(records)


def _canonical_requirement_id(scope: str, semantic_id: str, path: str) -> str:
    """Build the value-free identifier required by the public support schema."""
    encoded = quote(str(semantic_id), safe=":@._-~")
    return f"dtcs@1/{scope}/{encoded}#{path}"


def _support_fingerprint(payload: Mapping[str, Any]) -> str:
    semantic = {key: value for key, value in payload.items() if key != "fingerprint"}
    return sha256(
        json.dumps(
            semantic, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    ).hexdigest()


def validate_requirement_support_payload(payload: Mapping[str, Any]) -> None:
    """Validate the bounded requirement/support wire representation."""
    import json

    if payload.get("schema") != "etlantic.portable-requirement-support/1":
        raise ValueError("invalid requirement-support schema")
    if not isinstance(payload.get("target"), Mapping):
        raise ValueError("requirement-support target must be an object")
    target = payload["target"]
    for key in ("engine", "compiler", "version", "protocol"):
        if not isinstance(target.get(key), str) or not target[key]:
            raise ValueError(f"requirement-support target.{key} must be non-empty")
    requirements = payload.get("requirements")
    findings = payload.get("findings")
    if not isinstance(requirements, list) or not isinstance(findings, list):
        raise ValueError("requirements and findings must be arrays")
    if len(requirements) > MAX_REQUIREMENTS or len(findings) > MAX_FINDINGS:
        raise ValueError("requirement-support report exceeds record limit")
    requirement_ids: set[str] = set()
    for item in requirements:
        if not isinstance(item, Mapping):
            raise ValueError("requirement record must be an object")
        identifier = item.get("id")
        if (
            not isinstance(identifier, str)
            or not identifier
            or identifier in requirement_ids
        ):
            raise ValueError("requirement IDs must be non-empty and unique")
        requirement_ids.add(identifier)
        if not identifier.startswith("dtcs@1/") or "#" not in identifier:
            raise ValueError("requirement IDs must use canonical dtcs@1 form")
        if not isinstance(item.get("scope"), str) or not isinstance(
            item.get("path"), str
        ):
            raise ValueError("requirement scope and path are required")
        if not isinstance(item.get("parameters"), Mapping):
            raise ValueError("requirement parameters must be an object")
        if item.get("obligation") not in OBLIGATIONS:
            raise ValueError("invalid requirement obligation")
        if item.get("applicability") not in {"applicable", "not_applicable"}:
            raise ValueError("invalid requirement applicability")
    finding_ids: set[str] = set()
    for item in findings:
        if not isinstance(item, Mapping):
            raise ValueError("support finding must be an object")
        identifier = item.get("requirement")
        if (
            not isinstance(identifier, str)
            or not identifier
            or identifier in finding_ids
        ):
            raise ValueError("finding requirement IDs must be non-empty and unique")
        finding_ids.add(identifier)
        if item.get("support") not in SUPPORT_STATES:
            raise ValueError("invalid support state")
        if item.get("obligation") not in OBLIGATIONS:
            raise ValueError("invalid finding obligation")
        reason = item.get("reason")
        if (
            not isinstance(reason, str)
            or len(reason.encode("utf-8")) > MAX_REASON_BYTES
        ):
            raise ValueError("finding reason exceeds 1024 UTF-8 bytes")
        if not isinstance(item.get("reason_code"), str) or not item["reason_code"]:
            raise ValueError("support finding requires a stable reason code")
        evidence_refs = item.get("evidence", [])
        if not isinstance(evidence_refs, list):
            raise ValueError("finding evidence must be an array")
        if item["support"] in {"supported_exact", "supported_with_lowering"}:
            if not isinstance(item.get("evidence_fingerprint"), str):
                raise ValueError("supported finding requires evidence fingerprint")
            if not evidence_refs:
                raise ValueError("supported finding requires evidence reference")
        if item["support"] == "supported_with_lowering":
            if not item.get("lowering_id"):
                raise ValueError("lowered finding requires lowering identity")
            if not isinstance(item.get("proof_reference"), str):
                raise ValueError("lowered finding requires proof reference")
            if not isinstance(item.get("conditions"), list) or not isinstance(
                item.get("physical_effects"), list
            ):
                raise ValueError("lowered finding requires conditions and effects")
        for key in ("conditions", "physical_effects"):
            values = item.get(key, [])
            if not isinstance(values, list) or len(values) > MAX_CONDITIONS:
                raise ValueError(f"{key} exceeds 64 entries")
    applicable = {
        str(item["id"])
        for item in requirements
        if item.get("applicability") == "applicable"
    }
    if applicable != finding_ids:
        raise ValueError("every applicable requirement needs exactly one finding")
    evidence = payload.get("evidence")
    if not isinstance(evidence, list):
        raise ValueError("evidence must be an array")
    evidence_ids = set()
    for record in evidence:
        if not isinstance(record, Mapping) or not isinstance(record.get("id"), str):
            raise ValueError("evidence records require string IDs")
        if record["id"] in evidence_ids:
            raise ValueError("evidence IDs must be unique")
        evidence_ids.add(record["id"])
    for finding in findings:
        if not set(finding.get("evidence", [])).issubset(evidence_ids):
            raise ValueError("finding references unknown evidence")
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    if len(serialized) > MAX_REPORT_BYTES:
        raise ValueError("serialized support report exceeds 8 MiB")
    fingerprint = payload.get("fingerprint")
    if not isinstance(fingerprint, str) or fingerprint != _support_fingerprint(payload):
        raise ValueError("support report fingerprint is invalid")


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
