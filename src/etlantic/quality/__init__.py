"""Provisional portable quality expressions (``etlantic.quality/1``).

ContractModel remains the semantic authority for field and constraint meaning.
This package owns the pipeline quality-expression envelope used for planning
and capability negotiation.
"""

from __future__ import annotations

from etlantic.quality.analyze import QualityAnalysis, analyze_quality
from etlantic.quality.contract_map import (
    ContractConstraintMapping,
    UnmappedQualityRuleError,
    map_rule_to_contract,
    map_ruleset_to_contract,
)
from etlantic.quality.evaluate import evaluate_rule, split_by_quality
from etlantic.quality.gate import (
    QUALITY_METADATA_KEY,
    make_quality_gate,
    quality_expression_from_transform,
)
from etlantic.quality.model import (
    PORTABLE_RULE_KINDS,
    QUALITY_SCHEMA,
    QualityExpression,
    QualityRule,
    QualityRuleset,
)
from etlantic.quality.serialize import (
    quality_fingerprint,
    quality_from_dict,
    quality_to_dict,
    verify_quality_fingerprint,
)
from etlantic.quality.upgrade import (
    UnsupportedQualitySchemaError,
    upgrade_quality_dict,
)

__all__ = [
    "PORTABLE_RULE_KINDS",
    "QUALITY_METADATA_KEY",
    "QUALITY_SCHEMA",
    "ContractConstraintMapping",
    "QualityAnalysis",
    "QualityExpression",
    "QualityRule",
    "QualityRuleset",
    "UnmappedQualityRuleError",
    "UnsupportedQualitySchemaError",
    "analyze_quality",
    "evaluate_rule",
    "make_quality_gate",
    "map_rule_to_contract",
    "map_ruleset_to_contract",
    "quality_expression_from_transform",
    "quality_fingerprint",
    "quality_from_dict",
    "quality_to_dict",
    "split_by_quality",
    "upgrade_quality_dict",
    "verify_quality_fingerprint",
]
