"""Canonical serialization and fingerprinting for PipelinePlan."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from etlantic.plan.model import PipelinePlan


def canonical_plan_dict(plan: PipelinePlan) -> dict[str, Any]:
    """Return a deterministically ordered plan dict for hashing."""
    data = copy.deepcopy(plan.to_dict())
    # Derived / fill-in fields excluded from the content hash.
    data = {k: v for k, v in data.items() if k not in {"fingerprint", "plan_id"}}
    for item in data.get("output_resolutions") or []:
        artifact = item.get("artifact") or {}
        artifact.pop("cache_key", None)
    return _sort_structure(data)


def canonical_plan_json(plan: PipelinePlan) -> str:
    """Return canonical JSON bytes as a UTF-8 string."""
    return json.dumps(
        canonical_plan_dict(plan),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def plan_fingerprint(plan: PipelinePlan) -> str:
    """Compute a stable SHA-256 fingerprint of the canonical plan."""
    payload = canonical_plan_json(plan).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def plan_to_json(plan: PipelinePlan, *, indent: int | None = 2) -> str:
    """Serialize a plan including its fingerprint."""
    data = plan.to_dict()
    if indent is None:
        return json.dumps(data, sort_keys=True, separators=(",", ":"))
    return json.dumps(data, indent=indent, sort_keys=True) + "\n"


def verify_plan_fingerprint(plan: PipelinePlan) -> None:
    """Recompute the canonical plan fingerprint and compare to ``plan.fingerprint``.

    Args:
        plan: Plan whose embedded fingerprint is checked.

    Returns:
        ``None`` when the fingerprint matches.

    Raises:
        ValueError: When the embedded fingerprint does not match the canonical
            SHA-256 of the plan content (excluding derived ``plan_id`` fields).
    """
    expected = plan_fingerprint(plan)
    if plan.fingerprint != expected:
        raise ValueError(
            f"PipelinePlan fingerprint mismatch: "
            f"embedded={plan.fingerprint!r} computed={expected!r}"
        )


def plan_from_json(text: str, *, verify: bool = True) -> PipelinePlan:
    """Deserialize a plan from JSON text.

    Args:
        text: UTF-8 JSON object matching ``etlantic.plan/1``.
        verify: When True (default), validate wire ``schema`` and recompute the
            fingerprint after :meth:`PipelinePlan.from_dict`.

    Returns:
        Parsed :class:`~etlantic.plan.model.PipelinePlan`.

    Raises:
        ValueError: When JSON is not an object, schema is missing/unknown, or
            (when ``verify``) the fingerprint does not match content.
        UnsupportedPlanSchemaError: When the document schema cannot be upgraded.
    """
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("PipelinePlan JSON must be an object")
    plan = PipelinePlan.from_dict(data, verify=verify)
    if verify:
        verify_plan_fingerprint(plan)
    return plan


def _sort_structure(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _sort_structure(value[k]) for k in sorted(value)}
    if isinstance(value, list):
        return [_sort_structure(v) for v in value]
    return value
