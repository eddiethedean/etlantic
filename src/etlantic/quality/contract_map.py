"""Map portable quality rules onto ContractModel constraint surfaces.

This module does not invent a second schema vocabulary: every portable rule
must lower to nullability, FieldConstraints-shaped fields, or an explicit
custom-contract check.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from etlantic.quality.model import QualityRule, QualityRuleset


class UnmappedQualityRuleError(ValueError):
    """Raised when a quality rule cannot map onto ContractModel surfaces."""


@dataclass(frozen=True, slots=True)
class ContractConstraintMapping:
    """ContractModel-compatible constraint projection for one field."""

    field: str
    nullable: bool | None = None
    min_value: Any = None
    max_value: Any = None
    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None
    enum_values: list[Any] | None = None
    allowed_values: list[Any] | None = None
    disallowed_values: list[Any] | None = None
    unique: bool = False
    unique_fields: tuple[str, ...] = ()
    custom: tuple[dict[str, Any], ...] = ()
    compare_ops: tuple[dict[str, Any], ...] = ()

    def field_constraints_dict(self) -> dict[str, Any]:
        """Return a FieldConstraints-shaped mapping (ContractModel 0.2)."""
        custom = [dict(item) for item in self.custom]
        for item in self.compare_ops:
            custom.append(
                {
                    "name": f"compare_{item.get('op')}",
                    "type": "compare",
                    "expression": dict(item),
                    "metadata": {},
                }
            )
        data: dict[str, Any] = {
            "unique": self.unique,
            "immutable": False,
            "custom": custom,
        }
        if self.nullable is not None:
            data["nullable"] = self.nullable
        if self.min_value is not None:
            data["min_value"] = self.min_value
        if self.max_value is not None:
            data["max_value"] = self.max_value
        if self.min_length is not None:
            data["min_length"] = self.min_length
        if self.max_length is not None:
            data["max_length"] = self.max_length
        if self.pattern is not None:
            data["pattern"] = self.pattern
        if self.enum_values is not None:
            data["enum_values"] = list(self.enum_values)
        if self.allowed_values is not None:
            data["allowed_values"] = list(self.allowed_values)
        if self.disallowed_values is not None:
            data["disallowed_values"] = list(self.disallowed_values)
        if self.unique_fields:
            data["unique_fields"] = list(self.unique_fields)
        return data


def map_rule_to_contract(rule: QualityRule) -> ContractConstraintMapping:
    """Map a single portable rule onto ContractModel-compatible surfaces."""
    kind = rule.kind
    node = rule.node
    field_name = rule.field

    if kind == "not_null":
        return ContractConstraintMapping(field=field_name, nullable=False)

    if kind == "compare":
        op = str(node.get("op") or "")
        if op not in {"eq", "ne", "lt", "le", "gt", "ge"}:
            raise UnmappedQualityRuleError(
                f"Unsupported compare op {op!r} on field {field_name!r}"
            )
        value = node.get("value")
        # Prefer FieldConstraints range/equality where possible.
        if op == "ge":
            return ContractConstraintMapping(field=field_name, min_value=value)
        if op == "le":
            return ContractConstraintMapping(field=field_name, max_value=value)
        if op == "gt":
            return ContractConstraintMapping(
                field=field_name,
                compare_ops=(dict(op=op, value=value),),
            )
        if op == "lt":
            return ContractConstraintMapping(
                field=field_name,
                compare_ops=(dict(op=op, value=value),),
            )
        if op == "eq":
            return ContractConstraintMapping(field=field_name, allowed_values=[value])
        return ContractConstraintMapping(field=field_name, disallowed_values=[value])

    if kind == "membership":
        values = list(node.get("values") or [])
        allowed = bool(node.get("allowed", True))
        if allowed:
            return ContractConstraintMapping(
                field=field_name, allowed_values=values, enum_values=values
            )
        return ContractConstraintMapping(field=field_name, disallowed_values=values)

    if kind == "range":
        return ContractConstraintMapping(
            field=field_name,
            min_value=node.get("min_value"),
            max_value=node.get("max_value"),
        )

    if kind == "regex":
        pattern = node.get("pattern")
        if not isinstance(pattern, str) or not pattern:
            raise UnmappedQualityRuleError(
                f"regex rule on {field_name!r} requires a non-empty pattern"
            )
        return ContractConstraintMapping(field=field_name, pattern=pattern)

    if kind == "length":
        return ContractConstraintMapping(
            field=field_name,
            min_length=node.get("min_length"),
            max_length=node.get("max_length"),
        )

    if kind == "uniqueness":
        fields = tuple(node.get("fields") or ([field_name] if field_name else []))
        if not fields:
            raise UnmappedQualityRuleError("uniqueness rule requires field(s)")
        return ContractConstraintMapping(
            field=field_name or fields[0],
            unique=len(fields) == 1,
            unique_fields=fields,
        )

    if kind == "custom_contract":
        name = str(node.get("name") or "")
        if not name:
            raise UnmappedQualityRuleError("custom_contract requires name")
        custom = {
            "name": name,
            "type": node.get("type"),
            "expression": node.get("expression"),
            "metadata": dict(node.get("metadata") or {}),
        }
        return ContractConstraintMapping(
            field=field_name or name,
            custom=(custom,),
        )

    raise UnmappedQualityRuleError(f"Unmapped quality rule kind {kind!r}")


def map_ruleset_to_contract(
    ruleset: QualityRuleset,
) -> dict[str, ContractConstraintMapping]:
    """Merge ruleset mappings by field name (later rules overlay earlier)."""
    by_field: dict[str, ContractConstraintMapping] = {}
    for rule in ruleset.rules:
        mapped = map_rule_to_contract(rule)
        key = mapped.field
        existing = by_field.get(key)
        if existing is None:
            by_field[key] = mapped
            continue
        by_field[key] = _merge_mappings(existing, mapped)
    return by_field


def _merge_mappings(
    left: ContractConstraintMapping,
    right: ContractConstraintMapping,
) -> ContractConstraintMapping:
    """Merge two mappings for the same field (right wins on scalar conflicts)."""
    return ContractConstraintMapping(
        field=left.field,
        nullable=right.nullable if right.nullable is not None else left.nullable,
        min_value=right.min_value if right.min_value is not None else left.min_value,
        max_value=right.max_value if right.max_value is not None else left.max_value,
        min_length=(
            right.min_length if right.min_length is not None else left.min_length
        ),
        max_length=(
            right.max_length if right.max_length is not None else left.max_length
        ),
        pattern=right.pattern if right.pattern is not None else left.pattern,
        enum_values=(
            right.enum_values if right.enum_values is not None else left.enum_values
        ),
        allowed_values=(
            right.allowed_values
            if right.allowed_values is not None
            else left.allowed_values
        ),
        disallowed_values=(
            right.disallowed_values
            if right.disallowed_values is not None
            else left.disallowed_values
        ),
        unique=left.unique or right.unique,
        unique_fields=tuple(dict.fromkeys([*left.unique_fields, *right.unique_fields])),
        custom=tuple([*left.custom, *right.custom]),
        compare_ops=tuple([*left.compare_ops, *right.compare_ops]),
    )
