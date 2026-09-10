"""Canonical serialization and fingerprinting for adaptive plans."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from etlantic.plan.adaptive_model import AdaptivePipelinePlan


def canonical_adaptive_dict(plan: AdaptivePipelinePlan) -> dict[str, Any]:
    """Return all semantic ``/2`` fields in deterministic order."""
    data = copy.deepcopy(plan.to_dict())
    data.pop("fingerprint", None)
    data.pop("plan_id", None)
    return _sort_structure(data)


def canonical_adaptive_json(plan: AdaptivePipelinePlan) -> str:
    return json.dumps(
        canonical_adaptive_dict(plan),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def adaptive_plan_fingerprint(plan: AdaptivePipelinePlan) -> str:
    return hashlib.sha256(canonical_adaptive_json(plan).encode("utf-8")).hexdigest()


def verify_adaptive_fingerprint(plan: AdaptivePipelinePlan) -> None:
    expected = adaptive_plan_fingerprint(plan)
    if plan.fingerprint != expected:
        raise ValueError(
            "AdaptivePipelinePlan fingerprint mismatch: "
            f"embedded={plan.fingerprint!r} computed={expected!r}"
        )


def adaptive_plan_to_json(plan: AdaptivePipelinePlan, *, indent: int | None = 2) -> str:
    data = plan.to_dict()
    if indent is None:
        return json.dumps(data, sort_keys=True, separators=(",", ":"))
    return json.dumps(data, indent=indent, sort_keys=True) + "\n"


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
