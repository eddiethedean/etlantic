"""Requirement extraction and capability matching for portable IR."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from etlantic.transform.compiler import (
    TransformCapabilities,
    TransformSupportFinding,
    TransformSupportReport,
    validate_requirement_support_payload,
)
from etlantic.transform.portable_baseline import (
    BASELINE_FUNCTION_ARITIES,
    PROFILE_ALIASES,
    normalize_action,
    normalize_operator,
)
from etlantic.transform.protocol import (
    DEFAULT_PROFILE,
    KERNEL_PROFILE_V1,
)


def _claimed_profiles_with_aliases(profiles: set[str]) -> set[str]:
    """Expand only aliases explicitly proven by the normative manifest."""
    claimed = set(profiles)
    claimed.add(DEFAULT_PROFILE)
    for alias, details in PROFILE_ALIASES.items():
        canonical = details.get("canonical")
        if (
            canonical in claimed
            and details.get("proof") == "exact-vocabulary-equivalence"
        ):
            claimed.add(alias)
    return claimed


def extract_requirements(
    *,
    actions: set[str],
    functions: set[str],
    profiles: set[str],
    operators: set[str] | None = None,
    types: set[str] | None = None,
) -> dict[str, list[str]]:
    """Return sorted requirement lists for a portable definition."""
    profile_set = _claimed_profiles_with_aliases(set(profiles) | {KERNEL_PROFILE_V1})
    return {
        "profiles": sorted(profile_set),
        "actions": sorted(actions),
        "functions": sorted(functions),
        "operators": sorted(operators or set()),
        "types": sorted(types or set()),
    }


def requirements_from_plan(
    plan: dict[str, Any], *, include_extended: bool = False
) -> dict[str, list[str]]:
    """Best-effort extraction from an exported portable plan."""
    from etlantic.transform.protocol import PROFILE_WINDOW_V1, PROFILE_WINDOW_V2

    actions: set[str] = set()
    functions: set[str] = set()
    profiles: set[str] = set()
    operators: set[str] = set()
    types: set[str] = set()
    semantic_modes: set[str] = set()
    join_modes: set[str] = set()
    union_modes: set[str] = set()
    collision_policies: set[str] = set()
    if plan.get("profile"):
        profiles.add(str(plan["profile"]))
    for item in plan.get("actions") or []:
        kind = item.get("kind") or {}
        action = kind.get("action")
        if isinstance(action, str):
            actions.add(normalize_action(action))
        params = kind.get("parameters") if isinstance(kind, Mapping) else {}
        if isinstance(params, Mapping):
            if action == "dtcs:join":
                if params.get("type") is not None:
                    join_modes.add(str(params["type"]))
                if params.get("collisionPolicy") is not None:
                    collision_policies.add(str(params["collisionPolicy"]))
            elif action == "dtcs:union" and params.get("mode") is not None:
                union_modes.add(str(params["mode"]))
        _collect_expression_requirements(item, functions, operators, types)
        if _contains_distinct_three_state(item):
            semantic_modes.add("three_state_distinct")
        if _plan_has_window(item):
            profiles.add(PROFILE_WINDOW_V1)
            # V2 is only required when V2-only functions appear.
            if _plan_requires_window_v2(item):
                profiles.add(PROFILE_WINDOW_V2)
    for output in (plan.get("outputs") or {}).values():
        if isinstance(output, dict):
            _collect_expression_requirements(output, functions, operators, types)
            if _contains_distinct_three_state(output):
                semantic_modes.add("three_state_distinct")
            if _plan_has_window(output):
                profiles.add(PROFILE_WINDOW_V1)
                if _plan_requires_window_v2(output):
                    profiles.add(PROFILE_WINDOW_V2)
    # Infer V2 from function callees when present.
    v2_only = {"dtcs:ntile", "dtcs:percent_rank"}
    if functions & v2_only:
        profiles.add(PROFILE_WINDOW_V2)
        profiles.add(PROFILE_WINDOW_V1)
    result = extract_requirements(
        actions=actions,
        functions=functions,
        profiles=profiles,
        operators=operators,
        types=types,
    )
    result["semantic_modes"] = sorted(semantic_modes)
    result["join_modes"] = sorted(join_modes)
    result["union_modes"] = sorted(union_modes)
    result["collision_policies"] = sorted(collision_policies)
    if not include_extended:
        result.pop("operators", None)
        result.pop("types", None)
    return result


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


def _collect_expression_requirements(
    node: Any,
    functions: set[str],
    operators: set[str],
    types: set[str],
) -> None:
    """Collect governed expression vocabulary without losing dimensions."""
    if isinstance(node, Mapping):
        kind = node.get("kind")
        if kind == "call" and isinstance(node.get("callee"), str):
            callee = str(node["callee"])
            if callee == "dtcs:in":
                operators.add("in")
            else:
                functions.add(callee)
        elif (
            isinstance(kind, str)
            and kind in {"binary", "unary"}
            and isinstance(node.get("op"), str)
        ):
            operators.add(normalize_operator(str(node["op"])))
        elif kind == "literal":
            value = node.get("value")
            if isinstance(value, Mapping) and isinstance(value.get("type"), str):
                types.add(str(value["type"]))
        for value in node.values():
            _collect_expression_requirements(value, functions, operators, types)
    elif isinstance(node, list):
        for item in node:
            _collect_expression_requirements(item, functions, operators, types)


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
        "join_modes",
        "union_modes",
        "collision_policies",
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
    canonical: list[TransformSupportFinding] = []

    def record(
        requirement: str,
        ok: bool,
        reason: str,
        *,
        code: str = "PMXFORM301",
        support: str | None = None,
    ) -> None:
        state = support or ("supported_exact" if ok else "unsupported")
        finding = TransformSupportFinding(
            code=code,
            requirement=requirement,
            reason=("requirement is supported by the compiler" if ok else reason),
            expression_path=None,
            support=state,
        )
        canonical.append(finding)
        if not ok or state not in {"supported_exact", "supported_with_lowering"}:
            findings.append(finding)

    known_keys = {
        "profiles",
        "actions",
        "functions",
        "operators",
        "types",
        "semantic_modes",
        "join_modes",
        "union_modes",
        "collision_policies",
        "lazy",
        "eager",
    }
    for key in sorted(set(req) - known_keys):
        record(
            f"requirement:{key}",
            False,
            "requirement category is unknown to this protocol version",
            code="PMXFORM303",
            support="unknown",
        )

    claimed_profiles = set(capabilities.profiles)
    if allow_kernel_profile_alias:
        claimed_profiles = _claimed_profiles_with_aliases(claimed_profiles)

    for profile in req.get("profiles") or ():
        if profile not in claimed_profiles:
            # Kernel-only compilers may see only kernel aliases as required.
            if (
                allow_kernel_profile_alias
                and profile in PROFILE_ALIASES
                and PROFILE_ALIASES[profile].get("canonical") in capabilities.profiles
            ):
                record(f"profile:{profile}", True, "")
                continue
            record(
                f"profile:{profile}", False, "profile is not claimed by the compiler"
            )
        else:
            record(f"profile:{profile}", True, "")

    for action in req.get("actions") or ():
        action = normalize_action(str(action))
        if action not in capabilities.actions:
            record(f"action:{action}", False, "action is not implemented")
        else:
            record(f"action:{action}", True, "")

    for function in req.get("functions") or ():
        if function not in capabilities.functions:
            record(f"function:{function}", False, "function is not implemented")
        else:
            record(f"function:{function}", True, "")

    for operator in req.get("operators") or ():
        operator = normalize_operator(str(operator))
        if operator not in capabilities.operators:
            record(f"operator:{operator}", False, "operator is not implemented")
        else:
            record(f"operator:{operator}", True, "")

    for type_id in req.get("types") or ():
        if type_id not in capabilities.types:
            record(f"type:{type_id}", False, "type is not claimed by the compiler")
        else:
            record(f"type:{type_id}", True, "")

    for mode in req.get("semantic_modes") or ():
        if mode not in capabilities.semantic_modes:
            record(
                f"semantic_mode:{mode}",
                False,
                "semantic mode is not claimed by the compiler",
            )
        else:
            record(f"semantic_mode:{mode}", True, "")

    for mode in req.get("join_modes") or ():
        if mode not in capabilities.join_modes:
            record(
                f"join_mode:{mode}", False, "join mode is not claimed by the compiler"
            )
        else:
            record(f"join_mode:{mode}", True, "")
    for mode in req.get("union_modes") or ():
        if mode not in capabilities.union_modes:
            record(
                f"union_mode:{mode}", False, "union mode is not claimed by the compiler"
            )
        else:
            record(f"union_mode:{mode}", True, "")
    for policy in req.get("collision_policies") or ():
        if policy not in capabilities.collision_policies:
            record(
                f"collision_policy:{policy}",
                False,
                "collision policy is not claimed by the compiler",
            )
        else:
            record(f"collision_policy:{policy}", True, "")

    if req.get("lazy") is True and not capabilities.lazy:
        record("mode:lazy", False, "lazy execution is not claimed by the compiler")
    elif req.get("lazy") is True:
        record("mode:lazy", True, "")
    if req.get("eager") is True:
        if not capabilities.eager:
            record(
                "mode:eager", False, "eager execution is not claimed by the compiler"
            )
        else:
            record("mode:eager", True, "")

    return TransformSupportReport(
        supported=not findings,
        findings=tuple(findings),
        requirement_findings=tuple(canonical),
    )


def evaluate_adaptive_candidates(
    candidates: Sequence[Mapping[str, Any]],
    *,
    required_requirements: Sequence[str] | Mapping[str, Sequence[str]] = (),
    preferred_requirements: Sequence[str] | Mapping[str, Sequence[str]] = (),
    edges: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Evaluate candidate support vectors before preference scoring.

    Adaptive selection must eliminate a candidate with an unknown or negative
    required requirement before considering preferred capabilities. Unknown
    preferred requirements contribute no score. The returned decision record is
    data-only so it can be persisted as qualification evidence.
    """

    def _requirements_for(
        specification: Sequence[str] | Mapping[str, Sequence[str]], node_id: str
    ) -> set[str]:
        values = (
            specification.get(node_id, ())
            if isinstance(specification, Mapping)
            else specification
        )
        if isinstance(values, (str, bytes)):
            raise TypeError("adaptive requirement lists must be sequences")
        return {str(item) for item in values}

    decisions: list[dict[str, Any]] = []
    seen_ids: set[tuple[str, str]] = set()
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            raise TypeError("adaptive candidates must be mappings")
        candidate_id = str(candidate.get("id") or "")
        if not candidate_id:
            raise ValueError("adaptive candidate id is required")
        node_id = str(candidate.get("node") or candidate.get("node_id") or "node")
        identity = (node_id, candidate_id)
        if identity in seen_ids:
            raise ValueError("adaptive candidate id must be unique per node")
        seen_ids.add(identity)
        vectors = candidate.get("requirements")
        if not isinstance(vectors, Mapping):
            raise ValueError("adaptive candidate requirements must be a mapping")
        normalized = {str(key): str(value) for key, value in vectors.items()}
        support_report = candidate.get("support_report")
        if not isinstance(support_report, Mapping):
            raise ValueError("adaptive candidate requires validated support evidence")
        validate_requirement_support_payload(support_report)
        report_requirements = {
            str(item["id"]): item for item in support_report["requirements"]
        }
        report_findings = {
            str(item["requirement"]): item for item in support_report["findings"]
        }
        aliases = {
            str((item.get("parameters") or {}).get("value")): identifier
            for identifier, item in report_requirements.items()
            if (item.get("parameters") or {}).get("value") is not None
        }
        resolved_ids: dict[str, str] = {}
        for requirement, state in normalized.items():
            requirement_id = (
                requirement
                if requirement in report_findings
                else aliases.get(requirement)
            )
            if requirement_id is None or requirement_id not in report_findings:
                raise ValueError("adaptive requirement is absent from support evidence")
            finding = report_findings[requirement_id]
            if finding.get("support") != state:
                raise ValueError("adaptive support state disagrees with evidence")
            resolved_ids[requirement] = requirement_id
        applicable_ids = {
            identifier
            for identifier, item in report_requirements.items()
            if item.get("applicability") == "applicable"
        }
        if (
            set(resolved_ids.values()) != applicable_ids
            or set(report_findings) != applicable_ids
        ):
            raise ValueError(
                "adaptive candidate must retain the complete support vector"
            )
        required = _requirements_for(required_requirements, node_id)
        preferred = _requirements_for(preferred_requirements, node_id)
        required_failures = [
            requirement
            for requirement in sorted(required)
            if normalized.get(requirement)
            not in {"supported_exact", "supported_with_lowering"}
        ]
        lowering = candidate.get("lowering")
        if lowering is not None:
            raise ValueError("adaptive lowering must be derived from support evidence")
        lowering_records: list[dict[str, Any]] = []
        lowered_requirements = sorted(
            requirement
            for requirement, state in normalized.items()
            if state == "supported_with_lowering"
        )
        if lowered_requirements:
            lowered_findings = [
                report_findings[resolved_ids[requirement]]
                for requirement in lowered_requirements
            ]
            groups: dict[
                tuple[str, str, tuple[Any, ...], tuple[Any, ...]], list[str]
            ] = {}
            for requirement, finding in zip(
                lowered_requirements, lowered_findings, strict=True
            ):
                lowering_id = str(finding.get("lowering_id") or "")
                proof = str(finding.get("proof_reference") or "")
                conditions = tuple(finding.get("conditions") or ())
                effects = tuple(finding.get("physical_effects") or ())
                if not lowering_id or not proof or not effects:
                    raise ValueError("adaptive lowering evidence is incomplete")
                groups.setdefault((lowering_id, proof, conditions, effects), []).append(
                    requirement
                )
            for (lowering_id, proof, conditions, effects), requirements in sorted(
                groups.items(), key=lambda item: item[0]
            ):
                lowering_records.append(
                    {
                        "id": lowering_id,
                        "requirements": requirements,
                        "proof": proof,
                        "conditions": list(conditions),
                        "physical_effects": list(effects),
                    }
                )
        lowering_payload: dict[str, Any] = {}
        if lowering_records:
            lowering_payload["lowerings"] = lowering_records
            # Keep the historical singular field for the common one-lowering case.
            if len(lowering_records) == 1:
                lowering_payload["lowering"] = lowering_records[0]
        if required_failures:
            decisions.append(
                {
                    "id": candidate_id,
                    "node": node_id,
                    "requirements": normalized,
                    "support_report": dict(support_report),
                    "eligible": False,
                    "decision": "eliminated_before_preference_scoring",
                    "required_failures": required_failures,
                    "preferred_score": None,
                    **lowering_payload,
                }
            )
            continue
        # Preference expresses capability presence, not a generic lowering penalty.
        # Lowering trade-offs are represented by the evidence-derived records.
        score = sum(
            1
            for requirement in preferred
            if normalized.get(requirement)
            in {"supported_exact", "supported_with_lowering"}
        )
        decisions.append(
            {
                "id": candidate_id,
                "node": node_id,
                "requirements": normalized,
                "support_report": dict(support_report),
                "eligible": True,
                "decision": "eligible",
                "required_failures": [],
                "preferred_score": score,
                **lowering_payload,
            }
        )
    selected_by_node: dict[str, str | None] = {}
    for node_id in sorted({item["node"] for item in decisions}):
        eligible = [
            item for item in decisions if item["node"] == node_id and item["eligible"]
        ]
        selected_by_node[node_id] = (
            max(eligible, key=lambda item: (item["preferred_score"], item["id"]))["id"]
            if eligible
            else None
        )
    selected: str | dict[str, str | None] | None = (
        next(iter(selected_by_node.values()))
        if len(selected_by_node) == 1
        else selected_by_node
    )
    graph_failures: list[dict[str, str]] = []
    selected_candidates = {
        node_id: next(
            (
                item
                for item in decisions
                if item["node"] == node_id and item["id"] == candidate_id
            ),
            None,
        )
        for node_id, candidate_id in selected_by_node.items()
        if candidate_id is not None
    }
    for edge in edges:
        if not isinstance(edge, Mapping):
            raise TypeError("adaptive edges must be mappings")
        producer = str(edge.get("producer") or edge.get("producer_node") or "")
        consumer = str(edge.get("consumer") or edge.get("consumer_node") or "")
        requirements = edge.get("requirements") or ()
        if not producer or not consumer or isinstance(requirements, (str, bytes)):
            raise ValueError(
                "adaptive edge requires producer, consumer, and requirements"
            )
        producer_candidate = selected_candidates.get(producer)
        consumer_candidate = selected_candidates.get(consumer)
        for requirement in requirements:
            requirement_id = str(requirement)
            producer_state = (
                producer_candidate["requirements"].get(requirement_id)
                if producer_candidate
                else None
            )
            consumer_state = (
                consumer_candidate["requirements"].get(requirement_id)
                if consumer_candidate
                else None
            )
            if producer_state not in {
                "supported_exact",
                "supported_with_lowering",
            } or consumer_state not in {"supported_exact", "supported_with_lowering"}:
                graph_failures.append(
                    {
                        "producer": producer,
                        "consumer": consumer,
                        "requirement": requirement_id,
                    }
                )
    return {
        "nodes": sorted(selected_by_node),
        "candidates": decisions,
        "selected": selected,
        "graph_valid": not graph_failures,
        "graph_failures": graph_failures,
    }


def _contains_distinct_three_state(node: Any) -> bool:
    if isinstance(node, Mapping):
        value = node.get("value")
        if (
            node.get("kind") == "literal"
            and isinstance(value, Mapping)
            and value.get("type") in {"missing", "invalid"}
        ):
            return True
        return any(_contains_distinct_three_state(item) for item in node.values())
    if isinstance(node, list):
        return any(_contains_distinct_three_state(item) for item in node)
    return False


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


def portable_shape_findings(
    definition: Mapping[str, Any],
) -> list[TransformSupportFinding]:
    """Validate baseline action policies that are not capability-set members."""
    findings: list[TransformSupportFinding] = []
    for index, item in enumerate(definition.get("actions") or ()):
        if not isinstance(item, Mapping):
            findings.append(
                TransformSupportFinding(
                    "PMXFORM302",
                    "action",
                    "action must be an object",
                    f"actions[{index}]",
                )
            )
            continue
        kind = item.get("kind") or {}
        if not isinstance(kind, Mapping):
            findings.append(
                TransformSupportFinding(
                    "PMXFORM302",
                    f"action[{index}]",
                    "action kind must be an object",
                    f"actions[{index}].kind",
                )
            )
            continue
        raw_action = kind.get("action")
        if not isinstance(raw_action, str) or not raw_action:
            findings.append(
                TransformSupportFinding(
                    "PMXFORM302",
                    "action",
                    "action kind must contain a non-empty string action",
                    f"actions[{index}].kind.action",
                )
            )
            continue
        action = normalize_action(raw_action)
        params = kind.get("parameters") or {}
        if not isinstance(params, Mapping):
            findings.append(
                TransformSupportFinding(
                    "PMXFORM302",
                    f"action:{action}:parameters",
                    "action parameters must be an object",
                    f"actions[{index}].kind.parameters",
                )
            )
            continue
        if (
            action == "dtcs:join"
            and str(params.get("collisionPolicy", "fail")).lower() != "fail"
        ):
            findings.append(
                TransformSupportFinding(
                    "PMXFORM302",
                    "join:collisionPolicy",
                    "only collisionPolicy=fail is portable",
                    f"actions[{index}].kind.parameters.collisionPolicy",
                )
            )
        if action == "dtcs:union" and str(params.get("mode", "byName")).lower() not in {
            "byname",
            "byposition",
        }:
            findings.append(
                TransformSupportFinding(
                    "PMXFORM302",
                    "union:mode",
                    "union mode must be byName or byPosition",
                    f"actions[{index}].kind.parameters.mode",
                )
            )
        if action == "dtcs:union":
            mode = str(params.get("mode", "byName")).lower()
            if mode == "byposition" and bool(params.get("allowMissingColumns", False)):
                findings.append(
                    TransformSupportFinding(
                        "PMXFORM302",
                        "union:allowMissingColumns",
                        "allowMissingColumns is not supported for byPosition unions",
                        f"actions[{index}].kind.parameters.allowMissingColumns",
                    )
                )
        if action == "dtcs:join":
            join_type = str(params.get("type", "inner")).lower()
            if join_type == "outer":
                join_type = "full"
            if join_type not in {
                "inner",
                "left",
                "right",
                "full",
                "semi",
                "anti",
                "cross",
            }:
                findings.append(
                    TransformSupportFinding(
                        "PMXFORM302",
                        "join:type",
                        "join type is outside the portable vocabulary",
                        f"actions[{index}].kind.parameters.type",
                    )
                )
            left_key = params.get("leftKey", params.get("leftKeys"))
            right_key = params.get("rightKey", params.get("rightKeys"))
            if isinstance(left_key, list) or isinstance(right_key, list):
                left_count = (
                    len(left_key)
                    if isinstance(left_key, list)
                    else (1 if left_key else 0)
                )
                right_count = (
                    len(right_key)
                    if isinstance(right_key, list)
                    else (1 if right_key else 0)
                )
                if left_count != right_count:
                    findings.append(
                        TransformSupportFinding(
                            "PMXFORM302",
                            "join:key_arity",
                            "left and right join key counts must match",
                            f"actions[{index}].kind.parameters",
                        )
                    )

        def _walk_expression(node: Any, path: str) -> None:
            if isinstance(node, Mapping):
                node_kind = node.get("kind")
                if isinstance(node_kind, str) and node_kind not in {
                    "fieldRef",
                    "literal",
                    "binary",
                    "unary",
                    "call",
                }:
                    findings.append(
                        TransformSupportFinding(
                            "PMXFORM302",
                            f"expression_kind:{node_kind}",
                            "expression kind is outside the portable vocabulary",
                            path,
                        )
                    )
                    return
                if node_kind == "call" and isinstance(node.get("callee"), str):
                    callee = str(node["callee"])
                    bounds = BASELINE_FUNCTION_ARITIES.get(callee)
                    args = node.get("args") or []
                    if bounds is not None and (
                        len(args) < bounds[0]
                        or (bounds[1] is not None and len(args) > bounds[1])
                    ):
                        findings.append(
                            TransformSupportFinding(
                                "PMXFORM302",
                                f"function:{callee}:arity",
                                f"{callee} received {len(args)} arguments outside its portable arity",
                                path,
                            )
                        )
                    if callee == "dtcs:concat_ws" and args:
                        separator = args[0]
                        if not (
                            isinstance(separator, Mapping)
                            and separator.get("kind") == "literal"
                            and isinstance(separator.get("value"), Mapping)
                            and separator["value"].get("type") == "string"
                        ):
                            findings.append(
                                TransformSupportFinding(
                                    "PMXFORM302",
                                    "function:dtcs:concat_ws:separator",
                                    "concat_ws requires a literal string separator",
                                    path,
                                )
                            )
                for key, value in node.items():
                    _walk_expression(value, f"{path}.{key}" if path else key)
            elif isinstance(node, list):
                for child_index, value in enumerate(node):
                    _walk_expression(value, f"{path}[{child_index}]")

        _walk_expression(params, f"actions[{index}].kind.parameters")
    return findings


def portable_arithmetic_findings(
    definition: Mapping[str, Any],
) -> list[TransformSupportFinding]:
    """Reject arithmetic that cannot satisfy the frozen portable contract.

    Native engines disagree about division/modulo by zero and fixed-width
    integer overflow.  A portable plan therefore has to prove that a divisor
    is a non-zero literal before dispatch; inspecting source rows during
    planning would violate the no-I/O planning boundary.  Literal integer
    overflow is similarly rejected before a backend can wrap, coerce, or
    produce an engine-specific error.
    """
    findings: list[TransformSupportFinding] = []
    integer_min = -(2**63)
    integer_max = 2**63 - 1

    def literal_value(node: Any) -> tuple[str | None, Any]:
        if not isinstance(node, Mapping) or node.get("kind") != "literal":
            return None, None
        value = node.get("value")
        if isinstance(value, Mapping):
            return str(value.get("type") or ""), value.get("value")
        return None, value

    def append_finding(requirement: str, reason: str, path: str) -> None:
        findings.append(
            TransformSupportFinding(
                code="PMXFORM302",
                requirement=requirement,
                reason=reason,
                expression_path=path,
                support="unsupported",
            )
        )

    def walk(node: Any, path: str = "plan") -> None:
        if isinstance(node, Mapping):
            kind = node.get("kind")
            if isinstance(kind, str) and kind in {"binary", "operator"}:
                op = normalize_operator(str(node.get("op")))
                right = node.get("right")
                if op in {"divide", "modulo"}:
                    right_type, right_value = literal_value(right)
                    if right_type is None:
                        append_finding(
                            f"arithmetic:{op}:statically-nonzero-denominator",
                            f"{op} requires a statically non-zero literal denominator; "
                            "field and parameter denominators cannot be qualified "
                            "without source-row inspection",
                            f"{path}.right",
                        )
                    elif (
                        not isinstance(right_value, (int, float))
                        or isinstance(right_value, bool)
                        or right_value == 0
                    ):
                        append_finding(
                            f"arithmetic:{op}:nonzero-denominator",
                            f"{op} by a zero or non-numeric literal is an explicit "
                            "portable arithmetic error",
                            f"{path}.right",
                        )
                if op in {"add", "subtract", "multiply"}:
                    left_type, left_value = literal_value(node.get("left"))
                    right_type, right_value = literal_value(right)
                    if left_type != "integer" or right_type != "integer":
                        append_finding(
                            f"arithmetic:{op}:statically-bounded-operands",
                            f"{op} requires signed 64-bit integer literals; dynamic "
                            "operands cannot prove portable overflow behavior",
                            path,
                        )
                    else:
                        try:
                            value = {
                                "add": left_value + right_value,
                                "subtract": left_value - right_value,
                                "multiply": left_value * right_value,
                            }[op]
                        except TypeError:
                            value = None
                        if (
                            not isinstance(value, int)
                            or not integer_min <= value <= integer_max
                        ):
                            append_finding(
                                "arithmetic:integer-overflow",
                                "integer literal arithmetic exceeds the portable signed "
                                "64-bit range",
                                path,
                            )
            elif isinstance(kind, str) and kind == "unary":
                op = normalize_operator(str(node.get("op")))
                operand_type, operand_value = literal_value(
                    node.get("operand", node.get("expr"))
                )
                if op == "negate":
                    if operand_type != "integer":
                        append_finding(
                            "arithmetic:negate:statically-bounded-operand",
                            "negate requires a signed 64-bit integer literal; dynamic "
                            "operands cannot prove portable overflow behavior",
                            path,
                        )
                    elif operand_value == integer_min:
                        append_finding(
                            "arithmetic:integer-overflow",
                            "negating the portable signed 64-bit minimum overflows",
                            path,
                        )
            for key, value in node.items():
                walk(value, f"{path}.{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{path}[{index}]")

    walk(definition)
    return findings


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
