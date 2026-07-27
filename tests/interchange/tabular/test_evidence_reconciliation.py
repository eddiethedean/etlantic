"""WP2: planned vs observed interchange evidence reconciliation."""

from __future__ import annotations

from etlantic.interchange.tabular import (
    SCHEMA,
    CopyEligibility,
    InterchangeDescriptor,
    InterchangeEvidence,
    InterchangeMechanism,
    build_interchange_evidence,
    reconcile_interchange_evidence,
)


def _descriptor(
    *,
    mechanism: InterchangeMechanism = InterchangeMechanism.RECORDS_FALLBACK,
    copy_eligibility: CopyEligibility = CopyEligibility.COPY_REQUIRED,
    fingerprint: str = "a" * 64,
) -> InterchangeDescriptor:
    from etlantic.interchange.tabular.reconcile import interchange_evidence_refs

    return InterchangeDescriptor(
        schema=SCHEMA,
        mechanism=mechanism,
        producer_engine="polars",
        consumer_engine="pandas",
        producer_caps=(mechanism.value,),
        consumer_caps=(mechanism.value,),
        schema_fingerprint=fingerprint,
        ownership="copied",
        batching="collected",
        collection=True,
        copy_eligibility=copy_eligibility,
        fallback_reason="test" if "fallback" in mechanism.value else None,
        evidence_refs=interchange_evidence_refs(
            schema_fingerprint=fingerprint,
            mechanism=mechanism,
            copy_eligibility=copy_eligibility,
        ),
    )


def test_reconcile_agrees_for_copy_required_boundary() -> None:
    planned = _descriptor(copy_eligibility=CopyEligibility.COPY_REQUIRED)
    observed = build_interchange_evidence(
        descriptor=planned,
        value_before=[{"id": 1}],
        value_after=["different-object"],
    )
    result = reconcile_interchange_evidence(planned, observed)
    assert result.ok
    assert result.observed_copy is True


def test_reconcile_fails_when_zero_copy_claimed_but_copy_observed() -> None:
    planned = _descriptor(
        mechanism=InterchangeMechanism.ARROW_C_DATA,
        copy_eligibility=CopyEligibility.ELIGIBLE,
    )
    observed = InterchangeEvidence(
        evidence_id=f"interchange:{'a' * 64}",
        mechanism=InterchangeMechanism.ARROW_C_DATA,
        copy_observed=True,
        zero_copy_reported=True,
        fallback_reason=None,
        cleanup_status="observed",
        notes="",
    )
    result = reconcile_interchange_evidence(planned, observed)
    assert not result.ok
    assert any("zero-copy" in m for m in result.mismatches)


def test_planned_descriptor_emits_evidence_refs() -> None:
    planned = _descriptor()
    assert any(ref.startswith("descriptor:") for ref in planned.evidence_refs)
    assert any(ref.startswith("mechanism:") for ref in planned.evidence_refs)
    assert any(ref.startswith("copy:") for ref in planned.evidence_refs)
