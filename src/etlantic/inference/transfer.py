# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnnecessaryIsInstance=false
"""Pure normalized schema transfer over portable ``FrameExpr`` actions."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from etlantic.diagnostics import Diagnostic, Severity
from etlantic.schema_drift import NormalizedField, NormalizedSchema, json_safe_metadata

_MAX_LINEAGE_OPERATIONS = 256
_LINEAGE_TRUNCATION_MARKER = {"operation": "history_truncated"}


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
        if "decimal" in {left, right} and "number" in {left, right}:
            return "unknown"
        return "decimal"
    if "string" in {left, right}:
        return "string"
    return "unknown"


def _merge_call_results(
    left: str,
    right: str,
    diagnostics: list[Diagnostic] | None,
    *,
    function: str,
) -> str:
    merged = _merge(left, right)
    if (
        merged == "unknown"
        and left in {"integer", "decimal", "number"}
        and right in {"integer", "decimal", "number"}
        and {left, right} == {"decimal", "number"}
        and diagnostics is not None
    ):
        diagnostics.append(
            Diagnostic(
                "INFER_BACKWARD_UNSUPPORTED",
                Severity.ERROR,
                f"Expression {function!r} mixes decimal and number values without an explicit conversion",
                phase="inference",
            )
        )
    return merged


def _sequence(value: Any) -> list[Any]:
    """Return only JSON-array-like values from untrusted action parameters."""
    if isinstance(value, (list, tuple)):
        return list(value)
    return []


def _is_lineage_truncation_marker(value: Any) -> bool:
    return isinstance(value, Mapping) and value.get("operation") == "history_truncated"


def _bounded_lineage(lineage: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Bound operation history while retaining its beginning and latest steps."""
    bounded: dict[str, dict[str, Any]] = {}
    for field_name, raw_entry in lineage.items():
        if not isinstance(raw_entry, Mapping):
            continue
        entry = dict(raw_entry)
        operations = _sequence(entry.get("operations"))
        if len(operations) > _MAX_LINEAGE_OPERATIONS:
            retained = [
                item for item in operations if not _is_lineage_truncation_marker(item)
            ]
            # The marker represents all omitted middle history. Reserve one
            # slot for it and keep both the earliest provenance and newest work.
            first_count = (_MAX_LINEAGE_OPERATIONS - 1) // 2
            latest_count = _MAX_LINEAGE_OPERATIONS - first_count - 1
            operations = [
                *retained[:first_count],
                dict(_LINEAGE_TRUNCATION_MARKER),
                *retained[-latest_count:],
            ]
        entry["operations"] = operations
        bounded[str(field_name)] = entry
    return bounded


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
        op = node.get("op")
        if op in {"add", "subtract", "multiply", "divide", "modulo"}:
            numeric = {"integer", "number", "decimal"}
            if op == "add" and left == right == "string":
                return "string", left_null or right_null
            if left in numeric and right in numeric:
                if {left, right} == {"decimal", "number"}:
                    # Python and several backends reject or round this mix;
                    # require an explicit conversion policy before export.
                    pass
                elif op != "divide":
                    return _merge(left, right), left_null or right_null
                # Portable division of two integers produces a fractional
                # value. Decimal operands retain decimal arithmetic.
                else:
                    return (
                        "decimal" if "decimal" in {left, right} else "number",
                        left_null or right_null,
                    )
            if diagnostics is not None:
                diagnostics.append(
                    Diagnostic(
                        "INFER_BACKWARD_UNSUPPORTED",
                        Severity.ERROR,
                        f"Arithmetic operation {op!r} requires compatible numeric operands",
                        phase="inference",
                    )
                )
            return "unknown", True
        if op == "null_safe_eq":
            return "boolean", False
        if op in {
            "eq",
            "not_eq",
            "lt",
            "lte",
            "gt",
            "gte",
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
                logical = _merge_call_results(
                    logical, value, diagnostics, function=callee
                )
            return logical, all(nullable for _, nullable in inferred)
        if callee in {"dtcs:if_null", "if_null"} and len(args) >= 2:
            inferred = [infer_expression(arg, schema, diagnostics) for arg in args[:2]]
            return (
                _merge_call_results(
                    inferred[0][0], inferred[1][0], diagnostics, function=callee
                ),
                inferred[0][1] and inferred[1][1],
            )
        if callee in {"dtcs:null_if", "null_if"} and args:
            logical, nullable = infer_expression(args[0], schema, diagnostics)
            return logical, True if len(args) > 1 else nullable
        if callee in {"dtcs:case_when", "case_when"} and args:
            value_args = args[1:-1:2] + args[-1:]
            inferred = [
                infer_expression(arg, schema, diagnostics) for arg in value_args
            ]
            logical = inferred[0][0]
            for value, _ in inferred[1:]:
                logical = _merge_call_results(
                    logical, value, diagnostics, function=callee
                )
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
            "dtcs:floor": "integer",
            "dtcs:ceil": "integer",
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


def combine_schemas(
    left: NormalizedSchema,
    right: NormalizedSchema,
    action: Any,
    *,
    max_diagnostics: int = 100,
) -> NormalizedSchema:
    """Transfer a two-input join or union without evaluating either source."""
    name = str(action.action)
    params = action.parameters
    diagnostics: list[Diagnostic] = []

    def error(code: str, message: str, field: str | None = None) -> None:
        diagnostics.append(
            Diagnostic(
                code,
                Severity.ERROR,
                message,
                path=(field,) if field else (),
                phase="inference",
            )
        )

    left_by_name = {field.name: field for field in left.fields}
    right_by_name = {field.name: field for field in right.fields}
    output: list[NormalizedField] = []
    lineage: dict[str, dict[str, Any]] = {}
    left_lineage = _initial_lineage(left)
    right_lineage = _initial_lineage(right)

    def add(field: NormalizedField, origin: dict[str, Any]) -> None:
        output.append(field)
        lineage[field.name] = {
            **origin,
            "field": field.name,
            "operations": [*_sequence(origin.get("operations")), {"operation": name}],
            "invertible": False,
        }

    if name == "dtcs:union":
        mode = params.get("mode", "byPosition")
        allow_missing = params.get("allowMissingColumns") is True
        if mode not in {"byPosition", "byName"}:
            error("INFER_BACKWARD_UNSUPPORTED", "Union alignment mode is unsupported")
        if mode == "byPosition":
            if allow_missing or len(left.fields) != len(right.fields):
                error(
                    "INFER_BACKWARD_UNSUPPORTED", "Positional union field counts differ"
                )
            pairs = list(zip(left.fields, right.fields, strict=False))
        else:
            if not allow_missing and set(left_by_name) != set(right_by_name):
                error("INFER_BACKWARD_UNSUPPORTED", "Named union fields differ")
            names = list(dict.fromkeys([*left_by_name, *right_by_name]))
            pairs = [(left_by_name.get(key), right_by_name.get(key)) for key in names]
        for left_field, right_field in pairs:
            field = left_field or right_field
            if field is None:
                continue
            if left_field is not None and right_field is not None:
                logical = _merge(left_field.logical_type, right_field.logical_type)
                if logical == "unknown" or (
                    logical == "string"
                    and left_field.logical_type != right_field.logical_type
                ):
                    error(
                        "INFER_BACKWARD_UNSUPPORTED",
                        f"Union field {field.name!r} has incompatible types",
                        field.name,
                    )
                    logical = "unknown"
                nullable = (
                    left_field.nullable
                    or right_field.nullable
                    or not left_field.required
                    or not right_field.required
                )
                origin = left_lineage[left_field.name]
                other_origin = right_lineage[right_field.name]
                origin = {
                    **origin,
                    "source_fields": list(
                        dict.fromkeys(
                            [
                                *_sequence(origin.get("source_fields")),
                                *_sequence(other_origin.get("source_fields")),
                            ]
                        )
                    ),
                    "qualified_source_fields": list(
                        dict.fromkeys(
                            [
                                *_sequence(origin.get("qualified_source_fields")),
                                *_sequence(other_origin.get("qualified_source_fields")),
                            ]
                        )
                    ),
                }
            else:
                logical = field.logical_type
                nullable = True
                origin = (left_lineage if left_field else right_lineage)[field.name]
            add(
                NormalizedField(
                    field.name, logical, True, nullable, {"inferred": True}
                ),
                origin,
            )
    elif name == "dtcs:join":
        how = str(params.get("type", "inner")).lower()
        if how == "outer":
            how = "full"
        if how not in {"inner", "left", "right", "full", "semi", "anti", "cross"}:
            error("INFER_BACKWARD_UNSUPPORTED", "Join mode is unsupported")
        if params.get("collisionPolicy", "fail") != "fail":
            error("INFER_BACKWARD_UNSUPPORTED", "Join collision policy is unsupported")
        if "predicate" in params:
            error(
                "INFER_BACKWARD_UNSUPPORTED",
                "Join expression predicates are unsupported",
            )
        left_keys = params.get("leftKey", ())
        right_keys = params.get("rightKey", left_keys)
        left_keys = [left_keys] if isinstance(left_keys, str) else _sequence(left_keys)
        right_keys = (
            [right_keys] if isinstance(right_keys, str) else _sequence(right_keys)
        )
        if how != "cross" and (not left_keys or len(left_keys) != len(right_keys)):
            error(
                "INFER_LINEAGE_MISSING", "Join keys are missing or have different arity"
            )
        shared_keys: set[str] = set()
        for left_key, right_key in zip(left_keys, right_keys, strict=False):
            if left_key not in left_by_name or right_key not in right_by_name:
                error("INFER_LINEAGE_MISSING", "Join key references a missing field")
                continue
            if (
                left_by_name[left_key].logical_type
                != right_by_name[right_key].logical_type
            ):
                error("INFER_BACKWARD_UNSUPPORTED", "Join key types differ")
            if left_key == right_key:
                shared_keys.add(left_key)
        collisions = (set(left_by_name) & set(right_by_name)) - shared_keys
        if collisions and how not in {"semi", "anti"}:
            for field_name in sorted(collisions):
                error(
                    "INFER_LINEAGE_COLLISION",
                    f"Join field {field_name!r} collides",
                    field_name,
                )
        for field in left.fields:
            add(
                NormalizedField(
                    field.name,
                    field.logical_type,
                    field.required,
                    field.nullable or not field.required or how in {"right", "full"},
                    {"inferred": True},
                ),
                left_lineage[field.name],
            )
        if how not in {"semi", "anti"}:
            for field in right.fields:
                if field.name in shared_keys:
                    continue
                if field.name in left_by_name:
                    continue
                add(
                    NormalizedField(
                        field.name,
                        field.logical_type,
                        field.required,
                        field.nullable or not field.required or how in {"left", "full"},
                        {"inferred": True},
                    ),
                    right_lineage[field.name],
                )
    else:
        error(
            "INFER_BACKWARD_UNSUPPORTED",
            "Two-input schema transfer requires join or union",
        )
    lineage = _bounded_lineage(lineage)
    metadata: dict[str, Any] = {
        "lineage": lineage,
        "lineage_version": 1,
        "lineage_fingerprint": _lineage_fingerprint(lineage),
        "lineage_graph": {
            "version": 1,
            "fields": {
                field_name: {
                    "source_nodes": _sequence(entry.get("source_nodes"))
                    or ([entry.get("source_node")] if entry.get("source_node") else []),
                    "source_fields": _sequence(entry.get("source_fields")),
                    "qualified_source_fields": _sequence(
                        entry.get("qualified_source_fields")
                    ),
                    "operations": _sequence(entry.get("operations")),
                    "invertible": False,
                }
                for field_name, entry in lineage.items()
            },
        },
    }
    if diagnostics:
        metadata["inference_diagnostics"] = [
            item.to_dict() for item in diagnostics[: max(1, max_diagnostics)]
        ]
    return NormalizedSchema(str(action.action_id), tuple(output), metadata)


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
                            True,
                            nullable,
                            {"inferred": True},
                        )
                    )
            fields = projected
            lineage = next_lineage
        elif name == "dtcs:with_fields":
            # All expressions in one with_fields action read the same input
            # row. Keep their inference view fixed while building the output.
            current = {field.name: field for field in fields}
            input_view = NormalizedSchema(input_schema.identity, tuple(fields))
            next_lineage = dict(lineage)
            assigned_names: set[str] = set()
            for item in params.get("assignments", ()):
                if not isinstance(item, Mapping):
                    continue
                field_name = str(item.get("name"))
                logical, nullable = infer_expression(
                    item.get("expression", {}),
                    input_view,
                    transfer_diagnostics,
                )
                current[field_name] = NormalizedField(
                    field_name, logical, True, nullable, {"inferred": True}
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
        elif name == "dtcs:aggregate":
            input_fields = {field.name: field for field in fields}
            input_view = NormalizedSchema(input_schema.identity, tuple(fields))
            output_fields: list[NormalizedField] = []
            next_lineage: dict[str, dict[str, Any]] = {}

            def add_aggregate_field(
                output_name: str,
                logical_type: str,
                nullable: bool,
                expression: Any,
                *,
                direct: bool = False,
                _fields: list[NormalizedField] = output_fields,
                _next_lineage: dict[str, dict[str, Any]] = next_lineage,
                _input_lineage: dict[str, dict[str, Any]] = lineage,
            ) -> None:
                if output_name in _next_lineage:
                    transfer_diagnostics.append(
                        Diagnostic(
                            "INFER_LINEAGE_COLLISION",
                            Severity.ERROR,
                            f"Aggregation produces duplicate field {output_name!r}",
                            path=(output_name,),
                            phase="inference",
                        )
                    )
                    return
                _fields.append(
                    NormalizedField(
                        output_name,
                        logical_type,
                        True,
                        nullable,
                        {"inferred": True},
                    )
                )
                entry = _lineage_expression(expression, _input_lineage, "aggregate")
                entry["field"] = output_name
                entry["invertible"] = direct and bool(entry.get("invertible"))
                _next_lineage[output_name] = entry

            for key in _sequence(params.get("groupBy")):
                if isinstance(key, str):
                    field = input_fields.get(key)
                    if field is None:
                        transfer_diagnostics.append(
                            Diagnostic(
                                "INFER_LINEAGE_MISSING",
                                Severity.ERROR,
                                f"Group key references missing field {key!r}",
                                path=(key,),
                                phase="inference",
                            )
                        )
                        add_aggregate_field(
                            key, "unknown", True, {"kind": "fieldRef", "target": key}
                        )
                    else:
                        add_aggregate_field(
                            key,
                            field.logical_type,
                            field.nullable,
                            {"kind": "fieldRef", "target": key},
                            direct=True,
                        )
                elif isinstance(key, Mapping):
                    expression = key.get("expression", key)
                    output_name = key.get("name")
                    if not isinstance(output_name, str) or not output_name:
                        transfer_diagnostics.append(
                            Diagnostic(
                                "INFER_BACKWARD_UNSUPPORTED",
                                Severity.ERROR,
                                "Computed group keys require an output name",
                                phase="inference",
                            )
                        )
                        continue
                    logical, nullable = infer_expression(
                        expression, input_view, transfer_diagnostics
                    )
                    add_aggregate_field(output_name, logical, nullable, expression)
            for aggregate in _sequence(params.get("aggregates")):
                if not isinstance(aggregate, Mapping):
                    continue
                expression = aggregate.get("expression")
                function = (
                    expression.get("callee")
                    if isinstance(expression, Mapping)
                    else None
                )
                output_name = aggregate.get("name") or (
                    str(function).split(":")[-1] if function is not None else None
                )
                if not isinstance(output_name, str) or not output_name:
                    transfer_diagnostics.append(
                        Diagnostic(
                            "INFER_BACKWARD_UNSUPPORTED",
                            Severity.ERROR,
                            "Aggregation requires a named expression",
                            phase="inference",
                        )
                    )
                    continue
                args = (
                    _sequence(expression.get("args"))
                    if isinstance(expression, Mapping)
                    else []
                )
                logical, nullable = "unknown", True
                if function in {"dtcs:count", "dtcs:count_all", "dtcs:count_distinct"}:
                    expected_args = 0 if function == "dtcs:count_all" else 1
                    if len(args) == expected_args:
                        if args:
                            infer_expression(args[0], input_view, transfer_diagnostics)
                        logical, nullable = "integer", False
                    else:
                        transfer_diagnostics.append(
                            Diagnostic(
                                "INFER_BACKWARD_UNSUPPORTED",
                                Severity.ERROR,
                                f"Aggregate {function!r} requires {expected_args} argument(s)",
                                path=(output_name,),
                                phase="inference",
                            )
                        )
                elif (
                    function in {"dtcs:sum", "dtcs:average", "dtcs:min", "dtcs:max"}
                    and args
                ):
                    operand_type, _ = infer_expression(
                        args[0], input_view, transfer_diagnostics
                    )
                    if function in {
                        "dtcs:sum",
                        "dtcs:average",
                    } and operand_type not in {"integer", "number", "decimal"}:
                        transfer_diagnostics.append(
                            Diagnostic(
                                "INFER_BACKWARD_UNSUPPORTED",
                                Severity.ERROR,
                                f"Aggregate {function!r} requires a numeric operand",
                                path=(output_name,),
                                phase="inference",
                            )
                        )
                    elif function == "dtcs:average":
                        logical = "decimal" if operand_type == "decimal" else "number"
                    else:
                        logical = operand_type
                else:
                    transfer_diagnostics.append(
                        Diagnostic(
                            "INFER_BACKWARD_UNSUPPORTED",
                            Severity.ERROR,
                            f"Aggregate {function!r} has no qualified type rule",
                            path=(output_name,),
                            phase="inference",
                        )
                    )
                add_aggregate_field(output_name, logical, nullable, expression)
            fields = output_fields
            lineage = next_lineage
        elif name in {
            "dtcs:join",
            "dtcs:union",
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
    lineage = _bounded_lineage(lineage)
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
