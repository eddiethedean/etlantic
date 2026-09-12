"""Canonical serialization and fingerprinting for adaptive plans."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from etlantic.plan.adaptive_model import AdaptivePipelinePlan
from etlantic.planning.adaptive_budget import (
    budget_scope,
    canonical_chunks,
    materialize_wire,
    serialized_size,
    wire_view,
)


def canonical_adaptive_dict(plan: AdaptivePipelinePlan) -> dict[str, Any]:
    """Return all semantic ``/2`` fields in deterministic order."""
    data = wire_view(plan)
    data.pop("fingerprint", None)
    data.pop("plan_id", None)
    with budget_scope() as budget, budget.allocation(data, "serialization-record", 64):
        return materialize_wire(data)


def canonical_adaptive_json(plan: AdaptivePipelinePlan) -> str:
    data = wire_view(plan)
    data.pop("fingerprint", None)
    data.pop("plan_id", None)
    with (
        budget_scope() as budget,
        budget.allocation(data, "serialization-record", 64),
        budget.allocation(data, "serialization-buffer"),
    ):
        return json.dumps(
            materialize_wire(data),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )


def adaptive_plan_fingerprint(plan: AdaptivePipelinePlan) -> str:
    data = wire_view(plan)
    data.pop("fingerprint", None)
    data.pop("plan_id", None)
    digest = hashlib.sha256()
    for chunk in canonical_chunks(data):
        digest.update(chunk)
    return digest.hexdigest()


def verify_adaptive_fingerprint(plan: AdaptivePipelinePlan) -> None:
    expected = adaptive_plan_fingerprint(plan)
    if plan.fingerprint != expected:
        raise ValueError(
            "PMADP401: AdaptivePipelinePlan fingerprint mismatch: "
            f"embedded={plan.fingerprint!r} computed={expected!r}"
        )


def adaptive_plan_to_json(plan: AdaptivePipelinePlan, *, indent: int | None = 2) -> str:
    view = wire_view(plan)
    with budget_scope() as budget, budget.allocation(view, "serialization-record", 64):
        token = budget.reserve(
            serialized_size(view, indent) + (indent is not None), "serialization-buffer"
        )
        try:
            data = materialize_wire(view)
            if indent is None:
                return json.dumps(data, sort_keys=True, separators=(",", ":"))
            return json.dumps(data, indent=indent, sort_keys=True) + "\n"
        finally:
            budget.release(token)


def adaptive_plan_from_json(text: str, *, verify: bool = True) -> AdaptivePipelinePlan:
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("AdaptivePipelinePlan JSON must be an object")
    return AdaptivePipelinePlan.from_dict(data, verify=verify)


def _sort_structure(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _sort_structure(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_sort_structure(item) for item in value]
    return value
