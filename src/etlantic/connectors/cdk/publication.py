"""Helpers coupling CursorProposal advance to CommitReceipt outcomes."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from etlantic.connectors.errors import ConnectorWriteError
from etlantic.connectors.models import (
    CleanupReceipt,
    CommitReceipt,
    CursorProposal,
    LandingCheckpoint,
    ReconciliationResult,
)
from etlantic.connectors.session import merge_receipts


@dataclass(frozen=True, slots=True)
class PublicationDecision:
    """Whether a cursor/ledger may advance given publication receipts."""

    may_advance: bool
    status: str
    publication_id: str | None = None
    message: str | None = None
    proposal: CursorProposal | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "may_advance": self.may_advance,
            "status": self.status,
            "publication_id": self.publication_id,
            "message": self.message,
            "proposal": self.proposal.to_dict() if self.proposal else None,
        }


def require_committed(
    receipt: CommitReceipt,
    *,
    provider: str | None = None,
) -> CommitReceipt:
    """Raise when receipt is not committed (blocks cursor advance)."""
    if receipt.status != "committed":
        raise ConnectorWriteError(
            f"Publication not committed (status={receipt.status!r}); "
            "refusing cursor/ledger advance",
            code="PMCONN940",
            provider=provider or receipt.provider,
            details={"status": receipt.status, "session_id": receipt.session_id},
        )
    return receipt


def may_advance_cursor(
    receipts: CommitReceipt | Sequence[CommitReceipt],
    *,
    proposal: CursorProposal | None = None,
) -> PublicationDecision:
    """Decide whether a staged cursor proposal may advance."""
    seq: Sequence[CommitReceipt] = (
        (receipts,) if isinstance(receipts, CommitReceipt) else tuple(receipts)
    )
    summary = merge_receipts(seq)
    publication_id = None
    for receipt in seq:
        if receipt.publication_id:
            publication_id = receipt.publication_id
            break
    if summary.status == "committed":
        return PublicationDecision(
            may_advance=True,
            status="committed",
            publication_id=publication_id,
            proposal=proposal,
        )
    return PublicationDecision(
        may_advance=False,
        status=summary.status,
        publication_id=publication_id,
        message=summary.message or f"publication status={summary.status}",
        proposal=proposal,
    )


def couple_proposal_to_receipt(
    proposal: CursorProposal | None,
    receipt: CommitReceipt,
    *,
    provider: str | None = None,
) -> PublicationDecision:
    """Couple a staged proposal to a single sink receipt."""
    decision = may_advance_cursor(receipt, proposal=proposal)
    if not decision.may_advance:
        # Keep fail-closed semantics for callers that treat coupling as a gate.
        if receipt.status == "unknown":
            return decision
        require_committed(receipt, provider=provider)
    return decision


def receipt_from_reconciliation(
    result: ReconciliationResult,
    *,
    session_id: str | None = None,
    provider: str | None = None,
) -> CommitReceipt:
    """Normalize a reconciliation probe into a CommitReceipt."""
    return CommitReceipt(
        status=result.status,
        session_id=session_id,
        provider=provider,
        publication_id=result.publication_id,
        message=result.message,
        metadata=dict(result.metadata),
    )


def skipped_cleanup(
    *, consume: str | None = None, message: str | None = None
) -> CleanupReceipt:
    return CleanupReceipt(
        status="skipped",
        consume=consume,  # type: ignore[arg-type]
        message=message,
    )


def checkpoint_after_commit(
    *,
    may_advance: bool,
    checkpoint: LandingCheckpoint | None,
) -> LandingCheckpoint | None:
    """Return checkpoint only when advance is allowed; else None."""
    if not may_advance:
        return None
    return checkpoint


__all__ = [
    "PublicationDecision",
    "checkpoint_after_commit",
    "couple_proposal_to_receipt",
    "may_advance_cursor",
    "receipt_from_reconciliation",
    "require_committed",
    "skipped_cleanup",
]
