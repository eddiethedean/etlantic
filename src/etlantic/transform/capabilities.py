"""Requirement extraction and capability matching for portable IR."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from etlantic.transform.compiler import (
    TransformCapabilities,
    TransformSupportFinding,
    TransformSupportReport,
)
from etlantic.transform.protocol import (
    DEFAULT_PROFILE,
    KERNEL_PROFILE_V1,
    KERNEL_PROFILE_V2,
    RELATIONAL_PROFILE_V1,
    RELATIONAL_PROFILE_V2,
)

# Profiles that are plan-shape / metadata aliases of the kernel claim.
_KERNEL_PROFILE_ALIASES = frozenset(
    {
        KERNEL_PROFILE_V1,
        KERNEL_PROFILE_V2,
        DEFAULT_PROFILE,
    }
)

# Candidate relational /2 is treated as a metadata alias of claimed /1.
_RELATIONAL_PROFILE_ALIASES = frozenset(
    {
        RELATIONAL_PROFILE_V1,
        RELATIONAL_PROFILE_V2,
    }
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
    from etlantic.transform.protocol import PROFILE_WINDOW_V1, PROFILE_WINDOW_V2

    actions: set[str] = set()
    functions: set[str] = set()
    profiles: set[str] = set()
    if plan.get("profile"):
        profiles.add(str(plan["profile"]))
    for item in plan.get("actions") or []:
        kind = item.get("kind") or {}
        action = kind.get("action")
        if isinstance(action, str):
            actions.add(action)
        _collect_call_callees(item, functions)
        if _plan_has_window(item):
            profiles.add(PROFILE_WINDOW_V1)
            profiles.add(PROFILE_WINDOW_V2)
    for output in (plan.get("outputs") or {}).values():
        if isinstance(output, dict):
            _collect_call_callees(output, functions)
            if _plan_has_window(output):
                profiles.add(PROFILE_WINDOW_V1)
                profiles.add(PROFILE_WINDOW_V2)
    return extract_requirements(
        actions=actions,
        functions=functions,
        profiles=profiles,
    )


def _plan_has_window(node: Any) -> bool:
    if isinstance(node, dict):
        if "window" in node and node["window"] is not None:
            return True
        return any(_plan_has_window(v) for v in node.values())
    if isinstance(node, list):
        return any(_plan_has_window(item) for item in node)
    return False


def _collect_call_callees(node: Any, functions: set[str]) -> None:
    if isinstance(node, dict):
        if node.get("kind") == "call" and isinstance(node.get("callee"), str):
            functions.add(str(node["callee"]))
        for value in node.values():
            _collect_call_callees(value, functions)
    elif isinstance(node, list):
        for item in node:
            _collect_call_callees(item, functions)


def merge_requirements(
    *parts: Mapping[str, Sequence[str]] | None,
) -> dict[str, list[str]]:
    """Union requirement lists (profiles/actions/functions) fail-closed."""
    profiles: set[str] = set()
    actions: set[str] = set()
    functions: set[str] = set()
    for part in parts:
        if not part:
            continue
        profiles.update(str(x) for x in (part.get("profiles") or ()))
        actions.update(str(x) for x in (part.get("actions") or ()))
        functions.update(str(x) for x in (part.get("functions") or ()))
    return {
        "profiles": sorted(profiles),
        "actions": sorted(actions),
        "functions": sorted(functions),
    }


def match_requirements(
    requirements: Mapping[str, Sequence[str]] | None,
    capabilities: TransformCapabilities,
    *,
    allow_kernel_profile_alias: bool = True,
) -> TransformSupportReport:
    """Compare plan requirements against advertised compiler capabilities.

    When ``allow_kernel_profile_alias`` is true, requiring kernel ``/2`` (or
    the default plan-v2 profile) is satisfied by a compiler that claims
    ``portable-relational-kernel/1`` only — without granting extra relational
    ops. Requiring ``portable-relational/2`` is similarly satisfied by a
    compiler that claims ``portable-relational/1`` only (no candidate
    extensions).

    Empty ``capabilities.actions`` / ``capabilities.functions`` deny any
    required action/function (fail closed).
    """
    req = requirements or {}
    findings: list[TransformSupportFinding] = []

    claimed_profiles = set(capabilities.profiles)
    if allow_kernel_profile_alias and KERNEL_PROFILE_V1 in claimed_profiles:
        claimed_profiles |= _KERNEL_PROFILE_ALIASES
    if allow_kernel_profile_alias and RELATIONAL_PROFILE_V1 in claimed_profiles:
        claimed_profiles |= _RELATIONAL_PROFILE_ALIASES

    for profile in req.get("profiles") or ():
        if profile not in claimed_profiles:
            # Kernel-only compilers may see only kernel aliases as required.
            if (
                allow_kernel_profile_alias
                and profile in _KERNEL_PROFILE_ALIASES
                and KERNEL_PROFILE_V1 in capabilities.profiles
            ):
                continue
            if (
                allow_kernel_profile_alias
                and profile in _RELATIONAL_PROFILE_ALIASES
                and RELATIONAL_PROFILE_V1 in capabilities.profiles
            ):
                continue
            findings.append(
                TransformSupportFinding(
                    code="PMXFORM301",
                    requirement=f"profile:{profile}",
                    reason="profile is not claimed by the compiler",
                    expression_path=None,
                )
            )

    for action in req.get("actions") or ():
        if action not in capabilities.actions:
            findings.append(
                TransformSupportFinding(
                    code="PMXFORM301",
                    requirement=f"action:{action}",
                    reason="action is not implemented",
                    expression_path=None,
                )
            )

    for function in req.get("functions") or ():
        if function not in capabilities.functions:
            findings.append(
                TransformSupportFinding(
                    code="PMXFORM301",
                    requirement=f"function:{function}",
                    reason="function is not implemented",
                    expression_path=None,
                )
            )

    return TransformSupportReport(
        supported=not findings,
        findings=tuple(findings),
    )
