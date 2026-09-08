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
_TARGET_KEYS = frozenset(
    {"engine", "compiler", "version", "protocol", "package", "placement"}
)
_PLACEMENT_TARGET_KEYS = frozenset(
    {"resource", "location", "security_domain", "connector", "policy"}
)
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
        "proof_reference",
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
    action: str | None = None
    target: str | None = None
    proof_reference: str | None = None
    physical_effects: tuple[str, ...] = ()
    evidence_fingerprint: str | None = None
    obligation: str | None = None

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
            *(finding.evidence_fingerprint for finding in self.findings),
        ]:
            if candidate and candidate not in evidence_fingerprints:
                evidence_fingerprints.append(candidate)
        evidence_ids = {
            fingerprint: ("compiler" if index == 0 else f"compiler-{index + 1}")
            for index, fingerprint in enumerate(evidence_fingerprints)
        }
        requirement_by_legacy: dict[str, str] = {}
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
                requirement_by_legacy.setdefault(f"{singular}:{value}", identifier)
                if scope in {"eager", "lazy"}:
                    requirement_by_legacy.setdefault(f"mode:{scope}", identifier)
        findings = []
        canonical_findings = list(self.requirement_findings)
        used_ids: set[str] = set()
        serialized_by_requirement: dict[str, dict[str, Any]] = {}
        for index, finding in enumerate((*canonical_findings, *self.findings)):
            item = finding.to_dict()
            requirement_id = item.get("requirement")
            if requirement_id not in {r.get("id") for r in requirements}:
                requirement_id = requirement_by_legacy.get(str(requirement_id))
            if requirement_id is None and isinstance(requirement_id, str):
                # Unknown-category findings use ``requirement:<category>``;
                # bind them to the corresponding normalized record when one
                # exists rather than creating a second synthetic requirement.
                category = requirement_id.removeprefix("requirement:")
                for record in requirements:
                    if record.get("scope") == category:
                        requirement_id = record.get("id")
                        break
            if requirement_id is None:
                requirement_id = _canonical_requirement_id(
                    "legacy",
                    str(item.get("requirement") or f"finding-{index}"),
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
                        "parameters": {
                            "legacy_requirement": str(item.get("requirement") or "")
                        },
                    }
                )
            item["requirement"] = requirement_id
            item["support"] = finding.support or (
                "unsupported" if not self.supported else "supported_exact"
            )
            item["obligation"] = finding.obligation or "required"
            fingerprint = finding.evidence_fingerprint or self.evidence_fingerprint
            item["evidence_fingerprint"] = fingerprint
            item["evidence"] = [evidence_ids[fingerprint]] if fingerprint else []
            if (
                item["support"] in {"supported_exact", "supported_with_lowering"}
                and not fingerprint
            ):
                # Positive records without compiler evidence are legacy
                # omissions, not proof; preserve inspectability as unknown.
                item["support"] = "unknown"
                item["reason"] = (
                    "requirement has no independently verified support evidence"
                )
                item["reason_code"] = "PMXFORM999"
            if item.get("reason_code") != "PMXFORM999":
                item["reason_code"] = finding.code
            item["path"] = finding.expression_path or "findings"
            used_ids.add(requirement_id)
            serialized_by_requirement[requirement_id] = item
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
                    "path": finding.expression_path or "",
                    "obligation": finding.obligation or "required",
                    "applicability": "applicable",
                    "parameters": {},
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
        unique_requirements: list[dict[str, Any]] = []
        seen_requirement_ids: set[str] = set()
        for record in requirements:
            identifier = record.get("id")
            if identifier in seen_requirement_ids:
                continue
            seen_requirement_ids.add(str(identifier))
            unique_requirements.append(record)
        requirements = unique_requirements
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
) -> tuple[dict[str, Any], ...]:
    """Convert legacy requirement lists into stable bounded protocol records."""
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
            requirement_id = _canonical_requirement_id(scope, semantic_id, scope)
            if requirement_id in seen:
                continue
            seen.add(requirement_id)
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


def capabilities_fingerprint(capabilities: TransformCapabilities) -> str:
    """Stable evidence identity for an advertised capability set."""
    return sha256(
        json.dumps(
            capabilities.to_dict(), sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


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
                    outcome="pushed_exact",
                    reason="action lowered into the native relational plan",
                    action=action,
                    target=target,
                    proof_reference=f"runtime-required:{target}",
                    physical_effects=physical_effects,
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

    if payload.get("schema") != "etlantic.portable-requirement-support/1":
        raise ValueError("invalid requirement-support schema")
    if not isinstance(payload.get("target"), Mapping):
        raise ValueError("requirement-support target must be an object")
    target = payload["target"]
    unknown_target = set(target) - _TARGET_KEYS
    if unknown_target:
        raise ValueError("requirement-support target contains unsupported fields")
    for key in ("engine", "compiler", "version", "protocol"):
        if not isinstance(target.get(key), str) or not target[key]:
            raise ValueError(f"requirement-support target.{key} must be non-empty")
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
        if any(
            not isinstance(placement.get(key), str) or not placement[key]
            for key in _PLACEMENT_TARGET_KEYS
        ):
            raise ValueError(
                "requirement-support target.placement values must be non-empty strings"
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
        if (
            not isinstance(identifier, str)
            or not identifier
            or identifier in requirement_ids
        ):
            raise ValueError("requirement IDs must be non-empty and unique")
        requirement_ids.add(identifier)
        if not identifier.startswith("dtcs@1/") or "#" not in identifier:
            raise ValueError("requirement IDs must use canonical dtcs@1 form")
        if item.get("vocabulary") != "dtcs" or item.get("version") != "1":
            raise ValueError("requirement vocabulary/version are required")
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
        if set(item) - _FINDING_KEYS:
            raise ValueError("support finding contains unsupported fields")
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
            if (
                not isinstance(item.get("evidence_fingerprint"), str)
                or not item["evidence_fingerprint"]
            ):
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
    evidence_fingerprints: dict[str, str] = {}
    for record in evidence:
        if not isinstance(record, Mapping) or not isinstance(record.get("id"), str):
            raise ValueError("evidence records require string IDs")
        if set(record) - _EVIDENCE_KEYS:
            raise ValueError("evidence record contains unsupported fields")
        if record["id"] in evidence_ids:
            raise ValueError("evidence IDs must be unique")
        if not isinstance(record.get("kind"), str) or not record["kind"]:
            raise ValueError("evidence records require a kind")
        if not isinstance(record.get("fingerprint"), str) or not record["fingerprint"]:
            raise ValueError("evidence records require a fingerprint")
        if (
            not isinstance(record.get("baseline_digest"), str)
            or not record["baseline_digest"]
        ):
            raise ValueError("evidence records require baseline digest")
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
        if (
            item.get("obligation") is not None
            and item.get("obligation") not in OBLIGATIONS
        ):
            raise ValueError("invalid pushdown obligation")
        if not isinstance(item.get("boundary"), str) or not item["boundary"]:
            raise ValueError("pushdown boundary is required")
        if item["boundary"] in pushdown_boundaries:
            raise ValueError("pushdown boundaries must be unique")
        pushdown_boundaries.add(item["boundary"])
        if not isinstance(item.get("reason"), str) or not item["reason"]:
            raise ValueError("pushdown reason is required")
        if item.get("obligation") == "required":
            if not isinstance(item.get("action"), str) or not item["action"]:
                raise ValueError("required pushdown finding requires action")
            if not isinstance(item.get("target"), str) or not item["target"]:
                raise ValueError("required pushdown finding requires target")
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
                if item.get("outcome") == "pushed_with_lowering" and not item.get(
                    "proof_reference"
                ):
                    raise ValueError("lowered pushdown requires proof reference")
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
    if (
        target.get("compiler") != compiler.info.name
        or target.get("version") != compiler.info.version
    ):
        raise ValueError("portable support evidence targets a different compiler")
    evidence = payload.get("evidence") or []
    if not any(record.get("fingerprint") == expected_evidence for record in evidence):
        raise ValueError("portable support evidence does not match installed compiler")
    support_by_id = {
        item.get("requirement"): item.get("support") for item in payload["findings"]
    }
    if not all(
        item.get("applicability") != "applicable"
        or support_by_id.get(item.get("id"))
        in {"supported_exact", "supported_with_lowering"}
        for item in payload["requirements"]
    ):
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
