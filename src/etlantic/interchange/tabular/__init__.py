"""Versioned, capability-driven tabular interchange contracts."""

from __future__ import annotations

from etlantic.interchange.tabular.bounds import InterchangeBounds
from etlantic.interchange.tabular.descriptor import (
    CopyEligibility,
    InterchangeDescriptor,
)
from etlantic.interchange.tabular.errors import (
    InterchangeDescriptorError,
    InterchangeError,
    InterchangeSelectionError,
)
from etlantic.interchange.tabular.evidence import InterchangeEvidence
from etlantic.interchange.tabular.fidelity import (
    FidelityResult,
    FidelityStatus,
    MappingIssue,
    check_mapping_fidelity,
    evaluate_fidelity,
)
from etlantic.interchange.tabular.mechanisms import (
    SCHEMA,
    InterchangeMechanism,
)
from etlantic.interchange.tabular.reconcile import (
    ReconciliationResult,
    build_interchange_evidence,
    reconcile_interchange_evidence,
)
from etlantic.interchange.tabular.select import select_mechanism
from etlantic.interchange.tabular.validate import validate_descriptor

__all__ = [
    "SCHEMA",
    "CopyEligibility",
    "FidelityResult",
    "FidelityStatus",
    "InterchangeBounds",
    "InterchangeDescriptor",
    "InterchangeDescriptorError",
    "InterchangeError",
    "InterchangeEvidence",
    "InterchangeMechanism",
    "InterchangeSelectionError",
    "MappingIssue",
    "ReconciliationResult",
    "build_interchange_evidence",
    "check_mapping_fidelity",
    "evaluate_fidelity",
    "reconcile_interchange_evidence",
    "select_mechanism",
    "validate_descriptor",
]
