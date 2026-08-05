"""ETLantic optimization SDK (etlantic.optimization/1).

Advisory optimization-pass protocol: passes propose deterministic physical
plan changes with evidence, cost, and proof obligations. Default plan/run
emit the baseline; apply only after host opt-in and gate accept.
"""

from __future__ import annotations

from etlantic.optimization.cost import (
    CostBudget,
    CostProvider,
    CostScore,
    RuleCostProvider,
    StatisticalCostProvider,
    select_candidates,
)
from etlantic.optimization.diagnostics import (
    OPT_CODES,
    optimization_diagnostic,
)
from etlantic.optimization.engine import OptimizationResult, optimize_plan
from etlantic.optimization.evidence import (
    EvidenceRecord,
    EvidenceStore,
    PlanStatistics,
    evidence_fingerprint,
)
from etlantic.optimization.explanation import (
    OptimizationExplanation,
    explain_optimization,
)
from etlantic.optimization.protocol import (
    OPTIMIZATION_PROTOCOL,
    OPTIMIZATION_SCHEMA,
    OptimizationCandidate,
    OptimizationContext,
    OptimizationPass,
    PassMetadata,
    PassPrerequisites,
    ProofObligation,
)
from etlantic.optimization.registry import (
    builtin_passes,
    discover_optimization_passes,
    resolve_pass_order,
)
from etlantic.optimization.shadow import (
    ShadowCompareResult,
    ShadowThresholds,
    compare_shadow,
)

__all__ = [
    "OPTIMIZATION_PROTOCOL",
    "OPTIMIZATION_SCHEMA",
    "OPT_CODES",
    "CostBudget",
    "CostProvider",
    "CostScore",
    "EvidenceRecord",
    "EvidenceStore",
    "OptimizationCandidate",
    "OptimizationContext",
    "OptimizationExplanation",
    "OptimizationPass",
    "OptimizationResult",
    "PassMetadata",
    "PassPrerequisites",
    "PlanStatistics",
    "ProofObligation",
    "RuleCostProvider",
    "ShadowCompareResult",
    "ShadowThresholds",
    "StatisticalCostProvider",
    "builtin_passes",
    "compare_shadow",
    "discover_optimization_passes",
    "evidence_fingerprint",
    "explain_optimization",
    "optimization_diagnostic",
    "optimize_plan",
    "resolve_pass_order",
    "select_candidates",
]
