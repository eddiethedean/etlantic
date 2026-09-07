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
            # V2 is only required when V2-only functions appear.
            if _plan_requires_window_v2(item):
                profiles.add(PROFILE_WINDOW_V2)
    for output in (plan.get("outputs") or {}).values():
        if isinstance(output, dict):
            _collect_call_callees(output, functions)
            if _plan_has_window(output):
                profiles.add(PROFILE_WINDOW_V1)
                if _plan_requires_window_v2(output):
                    profiles.add(PROFILE_WINDOW_V2)
    # Infer V2 from function callees when present.
    v2_only = {"dtcs:ntile", "dtcs:percent_rank"}
    if functions & v2_only:
        profiles.add(PROFILE_WINDOW_V2)
        profiles.add(PROFILE_WINDOW_V1)
    return extract_requirements(
        actions=actions,
        functions=functions,
        profiles=profiles,
    )


_WINDOW_V2_CALLEES = frozenset({"dtcs:ntile", "dtcs:percent_rank"})


def _plan_requires_window_v2(node: Any) -> bool:
    found: set[str] = set()
    _collect_call_callees(node, found)
    return bool(found & _WINDOW_V2_CALLEES)


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
    *parts: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Union all capability requirements without dropping constraints.

    Requirement maps are extensible.  In addition to the original profile,
    action, and function lists, matching also understands operators, types,
    semantic modes, and lazy/eager execution flags.  The previous
    implementation silently discarded the former categories while combining
    explicit and inferred requirements, which made unsupported plans appear
    supported.  Preserve every known key and leave unknown keys untouched so
    future requirement categories fail closed in their matcher rather than
    being erased here.
    """
    list_keys = (
        "profiles",
        "actions",
        "functions",
        "operators",
        "types",
        "semantic_modes",
    )
    merged: dict[str, set[str]] = {key: set() for key in list_keys}
    boolean_values: dict[str, bool] = {}
    unknown: dict[str, Any] = {}
    for part in parts:
        if not part:
            continue
        for key in list_keys:
            values = part.get(key)
            if values is None:
                continue
            if isinstance(values, (str, bytes)):
                values = (values,)
            if isinstance(values, Sequence):
                merged[key].update(str(value) for value in values)
        for key in ("lazy", "eager"):
            value = part.get(key)
            if isinstance(value, bool):
                # Requirements are conjunctive: a requested lazy execution
                # mode must remain requested, and eager=False must remain
                # restrictive when any contributor asks for it.
                if key == "lazy":
                    boolean_values[key] = boolean_values.get(key, False) or value
                elif key not in boolean_values:
                    boolean_values[key] = value
                else:
                    boolean_values[key] = boolean_values[key] and value
        for key, value in part.items():
            if key not in list_keys and key not in {"lazy", "eager"}:
                unknown[key] = value

    result: dict[str, Any] = {key: sorted(values) for key, values in merged.items()}
    result.update(boolean_values)
    result.update(unknown)
    return result


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

    for operator in req.get("operators") or ():
        if operator not in capabilities.operators:
            findings.append(
                TransformSupportFinding(
                    code="PMXFORM301",
                    requirement=f"operator:{operator}",
                    reason="operator is not implemented",
                    expression_path=None,
                )
            )

    for type_id in req.get("types") or ():
        if type_id not in capabilities.types:
            findings.append(
                TransformSupportFinding(
                    code="PMXFORM301",
                    requirement=f"type:{type_id}",
                    reason="type is not claimed by the compiler",
                    expression_path=None,
                )
            )

    for mode in req.get("semantic_modes") or ():
        if mode not in capabilities.semantic_modes:
            findings.append(
                TransformSupportFinding(
                    code="PMXFORM301",
                    requirement=f"semantic_mode:{mode}",
                    reason="semantic mode is not claimed by the compiler",
                    expression_path=None,
                )
            )

    if req.get("lazy") is True and not capabilities.lazy:
        findings.append(
            TransformSupportFinding(
                code="PMXFORM301",
                requirement="mode:lazy",
                reason="lazy execution is not claimed by the compiler",
                expression_path=None,
            )
        )
    if req.get("eager") is False and not capabilities.lazy:
        findings.append(
            TransformSupportFinding(
                code="PMXFORM301",
                requirement="mode:lazy",
                reason="eager-only compilers cannot satisfy lazy=false requirements",
                expression_path=None,
            )
        )

    return TransformSupportReport(
        supported=not findings,
        findings=tuple(findings),
    )


def plan_requires_distinct_three_state(plan: Mapping[str, Any] | None) -> bool:
    """Return True when the plan uses distinct missing/invalid literals."""

    def _walk(node: Any) -> bool:
        if isinstance(node, dict):
            if node.get("kind") == "literal":
                value = node.get("value")
                if isinstance(value, dict):
                    lit_type = str(value.get("type") or "")
                    if lit_type in {"missing", "invalid"}:
                        return True
            return any(_walk(v) for v in node.values())
        if isinstance(node, list):
            return any(_walk(item) for item in node)
        return False

    return _walk(plan or {})


def three_state_findings(
    definition: Mapping[str, Any],
    capabilities: TransformCapabilities,
) -> list[TransformSupportFinding]:
    """Fail closed when distinct three-state is required but not claimed."""
    if not plan_requires_distinct_three_state(definition):
        return []
    if "three_state_distinct" in capabilities.semantic_modes:
        return []
    return [
        TransformSupportFinding(
            code="PMXFORM301",
            requirement="semantic_mode:three_state_distinct",
            reason=(
                "plan uses missing/invalid literals but the compiler does not "
                "claim distinct three-state preservation"
            ),
            expression_path=None,
        )
    ]


_WINDOWED_AGGREGATE_CALLEES = frozenset(
    {
        "dtcs:sum",
        "dtcs:average",
        "dtcs:min",
        "dtcs:max",
        "dtcs:count",
        "dtcs:count_all",
        "dtcs:count_distinct",
        "dtcs:variance",
        "dtcs:stddev",
        "dtcs:corr",
    }
)


def window_frame_findings(
    definition: Mapping[str, Any],
) -> list[TransformSupportFinding]:
    """Reject explicit window frames until compilers lower them honestly."""
    findings: list[TransformSupportFinding] = []

    def _walk(node: Any, *, path: str) -> None:
        if isinstance(node, dict):
            window = node.get("window")
            if isinstance(window, dict) and window.get("frame") is not None:
                findings.append(
                    TransformSupportFinding(
                        code="PMXFORM301",
                        requirement="mode:window_frame",
                        reason=(
                            "explicit window frames are not implemented; "
                            "omit rowsBetween/rangeBetween or use native APIs"
                        ),
                        expression_path=path,
                    )
                )
            for key, value in node.items():
                child = f"{path}.{key}" if path else str(key)
                _walk(value, path=child)
        elif isinstance(node, list):
            for index, item in enumerate(node):
                _walk(item, path=f"{path}[{index}]")

    _walk(definition, path="")
    return findings


def windowed_aggregate_findings(
    definition: Mapping[str, Any],
) -> list[TransformSupportFinding]:
    """Reject aggregate callees attached to windows outside dtcs:aggregate."""
    findings: list[TransformSupportFinding] = []

    def _callee(node: Any) -> str | None:
        if isinstance(node, dict) and node.get("kind") == "call":
            callee = node.get("callee")
            return str(callee) if callee else None
        return None

    for action in definition.get("actions") or []:
        kind = action.get("kind") or {}
        if kind.get("action") != "dtcs:with_fields":
            continue
        action_id = str(kind.get("id") or action.get("id") or "with_fields")
        params = kind.get("parameters") or {}
        for index, assignment in enumerate(params.get("assignments") or []):
            if not isinstance(assignment, dict):
                continue
            if assignment.get("window") is None:
                continue
            callee = _callee(assignment.get("expression"))
            if callee in _WINDOWED_AGGREGATE_CALLEES:
                findings.append(
                    TransformSupportFinding(
                        code="PMXFORM301",
                        requirement=f"function:{callee}:window",
                        reason=(
                            f"aggregate function {callee!r} cannot be used as a "
                            "window expression; use dtcs:aggregate"
                        ),
                        expression_path=f"{action_id}.assignments[{index}]",
                    )
                )
    return findings
