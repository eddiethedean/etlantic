"""Plan-time statistics and evidence store for optimization passes."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from etlantic.plan.freeze import deep_freeze, mutable_copy
from etlantic.plan.model import PipelinePlan

EvidenceKind = Literal[
    "cardinality",
    "partitioning",
    "ordering",
    "locality",
    "reuse",
    "freshness",
    "generic",
]


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    """One plan-time evidence fact with provenance and freshness."""

    evidence_id: str
    kind: str
    subject: str
    value: Any
    confidence: float = 1.0
    provenance: str = "static"
    collected_at: str | None = None
    expires_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_stale(self, *, now: datetime | None = None) -> bool:
        if not self.expires_at:
            return False
        current = now or datetime.now(UTC)
        try:
            expiry = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
        except ValueError:
            return True
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=UTC)
        return current >= expiry

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "kind": self.kind,
            "subject": self.subject,
            "value": mutable_copy(self.value),
            "confidence": self.confidence,
            "provenance": self.provenance,
            "collected_at": self.collected_at,
            "expires_at": self.expires_at,
            "metadata": mutable_copy(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvidenceRecord:
        record = cls(
            evidence_id=str(data["evidence_id"]),
            kind=str(data.get("kind") or "generic"),
            subject=str(data.get("subject") or ""),
            value=data.get("value"),
            confidence=float(
                data.get("confidence") if data.get("confidence") is not None else 1.0
            ),
            provenance=str(data.get("provenance") or "static"),
            collected_at=data.get("collected_at"),
            expires_at=data.get("expires_at"),
            metadata=dict(data.get("metadata") or {}),
        )
        object.__setattr__(record, "metadata", deep_freeze(record.metadata))
        return record


@dataclass(frozen=True, slots=True)
class PlanStatistics:
    """Aggregated statistics view over an EvidenceStore."""

    by_kind: dict[str, tuple[EvidenceRecord, ...]] = field(default_factory=dict)
    missing_kinds: tuple[str, ...] = ()
    stale_ids: tuple[str, ...] = ()
    conflicting_subjects: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "by_kind": {
                k: [r.to_dict() for r in v] for k, v in sorted(self.by_kind.items())
            },
            "missing_kinds": list(self.missing_kinds),
            "stale_ids": list(self.stale_ids),
            "conflicting_subjects": list(self.conflicting_subjects),
        }


class EvidenceStore:
    """Mutable builder that freezes into deterministic evidence fingerprints."""

    def __init__(self, records: list[EvidenceRecord] | None = None) -> None:
        self._records: dict[str, EvidenceRecord] = {}
        for record in records or []:
            self.add(record)

    def add(self, record: EvidenceRecord) -> None:
        self._records[record.evidence_id] = record

    def get(self, evidence_id: str) -> EvidenceRecord | None:
        return self._records.get(evidence_id)

    def records(self) -> tuple[EvidenceRecord, ...]:
        return tuple(sorted(self._records.values(), key=lambda r: r.evidence_id))

    def by_kind(self, kind: str) -> tuple[EvidenceRecord, ...]:
        return tuple(r for r in self.records() if r.kind == kind)

    def for_subject(self, subject: str) -> tuple[EvidenceRecord, ...]:
        return tuple(r for r in self.records() if r.subject == subject)

    def conflicts(self) -> tuple[str, ...]:
        """Subjects with same kind but disagreeing values."""
        groups: dict[tuple[str, str], list[EvidenceRecord]] = {}
        for record in self.records():
            groups.setdefault((record.kind, record.subject), []).append(record)
        conflicts: list[str] = []
        for (kind, subject), items in sorted(groups.items()):
            values = {json.dumps(i.value, sort_keys=True, default=str) for i in items}
            if len(values) > 1:
                conflicts.append(f"{kind}:{subject}")
        return tuple(conflicts)

    def stale_ids(self, *, now: datetime | None = None) -> tuple[str, ...]:
        return tuple(r.evidence_id for r in self.records() if r.is_stale(now=now))

    def statistics(
        self,
        *,
        required_kinds: tuple[str, ...] = (),
        now: datetime | None = None,
    ) -> PlanStatistics:
        by_kind: dict[str, list[EvidenceRecord]] = {}
        for record in self.records():
            by_kind.setdefault(record.kind, []).append(record)
        present = set(by_kind)
        missing = tuple(k for k in required_kinds if k not in present)
        return PlanStatistics(
            by_kind={k: tuple(v) for k, v in by_kind.items()},
            missing_kinds=missing,
            stale_ids=self.stale_ids(now=now),
            conflicting_subjects=self.conflicts(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"records": [r.to_dict() for r in self.records()]}

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> EvidenceStore:
        raw = dict(data or {})
        return cls([EvidenceRecord.from_dict(r) for r in (raw.get("records") or [])])

    @classmethod
    def from_plan(
        cls,
        plan: PipelinePlan,
        *,
        prior_report_summary: dict[str, Any] | None = None,
    ) -> EvidenceStore:
        """Collect plan-time evidence from plan metadata and optional run summary.

        Does not access live data or secrets.
        """
        store = cls()
        meta = dict(plan.metadata or {})
        stats = dict(meta.get("etlantic.statistics") or meta.get("statistics") or {})
        for subject, payload in sorted(stats.items()):
            if isinstance(payload, dict):
                kind = str(payload.get("kind") or "generic")
                value = payload.get("value", payload)
                confidence = float(payload.get("confidence") or 0.5)
                expires = payload.get("expires_at")
            else:
                kind = "generic"
                value = payload
                confidence = 0.5
                expires = None
            store.add(
                EvidenceRecord(
                    evidence_id=f"plan-stat:{subject}",
                    kind=kind,
                    subject=str(subject),
                    value=value,
                    confidence=confidence,
                    provenance="plan.metadata.statistics",
                    expires_at=str(expires) if expires else None,
                )
            )
        for boundary in plan.materialization_boundaries:
            store.add(
                EvidenceRecord(
                    evidence_id=f"boundary:{boundary.identity}",
                    kind="reuse" if "reuse" in boundary.reason else "locality",
                    subject=boundary.identity,
                    value={
                        "reason": boundary.reason,
                        "producer": boundary.producer_node,
                        "producer_port": boundary.producer_port,
                        "security_domain": boundary.security_domain,
                    },
                    confidence=0.8,
                    provenance="plan.materialization_boundaries",
                )
            )
        for region in plan.regions:
            store.add(
                EvidenceRecord(
                    evidence_id=f"region:{region.identity}",
                    kind="locality",
                    subject=region.identity,
                    value={
                        "engine": region.engine,
                        "security_domain": region.security_domain,
                        "nodes": list(region.node_names),
                    },
                    confidence=1.0,
                    provenance="plan.regions",
                )
            )
        fusion = {}
        if meta.get("sql_fusion"):
            fusion["sql_fusion"] = meta["sql_fusion"]
        if meta.get("spark_fusion"):
            fusion["spark_fusion"] = meta["spark_fusion"]
        if fusion:
            store.add(
                EvidenceRecord(
                    evidence_id="plan-fusion",
                    kind="ordering",
                    subject="fusion",
                    value=fusion,
                    confidence=0.7,
                    provenance="plan.metadata.fusion",
                )
            )
        if prior_report_summary:
            store.add(
                EvidenceRecord(
                    evidence_id="prior-report",
                    kind="freshness",
                    subject="prior_run",
                    value=dict(prior_report_summary),
                    confidence=float(prior_report_summary.get("confidence") or 0.6),
                    provenance="prior_run_report_summary",
                    expires_at=prior_report_summary.get("expires_at"),
                )
            )
        return store


def evidence_fingerprint(store: EvidenceStore) -> str:
    """Stable SHA-256 of sorted evidence records."""
    payload = json.dumps(
        store.to_dict(), sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
