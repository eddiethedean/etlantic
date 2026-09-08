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
BASELINE_FUNCTION_ARITIES = {
    **{
        name: (1, 1)
        for name in (
            "dtcs:lower",
            "dtcs:upper",
            "dtcs:length",
            "dtcs:is_null",
            "dtcs:abs",
            "dtcs:floor",
            "dtcs:ceil",
            "dtcs:sqrt",
        )
    },
    "dtcs:concat": (1, None),
    "dtcs:concat_ws": (2, None),
    "dtcs:substr": (2, 3),
    "dtcs:replace": (3, 3),
    "dtcs:contains": (2, 2),
    "dtcs:starts_with": (2, 2),
    "dtcs:ends_with": (2, 2),
    "dtcs:case_when": (3, None),
    "dtcs:coalesce": (1, None),
    "dtcs:if_null": (2, 2),
    "dtcs:null_if": (2, 2),
    "dtcs:round": (1, 2),
    "dtcs:power": (2, 2),
    "dtcs:least": (1, None),
    "dtcs:greatest": (1, None),
    "dtcs:sum": (1, 1),
    "dtcs:average": (1, 1),
    "dtcs:min": (1, 1),
    "dtcs:max": (1, 1),
    "dtcs:count": (0, 1),
    "dtcs:count_all": (0, 0),
    "dtcs:count_distinct": (1, 1),
}
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
        "function_arities": {
            name: list(bounds)
            for name, bounds in sorted(BASELINE_FUNCTION_ARITIES.items())
        },
        "defaults": {
            "join.type": "inner",
            "join.collisionPolicy": "fail",
            "union.mode": "byName",
            "union.allowMissingColumns": False,
            "sort.direction": "asc",
            "sort.nulls": "last",
        },
        "semantic_rules": {
            "nulls": "null propagates through scalar expressions; filters retain only true",
            "missing_invalid": "missing and invalid remain distinct and reject unless three_state_distinct is claimed",
            "ordering": "sort keys are applied left-to-right with explicit null placement",
            "numeric": "decimal precision is preserved; overflow and divide/modulo errors are explicit",
            "joins": "null keys do not match unless nullSafe=true; collisionPolicy=fail rejects overlaps",
            "unions": "byName aligns names; byPosition aligns ordinal fields; missing columns are explicit",
            "deduplication": "distinct uses complete logical row identity; keyed deduplicate uses declared keys",
        },
        # Machine-readable constraints supplement the human-readable rules
        # above.  These fields are intentionally part of the frozen manifest
        # so a compiler cannot qualify by merely advertising a name.
        "obligations": {
            "baseline": "required",
            "advanced": "informational",
            "preferred_pushdown": "preferred",
        },
        "applicability": {
            "host_boundary": "not_applicable",
            "native_relational_boundary": "applicable",
        },
        "function_constraints": {
            name: {
                "arity": list(bounds),
                "null_policy": (
                    "aware"
                    if name in {
                        "dtcs:coalesce",
                        "dtcs:if_null",
                        "dtcs:is_null",
                        "dtcs:null_if",
                        "dtcs:case_when",
                    }
                    else "propagate"
                ),
            }
            for name, bounds in sorted(BASELINE_FUNCTION_ARITIES.items())
        },
        "aggregate_empty_results": {
            "dtcs:sum": None,
            "dtcs:average": None,
            "dtcs:min": None,
            "dtcs:max": None,
            "dtcs:count": 0,
            "dtcs:count_all": 0,
            "dtcs:count_distinct": 0,
        },
        "numeric_rules": {
            "integer": "signed_64_or_wider",
            "decimal": "preserve_declared_precision_and_scale",
            "overflow": "raise_portable_numeric_error",
            "divide_by_zero": "raise_portable_arithmetic_error",
            "modulo_by_zero": "raise_portable_arithmetic_error",
        },
        "union_policies": {
            "byName": {"missing_fields": "reject", "duplicates": "reject"},
            "byPosition": {"missing_fields": "reject", "duplicates": "reject"},
        },
        "determinism": {
            "sort": "stable_left_to_right",
            "limit": "requires_explicit_order_for_determinism",
            "distinct": "complete_row_identity",
            "deduplicate": "declared_keys_or_complete_row_identity",
        },
        "pushdown_boundaries": {
            "source": "manifest_declared",
            "relational": "required_for_native_targets",
            "sink": "manifest_declared",
        },
        "leaf_fixture_ids": {
            "dtcs:filter": "kernel_filter_project_lower",
            "dtcs:project": "baseline_scalar_functions",
            "dtcs:with_fields": "kernel_filter_project_lower",
            "dtcs:drop_fields": "baseline_field_actions",
            "dtcs:rename_fields": "baseline_field_actions",
            "dtcs:join": "relational_join_aggregate",
            "dtcs:union": "baseline_union",
            "dtcs:aggregate": "baseline_aggregate_functions",
            "dtcs:sort": "relational_sort_nulls_limit",
            "dtcs:distinct": "baseline_field_actions",
            "dtcs:deduplicate": "baseline_field_actions",
            "dtcs:limit": "relational_sort_nulls_limit",
            **{function: "baseline_scalar_functions" for function in SCALAR_FUNCTIONS},
            **{
                function: "baseline_aggregate_functions"
                for function in AGGREGATE_FUNCTIONS
            },
            **{
                f"operator:{operator}": "baseline_scalar_functions"
                for operator in BASELINE_OPERATORS
            },
            "type:null": "baseline_scalar_functions",
            "type:boolean": "baseline_scalar_functions",
            "type:integer": "baseline_scalar_functions",
            "type:decimal": "baseline_scalar_functions",
            "type:string": "baseline_scalar_functions",
            "type:missing": "reject_missing_literal_without_three_state",
            "type:invalid": "reject_missing_literal_without_three_state",
            "join_modes": "baseline_join_modes",
            "union_modes": "baseline_union_modes",
            "semantic_modes": "reject_missing_literal_without_three_state",
        },
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
