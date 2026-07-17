"""Requirement extraction from portable authoring artifacts."""

from __future__ import annotations

from typing import Any

from etlantic.transform.protocol import (
    DEFAULT_PROFILE,
    KERNEL_PROFILE_V1,
    KERNEL_PROFILE_V2,
)


def extract_requirements(
    *,
    actions: set[str],
    functions: set[str],
    profiles: set[str],
) -> dict[str, list[str]]:
    """Return sorted requirement lists for a portable definition."""
    profile_set = set(profiles) | {
        KERNEL_PROFILE_V1,
        KERNEL_PROFILE_V2,
        DEFAULT_PROFILE,
    }
    return {
        "profiles": sorted(profile_set),
        "actions": sorted(actions),
        "functions": sorted(functions),
    }


def requirements_from_plan(plan: dict[str, Any]) -> dict[str, list[str]]:
    """Best-effort extraction from an exported portable plan."""
    actions: set[str] = set()
    for item in plan.get("actions") or []:
        kind = item.get("kind") or {}
        action = kind.get("action")
        if isinstance(action, str):
            actions.add(action)
    profiles = {plan.get("profile")} if plan.get("profile") else set()
    return extract_requirements(actions=actions, functions=set(), profiles=profiles)  # type: ignore[arg-type]
