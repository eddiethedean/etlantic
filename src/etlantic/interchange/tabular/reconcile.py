"""Reconcile planned interchange descriptors with runtime evidence."""

from __future__ import annotations

import contextlib
import os
from dataclasses import dataclass
from typing import Any

from etlantic.interchange.tabular.descriptor import (
    CopyEligibility,
    InterchangeDescriptor,
)
from etlantic.interchange.tabular.evidence import InterchangeEvidence
from etlantic.interchange.tabular.mechanisms import InterchangeMechanism


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    """Outcome of comparing planned vs observed interchange evidence."""

    ok: bool
    mismatches: tuple[str, ...]
    planned_copy_eligibility: CopyEligibility
    observed_copy: bool | None


def interchange_evidence_refs(
    *,
    schema_fingerprint: str,
    mechanism: InterchangeMechanism,
    copy_eligibility: CopyEligibility,
) -> tuple[str, ...]:
    """Stable evidence reference ids recorded on a planned descriptor."""
    return (
        f"descriptor:{schema_fingerprint}",
        f"mechanism:{mechanism.value}",
        f"copy:{copy_eligibility.value}",
    )


def build_interchange_evidence(
    *,
    descriptor: InterchangeDescriptor,
    value_before: Any,
    value_after: Any,
    mechanism_observed: str | None = None,
) -> InterchangeEvidence:
    """Build runtime evidence for one cross-engine materialization boundary."""
    copy_observed: bool | None
    if (
        value_before is not value_after
        or descriptor.copy_eligibility is CopyEligibility.COPY_REQUIRED
    ):
        copy_observed = True
    elif descriptor.copy_eligibility is CopyEligibility.ELIGIBLE:
        copy_observed = False
    else:
        copy_observed = None

    mechanism = descriptor.mechanism
    if mechanism_observed is not None:
        with contextlib.suppress(ValueError):
            mechanism = InterchangeMechanism(mechanism_observed)

    notes = ""
    if os.environ.get("ETLANTIC_INTERCHANGE_EVIDENCE") == "1":
        try:
            import tracemalloc

            _current, peak = tracemalloc.get_traced_memory()
            notes = f"peak_bytes={peak}"
        except Exception:
            pass

    return InterchangeEvidence(
        evidence_id=f"interchange:{descriptor.schema_fingerprint}",
        mechanism=mechanism,
        copy_observed=copy_observed,
        zero_copy_reported=descriptor.copy_eligibility is CopyEligibility.ELIGIBLE,
        fallback_reason=descriptor.fallback_reason,
        cleanup_status="observed",
        notes=notes,
    )


def reconcile_interchange_evidence(
    planned_descriptor: InterchangeDescriptor,
    observed_evidence: InterchangeEvidence,
) -> ReconciliationResult:
    """Compare planned interchange claims with runtime observations."""
    mismatches: list[str] = []

    if planned_descriptor.mechanism != observed_evidence.mechanism:
        mismatches.append(
            "mechanism mismatch: "
            f"planned={planned_descriptor.mechanism.value} "
            f"observed={observed_evidence.mechanism.value}"
        )

    if (
        planned_descriptor.copy_eligibility is CopyEligibility.ELIGIBLE
        and observed_evidence.copy_observed is True
    ):
        mismatches.append(
            "zero-copy claimed but copy observed at runtime "
            "(planned copy_eligibility=eligible)"
        )

    if (
        planned_descriptor.copy_eligibility is CopyEligibility.COPY_REQUIRED
        and observed_evidence.copy_observed is False
    ):
        mismatches.append("copy required by plan but no copy observed at runtime")

    expected_refs = set(
        interchange_evidence_refs(
            schema_fingerprint=planned_descriptor.schema_fingerprint,
            mechanism=planned_descriptor.mechanism,
            copy_eligibility=planned_descriptor.copy_eligibility,
        )
    )
    if planned_descriptor.evidence_refs and not expected_refs.issubset(
        set(planned_descriptor.evidence_refs)
    ):
        mismatches.append("planned evidence_refs missing expected stable ids")

    if (
        observed_evidence.evidence_id
        != f"interchange:{planned_descriptor.schema_fingerprint}"
    ):
        mismatches.append(f"evidence_id mismatch: {observed_evidence.evidence_id!r}")

    return ReconciliationResult(
        ok=not mismatches,
        mismatches=tuple(mismatches),
        planned_copy_eligibility=planned_descriptor.copy_eligibility,
        observed_copy=observed_evidence.copy_observed,
    )


__all__ = [
    "ReconciliationResult",
    "build_interchange_evidence",
    "interchange_evidence_refs",
    "reconcile_interchange_evidence",
]
