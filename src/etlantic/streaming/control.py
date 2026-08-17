"""Bounded, deterministic dynamic-control types (046-D)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from etlantic.diagnostics import Diagnostic, ValidationReport
from etlantic.exceptions import PipelineValidationError
from etlantic.model import NodeKind
from etlantic.streaming.diagnostics import dyn_diagnostic

STREAMING_SCHEMA = "etlantic.streaming/1"
CONTROL_KIND_VALUES = frozenset(
    {
        NodeKind.MAP.value,
        NodeKind.REDUCE.value,
        NodeKind.CONDITIONAL.value,
        NodeKind.FAILURE.value,
        NodeKind.COMPENSATION.value,
    }
)
CONTROL_NODE_KINDS = frozenset(
    {
        NodeKind.MAP,
        NodeKind.REDUCE,
        NodeKind.CONDITIONAL,
        NodeKind.FAILURE,
        NodeKind.COMPENSATION,
    }
)

# Frozen extras engines/orchestrators must claim to preserve 0.46 graphs.
STREAMING_EXTRAS = frozenset(
    {
        "control.expansion",
        "control.branch",
        "stream.event_time",
        "stream.handoff",
        "record_error.dead_letter",
        "schema.registry",
    }
)


def is_control_kind(kind: NodeKind | str) -> bool:
    """Return True when ``kind`` is a 0.46 dynamic-control node."""
    if isinstance(kind, NodeKind):
        return kind in CONTROL_NODE_KINDS
    return str(kind) in CONTROL_KIND_VALUES


@dataclass(frozen=True, slots=True)
class ExpansionBounds:
    """Hard limits that fail before unbounded work is accepted."""

    max_children: int = 1024
    max_depth: int = 8
    max_concurrency: int = 32
    max_metadata_bytes: int = 65536
    max_duration_seconds: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_children": self.max_children,
            "max_depth": self.max_depth,
            "max_concurrency": self.max_concurrency,
            "max_metadata_bytes": self.max_metadata_bytes,
            "max_duration_seconds": self.max_duration_seconds,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> ExpansionBounds:
        raw = dict(data or {})
        duration = raw.get("max_duration_seconds")
        return cls(
            max_children=_bound_int(raw, "max_children", 1024),
            max_depth=_bound_int(raw, "max_depth", 8),
            max_concurrency=_bound_int(raw, "max_concurrency", 32),
            max_metadata_bytes=_bound_int(raw, "max_metadata_bytes", 65536),
            max_duration_seconds=(None if duration in (None, "") else float(duration)),
        )


def _bound_int(raw: Mapping[str, Any], key: str, default: int) -> int:
    if key not in raw or raw[key] in (None, ""):
        return default
    return int(raw[key])


def child_identity(
    *,
    plan_id: str,
    parent_id: str,
    map_key: str,
    input_snapshot_id: str,
) -> str:
    """Deterministic child identity for a declared expansion input."""
    payload = json.dumps(
        {
            "plan_id": str(plan_id),
            "parent_id": str(parent_id),
            "map_key": str(map_key),
            "input_snapshot_id": str(input_snapshot_id),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ChildExpansion:
    """One expanded child unit (identifiers only)."""

    identity: str
    parent_id: str
    map_key: str
    input_snapshot_id: str
    depth: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity,
            "parent_id": self.parent_id,
            "map_key": self.map_key,
            "input_snapshot_id": self.input_snapshot_id,
            "depth": self.depth,
        }


@dataclass(frozen=True, slots=True)
class ExpansionSpec:
    """Declared map/reduce expansion over a bounded collection identity."""

    parent_id: str
    collection_identity: str
    bounds: ExpansionBounds = field(default_factory=ExpansionBounds)
    decision_evidence: Mapping[str, str] = field(default_factory=dict)
    required_extras: tuple[str, ...] = ("control.expansion",)

    def to_dict(self) -> dict[str, Any]:
        return {
            "parent_id": self.parent_id,
            "collection_identity": self.collection_identity,
            "bounds": self.bounds.to_dict(),
            "decision_evidence": dict(self.decision_evidence),
            "required_extras": list(self.required_extras),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ExpansionSpec:
        extra_raw = data.get("required_extras") or ("control.expansion",)
        evidence = {
            str(k): str(v) for k, v in dict(data.get("decision_evidence") or {}).items()
        }
        return cls(
            parent_id=str(data["parent_id"]),
            collection_identity=str(data["collection_identity"]),
            bounds=ExpansionBounds.from_dict(data.get("bounds")),
            decision_evidence=evidence,
            required_extras=tuple(str(x) for x in extra_raw),
        )


def _metadata_size(evidence: Mapping[str, str]) -> int:
    payload = json.dumps(dict(evidence), sort_keys=True, separators=(",", ":"))
    return len(payload.encode("utf-8"))


def expand_children(
    spec: ExpansionSpec,
    keys: Sequence[str],
    *,
    plan_id: str,
    input_snapshot_id: str,
    depth: int = 1,
) -> tuple[ChildExpansion, ...]:
    """Expand ``keys`` into deterministic child identities.

    Raises:
        PipelineValidationError: When bounds would be exhausted.
    """
    diagnostics: list[Diagnostic] = []
    n = len(keys)
    if n > spec.bounds.max_children:
        diagnostics.append(
            dyn_diagnostic(
                "bound_exhausted",
                (
                    f"Expansion of {spec.parent_id!r} produced {n} children; "
                    f"max_children={spec.bounds.max_children}"
                ),
                path=("expansion", spec.parent_id, "max_children"),
                metadata={
                    "parent_id": spec.parent_id,
                    "child_count": n,
                    "max_children": spec.bounds.max_children,
                },
            )
        )
    if depth > spec.bounds.max_depth:
        diagnostics.append(
            dyn_diagnostic(
                "bound_exhausted",
                (f"Expansion depth {depth} exceeds max_depth={spec.bounds.max_depth}"),
                path=("expansion", spec.parent_id, "max_depth"),
            )
        )
    meta_bytes = _metadata_size(spec.decision_evidence)
    if meta_bytes > spec.bounds.max_metadata_bytes:
        diagnostics.append(
            dyn_diagnostic(
                "bound_exhausted",
                (
                    f"Decision evidence is {meta_bytes} bytes; "
                    f"max_metadata_bytes={spec.bounds.max_metadata_bytes}"
                ),
                path=("expansion", spec.parent_id, "max_metadata_bytes"),
            )
        )
    if n > spec.bounds.max_concurrency:
        diagnostics.append(
            dyn_diagnostic(
                "bound_exhausted",
                (
                    f"Expansion of {spec.parent_id!r} produced {n} children; "
                    f"max_concurrency={spec.bounds.max_concurrency}"
                ),
                path=("expansion", spec.parent_id, "max_concurrency"),
                metadata={
                    "parent_id": spec.parent_id,
                    "child_count": n,
                    "max_concurrency": spec.bounds.max_concurrency,
                },
            )
        )
    duration = spec.bounds.max_duration_seconds
    if duration is not None and duration <= 0:
        diagnostics.append(
            dyn_diagnostic(
                "bound_exhausted",
                (
                    f"Expansion of {spec.parent_id!r} has "
                    f"max_duration_seconds={duration}; "
                    "refusing work with a non-positive duration budget"
                ),
                path=("expansion", spec.parent_id, "max_duration_seconds"),
            )
        )
    if n == 0:
        diagnostics.append(
            dyn_diagnostic(
                "unbounded_expansion",
                (
                    f"Expansion of {spec.parent_id!r} has no declared keys; "
                    "refusing unbounded work"
                ),
                path=("expansion", spec.parent_id, "keys"),
            )
        )
    if diagnostics:
        raise PipelineValidationError(
            "Dynamic expansion bounds exhausted.",
            report=ValidationReport.from_diagnostics(
                diagnostics, phases=("expansion",)
            ),
        )
    children: list[ChildExpansion] = []
    for key in keys:
        identity = child_identity(
            plan_id=plan_id,
            parent_id=spec.parent_id,
            map_key=str(key),
            input_snapshot_id=input_snapshot_id,
        )
        children.append(
            ChildExpansion(
                identity=identity,
                parent_id=spec.parent_id,
                map_key=str(key),
                input_snapshot_id=input_snapshot_id,
                depth=depth,
            )
        )
    return tuple(children)


def reject_python_branch(*, path: tuple[str, ...] = ("authoring",)) -> Diagnostic:
    """Diagnostic for inferred Python control flow (never a plan surface)."""
    return dyn_diagnostic(
        "python_branch",
        "Arbitrary Python control flow is not a portable plan surface.",
        path=path,
        help="Declare explicit map/reduce/conditional/failure/compensation nodes.",
    )
