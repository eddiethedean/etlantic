"""Pure analysis of quality expressions for planning (no engine I/O)."""

from __future__ import annotations

from dataclasses import dataclass

from etlantic.quality.model import (
    RULE_CAPABILITY_BY_KIND,
    QualityExpression,
    QualityRuleset,
)

# Relative cost weights for plan evidence (unitless; higher = more expensive).
_COST_BY_KIND: dict[str, int] = {
    "not_null": 1,
    "compare": 1,
    "membership": 2,
    "range": 1,
    "regex": 3,
    "length": 1,
    "uniqueness": 5,
    "custom_contract": 4,
}


@dataclass(frozen=True, slots=True)
class QualityAnalysis:
    """Plan-time analysis of a quality expression."""

    required_capabilities: frozenset[str]
    optional_capabilities: frozenset[str]
    validation_cost: int
    rule_count: int
    required_rule_count: int
    kinds: tuple[str, ...] = ()
    fallback_evidence: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        """Serialize analysis for plan metadata."""
        return {
            "required_capabilities": sorted(self.required_capabilities),
            "optional_capabilities": sorted(self.optional_capabilities),
            "validation_cost": self.validation_cost,
            "rule_count": self.rule_count,
            "required_rule_count": self.required_rule_count,
            "kinds": list(self.kinds),
            "fallback_evidence": list(self.fallback_evidence),
        }


def analyze_ruleset(ruleset: QualityRuleset) -> QualityAnalysis:
    """Analyze a ruleset for capability requirements and validation cost."""
    required: set[str] = set()
    optional: set[str] = set()
    kinds: list[str] = []
    cost = 0
    required_count = 0
    evidence: list[str] = []

    for rule in ruleset.rules:
        cap = RULE_CAPABILITY_BY_KIND[rule.kind]
        kinds.append(rule.kind)
        cost += _COST_BY_KIND.get(rule.kind, 1)
        if rule.required:
            required.add(cap)
            required_count += 1
        else:
            optional.add(cap)
            evidence.append(
                f"optional rule {rule.kind!r} on {rule.field!r} may be skipped "
                f"when capability {cap!r} is unavailable"
            )

    # Row separation is required whenever any rule is present.
    if ruleset.rules:
        required.add("invalid_row_separation")

    return QualityAnalysis(
        required_capabilities=frozenset(required),
        optional_capabilities=frozenset(optional - required),
        validation_cost=cost,
        rule_count=len(ruleset.rules),
        required_rule_count=required_count,
        kinds=tuple(kinds),
        fallback_evidence=tuple(evidence),
    )


def analyze_quality(expr: QualityExpression) -> QualityAnalysis:
    """Analyze a quality expression document."""
    return analyze_ruleset(expr.ruleset)
