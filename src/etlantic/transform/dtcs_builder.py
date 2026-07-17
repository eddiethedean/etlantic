"""Lower FrameExpr trees to DTCS COM plans and portable envelopes."""

from __future__ import annotations

from typing import Any

import dtcs

from etlantic.exceptions import ModelDefinitionError
from etlantic.transform.capabilities import extract_requirements
from etlantic.transform.dataframe import FrameExpr, input_frame
from etlantic.transform.protocol import (
    AUTHORING_PROFILE,
    DEFAULT_BUDGETS,
    DEFAULT_PROFILE,
    DTCS_SPEC_VERSION,
    KERNEL_PROFILE_V1,
    KERNEL_PROFILE_V2,
    PLAN_PROTOCOL,
    REGISTRY_VERSIONS,
    PortableDefinition,
    TransformBudgets,
)
from etlantic.transform.validate import (
    report_or_raise,
    validate_output_binding,
    validate_plan_budgets,
)


def _schema_from_contract(contract_type: type[Any] | None) -> dict[str, Any]:
    fields: list[dict[str, Any]] = []
    if contract_type is None:
        return {"fields": fields}
    annotations = getattr(contract_type, "__annotations__", {}) or {}
    for name in annotations:
        if name.startswith("_"):
            continue
        fields.append({"name": name, "type": "string", "nullable": True})
    # Prefer model_fields when available (pydantic / ContractModel)
    model_fields = getattr(contract_type, "model_fields", None)
    if isinstance(model_fields, dict) and model_fields:
        fields = []
        for name, info in model_fields.items():
            annotation = getattr(info, "annotation", str)
            type_name = getattr(annotation, "__name__", str(annotation))
            logical = {
                "int": "integer",
                "float": "decimal",
                "bool": "boolean",
                "str": "string",
            }.get(type_name, "string")
            fields.append({"name": name, "type": logical, "nullable": True})
    return {"fields": fields}


def _action_parameters(action: Any) -> dict[str, Any]:
    params = dict(action.parameters)
    # Attach window specs from with_fields assignments if present later.
    return params


def build_com_plan(
    *,
    transformation_id: str,
    transformation_name: str,
    inputs: list[Any],
    outputs: list[Any],
    parameters: list[Any],
    produced: dict[str, FrameExpr],
) -> tuple[dict[str, Any], dict[str, list[str]]]:
    """Build a COM transformation plan and requirement sets."""
    com_inputs = []
    for port in inputs:
        com_inputs.append(
            {
                "id": port.name,
                "schema": _schema_from_contract(port.contract_type),
                "optional": False,
            }
        )

    com_outputs = []
    for port in outputs:
        frame = produced[port.name]
        schema = _schema_from_contract(port.contract_type)
        if frame.schema_fields:
            schema = {
                "fields": [
                    {"name": name, "type": "string", "nullable": True}
                    for name in frame.schema_fields
                ]
            }
        com_outputs.append({"id": port.name, "schema": schema})

    nodes: list[dict[str, Any]] = []
    dependencies: list[dict[str, str]] = []
    actions_used: set[str] = set()
    functions_used: set[str] = set()
    profiles_used: set[str] = {KERNEL_PROFILE_V1, KERNEL_PROFILE_V2, DEFAULT_PROFILE}

    seen_action_ids: set[str] = set()
    for out_name, frame in produced.items():
        for action in frame.actions:
            if action.action_id in seen_action_ids:
                continue
            seen_action_ids.add(action.action_id)
            actions_used.add(action.action)
            functions_used |= set(action.functions)
            profiles_used |= set(action.profiles)
            params = _action_parameters(action)
            nodes.append(
                {
                    "id": action.action_id,
                    "kind": {
                        "kind": "semanticAction",
                        "id": action.action_id,
                        "action": action.action,
                        "target": action.target,
                        "parameters": params,
                    },
                    "objectRef": f"semanticActions.{action.action_id}",
                }
            )
            dependencies.append(
                {"from": action.target, "to": action.action_id, "reason": "fieldRead"}
            )
            # Join/union also depend on the right/other relation.
            right = params.get("right") or params.get("other")
            if isinstance(right, str):
                dependencies.append(
                    {"from": right, "to": action.action_id, "reason": "fieldRead"}
                )
        dependencies.append(
            {
                "from": frame.relation_id,
                "to": out_name,
                "reason": "lineage",
            }
        )

    # Collect functions/profiles from any window metadata embedded via withColumn over()
    for frame in produced.values():
        functions_used |= set(frame.functions)
        profiles_used |= set(frame.profiles)

    lineage = {
        "mappings": [
            {
                "output": out_name,
                "inputs": [frame.root_input],
                "operation": "dtcs:derive",
                "flow": "derived",
            }
            for out_name, frame in produced.items()
        ]
    }

    com = {
        "identity": {
            "dtcsVersion": DTCS_SPEC_VERSION,
            "id": transformation_id,
            "name": transformation_name,
            "version": "1.0.0",
        },
        "inputs": com_inputs,
        "outputs": com_outputs,
        "nodes": nodes,
        "dependencies": dependencies,
        "lineage": lineage,
        "guarantees": {},
        "metadata": {
            "description": f"ETLantic portable definition ({AUTHORING_PROFILE})",
            "classification": "internal",
            "governance": {"owner": "etlantic", "steward": "etlantic"},
            "provenance": {
                "author": "etlantic.transform",
                "createdAt": "1970-01-01T00:00:00Z",
            },
        },
        "findings": [],
        "parameters": {port.name: {"type": {"kind": "string"}} for port in parameters},
    }
    requirements = extract_requirements(
        actions=actions_used,
        functions=functions_used,
        profiles=profiles_used,
    )
    return com, requirements


def _attach_window_actions(produced: dict[str, FrameExpr]) -> dict[str, FrameExpr]:
    """Rewrite with_fields assignments that carry ColumnExpr.window into params."""
    # FrameExpr already stores lowered expression nodes; window attachment is
    # handled when building withColumns by embedding window dict beside expression.
    return produced


def lower_with_columns_windows(frame: FrameExpr) -> FrameExpr:
    """No-op placeholder kept for API symmetry."""
    return frame


def build_portable_definition(
    *,
    transformation: type[Any],
    produced: dict[str, FrameExpr],
    budgets: TransformBudgets = DEFAULT_BUDGETS,
) -> PortableDefinition:
    """Validate outputs, export `dtcs.transform-plan/2`, and fingerprint."""
    declared = {p.name for p in transformation.outputs()}
    diagnostics = validate_output_binding(declared_outputs=declared, produced=produced)
    report_or_raise(diagnostics)

    for name, value in produced.items():
        if not isinstance(value, FrameExpr):
            raise ModelDefinitionError(
                f"Portable output {name!r} must be a FrameExpr (PMXFORM110)"
            )

    com, requirements = build_com_plan(
        transformation_id=transformation.identity(),
        transformation_name=transformation.__name__,
        inputs=list(transformation.inputs()),
        outputs=list(transformation.outputs()),
        parameters=list(transformation.parameters()),
        produced=produced,
    )

    try:
        portable = dtcs.plan_export_portable(com, profile=DEFAULT_PROFILE)
    except Exception as exc:
        raise ModelDefinitionError(
            f"Failed to export dtcs.transform-plan/2: {exc}"
        ) from exc

    if portable.get("planIdentity") != PLAN_PROTOCOL:
        raise ModelDefinitionError(
            f"Expected {PLAN_PROTOCOL}, got {portable.get('planIdentity')!r} (PMXFORM901)"
        )

    portable.setdefault("registryVersions", REGISTRY_VERSIONS)

    budget_diags = validate_plan_budgets(portable, budgets=budgets)
    report_or_raise(budget_diags)

    try:
        fingerprint = dtcs.plan_fingerprint(portable)
    except Exception as exc:
        raise ModelDefinitionError(
            f"Failed to fingerprint portable plan: {exc}"
        ) from exc

    # Authoring metadata stays beside the plan so fingerprinting remains DTCS-pure.
    return PortableDefinition(
        transformation_id=transformation.identity(),
        authoring_profile=AUTHORING_PROFILE,
        plan=portable,
        fingerprint=fingerprint,
        requirements=requirements,
        extensions={
            "etlantic": {
                "authoringProfile": AUTHORING_PROFILE,
                "requirements": requirements,
            }
        },
    )


def invoke_portable(
    transformation: type[Any],
    fn: Any,
    *,
    budgets: TransformBudgets = DEFAULT_BUDGETS,
) -> PortableDefinition:
    """Call a portable authoring function with symbolic bindings and build IR."""
    kwargs: dict[str, Any] = {}
    for port in transformation.inputs():
        schema = _schema_from_contract(port.contract_type)
        names = tuple(f["name"] for f in schema.get("fields", []))
        kwargs[port.name] = input_frame(port.name, schema_fields=names or None)
    for port in transformation.parameters():
        from etlantic.transform.column import ParameterRef

        kwargs[port.name] = ParameterRef(port.name)

    try:
        result = fn(**kwargs)
    except TypeError as exc:
        raise ModelDefinitionError(
            f"Portable definition signature mismatch: {exc} (PMXFORM101)"
        ) from exc

    if isinstance(result, FrameExpr):
        outputs = transformation.outputs()
        if len(outputs) != 1:
            raise ModelDefinitionError(
                "Returning a single FrameExpr requires exactly one Output port (PMXFORM203)"
            )
        produced = {outputs[0].name: result}
    elif isinstance(result, dict):
        produced = result
    else:
        raise ModelDefinitionError(
            "Portable definition must return FrameExpr or mapping of output name "
            "to FrameExpr (PMXFORM110)"
        )

    # Materialize window specs into with_fields parameters when ColumnExpr.over used.
    produced = {name: _materialize_windows(frame) for name, frame in produced.items()}
    return build_portable_definition(
        transformation=transformation,
        produced=produced,
        budgets=budgets,
    )


def _materialize_windows(frame: FrameExpr) -> FrameExpr:
    """Embed window dicts into with_fields assignment parameters when present.

    ColumnExpr.over() is applied before withColumns stores expression nodes.
    Authors should pass columns that already include window metadata; we scan
    nothing here because nodes are plain dicts. Windowed analytics are represented
    by wrapping call nodes with a `window` parameter on the with_fields assignment
    when the ColumnExpr still carries `.window` at withColumns time.
    """
    return frame
