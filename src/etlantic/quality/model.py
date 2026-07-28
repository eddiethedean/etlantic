"""Frozen AST for provisional ``etlantic.quality/1`` expressions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

QUALITY_SCHEMA = "etlantic.quality/1"

PORTABLE_RULE_KINDS = frozenset(
    {
        "not_null",
        "compare",
        "membership",
        "range",
        "regex",
        "length",
        "uniqueness",
        "custom_contract",
    }
)

# Capability extras advertised/required per rule kind.
RULE_CAPABILITY_BY_KIND: dict[str, str] = {
    "not_null": "quality.not_null",
    "compare": "quality.compare",
    "membership": "quality.membership",
    "range": "quality.range",
    "regex": "quality.regex",
    "length": "quality.length",
    "uniqueness": "quality.uniqueness",
    "custom_contract": "quality.custom_contract",
}

# Portable core capabilities advertised by live Polars/Pandas compilers in 0.30.
# custom_contract stays capability-gated (engines must opt in explicitly).
PORTABLE_QUALITY_CAPABILITIES: frozenset[str] = frozenset(
    {
        "quality.not_null",
        "quality.compare",
        "quality.membership",
        "quality.range",
        "quality.regex",
        "quality.length",
        "quality.uniqueness",
    }
)


@dataclass(frozen=True, slots=True)
class QualityRule:
    """One portable quality rule attached to a field (or multi-field set)."""

    kind: str
    field: str
    node: dict[str, Any] = field(default_factory=dict)
    required: bool = True
    rule_id: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in PORTABLE_RULE_KINDS:
            raise ValueError(
                f"Unknown quality rule kind {self.kind!r}; "
                f"expected one of {sorted(PORTABLE_RULE_KINDS)}"
            )
        if not self.field and self.kind != "custom_contract":
            raise ValueError(f"Quality rule kind {self.kind!r} requires a field")

    def capability(self) -> str:
        """Return the capability vocabulary key for this rule kind."""
        return RULE_CAPABILITY_BY_KIND[self.kind]

    def to_dict(self) -> dict[str, Any]:
        """Serialize rule to a JSON-compatible mapping."""
        data: dict[str, Any] = {
            "kind": self.kind,
            "field": self.field,
            "node": dict(self.node),
            "required": self.required,
        }
        if self.rule_id is not None:
            data["rule_id"] = self.rule_id
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QualityRule:
        """Deserialize a rule mapping."""
        if not isinstance(data, dict):
            raise TypeError(f"QualityRule must be a mapping, got {type(data)!r}")
        return cls(
            kind=str(data["kind"]),
            field=str(data.get("field") or ""),
            node=dict(data.get("node") or {}),
            required=bool(data.get("required", True)),
            rule_id=(str(data["rule_id"]) if data.get("rule_id") is not None else None),
        )


@dataclass(frozen=True, slots=True)
class QualityRuleset:
    """Ordered collection of portable quality rules for one gate."""

    rules: tuple[QualityRule, ...] = ()
    name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize ruleset."""
        data: dict[str, Any] = {
            "rules": [rule.to_dict() for rule in self.rules],
        }
        if self.name is not None:
            data["name"] = self.name
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QualityRuleset:
        """Deserialize a ruleset mapping."""
        if not isinstance(data, dict):
            raise TypeError(f"QualityRuleset must be a mapping, got {type(data)!r}")
        rules = tuple(QualityRule.from_dict(item) for item in (data.get("rules") or []))
        name = data.get("name")
        return cls(rules=rules, name=str(name) if name is not None else None)


@dataclass(frozen=True, slots=True)
class QualityExpression:
    """Versioned quality-expression document (``etlantic.quality/1``)."""

    schema: str = QUALITY_SCHEMA
    expression_id: str = "quality"
    ruleset: QualityRuleset = field(default_factory=QualityRuleset)
    fingerprint: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the expression document."""
        data: dict[str, Any] = {
            "schema": self.schema,
            "expression_id": self.expression_id,
            "ruleset": self.ruleset.to_dict(),
            "metadata": dict(self.metadata),
        }
        if self.fingerprint is not None:
            data["fingerprint"] = self.fingerprint
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QualityExpression:
        """Deserialize an expression document (caller should upgrade first)."""
        if not isinstance(data, dict):
            raise TypeError(f"QualityExpression must be a mapping, got {type(data)!r}")
        return cls(
            schema=str(data.get("schema") or QUALITY_SCHEMA),
            expression_id=str(data.get("expression_id") or "quality"),
            ruleset=QualityRuleset.from_dict(dict(data.get("ruleset") or {})),
            fingerprint=(
                str(data["fingerprint"])
                if data.get("fingerprint") is not None
                else None
            ),
            metadata=dict(data.get("metadata") or {}),
        )


def rule_not_null(
    field: str, *, required: bool = True, rule_id: str | None = None
) -> QualityRule:
    """Build a ``not_null`` rule."""
    return QualityRule(kind="not_null", field=field, required=required, rule_id=rule_id)


def rule_compare(
    field: str,
    op: str,
    value: Any,
    *,
    required: bool = True,
    rule_id: str | None = None,
) -> QualityRule:
    """Build a comparison rule (``eq``, ``ne``, ``lt``, ``le``, ``gt``, ``ge``)."""
    return QualityRule(
        kind="compare",
        field=field,
        node={"op": op, "value": value},
        required=required,
        rule_id=rule_id,
    )


def rule_membership(
    field: str,
    values: list[Any],
    *,
    allowed: bool = True,
    required: bool = True,
    rule_id: str | None = None,
) -> QualityRule:
    """Build a membership (allowed/disallowed values) rule."""
    return QualityRule(
        kind="membership",
        field=field,
        node={"values": list(values), "allowed": allowed},
        required=required,
        rule_id=rule_id,
    )


def rule_range(
    field: str,
    *,
    min_value: Any = None,
    max_value: Any = None,
    required: bool = True,
    rule_id: str | None = None,
) -> QualityRule:
    """Build a numeric/string range rule."""
    node: dict[str, Any] = {}
    if min_value is not None:
        node["min_value"] = min_value
    if max_value is not None:
        node["max_value"] = max_value
    return QualityRule(
        kind="range", field=field, node=node, required=required, rule_id=rule_id
    )


def rule_regex(
    field: str,
    pattern: str,
    *,
    required: bool = True,
    rule_id: str | None = None,
) -> QualityRule:
    """Build a regex/pattern rule."""
    return QualityRule(
        kind="regex",
        field=field,
        node={"pattern": pattern},
        required=required,
        rule_id=rule_id,
    )


def rule_length(
    field: str,
    *,
    min_length: int | None = None,
    max_length: int | None = None,
    required: bool = True,
    rule_id: str | None = None,
) -> QualityRule:
    """Build a string length rule."""
    node: dict[str, Any] = {}
    if min_length is not None:
        node["min_length"] = min_length
    if max_length is not None:
        node["max_length"] = max_length
    return QualityRule(
        kind="length", field=field, node=node, required=required, rule_id=rule_id
    )


def rule_uniqueness(
    field: str,
    *,
    fields: list[str] | None = None,
    required: bool = True,
    rule_id: str | None = None,
) -> QualityRule:
    """Build a uniqueness rule (single field or composite)."""
    node: dict[str, Any] = {}
    if fields:
        node["fields"] = list(fields)
    return QualityRule(
        kind="uniqueness",
        field=field,
        node=node,
        required=required,
        rule_id=rule_id,
    )


def rule_custom_contract(
    name: str,
    *,
    field: str = "",
    expression: str | None = None,
    constraint_type: str | None = None,
    required: bool = True,
    rule_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> QualityRule:
    """Build an explicit custom-contract check."""
    node: dict[str, Any] = {"name": name}
    if expression is not None:
        node["expression"] = expression
    if constraint_type is not None:
        node["type"] = constraint_type
    if metadata:
        node["metadata"] = dict(metadata)
    return QualityRule(
        kind="custom_contract",
        field=field,
        node=node,
        required=required,
        rule_id=rule_id,
    )
