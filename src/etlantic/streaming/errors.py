"""Record-error policy vocabulary (046-Q). Identifiers only."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from etlantic.streaming.diagnostics import dlq_diagnostic


class RecordErrorOutcome(StrEnum):
    """Per-record disposition (distinct from dataframe invalid-row outcomes)."""

    FAIL = "fail"
    SKIP = "skip"
    QUARANTINE = "quarantine"
    DEAD_LETTER = "dead_letter"


class OffsetAdvanceRule(StrEnum):
    """When a source offset/checkpoint may advance after a record error."""

    NEVER = "never"
    AFTER_SKIP = "after_skip"
    AFTER_QUARANTINE = "after_quarantine"
    AFTER_DEAD_LETTER = "after_dead_letter"


@dataclass(frozen=True, slots=True)
class RecordErrorPolicy:
    """Fail/skip/quarantine/dead-letter policy with bounded retries."""

    outcome: RecordErrorOutcome = RecordErrorOutcome.FAIL
    max_retries: int = 0
    offset_advance: OffsetAdvanceRule = OffsetAdvanceRule.NEVER
    dlq_identity: str | None = None
    authorization_identity: str | None = None
    retention: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome.value,
            "max_retries": self.max_retries,
            "offset_advance": self.offset_advance.value,
            "dlq_identity": self.dlq_identity,
            "authorization_identity": self.authorization_identity,
            "retention": self.retention,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RecordErrorPolicy:
        dlq = data.get("dlq_identity")
        auth = data.get("authorization_identity")
        retention = data.get("retention")
        max_retries = int(data.get("max_retries") or 0)
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        return cls(
            outcome=RecordErrorOutcome(str(data.get("outcome") or "fail")),
            max_retries=max_retries,
            offset_advance=OffsetAdvanceRule(
                str(data.get("offset_advance") or "never")
            ),
            dlq_identity=None if dlq in (None, "") else str(dlq),
            authorization_identity=None if auth in (None, "") else str(auth),
            retention=None if retention in (None, "") else str(retention),
        )

    def may_advance_offset(self, *, retries_used: int) -> bool:
        """Return whether policy allows checkpoint advance (never on unbounded fail)."""
        if self.outcome is RecordErrorOutcome.FAIL:
            return False
        if retries_used < self.max_retries:
            return False
        if self.offset_advance is OffsetAdvanceRule.NEVER:
            return False
        if (
            self.outcome is RecordErrorOutcome.SKIP
            and self.offset_advance is OffsetAdvanceRule.AFTER_SKIP
        ):
            return True
        if (
            self.outcome is RecordErrorOutcome.QUARANTINE
            and self.offset_advance is OffsetAdvanceRule.AFTER_QUARANTINE
        ):
            return True
        return (
            self.outcome is RecordErrorOutcome.DEAD_LETTER
            and self.offset_advance is OffsetAdvanceRule.AFTER_DEAD_LETTER
        )

    def validate_dead_letter(self) -> Any | None:
        """Return a diagnostic when DLQ is declared without authorization identity."""
        if self.outcome is not RecordErrorOutcome.DEAD_LETTER:
            return None
        if not self.dlq_identity or not self.authorization_identity:
            return dlq_diagnostic(
                "missing_authorization",
                "Dead-letter policy requires dlq_identity and authorization_identity.",
                path=("record_error", "dead_letter"),
            )
        return None
