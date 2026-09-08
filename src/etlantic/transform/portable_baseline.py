"""Normative 0.50 portable baseline vocabulary and manifest helpers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Literal

BASELINE_ID = "etlantic.portable-baseline/1"
SUPPORT_PROTOCOL_ID = "etlantic.portable-requirement-support/1"

KERNEL_ACTIONS = (
    "dtcs:filter",
    "dtcs:project",
    "dtcs:with_fields",
    "dtcs:drop_fields",
    "dtcs:rename_fields",
)
RELATIONAL_ACTIONS = (
    "dtcs:join",
    "dtcs:union",
    "dtcs:aggregate",
    "dtcs:sort",
    "dtcs:distinct",
    "dtcs:deduplicate",
    "dtcs:limit",
)
SCALAR_FUNCTIONS = (
    "dtcs:lower",
    "dtcs:upper",
    "dtcs:concat",
    "dtcs:concat_ws",
    "dtcs:substr",
    "dtcs:replace",
    "dtcs:length",
    "dtcs:contains",
    "dtcs:starts_with",
    "dtcs:ends_with",
    "dtcs:case_when",
    "dtcs:coalesce",
    "dtcs:if_null",
    "dtcs:null_if",
    "dtcs:is_null",
    "dtcs:abs",
    "dtcs:round",
    "dtcs:floor",
    "dtcs:ceil",
    "dtcs:power",
    "dtcs:sqrt",
    "dtcs:least",
    "dtcs:greatest",
)
AGGREGATE_FUNCTIONS = (
    "dtcs:sum",
    "dtcs:average",
    "dtcs:min",
    "dtcs:max",
    "dtcs:count",
    "dtcs:count_all",
    "dtcs:count_distinct",
)
BASELINE_FUNCTIONS = SCALAR_FUNCTIONS + AGGREGATE_FUNCTIONS
BASELINE_OPERATORS = (
    "eq",
    "not_eq",
    "lt",
    "lte",
    "gt",
    "gte",
    "null_safe_eq",
    "and",
    "or",
    "not",
    "add",
    "subtract",
    "multiply",
    "divide",
    "modulo",
    "negate",
    "in",
)
BASELINE_TYPES = (
    "null",
    "boolean",
    "integer",
    "decimal",
    "string",
    "missing",
    "invalid",
)
BASELINE_JOIN_MODES = ("inner", "left", "right", "full", "semi", "anti", "cross")
SupportState = Literal[
    "supported_exact",
    "supported_with_lowering",
    "unsupported",
    "unavailable",
    "unknown",
]
Obligation = Literal["required", "preferred", "informational"]

ACTION_ALIASES = {"dtcs:drop": "dtcs:drop_fields", "dtcs:rename": "dtcs:rename_fields"}
OPERATOR_ALIASES = {
    "neq": "not_eq",
    "sub": "subtract",
    "mul": "multiply",
    "div": "divide",
    "mod": "modulo",
    "neg": "negate",
}


def normalize_action(action: str) -> str:
    return ACTION_ALIASES.get(action, action)


def normalize_operator(operator: str) -> str:
    return OPERATOR_ALIASES.get(operator, operator)


def baseline_manifest() -> dict[str, Any]:
    """Return a fresh, deterministic copy of the public baseline manifest."""
    return {
        "id": BASELINE_ID,
        "plan": "dtcs.transform-plan/2",
        "profiles": [
            "dtcs:profile/portable-relational-kernel/1",
            "dtcs:profile/portable-relational/1",
        ],
        "actions": list(KERNEL_ACTIONS + RELATIONAL_ACTIONS),
        "scalar_functions": list(SCALAR_FUNCTIONS),
        "aggregate_functions": list(AGGREGATE_FUNCTIONS),
        "operators": list(BASELINE_OPERATORS),
        "types": list(BASELINE_TYPES),
        "join_modes": list(BASELINE_JOIN_MODES),
        "collision_policy": "fail",
        "union_modes": ["byName", "byPosition"],
        "semantic_modes": ["three_state_distinct"],
    }


@dataclass(frozen=True, slots=True)
class PortableRequirement:
    """Bounded, value-free requirement identity for support analysis."""

    requirement_id: str
    scope: str
    path: str
    obligation: Obligation = "required"
    applicability: str = "applicable"
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.requirement_id,
            "scope": self.scope,
            "path": self.path,
            "obligation": self.obligation,
            "applicability": self.applicability,
            "parameters": self.parameters,
        }


@dataclass(frozen=True, slots=True)
class PortableSupportFinding:
    """Requirement-level support outcome with deterministic evidence identity."""

    requirement_id: str
    support: SupportState
    reason: str
    evidence_id: str
    conditions: tuple[str, ...] = ()
    physical_effects: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement": self.requirement_id,
            "support": self.support,
            "reason": self.reason,
            "evidence": self.evidence_id,
            "conditions": list(self.conditions),
            "physical_effects": list(self.physical_effects),
        }


def support_fingerprint(payload: dict[str, Any]) -> str:
    """Hash canonical support data without timestamps, rows, or host paths."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()
