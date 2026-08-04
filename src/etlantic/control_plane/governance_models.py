"""Data-governance constraints attached to CP4 policy decisions."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from etlantic.control_plane.redaction import (
    redact_control_plane_payload,
    redact_control_plane_text,
)

GOVERNANCE_CONSTRAINTS_SCHEMA = "etlantic.control_plane.governance_constraints/1"


@dataclass(frozen=True, slots=True)
class GovernanceConstraints:
    """Classification, residency, masking, retention, and egress bounds."""

    classification: str | None = None
    residency_regions: tuple[str, ...] = ()
    masking_profiles: tuple[str, ...] = ()
    retention_days: int | None = None
    egress_allowlist: tuple[str, ...] = ()
    field_impacts: Mapping[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": GOVERNANCE_CONSTRAINTS_SCHEMA,
            "classification": (
                redact_control_plane_text(self.classification)
                if self.classification
                else None
            ),
            "residency_regions": list(self.residency_regions),
            "masking_profiles": list(self.masking_profiles),
            "retention_days": self.retention_days,
            "egress_allowlist": list(self.egress_allowlist),
            "field_impacts": redact_control_plane_payload(dict(self.field_impacts)),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> GovernanceConstraints:
        if not data:
            return cls()
        regions = data.get("residency_regions") or ()
        profiles = data.get("masking_profiles") or ()
        egress = data.get("egress_allowlist") or ()
        return cls(
            classification=(
                str(data["classification"])
                if data.get("classification") is not None
                else None
            ),
            residency_regions=tuple(str(x) for x in regions),
            masking_profiles=tuple(str(x) for x in profiles),
            retention_days=(
                int(data["retention_days"])
                if data.get("retention_days") is not None
                else None
            ),
            egress_allowlist=tuple(str(x) for x in egress),
            field_impacts={
                str(k): str(v) for k, v in dict(data.get("field_impacts") or {}).items()
            },
        )

    def crosses_boundary(
        self,
        *,
        target_region: str | None = None,
        egress_destination: str | None = None,
    ) -> bool:
        """Return True when a proposed action would violate constraints."""
        if (
            target_region is not None
            and self.residency_regions
            and target_region not in self.residency_regions
        ):
            return True
        return (
            egress_destination is not None
            and bool(self.egress_allowlist)
            and egress_destination not in self.egress_allowlist
        )


def merge_constraints(
    base: GovernanceConstraints,
    extra: GovernanceConstraints | Mapping[str, Any] | None,
) -> GovernanceConstraints:
    """Intersect allowlists and prefer the stricter retention."""
    other = (
        extra
        if isinstance(extra, GovernanceConstraints)
        else GovernanceConstraints.from_dict(extra)
    )
    regions: Sequence[str]
    if base.residency_regions and other.residency_regions:
        regions = tuple(
            sorted(set(base.residency_regions) & set(other.residency_regions))
        )
    else:
        regions = base.residency_regions or other.residency_regions
    egress: Sequence[str]
    if base.egress_allowlist and other.egress_allowlist:
        egress = tuple(sorted(set(base.egress_allowlist) & set(other.egress_allowlist)))
    else:
        egress = base.egress_allowlist or other.egress_allowlist
    retention = base.retention_days
    if other.retention_days is not None:
        retention = (
            other.retention_days
            if retention is None
            else min(retention, other.retention_days)
        )
    impacts = dict(base.field_impacts)
    impacts.update(dict(other.field_impacts))
    return GovernanceConstraints(
        classification=other.classification or base.classification,
        residency_regions=tuple(regions),
        masking_profiles=tuple(
            dict.fromkeys([*base.masking_profiles, *other.masking_profiles])
        ),
        retention_days=retention,
        egress_allowlist=tuple(egress),
        field_impacts=impacts,
    )


__all__ = [
    "GOVERNANCE_CONSTRAINTS_SCHEMA",
    "GovernanceConstraints",
    "merge_constraints",
]
