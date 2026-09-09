"""Portable transform compiler protocol (`etlantic.transform-compiler/1`)."""

from __future__ import annotations

import json
import re
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
    {
        "pushed_exact",
        "pushed_with_lowering",
        "not_pushed",
        "not_applicable",
        "unsupported",
        "unavailable",
        "unknown",
    }
)
MAX_REQUIREMENTS = 100_000
MAX_FINDINGS = 100_000
MAX_REPORT_BYTES = 8 * 1024 * 1024
MAX_CONDITIONS = 64
MAX_REASON_BYTES = 1_024
MAX_PARAMETER_BYTES = 1_024
_STATIC_CONDITION_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]*(?:[._:/-][A-Za-z0-9]+)*$")
_STATIC_CONDITION_IDENTIFIERS = frozenset({"preserve-null", "preserve-order"})
_DYNAMIC_CONDITION_PARTS = frozenset(
    {
        "source",
        "row",
        "rows",
        "input",
        "inputs",
        "runtime",
        "live",
        "probe",
        "value",
        "values",
        "param",
        "parameter",
        "data",
    }
)
PHYSICAL_EFFECTS = frozenset(
    {"collection", "transfer", "materialization", "lost_fusion"}
)
_TARGET_KEYS = frozenset(
    {
        "engine",
        "compiler",
        "version",
        "protocol",
        "package",
        "implementation",
        "environment",
        "placement",
    }
)
_SUPPORT_PAYLOAD_KEYS = frozenset(
    {
        "schema",
        "target",
        "requirements",
        "findings",
        "evidence",
        "pushdown",
        "fingerprint",
    }
)
_PLACEMENT_TARGET_KEYS = frozenset(
    {"resource", "location", "security_domain", "connector", "policy"}
)
_ENVIRONMENT_KEYS = frozenset({"dialect", "runtime", "driver", "version"})
_REQUIREMENT_KEYS = frozenset(
    {
        "id",
        "vocabulary",
        "version",
        "scope",
        "path",
        "obligation",
        "applicability",
        "parameters",
    }
)
_FINDING_KEYS = frozenset(
    {
        "code",
        "requirement",
        "reason",
        "expression_path",
        "obligation",
        "support",
        "lowering_id",
        "proof_reference",
        "conditions",
        "physical_effects",
        "evidence_fingerprint",
        "reason_code",
        "evidence",
        "path",
    }
)
_EVIDENCE_KEYS = frozenset({"id", "kind", "fingerprint", "baseline_digest"})
_PUSHDOWN_KEYS = frozenset(
    {
        "boundary",
        "action",
        "target",
        "lowering_id",
        "proof_reference",
        "conditions",
        "outcome",
        "reason",
        "obligation",
        "physical_effects",
        "evidence_fingerprint",
    }
)


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
    # Additive dimensions; kept last for positional /1 compatibility.
    partial_profiles: frozenset[str] = frozenset()
    join_modes: frozenset[str] = frozenset()
    union_modes: frozenset[str] = frozenset()
    collision_policies: frozenset[str] = frozenset()

    def to_dict(self) -> dict[str, Any]:
        return {
            "profiles": sorted(self.profiles),
            "partial_profiles": sorted(self.partial_profiles),
            "actions": sorted(self.actions),
            "functions": sorted(self.functions),
            "operators": sorted(self.operators),
            "types": sorted(self.types),
            "semantic_modes": sorted(self.semantic_modes),
            "join_modes": sorted(self.join_modes),
            "union_modes": sorted(self.union_modes),
            "collision_policies": sorted(self.collision_policies),
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
    implementation: str | None = None
    package: str | None = None
    # Runtime/dialect identity that participates in evidence fingerprints.
    environment: Mapping[str, str] | None = None

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
        if self.implementation is not None:
            payload["implementation"] = self.implementation
        if self.package is not None:
            payload["package"] = self.package
        if self.environment is not None:
            payload["environment"] = dict(self.environment)
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
    action: str | None = None
    target: str | None = None
    proof_reference: str | None = None
    physical_effects: tuple[str, ...] = ()
    evidence_fingerprint: str | None = None
    obligation: str | None = None
    # Additive /1 fields kept last for positional compatibility.
    lowering_id: str | None = None
    conditions: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "boundary": self.boundary,
            "outcome": self.outcome,
            "reason": self.reason,
            "physical_effects": list(self.physical_effects),
        }
        if self.action is not None:
            payload["action"] = self.action
        if self.target is not None:
            payload["target"] = self.target
        if self.proof_reference is not None:
            payload["proof_reference"] = self.proof_reference
        if self.lowering_id is not None:
            payload["lowering_id"] = self.lowering_id
        if self.conditions:
            payload["conditions"] = list(self.conditions)
        if self.obligation is not None:
            payload["obligation"] = self.obligation
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
    # Complete requirement vector produced by capability matching.  Kept
    # separate from ``findings`` for /1 compatibility, where findings were
    # traditionally failures only.
    requirement_findings: tuple[TransformSupportFinding, ...] = ()

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
        supplied_target = dict(target or {})
        unknown_target = set(supplied_target) - _TARGET_KEYS
        if unknown_target:
            raise ValueError(
                "requirement-support target contains unsupported fields: "
                + ", ".join(sorted(unknown_target))
            )
        requirements = [dict(item) for item in self.requirements]
        evidence_fingerprints: list[str] = []
        for candidate in [
            self.evidence_fingerprint,
            *(finding.evidence_fingerprint for finding in self.requirement_findings),
            *(finding.evidence_fingerprint for finding in self.findings),
        ]:
            if candidate and candidate not in evidence_fingerprints:
                evidence_fingerprints.append(candidate)
        evidence_ids = {
            fingerprint: ("compiler" if index == 0 else f"compiler-{index + 1}")
            for index, fingerprint in enumerate(evidence_fingerprints)
        }
        requirement_by_legacy: dict[str, list[str]] = {}
        for record in requirements:
            identifier = record.get("id")
            value = (record.get("parameters") or {}).get("value")
            scope = str(record.get("scope") or "")
            if isinstance(identifier, str) and value is not None:
                singular = {
                    "profiles": "profile",
                    "actions": "action",
                    "functions": "function",
                    "operators": "operator",
                    "types": "type",
                    "semantic_modes": "semantic_mode",
                    "join_modes": "join_mode",
                    "union_modes": "union_mode",
                    "collision_policies": "collision_policy",
                }.get(scope, scope.rstrip("s"))
                requirement_by_legacy.setdefault(f"{singular}:{value}", []).append(
                    identifier
                )
                if scope in {"eager", "lazy"}:
                    requirement_by_legacy.setdefault(f"mode:{scope}", []).append(
                        identifier
                    )
        findings = []
        canonical_findings = list(self.requirement_findings)
        used_ids: set[str] = set()
        serialized_by_requirement: dict[str, dict[str, Any]] = {}
        requirements_by_id: dict[str, dict[str, Any]] = {}
        for record in requirements:
            identifier = record.get("id")
            if not isinstance(identifier, str) or not identifier:
                raise ValueError("requirement records must have non-empty string IDs")
            if identifier in requirements_by_id:
                raise ValueError("requirement IDs must be unique")
            requirements_by_id[identifier] = record
        requirement_ids = set(requirements_by_id)
        for collection in (canonical_findings, list(self.findings)):
            collection_object_ids: set[int] = set()
            for finding in collection:
                if id(finding) in collection_object_ids:
                    raise ValueError(
                        "support findings must contain exactly one result per requirement"
                    )
                collection_object_ids.add(id(finding))
        seen_finding_objects: set[int] = set()
        for index, finding in enumerate((*canonical_findings, *self.findings)):
            item = finding.to_dict()
            finding_object_id = id(finding)
            if finding_object_id in seen_finding_objects:
                continue
            seen_finding_objects.add(finding_object_id)
            original_requirement = str(item.get("requirement") or f"finding-{index}")
            matched_requirement_ids: list[str] = []
            if original_requirement in requirement_ids:
                matched_requirement_ids.append(original_requirement)
            else:
                legacy_match = requirement_by_legacy.get(original_requirement)
                if legacy_match is not None:
                    matched_requirement_ids.extend(legacy_match)
                elif original_requirement.startswith("requirement:"):
                    category = original_requirement.removeprefix("requirement:")
                    matched_requirement_ids.extend(
                        str(record["id"])
                        for record in requirements
                        if record.get("scope") == category
                        and isinstance(record.get("id"), str)
                    )
                elif original_requirement.startswith("environment:"):
                    matched_requirement_ids.extend(
                        str(record["id"])
                        for record in requirements
                        if record.get("scope") == "environment_requirements"
                        and (record.get("parameters") or {}).get("value")
                        == original_requirement.removeprefix("environment:")
                        and isinstance(record.get("id"), str)
                    )
            if not matched_requirement_ids:
                requirement_id = _canonical_requirement_id(
                    "legacy",
                    original_requirement,
                    "findings",
                )
                requirements.append(
                    {
                        "id": requirement_id,
                        "vocabulary": "dtcs",
                        "version": "1",
                        "scope": "legacy",
                        "path": "findings",
                        "obligation": finding.obligation or "required",
                        "applicability": "applicable",
                        "parameters": {"legacy_requirement": original_requirement},
                    }
                )
                requirement_ids.add(requirement_id)
                requirements_by_id[requirement_id] = requirements[-1]
                matched_requirement_ids.append(requirement_id)
            for requirement_id in matched_requirement_ids:
                serialized = dict(item)
                serialized["requirement"] = requirement_id
                serialized["support"] = finding.support or (
                    "unsupported" if not self.supported else "supported_exact"
                )
                requirement = requirements_by_id[requirement_id]
                serialized["obligation"] = str(
                    requirement.get("obligation") or "required"
                )
                fingerprint = finding.evidence_fingerprint or self.evidence_fingerprint
                serialized["evidence_fingerprint"] = fingerprint
                serialized["evidence"] = (
                    [evidence_ids[fingerprint]] if fingerprint else []
                )
                if (
                    serialized["support"]
                    in {"supported_exact", "supported_with_lowering"}
                    and not fingerprint
                ):
                    # Positive records without compiler evidence are legacy
                    # omissions, not proof; preserve inspectability as unknown.
                    serialized["support"] = "unknown"
                    serialized["reason"] = (
                        "requirement has no independently verified support evidence"
                    )
                    serialized["reason_code"] = "PMXFORM999"
                if serialized.get("reason_code") != "PMXFORM999":
                    serialized["reason_code"] = finding.code
                serialized["path"] = finding.expression_path or str(
                    requirement.get("path") or "findings"
                )
                if requirement_id in serialized_by_requirement:
                    raise ValueError(
                        "support findings must contain exactly one result per requirement"
                    )
                used_ids.add(requirement_id)
                serialized_by_requirement[requirement_id] = serialized
        findings.extend(serialized_by_requirement.values())
        # Legacy compilers may only provide aggregate findings. Preserve those
        # records while making successful reports explicit about their target.
        if not requirements:
            requirements = [
                {
                    "id": _canonical_requirement_id(
                        "legacy", finding.requirement, "findings"
                    ),
                    "vocabulary": "dtcs",
                    "version": "1",
                    "scope": "legacy",
                    "path": "findings",
                    "obligation": finding.obligation or "required",
                    "applicability": "applicable",
                    "parameters": {"legacy_requirement": finding.requirement},
                }
                for finding in self.findings
            ]
        if requirements:
            # Missing vector entries are always unknown.  Aggregate success is
            # deliberately never converted into positive requirement evidence.
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
        for fingerprint, evidence_id in evidence_ids.items():
            evidence.append(
                {
                    "id": evidence_id,
                    "kind": "compiler_capability",
                    "fingerprint": fingerprint,
                    "baseline_digest": _baseline_digest(),
                }
            )
        # Duplicate IDs are rejected above; no requirement may be silently
        # discarded while normalizing a report.
        payload = {
            "schema": "etlantic.portable-requirement-support/1",
            "target": {
                "engine": "unknown",
                "compiler": "unknown",
                "version": "unknown",
                "protocol": COMPILER_PROTOCOL,
                **supplied_target,
            },
            "requirements": requirements,
            "findings": findings,
            "evidence": evidence,
            "pushdown": [item.to_dict() for item in self.pushdown],
        }
        payload["fingerprint"] = _support_fingerprint(payload)
        validate_requirement_support_payload(payload)
        return payload


def requirement_records_from_mapping(
    requirements: Mapping[str, Any] | None,
    *,
    definition: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], ...]:
    """Convert requirement lists into stable, occurrence-aware protocol records."""
    occurrence_paths = _requirement_occurrence_paths(definition or {})
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
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
            paths = occurrence_paths.get((scope, semantic_id)) or (scope,)
            for path in paths:
                requirement_id = _canonical_requirement_id(scope, semantic_id, path)
                if requirement_id in seen:
                    continue
                seen.add(requirement_id)
                records.append(
                    {
                        "id": requirement_id,
                        "vocabulary": "dtcs",
                        "version": "1",
                        "scope": scope,
                        "path": path,
                        "obligation": "required",
                        "applicability": "applicable",
                        "parameters": {"value": semantic_id},
                    }
                )
    return tuple(records)


def _requirement_occurrence_paths(
    definition: Mapping[str, Any],
) -> dict[tuple[str, str], tuple[str, ...]]:
    """Return value-free logical paths for governed plan requirements."""
    from etlantic.transform.portable_baseline import (
        normalize_action,
        normalize_operator,
    )

    paths: dict[tuple[str, str], list[str]] = {}

    def record(scope: str, semantic_id: Any, path: str) -> None:
        key = (scope, str(semantic_id))
        values = paths.setdefault(key, [])
        if path not in values:
            values.append(path)

    def visit(node: Any, path: str) -> None:
        if isinstance(node, Mapping):
            kind = node.get("kind")
            if kind == "call" and isinstance(node.get("callee"), str):
                callee = str(node["callee"])
                if callee == "dtcs:in":
                    record("operators", "in", path)
                else:
                    record("functions", callee, path)
            elif (
                isinstance(kind, str)
                and kind in {"binary", "unary"}
                and isinstance(node.get("op"), str)
            ):
                record("operators", normalize_operator(str(node["op"])), path)
            elif kind == "literal":
                value = node.get("value")
                if isinstance(value, Mapping) and isinstance(value.get("type"), str):
                    record("types", value["type"], path)
            for key, value in node.items():
                visit(value, f"{path}/{key}" if path else str(key))
        elif isinstance(node, list):
            for index, value in enumerate(node):
                visit(value, f"{path}/{index}")

    profile = definition.get("profile")
    if isinstance(profile, str):
        record("profiles", profile, "profile")
    for index, item in enumerate(definition.get("actions") or ()):
        if not isinstance(item, Mapping):
            continue
        kind = item.get("kind")
        if not isinstance(kind, Mapping):
            continue
        action = kind.get("action")
        base = f"actions/{index}"
        if isinstance(action, str):
            action = normalize_action(action)
            record("actions", action, base)
        parameters = kind.get("parameters")
        if isinstance(parameters, Mapping):
            if action == "dtcs:join":
                if parameters.get("type") is not None:
                    record("join_modes", parameters["type"], f"{base}/parameters/type")
                if parameters.get("collisionPolicy") is not None:
                    record(
                        "collision_policies",
                        parameters["collisionPolicy"],
                        f"{base}/parameters/collisionPolicy",
                    )
            elif action == "dtcs:union" and parameters.get("mode") is not None:
                record("union_modes", parameters["mode"], f"{base}/parameters/mode")
        visit(item, base)
    for name, output in sorted((definition.get("outputs") or {}).items()):
        visit(output, f"outputs/{name}")
    return {key: tuple(values) for key, values in paths.items()}


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


def required_support_failures(payload: Mapping[str, Any]) -> tuple[str, ...]:
    """Return applicable required requirements without positive support."""
    findings = {
        item.get("requirement"): item.get("support")
        for item in payload.get("findings", ())
        if isinstance(item, Mapping)
    }
    invalid_lowerings = {
        str(item.get("requirement"))
        for item in payload.get("findings", ())
        if isinstance(item, Mapping)
        and item.get("support") == "supported_with_lowering"
        and (
            not isinstance(item.get("conditions"), list)
            or any(
                _static_condition_error(condition)
                for condition in item.get("conditions", ())
            )
        )
    }
    return tuple(
        str(item.get("id"))
        for item in payload.get("requirements", ())
        if isinstance(item, Mapping)
        and item.get("applicability") == "applicable"
        and item.get("obligation") == "required"
        and (
            findings.get(item.get("id"))
            not in {"supported_exact", "supported_with_lowering"}
            or item.get("id") in invalid_lowerings
        )
    )


def capabilities_fingerprint(
    capabilities: TransformCapabilities,
    *,
    compiler: str | None = None,
    implementation: str | None = None,
    package: str | None = None,
    version: str | None = None,
    engine: str | None = None,
    protocol: str = COMPILER_PROTOCOL,
    environment: Mapping[str, str] | None = None,
) -> str:
    """Stable evidence identity for capabilities and compiler identity."""
    semantic = {
        "capabilities": capabilities.to_dict(),
        "compiler": compiler,
        "implementation": implementation,
        "package": package,
        "version": version,
        "engine": engine,
        "protocol": protocol,
        "environment": dict(environment or {}),
    }
    return sha256(
        json.dumps(semantic, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _validate_static_condition(value: Any) -> None:
    """Reject lowering conditions that require runtime or source inspection."""
    if not isinstance(value, str) or not _STATIC_CONDITION_RE.fullmatch(value):
        raise ValueError("conditions must be resolved static identifiers")
    parts = set(re.split(r"[._:/-]+", value.lower()))
    if parts & _DYNAMIC_CONDITION_PARTS:
        raise ValueError("conditions must be resolved static identifiers")
    if value.lower() not in _STATIC_CONDITION_IDENTIFIERS:
        raise ValueError("conditions must be manifest-declared static identifiers")


def _static_condition_error(value: Any) -> bool:
    try:
        _validate_static_condition(value)
    except ValueError:
        return True
    return False


def host_pushdown_findings(
    definition: Mapping[str, Any], *, evidence_fingerprint: str | None
) -> tuple[TransformPushdownFinding, ...]:
    """Describe host-owned boundaries for non-relational dataframe engines.

    Local, Pandas, and Polars execute their portable plans in the host runtime;
    recording explicit applicability prevents consumers from interpreting an
    omitted pushdown result as an optimistic success.
    """
    findings: list[TransformPushdownFinding] = []
    for index, _ in enumerate(definition.get("actions") or ()):
        for boundary in (f"source:{index}", f"relational:{index}", f"sink:{index}"):
            findings.append(
                TransformPushdownFinding(
                    boundary=boundary,
                    outcome="not_applicable",
                    reason="host-owned execution has no backend pushdown boundary",
                    action=str(
                        (definition.get("actions") or ())[index]
                        .get("kind", {})
                        .get("action", "")
                    ),
                    target=str(
                        (definition.get("actions") or ())[index].get("id", index)
                    ),
                    obligation="informational",
                    evidence_fingerprint=evidence_fingerprint,
                )
            )
    return tuple(findings)


def relational_pushdown_findings(
    definition: Mapping[str, Any],
    *,
    evidence_fingerprint: str | None,
    physical_effects: tuple[str, ...] = (),
    supported_actions: frozenset[str] | set[str] | None = None,
) -> tuple[TransformPushdownFinding, ...]:
    """Emit the planned pushdown matrix for native relational compilers.

    This result is a planning assertion used by normal runtime selection.  It
    is deliberately not sufficient as qualification proof: the evidence
    campaign independently executes each action and captures native evidence
    before a release artifact can retain this outcome.
    """
    findings: list[TransformPushdownFinding] = []
    actions = definition.get("actions") or ()
    for index, action_item in enumerate(actions):
        kind = action_item.get("kind") if isinstance(action_item, Mapping) else {}
        action = str((kind or {}).get("action") or "")
        target = str((action_item or {}).get("id") or index)
        action_supported = supported_actions is None or action in supported_actions
        relational_outcome = "pushed_exact" if action_supported else "unsupported"
        relational_reason = (
            "action lowered into the native relational plan"
            if action_supported
            else "action is not supported by the native relational compiler"
        )
        findings.extend(
            (
                TransformPushdownFinding(
                    boundary=f"source:{index}",
                    outcome="not_applicable",
                    reason="connector source pushdown is outside the native plan contract",
                    action=action,
                    target=target,
                    obligation="informational",
                    evidence_fingerprint=evidence_fingerprint,
                ),
                TransformPushdownFinding(
                    boundary=f"relational:{index}",
                    outcome=relational_outcome,
                    reason=relational_reason,
                    action=action,
                    target=target,
                    proof_reference=(
                        f"runtime-required:{target}" if action_supported else None
                    ),
                    physical_effects=(physical_effects if action_supported else ()),
                    obligation="required",
                    evidence_fingerprint=evidence_fingerprint,
                ),
                TransformPushdownFinding(
                    boundary=f"sink:{index}",
                    outcome="not_applicable",
                    reason="sink pushdown is outside the native plan contract",
                    action=action,
                    target=target,
                    obligation="informational",
                    evidence_fingerprint=evidence_fingerprint,
                ),
            )
        )
    return tuple(findings)


def _baseline_digest() -> str:
    try:
        from etlantic.transform.portable_baseline import baseline_manifest

        value = json.dumps(
            baseline_manifest(), sort_keys=True, separators=(",", ":")
        ).encode()
    except Exception:
        value = b"etlantic.portable-baseline/1"
    return sha256(value).hexdigest()


def validate_requirement_support_payload(payload: Mapping[str, Any]) -> None:
    """Validate the bounded requirement/support wire representation."""
    import json

    def validate_bounded_string(value: Any, *, field_name: str) -> None:
        if (
            not isinstance(value, str)
            or not value
            or len(value.encode("utf-8")) > MAX_PARAMETER_BYTES
            or any(ord(character) < 32 for character in value)
        ):
            raise ValueError(f"{field_name} must be a bounded string")

    def validate_bounded_strings(
        values: Any, *, field_name: str, allowed: frozenset[str] | None = None
    ) -> None:
        if not isinstance(values, list) or len(values) > MAX_CONDITIONS:
            raise ValueError(f"{field_name} exceeds 64 entries")
        for value in values:
            if (
                not isinstance(value, str)
                or not value
                or len(value.encode("utf-8")) > MAX_PARAMETER_BYTES
                or any(ord(character) < 32 for character in value)
            ):
                raise ValueError(f"{field_name} entries must be bounded strings")
            if allowed is not None and value not in allowed:
                raise ValueError(f"invalid {field_name} value")

    if set(payload) != _SUPPORT_PAYLOAD_KEYS:
        raise ValueError("requirement-support payload contains unsupported fields")
    if payload.get("schema") != "etlantic.portable-requirement-support/1":
        raise ValueError("invalid requirement-support schema")
    if not isinstance(payload.get("target"), Mapping):
        raise ValueError("requirement-support target must be an object")
    target = payload["target"]
    unknown_target = set(target) - _TARGET_KEYS
    if unknown_target:
        raise ValueError("requirement-support target contains unsupported fields")
    for key in ("engine", "compiler", "version", "protocol"):
        validate_bounded_string(
            target.get(key), field_name=f"requirement-support target.{key}"
        )
    if "package" in target:
        validate_bounded_string(
            target.get("package"), field_name="requirement-support target.package"
        )
    if "implementation" in target:
        validate_bounded_string(
            target.get("implementation"),
            field_name="requirement-support target.implementation",
        )
    environment = target.get("environment")
    if environment is not None:
        if not isinstance(environment, Mapping) or not environment:
            raise ValueError(
                "requirement-support target.environment must be a non-empty object"
            )
        if set(environment) - _ENVIRONMENT_KEYS:
            raise ValueError(
                "requirement-support target.environment contains unsupported fields"
            )
        for key, value in environment.items():
            validate_bounded_string(
                value, field_name=f"requirement-support target.environment.{key}"
            )
    if target.get("protocol") != COMPILER_PROTOCOL:
        raise ValueError("requirement-support target.protocol is unsupported")
    placement = target.get("placement")
    if placement is not None:
        if not isinstance(placement, Mapping):
            raise ValueError("requirement-support target.placement must be an object")
        if set(placement) != _PLACEMENT_TARGET_KEYS:
            raise ValueError(
                "requirement-support target.placement must contain the complete "
                "resource, location, security_domain, connector, and policy identity"
            )
        for key in _PLACEMENT_TARGET_KEYS:
            validate_bounded_string(
                placement.get(key),
                field_name=f"requirement-support target.placement.{key}",
            )
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
        if set(item) - _REQUIREMENT_KEYS:
            raise ValueError("requirement record contains unsupported fields")
        identifier = item.get("id")
        if not isinstance(identifier, str) or identifier in requirement_ids:
            raise ValueError("requirement IDs must be non-empty and unique")
        validate_bounded_string(identifier, field_name="requirement ID")
        requirement_ids.add(identifier)
        if not identifier.startswith("dtcs@1/") or "#" not in identifier:
            raise ValueError("requirement IDs must use canonical dtcs@1 form")
        if item.get("vocabulary") != "dtcs" or item.get("version") != "1":
            raise ValueError("requirement vocabulary/version are required")
        validate_bounded_string(item.get("scope"), field_name="requirement scope")
        validate_bounded_string(item.get("path"), field_name="requirement path")
        parameters = item.get("parameters")
        if not isinstance(parameters, Mapping):
            raise ValueError("requirement parameters must be an object")
        if set(parameters) - {"value", "legacy_requirement"}:
            raise ValueError("requirement parameters contain unsupported fields")
        if set(parameters) == {"value", "legacy_requirement"}:
            raise ValueError("requirement parameters are ambiguous")
        if item.get("scope") == "legacy":
            if set(parameters) != {"legacy_requirement"}:
                raise ValueError("legacy requirement needs legacy_requirement")
        elif set(parameters) != {"value"}:
            raise ValueError("requirement parameters require a value")
        for value in parameters.values():
            if (
                not isinstance(value, str)
                or not value
                or len(value.encode("utf-8")) > MAX_PARAMETER_BYTES
                or any(ord(character) < 32 for character in value)
            ):
                raise ValueError("requirement parameter values must be bounded strings")
        semantic_value = parameters.get(
            "legacy_requirement" if item.get("scope") == "legacy" else "value"
        )
        if identifier != _canonical_requirement_id(
            str(item.get("scope")), str(semantic_value), str(item.get("path"))
        ):
            raise ValueError("requirement ID does not match its typed parameters")
        if item.get("obligation") not in OBLIGATIONS:
            raise ValueError("invalid requirement obligation")
        if item.get("applicability") not in {"applicable", "not_applicable"}:
            raise ValueError("invalid requirement applicability")
    finding_ids: set[str] = set()
    for item in findings:
        if not isinstance(item, Mapping):
            raise ValueError("support finding must be an object")
        if set(item) - _FINDING_KEYS:
            raise ValueError("support finding contains unsupported fields")
        identifier = item.get("requirement")
        if not isinstance(identifier, str) or identifier in finding_ids:
            raise ValueError("finding requirement IDs must be non-empty and unique")
        validate_bounded_string(identifier, field_name="finding requirement ID")
        finding_ids.add(identifier)
        if item.get("support") not in SUPPORT_STATES:
            raise ValueError("invalid support state")
        if item.get("obligation") not in OBLIGATIONS:
            raise ValueError("invalid finding obligation")
        reason = item.get("reason")
        if (
            not isinstance(reason, str)
            or not reason
            or len(reason.encode("utf-8")) > MAX_REASON_BYTES
            or any(ord(character) < 32 for character in reason)
        ):
            raise ValueError("finding reason must be a bounded string")
        if "code" in item:
            validate_bounded_string(item.get("code"), field_name="finding code")
        if item.get("expression_path") is not None:
            validate_bounded_string(
                item.get("expression_path"), field_name="finding expression path"
            )
        validate_bounded_string(
            item.get("reason_code"), field_name="finding reason code"
        )
        validate_bounded_string(item.get("path"), field_name="finding path")
        evidence_refs = item.get("evidence", [])
        validate_bounded_strings(evidence_refs, field_name="finding evidence")
        evidence_fingerprint = item.get("evidence_fingerprint")
        if evidence_fingerprint is not None:
            validate_bounded_string(
                evidence_fingerprint, field_name="finding evidence fingerprint"
            )
        if item["support"] in {"supported_exact", "supported_with_lowering"}:
            if (
                not isinstance(item.get("evidence_fingerprint"), str)
                or not item["evidence_fingerprint"]
            ):
                raise ValueError("supported finding requires evidence fingerprint")
            if not evidence_refs:
                raise ValueError("supported finding requires evidence reference")
        if item["support"] == "supported_with_lowering":
            validate_bounded_string(
                item.get("lowering_id"), field_name="lowering identity"
            )
            validate_bounded_string(
                item.get("proof_reference"), field_name="lowering proof reference"
            )
            if not isinstance(item.get("conditions"), list) or not isinstance(
                item.get("physical_effects"), list
            ):
                raise ValueError("lowered finding requires conditions and effects")
        validate_bounded_strings(item.get("conditions", []), field_name="conditions")
        for condition in item.get("conditions", []):
            _validate_static_condition(condition)
        validate_bounded_strings(
            item.get("physical_effects", []),
            field_name="physical_effects",
            allowed=PHYSICAL_EFFECTS,
        )
    applicable = {
        str(item["id"])
        for item in requirements
        if item.get("applicability") == "applicable"
    }
    if applicable != finding_ids:
        raise ValueError("every applicable requirement needs exactly one finding")
    if any(
        finding.get("support") in {"supported_exact", "supported_with_lowering"}
        for finding in findings
    ) and (
        not isinstance(target.get("package"), str)
        or not isinstance(target.get("implementation"), str)
    ):
        raise ValueError(
            "positive support evidence requires package and implementation identity"
        )
    requirement_by_id = {str(item["id"]): item for item in requirements}
    for finding in findings:
        requirement = requirement_by_id[str(finding["requirement"])]
        if finding.get("obligation") != requirement.get("obligation"):
            raise ValueError("finding obligation must match requirement obligation")
    evidence = payload.get("evidence")
    if not isinstance(evidence, list):
        raise ValueError("evidence must be an array")
    evidence_ids = set()
    evidence_fingerprints: dict[str, str] = {}
    for record in evidence:
        if not isinstance(record, Mapping):
            raise ValueError("evidence record must be an object")
        if set(record) - _EVIDENCE_KEYS:
            raise ValueError("evidence record contains unsupported fields")
        validate_bounded_string(record.get("id"), field_name="evidence ID")
        if record["id"] in evidence_ids:
            raise ValueError("evidence IDs must be unique")
        validate_bounded_string(record.get("kind"), field_name="evidence kind")
        validate_bounded_string(
            record.get("fingerprint"), field_name="evidence fingerprint"
        )
        validate_bounded_string(
            record.get("baseline_digest"), field_name="evidence baseline digest"
        )
        if record["baseline_digest"] != _baseline_digest():
            raise ValueError("evidence baseline digest is stale")
        evidence_ids.add(record["id"])
        evidence_fingerprints[record["id"]] = record["fingerprint"]
    for finding in findings:
        if not set(finding.get("evidence", [])).issubset(evidence_ids):
            raise ValueError("finding references unknown evidence")
        if finding.get("evidence_fingerprint"):
            references = finding.get("evidence", [])
            if not references or not any(
                evidence_fingerprints[reference] == finding["evidence_fingerprint"]
                for reference in references
            ):
                raise ValueError("finding evidence fingerprint does not match evidence")
    pushdown = payload.get("pushdown", [])
    if not isinstance(pushdown, list):
        raise ValueError("pushdown findings must be an array")
    pushdown_boundaries: set[str] = set()
    for item in pushdown:
        if not isinstance(item, Mapping):
            raise ValueError("pushdown finding must be an object")
        if set(item) - _PUSHDOWN_KEYS:
            raise ValueError("pushdown finding contains unsupported fields")
        if item.get("outcome") not in PUSHDOWN_OUTCOMES:
            raise ValueError("invalid pushdown outcome")
        if item.get("obligation") not in OBLIGATIONS:
            raise ValueError("invalid pushdown obligation")
        validate_bounded_string(item.get("boundary"), field_name="pushdown boundary")
        if item["boundary"] in pushdown_boundaries:
            raise ValueError("pushdown boundaries must be unique")
        pushdown_boundaries.add(item["boundary"])
        validate_bounded_string(item.get("reason"), field_name="pushdown reason")
        for optional_field in (
            "action",
            "target",
            "lowering_id",
            "proof_reference",
            "evidence_fingerprint",
        ):
            if item.get(optional_field) is not None:
                validate_bounded_string(
                    item[optional_field], field_name=f"pushdown {optional_field}"
                )
        validate_bounded_strings(
            item.get("conditions", []), field_name="pushdown conditions"
        )
        for condition in item.get("conditions", []):
            _validate_static_condition(condition)
        validate_bounded_strings(
            item.get("physical_effects", []),
            field_name="pushdown physical_effects",
            allowed=PHYSICAL_EFFECTS,
        )
        if not isinstance(item.get("action"), str) or not item["action"]:
            raise ValueError("pushdown finding requires action")
        if not isinstance(item.get("target"), str) or not item["target"]:
            raise ValueError("pushdown finding requires target")
        if item.get("outcome") == "not_pushed" and item.get("obligation") == "required":
            raise ValueError("required pushdown cannot be not_pushed")
        if item.get("outcome") in {"pushed_exact", "pushed_with_lowering"}:
            if (
                not isinstance(item.get("evidence_fingerprint"), str)
                or not item["evidence_fingerprint"]
            ):
                raise ValueError("pushed finding requires evidence fingerprint")
            if (
                not isinstance(item.get("proof_reference"), str)
                or not item["proof_reference"]
            ):
                raise ValueError("pushed finding requires proof reference")
        if item.get("outcome") == "pushed_with_lowering":
            if not isinstance(item.get("lowering_id"), str) or not item["lowering_id"]:
                raise ValueError("lowered pushdown requires lowering identity")
            if not item.get("conditions"):
                raise ValueError("lowered pushdown requires static conditions")
            if not item.get("physical_effects"):
                raise ValueError("lowered pushdown requires physical effects")
        if item.get("evidence_fingerprint") and not any(
            record.get("fingerprint") == item["evidence_fingerprint"]
            for record in evidence
        ):
            raise ValueError("pushdown evidence fingerprint is unbound")
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    if len(serialized) > MAX_REPORT_BYTES:
        raise ValueError("serialized support report exceeds 8 MiB")
    fingerprint = payload.get("fingerprint")
    if not isinstance(fingerprint, str) or fingerprint != _support_fingerprint(payload):
        raise ValueError("support report fingerprint is invalid")


def preflight_portable_support(descriptor: Any, compiler: Any, *, engine: str) -> None:
    """Fail closed before portable execution uses resources or input data."""
    expected_evidence = getattr(compiler.info, "evidence_fingerprint", None)
    planned_evidence = getattr(descriptor, "compiler_evidence_fingerprint", None)
    if (
        not planned_evidence
        or not expected_evidence
        or planned_evidence != expected_evidence
    ):
        raise ValueError(
            "portable compiler evidence is missing or stale; replan required"
        )
    payload = getattr(descriptor, "support_summary", None)
    if not isinstance(payload, Mapping):
        raise ValueError("portable support evidence is missing; replan required")
    validate_requirement_support_payload(payload)
    target = payload.get("target")
    if not isinstance(target, Mapping) or target.get("engine") != engine:
        raise ValueError("portable support evidence targets a different engine")
    expected_package = getattr(compiler.info, "package", None)
    expected_implementation = getattr(compiler.info, "implementation", None)
    expected_environment = getattr(compiler.info, "environment", None)
    if (
        target.get("compiler") != compiler.info.name
        or target.get("version") != compiler.info.version
        or (expected_package is not None and target.get("package") != expected_package)
        or (
            expected_implementation is not None
            and target.get("implementation") != expected_implementation
        )
        or (
            expected_environment is not None
            and target.get("environment") != dict(expected_environment)
        )
    ):
        raise ValueError("portable support evidence targets a different compiler")
    evidence = payload.get("evidence") or []
    if not any(record.get("fingerprint") == expected_evidence for record in evidence):
        raise ValueError("portable support evidence does not match installed compiler")
    if required_support_failures(payload):
        raise ValueError("portable support evidence contains unsupported requirements")


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
