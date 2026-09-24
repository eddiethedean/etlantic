# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnnecessaryIsInstance=false
"""Pure normalized schema transfer over portable ``FrameExpr`` actions."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from etlantic.diagnostics import Diagnostic, Severity
from etlantic.schema_drift import NormalizedField, NormalizedSchema, json_safe_metadata


def _merge(left: str, right: str) -> str:
    if left == right:
        return left
    if "unknown" in {left, right}:
        return "unknown"
    if {left, right} <= {"integer", "number"}:
        return "number"
    if {left, right} <= {"integer", "decimal"}:
        return "decimal"
    if {left, right} <= {"integer", "decimal", "number"}:
        return "decimal"
    if "string" in {left, right}:
        return "string"
    return "unknown"


def _sequence(value: Any) -> list[Any]:
    """Return only JSON-array-like values from untrusted action parameters."""
    if isinstance(value, (list, tuple)):
        return list(value)
    return []


def _expression_refs(node: Any) -> tuple[str, ...]:
    """Collect field references without evaluating the expression."""
    if not isinstance(node, Mapping):
        return ()
    if node.get("kind") == "fieldRef":
        target = node.get("target")
        return (str(target),) if target is not None else ()
    refs: list[str] = []
    for value in node.values():
        if isinstance(value, Mapping):
            refs.extend(_expression_refs(value))
        elif isinstance(value, (list, tuple)):
            for item in value:
                refs.extend(_expression_refs(item))
    return tuple(dict.fromkeys(refs))


def _initial_lineage(schema: NormalizedSchema) -> dict[str, dict[str, Any]]:
    existing = schema.metadata.get("lineage", {})
    lineage: dict[str, dict[str, Any]] = {}
    for field in schema.fields:
        entry = existing.get(field.name) if isinstance(existing, Mapping) else None
        if isinstance(entry, Mapping):
            lineage[field.name] = dict(entry)
            continue
        lineage[field.name] = {
            "field": field.name,
            "source_node": schema.identity,
            "source_fields": [field.name],
            "qualified_source_fields": [f"{schema.identity}.{field.name}"],
            "source_types": {field.name: field.logical_type},
            "operations": [],
            "invertible": True,
        }
    return lineage


def _lineage_fingerprint(lineage: Mapping[str, Any]) -> str:
    payload = json.dumps(
        json_safe_metadata(lineage),
        sort_keys=True,
        allow_nan=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _lineage_expression(
    expression: Any,
    current: Mapping[str, dict[str, Any]],
    operation: str,
) -> dict[str, Any]:
    refs = _expression_refs(expression)
    entries = [current[name] for name in refs if name in current]
    source_fields = list(
        dict.fromkeys(
            field for entry in entries for field in entry.get("source_fields", ())
        )
    )
    source_types: dict[str, Any] = {}
    for entry in entries:
        source_types.update(entry.get("source_types", {}))
    direct = (
        isinstance(expression, Mapping)
        and expression.get("kind") == "fieldRef"
        and len(refs) == 1
        and refs[0] in current
    )
    operations = [
        *[operation],
        *[item for entry in entries for item in entry.get("operations", ())],
    ]
    return {
        "field": operation,
        "source_nodes": list(
            dict.fromkeys(
                str(entry.get("source_node"))
                for entry in entries
                if entry.get("source_node") is not None
            )
        ),
        "source_fields": source_fields,
        "qualified_source_fields": list(
            dict.fromkeys(
                field
                for entry in entries
                for field in entry.get("qualified_source_fields", ())
            )
        ),
        "source_types": source_types,
        "operations": operations,
        "invertible": direct
        and all(entry.get("invertible", False) for entry in entries),
    }


def infer_expression(
    node: Mapping[str, Any] | Any,
    schema: NormalizedSchema,
    diagnostics: list[Diagnostic] | None = None,
) -> tuple[str, bool]:
    """Return ``(logical_type, nullable)`` without evaluating row values."""
    if not isinstance(node, Mapping):
        if diagnostics is not None:
            diagnostics.append(
                Diagnostic(
                    "INFER_BACKWARD_UNSUPPORTED",
                    Severity.WARNING,
                    "Schema transfer received a malformed expression",
                    phase="inference",
                )
            )
        return "unknown", True
    kind = node.get("kind")
    if kind == "fieldRef":
        target = node.get("target")
        field = next((field for field in schema.fields if field.name == target), None)
        if field is None and diagnostics is not None:
            diagnostics.append(
                Diagnostic(
                    "INFER_LINEAGE_MISSING",
                    Severity.ERROR,
                    f"Expression references missing field {target!r}",
                    path=(str(target),),
                    phase="inference",
                )
            )
        return (field.logical_type, field.nullable) if field else ("unknown", True)
    if kind == "literal":
        value = node.get("value")
        if isinstance(value, Mapping) and "type" in value:
            return str(value["type"]), value.get("value") is None
        if value is None:
            return "null", True
        if isinstance(value, bool):
            return "boolean", False
        if isinstance(value, int):
            return "integer", False
        if isinstance(value, float):
            return "number", False
        return "string", False
    if kind == "unary":
        logical, nullable = infer_expression(node.get("expr", {}), schema, diagnostics)
        return ("boolean", nullable) if node.get("op") == "not" else (logical, nullable)
    if kind == "binary":
        left, left_null = infer_expression(node.get("left", {}), schema, diagnostics)
        right, right_null = infer_expression(node.get("right", {}), schema, diagnostics)
        if node.get("op") in {
            "eq",
            "not_eq",
            "lt",
            "lte",
            "gt",
            "gte",
            "null_safe_eq",
            "and",
            "or",
        }:
            return "boolean", left_null or right_null
        return _merge(left, right), left_null or right_null
    if kind == "call":
        callee = str(node.get("callee"))
        args = list(node.get("args", ()))
        if callee in {
            "dtcs:is_null",
            "dtcs:is_not_null",
            "dtcs:is_missing",
            "dtcs:is_invalid",
        }:
            return "boolean", False
        if callee in {"dtcs:cast", "dtcs:try_cast"} and len(args) > 1:
            input_nullable = infer_expression(args[0], schema, diagnostics)[1]
            target = (
                args[1].get("value", "unknown")
                if isinstance(args[1], Mapping)
                else "unknown"
            )
            if isinstance(target, Mapping):
                target = target.get("value", "unknown")
            return str(target), input_nullable or callee.endswith("try_cast")
        if callee in {"dtcs:coalesce", "coalesce"} and args:
            inferred = [infer_expression(arg, schema, diagnostics) for arg in args]
            logical = inferred[0][0]
            for value, _ in inferred[1:]:
                logical = _merge(logical, value)
            return logical, all(nullable for _, nullable in inferred)
        if callee in {"dtcs:if_null", "if_null"} and len(args) >= 2:
            inferred = [infer_expression(arg, schema, diagnostics) for arg in args[:2]]
            return _merge(inferred[0][0], inferred[1][0]), inferred[0][1] and inferred[
                1
            ][1]
        if callee in {"dtcs:null_if", "null_if"} and args:
            logical, nullable = infer_expression(args[0], schema, diagnostics)
            return logical, True if len(args) > 1 else nullable
        if callee in {"dtcs:case_when", "case_when"} and args:
            value_args = args[1::2][:-1] + args[-1:]
            inferred = [
                infer_expression(arg, schema, diagnostics) for arg in value_args
            ]
            logical = inferred[0][0]
            for value, _ in inferred[1:]:
                logical = _merge(logical, value)
            return logical, any(nullable for _, nullable in inferred)
        scalar_types = {
            "dtcs:lower": "string",
            "dtcs:upper": "string",
            "dtcs:concat": "string",
            "dtcs:concat_ws": "string",
            "dtcs:substr": "string",
            "dtcs:substring": "string",
            "dtcs:replace": "string",
            "dtcs:trim": "string",
            "dtcs:ltrim": "string",
            "dtcs:rtrim": "string",
            "dtcs:normalize_whitespace": "string",
            "dtcs:regex_extract": "string",
            "dtcs:regex_replace": "string",
            "dtcs:to_string": "string",
            "dtcs:length": "integer",
            "dtcs:to_integer": "integer",
            "dtcs:abs": "number",
            "dtcs:round": "number",
            "dtcs:floor": "number",
            "dtcs:ceil": "number",
            "dtcs:power": "number",
            "dtcs:sqrt": "number",
            "dtcs:to_decimal": "decimal",
            "dtcs:current_date": "date",
            "dtcs:current_timestamp": "datetime",
        }
        if callee in scalar_types:
            nullable = any(
                infer_expression(arg, schema, diagnostics)[1] for arg in args
            )
            return scalar_types[callee], nullable
        if diagnostics is not None:
            diagnostics.append(
                Diagnostic(
                    "INFER_BACKWARD_UNSUPPORTED",
                    Severity.WARNING,
                    f"Schema transfer does not support expression {callee!r}",
                    phase="inference",
                )
            )
        return "unknown", True
    if diagnostics is not None:
        diagnostics.append(
            Diagnostic(
                "INFER_BACKWARD_UNSUPPORTED",
                Severity.WARNING,
                "Schema transfer does not support this expression",
                phase="inference",
            )
        )
    return "unknown", True


def forward_schema(
    frame: Any,
    input_schema: NormalizedSchema,
    *,
    max_diagnostics: int = 100,
) -> NormalizedSchema:
    """Transfer a schema through a ``FrameExpr`` action list."""
    fields = list(input_schema.fields)
    lineage = _initial_lineage(input_schema)
    transfer_diagnostics: list[Diagnostic] = []
    for action in getattr(frame, "actions", ()):
        name = action.action
        params = action.parameters
        if name == "dtcs:filter":
            available_fields = {field.name for field in fields}
            for field_name in _expression_refs(params.get("predicate", {})):
                if field_name not in available_fields:
                    transfer_diagnostics.append(
                        Diagnostic(
                            "INFER_LINEAGE_MISSING",
                            Severity.ERROR,
                            f"Filter predicate references missing field {field_name!r}",
                            path=(field_name,),
                            phase="inference",
                        )
                    )
            for entry in lineage.values():
                entry["operations"] = [
                    *_sequence(entry.get("operations")),
                    {"operation": name},
                ]
            continue
        if name in {"dtcs:sort", "dtcs:limit", "dtcs:distinct"}:
            for entry in lineage.values():
                entry["operations"] = [
                    *_sequence(entry.get("operations")),
                    {"operation": name},
                ]
            continue
        if name == "dtcs:drop_fields":
            drop = set(_sequence(params.get("fields")))
            fields = [field for field in fields if field.name not in drop]
            lineage = {
                field_name: entry
                for field_name, entry in lineage.items()
                if field_name not in drop
            }
        elif name == "dtcs:rename_fields":
            mapping = params.get("mapping", {})
            if not isinstance(mapping, Mapping):
                mapping = {}
            renamed: list[NormalizedField] = []
            next_lineage: dict[str, dict[str, Any]] = {}
            for field in fields:
                output_name = mapping.get(field.name, field.name)
                entry = dict(lineage.get(field.name, {}))
                entry["field"] = output_name
                entry["operations"] = [
                    *_sequence(entry.get("operations")),
                    {"operation": "rename", "from": field.name, "to": output_name},
                ]
                if output_name in next_lineage:
                    transfer_diagnostics.append(
                        Diagnostic(
                            "INFER_LINEAGE_COLLISION",
                            Severity.ERROR,
                            f"Rename produces duplicate field {output_name!r}",
                            path=(output_name,),
                            phase="inference",
                        )
                    )
                    continue
                next_lineage[output_name] = entry
                renamed.append(
                    NormalizedField(
                        output_name,
                        field.logical_type,
                        field.required,
                        field.nullable,
                        dict(field.metadata),
                    )
                )
            fields = renamed
            lineage = next_lineage
        elif name == "dtcs:project":
            projected: list[NormalizedField] = []
            next_lineage: dict[str, dict[str, Any]] = {}
            for item in _sequence(params.get("fields")):
                if isinstance(item, str):
                    source = next(
                        (field for field in fields if field.name == item), None
                    )
                    if source:
                        entry = dict(lineage.get(source.name, {}))
                        entry["field"] = item
                        entry["operations"] = [
                            *_sequence(entry.get("operations")),
                            {"operation": "project", "field": item},
                        ]
                        next_lineage[item] = entry
                        projected.append(source)
                    else:
                        transfer_diagnostics.append(
                            Diagnostic(
                                "INFER_LINEAGE_MISSING",
                                Severity.ERROR,
                                f"Projection references missing field {item!r}",
                                path=(item,),
                                phase="inference",
                            )
                        )
                        next_lineage[item] = {
                            "field": item,
                            "source_fields": [],
                            "source_types": {},
                            "operations": [{"operation": "project", "field": item}],
                            "invertible": False,
                        }
                        projected.append(
                            NormalizedField(
                                item,
                                "unknown",
                                False,
                                True,
                                {"inference_missing": True},
                            )
                        )
                elif isinstance(item, Mapping):
                    output_name = str(item.get("name"))
                    logical, nullable = infer_expression(
                        item.get("expression", {}),
                        NormalizedSchema(input_schema.identity, tuple(fields)),
                        transfer_diagnostics,
                    )
                    if output_name in next_lineage:
                        transfer_diagnostics.append(
                            Diagnostic(
                                "INFER_LINEAGE_COLLISION",
                                Severity.ERROR,
                                f"Projection produces duplicate field {output_name!r}",
                                path=(output_name,),
                                phase="inference",
                            )
                        )
                        continue
                    next_lineage[output_name] = _lineage_expression(
                        item.get("expression", {}), lineage, "project"
                    )
                    next_lineage[output_name]["field"] = output_name
                    projected.append(
                        NormalizedField(
                            output_name,
                            logical,
                            not nullable,
                            nullable,
                            {"inferred": True},
                        )
                    )
            fields = projected
            lineage = next_lineage
        elif name == "dtcs:with_fields":
            current = {field.name: field for field in fields}
            next_lineage = dict(lineage)
            assigned_names: set[str] = set()
            for item in params.get("assignments", ()):
                if not isinstance(item, Mapping):
                    continue
                field_name = str(item.get("name"))
                logical, nullable = infer_expression(
                    item.get("expression", {}),
                    NormalizedSchema(input_schema.identity, tuple(current.values())),
                    transfer_diagnostics,
                )
                current[field_name] = NormalizedField(
                    field_name, logical, not nullable, nullable, {"inferred": True}
                )
                if field_name in assigned_names or (
                    field_name in next_lineage and field_name not in lineage
                ):
                    transfer_diagnostics.append(
                        Diagnostic(
                            "INFER_LINEAGE_COLLISION",
                            Severity.ERROR,
                            f"Assignments produce duplicate field {field_name!r}",
                            path=(field_name,),
                            phase="inference",
                        )
                    )
                assigned_names.add(field_name)
                next_lineage[field_name] = _lineage_expression(
                    item.get("expression", {}), lineage, "with_fields"
                )
                next_lineage[field_name]["field"] = field_name
            fields = list(current.values())
            lineage = next_lineage
        elif name in {
            "dtcs:join",
            "dtcs:union",
            "dtcs:aggregate",
            "dtcs:intersect",
            "dtcs:except",
            "dtcs:explode",
        }:
            transfer_diagnostics.append(
                Diagnostic(
                    "INFER_BACKWARD_UNSUPPORTED",
                    Severity.WARNING,
                    f"Schema transfer does not support frame action {name!r}",
                    phase="inference",
                )
            )
            fields = [
                NormalizedField(
                    field.name,
                    "unknown",
                    False,
                    True,
                    {**field.metadata, "inference_unsupported": name},
                )
                for field in fields
            ]
            lineage = {
                field.name: {
                    **lineage.get(field.name, {}),
                    "field": field.name,
                    "invertible": False,
                    "operations": [
                        *lineage.get(field.name, {}).get("operations", ()),
                        {"operation": name},
                    ],
                }
                for field in fields
            }
        else:
            # Fail closed for newly introduced or non portable actions.  A
            # silently preserved schema can cause a downstream write to use
            # an incorrect model.
            transfer_diagnostics.append(
                Diagnostic(
                    "INFER_BACKWARD_UNSUPPORTED",
                    Severity.WARNING,
                    f"Schema transfer does not support frame action {name!r}",
                    phase="inference",
                )
            )
            fields = [
                NormalizedField(
                    field.name,
                    "unknown",
                    False,
                    True,
                    {**field.metadata, "inference_unsupported": name},
                )
                for field in fields
            ]
            lineage = {
                field.name: {
                    **lineage.get(field.name, {}),
                    "field": field.name,
                    "invertible": False,
                    "operations": [
                        *lineage.get(field.name, {}).get("operations", ()),
                        {"operation": name},
                    ],
                }
                for field in fields
            }
    # Diagnostics are part of the wire contract. Deduplicate and cap them so
    # repeated data-first transformations cannot grow an unbounded payload.
    bounded_diagnostics: list[Diagnostic] = []
    seen: set[tuple[str, tuple[str, ...], str]] = set()
    for diagnostic in transfer_diagnostics:
        key = (diagnostic.code, tuple(diagnostic.path), diagnostic.message)
        if key in seen:
            continue
        seen.add(key)
        if len(bounded_diagnostics) < max(1, max_diagnostics):
            bounded_diagnostics.append(diagnostic)
    metadata = dict(input_schema.metadata)
    metadata["lineage"] = lineage
    metadata["lineage_version"] = 1
    metadata["lineage_fingerprint"] = _lineage_fingerprint(lineage)
    metadata["lineage_graph"] = {
        "version": 1,
        "fields": {
            name: {
                "source_nodes": _sequence(entry.get("source_nodes"))
                or ([entry.get("source_node")] if entry.get("source_node") else []),
                "source_fields": _sequence(entry.get("source_fields")),
                "qualified_source_fields": _sequence(
                    entry.get("qualified_source_fields")
                ),
                "operations": _sequence(entry.get("operations")),
                "invertible": bool(entry.get("invertible", False)),
            }
            for name, entry in lineage.items()
        },
    }
    if bounded_diagnostics:
        metadata["inference_diagnostics"] = [
            diagnostic.to_dict() for diagnostic in bounded_diagnostics
        ]
    schema_field_order = getattr(frame, "schema_fields", None)
    if isinstance(schema_field_order, (list, tuple)):
        by_name = {field.name: field for field in fields}
        ordered_names = [
            str(name) for name in schema_field_order if str(name) in by_name
        ]
        ordered_fields = [by_name[name] for name in ordered_names]
        present = set(ordered_names)
        ordered_fields.extend(field for field in fields if field.name not in present)
        fields = ordered_fields
    else:
        # Preserve the input contract order when the frame does not carry an
        # explicit projection/order hint. Fingerprints canonicalize field
        # order separately, so this does not weaken deterministic identity.
        fields = list(fields)
    return NormalizedSchema(
        input_schema.identity,
        tuple(fields),
        metadata,
    )


infer_frame_schema = forward_schema
