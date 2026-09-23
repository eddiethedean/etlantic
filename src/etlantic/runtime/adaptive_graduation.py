# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnnecessaryIsInstance=false
"""Integrity safeguards for independent, exact-row graduation projections.

Validation is not authentication or approval. Release review/attestation still
owns the trusted packaged record; provider conformance cannot write it.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any

MATURITY = {"Experimental": 0, "Available": 1}
COMPONENTS = {
    "engine",
    "compiler",
    "source",
    "interchange",
    "runtime",
    "io",
    "environment",
}


@dataclass(frozen=True)
class VerifiedQualification:
    """Integrity result supplied by the evidence verifier, not an approval."""

    source: str
    evidence: str
    row_refs: Mapping[str, frozenset[str]]

    def __post_init__(self):
        object.__setattr__(
            self,
            "row_refs",
            MappingProxyType(
                {row: frozenset(refs) for row, refs in self.row_refs.items()}
            ),
        )


def validate_graduation(
    value: Mapping[str, Any],
    *,
    rows: set[str],
    qualification: VerifiedQualification | None = None,
) -> None:
    fields = {
        "schema",
        "decision",
        "date",
        "reviewer",
        "release_owner",
        "source",
        "evidence",
        "rows",
        "findings",
        "rollback_trigger",
    }
    if (
        not isinstance(value, Mapping)
        or set(value) != fields
        or value["schema"] != "etlantic.adaptive_graduation/1"
        or value["decision"] not in {"pending", "go", "no_go"}
    ):
        raise ValueError("Invalid adaptive graduation record")
    if not isinstance(value["rows"], Mapping) or set(value["rows"]) != rows:
        raise ValueError("Graduation must decide every exact row")
    pending = value["decision"] == "pending"
    for field in ("source", "evidence"):
        digest = value[field]
        if digest is None and pending:
            continue
        if (
            type(digest) is not str
            or re.fullmatch(r"sha256:[0-9a-f]{64}", digest) is None
        ):
            raise ValueError("Graduation requires source/evidence digests")
    for field in ("reviewer", "release_owner", "rollback_trigger", "date"):
        item = value[field]
        if item is None and pending:
            continue
        if type(item) is not str or not item or len(item) > 4096:
            raise ValueError("Graduation requires independent decision ownership")
    if not pending:
        decision_date = value["date"]
        if not isinstance(decision_date, str):
            raise ValueError("Graduation decision must be UTC dated")
        timestamp = datetime.fromisoformat(decision_date)
        offset = timestamp.utcoffset()
        if offset is None or offset.total_seconds() != 0:
            raise ValueError("Graduation decision must be UTC dated")
        if value["reviewer"] == value["release_owner"]:
            raise ValueError("Graduation reviewer must be independent")
    findings = value["findings"]
    if not isinstance(findings, (list, tuple)) or any(
        not isinstance(f, Mapping)
        or set(f) != {"id", "severity", "resolved"}
        or type(f["id"]) is not str
        or not f["id"]
        or f["severity"] not in {"critical", "high", "medium", "low"}
        or type(f["resolved"]) is not bool
        for f in findings
    ):
        raise ValueError("Invalid scoped graduation findings")
    if value["decision"] == "go" and any(
        f["severity"] in {"critical", "high"} and not f["resolved"] for f in findings
    ):
        raise ValueError("Unresolved high finding prevents graduation")
    for identity, row in value["rows"].items():
        if (
            not isinstance(row, Mapping)
            or set(row) != {"decision", "maturity", "components", "evidence_refs"}
            or row["decision"] not in {"pending", "go", "no_go"}
            or row["maturity"] not in MATURITY
        ):
            raise ValueError("Invalid exact-row graduation decision")
        components = row["components"]
        if (
            not isinstance(components, Mapping)
            or set(components) != COMPONENTS
            or any(v not in MATURITY for v in components.values())
        ):
            raise ValueError("Graduation requires every participating maturity")
        if MATURITY[row["maturity"]] > min(MATURITY[v] for v in components.values()):
            raise ValueError("Graduation cannot exceed weakest participating maturity")
        refs = row["evidence_refs"]
        if (
            not isinstance(refs, (list, tuple))
            or any(
                type(ref) is not str
                or re.fullmatch(r"sha256:[0-9a-f]{64}", ref) is None
                for ref in refs
            )
            or len(set(refs)) != len(refs)
        ):
            raise ValueError("Invalid graduation evidence references")
        if row["decision"] == "go" and (
            pending
            or not refs
            or not isinstance(qualification, VerifiedQualification)
            or qualification.source != value["source"]
            or qualification.evidence != value["evidence"]
            or set(qualification.row_refs) != rows
            or not set(refs) <= qualification.row_refs.get(identity, frozenset())
        ):
            raise ValueError("Go requires verified executed exact-row evidence")
        if row["maturity"] == "Available" and (
            pending or value["decision"] != "go" or row["decision"] != "go" or not refs
        ):
            raise ValueError("Only independently reviewed go rows can be Available")
    if value["decision"] == "go":
        for required in (
            "scan-filter-project-chain/1:polars-pandas",
            "chain/1:pandas-polars",
        ):
            if (
                required not in value["rows"]
                or value["rows"][required]["decision"] != "go"
            ):
                raise ValueError(
                    "Mandatory primary and independent reverse rows cannot be waived"
                )


def validate_candidate(value: Mapping[str, Any], decision: Mapping[str, Any]) -> None:
    """Development authority is closed, Experimental, and never self-approving."""
    if (
        not isinstance(value, Mapping)
        or set(value) != {"schema", "authority", "graduation", "rows", "observations"}
        or value["schema"] != "etlantic.adaptive_qualification/2"
        or value["authority"] != "development-candidate"
        or value["graduation"] != "pending"
        or value["observations"]
        or not isinstance(value["rows"], Mapping)
        or set(value["rows"])
        != {
            "scan-filter-project-chain/1:polars-pandas",
            *(
                f"chain/1:{family}"
                for family in (
                    "local",
                    "polars",
                    "pandas",
                    "polars-pandas",
                    "pandas-polars",
                )
            ),
            *(
                f"{pattern}/1:{family}"
                for pattern in ("diamond", "fanout")
                for family in ("local", "polars", "pandas")
            ),
            "dual-port-chain/1:polars-pandas",
            "dual-port-chain/1:pandas-polars",
        }
    ):
        raise ValueError("Invalid packaged adaptive candidate")
    validate_graduation(decision, rows=set(value["rows"]))
    if decision["decision"] != "pending":
        raise ValueError(
            "Development candidate cannot substitute an approval projection"
        )
    for identity, row in value["rows"].items():
        if (
            not isinstance(row, Mapping)
            or set(row)
            != {"maturity", "versions", "operations", "policies", "evidence_refs"}
            or row["maturity"] != "Experimental"
            or row["evidence_refs"]
        ):
            raise ValueError("Unqualified candidate row cannot advertise availability")
        if (
            not isinstance(row["versions"], Mapping)
            or "etlantic" not in row["versions"]
            or not set(row["versions"])
            <= {
                "etlantic",
                "etlantic-polars",
                "etlantic-pandas",
                "polars",
                "pandas",
                "pyarrow",
            }
        ):
            raise ValueError("Candidate requires exact package/backend pins")
        pins = {
            "etlantic": "0.54.0",
            "etlantic-polars": "0.54.0",
            "etlantic-pandas": "0.54.0",
            "polars": "1.42.1",
            "pandas": "2.3.3",
            "pyarrow": "25.0.0",
        }
        family = identity.split(":", 1)[1]
        required = {"etlantic"}
        for backend in ("polars", "pandas"):
            if backend in family.split("-"):
                required.update({backend, "etlantic-" + backend})
        if family in {"polars-pandas", "pandas-polars"}:
            required.add("pyarrow")
        if set(row["versions"]) != required:
            raise ValueError("Candidate requires exact row dependency sets")
        if any(version != pins[name] for name, version in row["versions"].items()):
            raise ValueError("Candidate package/backend pin drift")
        for values in (row["operations"], row["policies"]):
            if (
                not isinstance(values, (list, tuple))
                or not values
                or len(set(values)) != len(values)
                or any(type(v) is not str or not v for v in values)
            ):
                raise ValueError("Invalid candidate signature operations/policies")
        primary = identity == "scan-filter-project-chain/1:polars-pandas"
        operations = (
            {
                "bounded-parquet-snapshot",
                "scan-equality-filter",
                "ordered-project",
                "arrow-transfer",
                "pandas-project",
                "validation",
                "publication",
            }
            if primary
            else {
                "compute",
                "transfer",
                "collection",
                "validation",
                "materialization",
                "reuse",
                "publication",
            }
        )
        policies = {"standard", "validate", "overwrite", "no_write"}
        if primary:
            policies.add("single-attempt")
        if set(row["operations"]) != operations or set(row["policies"]) != policies:
            raise ValueError("Candidate requires exact signature operations/policies")
