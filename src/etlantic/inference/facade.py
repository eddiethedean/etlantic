"""User friendly data first inference facade."""

from __future__ import annotations

import datetime as _dt
import math
import operator
import re
from collections.abc import Callable, Mapping
from decimal import Decimal, DecimalException
from typing import Any

from pydantic import Field, create_model

from etlantic.authoring.definition import (
    ContractDefinition,
    EdgeDefinition,
    FieldSpec,
    ImplementationRef,
    NodeDefinition,
    PipelineDefinition,
    PortDefinitionSpec,
    TransformationDefinition,
)
from etlantic.contracts import Data
from etlantic.diagnostics import Diagnostic, Severity
from etlantic.schema_drift import NormalizedSchema
from etlantic.transform.column import ColumnExpr, coerce_column
from etlantic.transform.dataframe import FrameExpr

from .records import _path_identity, infer_csv, infer_records
from .sources import infer_source
from .targets import (
    _backfill_observation,
    _coerce_value,
    check_write_compatibility,
    infer_records_for_target,
    inspect_target,
)
from .transfer import forward_schema
from .types import InferenceLimits, InferenceResult, OutputProposal, TargetObservation

_PY_TYPES = {
    "boolean": bool,
    "integer": int,
    "number": float,
    "decimal": Decimal,
    "binary": bytes,
    "string": str,
    "date": __import__("datetime").date,
    "datetime": __import__("datetime").datetime,
    "array": list,
    "object": dict,
    "null": Any,
    "unknown": Any,
}


def _model_name(name: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_]", "_", name or "InferredRecord")
    safe = safe.strip("_") or "InferredRecord"
    return safe[:1].upper() + safe[1:] + "Model"


def model_from_schema(
    schema: NormalizedSchema, *, name: str | None = None
) -> type[Any]:
    """Build a Pydantic ``Data`` subclass from a normalized schema."""
    fields: dict[str, Any] = {}
    used_names: set[str] = set()
    for field in schema.fields:
        annotation = _PY_TYPES.get(field.logical_type, Any)
        # Requiredness controls whether the key may be omitted; nullability
        # controls whether an explicit ``None`` is valid.  They are separate
        # contract dimensions.  In particular, an optional non-nullable field
        # must keep its concrete annotation so explicit nulls are rejected.
        if field.nullable:
            annotation = annotation | None
        default: Any = ... if field.required else None
        alias = field.name
        safe = alias if alias.isidentifier() else re.sub(r"\W", "_", alias) or "field"
        if safe in used_names:
            base = safe
            suffix = 2
            while f"{base}_{suffix}" in used_names:
                suffix += 1
            safe = f"{base}_{suffix}"
        used_names.add(safe)
        fields[safe] = (
            annotation,
            default if safe == alias else Field(default, alias=alias),
        )
    return create_model(_model_name(name or schema.identity), __base__=Data, **fields)


def _literal(node: Mapping[str, Any]) -> Any:
    value = node.get("value")
    if not isinstance(value, Mapping) or "type" not in value:
        return (
            value.get("value")
            if isinstance(value, Mapping) and "value" in value
            else value
        )
    logical_type = str(value.get("type", "")).lower()
    raw = value.get("value")
    if raw is None:
        return None
    try:
        if logical_type in {"int", "integer", "long"}:
            return int(raw)
        if logical_type in {"float", "number", "double"}:
            return float(raw)
        if logical_type in {"decimal", "numeric"}:
            return Decimal(str(raw))
        if logical_type in {"bool", "boolean"}:
            if isinstance(raw, str):
                lowered = raw.strip().lower()
                if lowered in {"true", "1", "yes"}:
                    return True
                if lowered in {"false", "0", "no"}:
                    return False
                return None
            return bool(raw)
        if logical_type == "date":
            return _dt.date.fromisoformat(str(raw))
        if logical_type == "datetime":
            return _dt.datetime.fromisoformat(str(raw))
        if logical_type in {"binary", "bytes"}:
            return bytes.fromhex(raw) if isinstance(raw, str) else bytes(raw)
        if logical_type in {"null", "none"}:
            return None
    except (TypeError, ValueError, OverflowError):
        return None
    return raw


def _sql_and(left: Any, right: Any) -> bool | None:
    if left is False or right is False:
        return False
    if left is None or right is None:
        return None
    return bool(left and right)


def _sql_or(left: Any, right: Any) -> bool | None:
    if left is True or right is True:
        return True
    if left is None or right is None:
        return None
    return bool(left or right)


def _eval(
    node: Any,
    row: Mapping[str, Any],
    diagnostics: list[Diagnostic] | None = None,
) -> Any:
    if not isinstance(node, Mapping):
        return node
    kind = node.get("kind")
    if kind == "fieldRef":
        return row.get(str(node.get("target")))
    if kind == "literal":
        return _literal(node)
    if kind == "binary":
        left, right = (
            _eval(node.get("left"), row, diagnostics),
            _eval(node.get("right"), row, diagnostics),
        )
        op = str(node.get("op"))
        if op in {"eq", "not_eq", "lt", "lte", "gt", "gte"} and (
            left is None or right is None
        ):
            return None
        if op == "and":
            return _sql_and(left, right)
        if op == "or":
            return _sql_or(left, right)
        ops: dict[str, Callable[[Any, Any], Any]] = {
            "add": operator.add,
            "subtract": operator.sub,
            "multiply": operator.mul,
            "divide": operator.truediv,
            "modulo": operator.mod,
            "eq": operator.eq,
            "not_eq": operator.ne,
            "lt": operator.lt,
            "lte": operator.le,
            "gt": operator.gt,
            "gte": operator.ge,
            "null_safe_eq": lambda a, b: a == b,
        }
        try:
            return ops[op](left, right)
        except (KeyError, TypeError, ZeroDivisionError, DecimalException):
            return None
    if kind == "unary":
        value = _eval(node.get("expr"), row, diagnostics)
        if node.get("op") == "not":
            return None if value is None else not bool(value)
        if node.get("op") == "negate":
            try:
                return -value
            except TypeError:
                return None
    if kind == "call":
        callee = str(node.get("callee"))
        args = [_eval(item, row, diagnostics) for item in node.get("args", ())]
        if callee in {"dtcs:is_null", "is_null"}:
            return args[0] is None
        if callee in {"dtcs:is_not_null", "is_not_null"}:
            return args[0] is not None
        if callee in {"dtcs:coalesce", "coalesce"}:
            return next((value for value in args if value is not None), None)
        if callee in {"dtcs:if_null", "if_null"} and len(args) >= 2:
            return args[1] if args[0] is None else args[0]
        if callee in {"dtcs:null_if", "null_if"} and len(args) >= 2:
            return None if args[0] == args[1] else args[0]
        if callee in {"dtcs:case_when", "case_when"} and args:
            # ``when`` lowers to condition/value pairs followed by an else.
            for index in range(0, max(0, len(args) - 1), 2):
                if bool(args[index]):
                    return args[index + 1]
            return args[-1]
        if callee in {"dtcs:cast", "dtcs:try_cast"} and args:
            target_value = (
                _literal(node.get("args", ())[1])
                if len(node.get("args", ())) > 1
                and isinstance(node.get("args", ())[1], Mapping)
                else (args[1] if len(args) > 1 else "string")
            )
            target = str(target_value).lower()
            try:
                target_aliases = {
                    "int": "integer",
                    "long": "integer",
                    "float": "number",
                    "double": "number",
                    "numeric": "decimal",
                    "bool": "boolean",
                    "str": "string",
                    "bytes": "binary",
                }
                return _coerce_value(args[0], target_aliases.get(target, target))
            except (TypeError, ValueError, OverflowError, DecimalException):
                if callee == "dtcs:cast" and diagnostics is not None:
                    diagnostics.append(
                        Diagnostic(
                            "INFER_RUNTIME_CONVERSION",
                            Severity.ERROR,
                            f"Preview value cannot be safely cast to {target!r}",
                            phase="inference",
                        )
                    )
                return None
        if callee in {"dtcs:to_string", "to_string"} and args:
            return None if args[0] is None else str(args[0])
        if callee in {"dtcs:to_integer", "to_integer"} and args:
            try:
                return _coerce_value(args[0], "integer")
            except (TypeError, ValueError, OverflowError, DecimalException):
                return None
        if callee in {"dtcs:to_decimal", "to_decimal"} and args:
            try:
                return _coerce_value(args[0], "decimal")
            except (TypeError, ValueError, OverflowError, DecimalException):
                return None
        if callee.endswith("lower") and args:
            if args[0] is None:
                return None
            return str(args[0]).lower()
        if callee.endswith("upper") and args:
            if args[0] is None:
                return None
            return str(args[0]).upper()
        if callee in {"dtcs:concat", "concat"}:
            return (
                None
                if any(value is None for value in args)
                else "".join(str(value) for value in args)
            )
        if callee in {"dtcs:concat_ws", "concat_ws"} and args:
            if args[0] is None:
                return None
            return str(args[0]).join(
                str(value) for value in args[1:] if value is not None
            )
        if callee in {"dtcs:substr", "dtcs:substring"} and args:
            if args[0] is None:
                return None
            start = int(args[1]) if len(args) > 1 else 0
            length = int(args[2]) if len(args) > 2 else None
            return (
                str(args[0])[start:]
                if length is None
                else str(args[0])[start : start + length]
            )
        if callee in {"dtcs:replace", "replace"} and len(args) >= 3:
            return (
                None
                if args[0] is None
                else str(args[0]).replace(str(args[1]), str(args[2]))
            )
        if callee in {"dtcs:regex_extract", "regex_extract"} and len(args) >= 2:
            if args[0] is None or args[1] is None:
                return None
            try:
                match = re.search(str(args[1]), str(args[0]))
                if match is None:
                    return None
                group = int(args[2]) if len(args) > 2 and args[2] is not None else 0
                return match.group(group)
            except (IndexError, re.error, TypeError, ValueError):
                return None
        if callee in {"dtcs:regex_replace", "regex_replace"} and len(args) >= 3:
            if args[0] is None or args[1] is None or args[2] is None:
                return None
            try:
                return re.sub(str(args[1]), str(args[2]), str(args[0]))
            except (re.error, TypeError, ValueError):
                return None
        if (
            callee
            in {
                "dtcs:trim",
                "dtcs:ltrim",
                "dtcs:rtrim",
                "dtcs:normalize_whitespace",
            }
            and args
        ):
            if args[0] is None:
                return None
            value = str(args[0])
            if callee.endswith("ltrim"):
                return value.lstrip()
            if callee.endswith("rtrim"):
                return value.rstrip()
            return (
                " ".join(value.split())
                if callee.endswith("normalize_whitespace")
                else value.strip()
            )
        if callee in {"dtcs:length", "length"} and args:
            return len(args[0]) if args[0] is not None else None
        if callee in {"dtcs:abs", "abs"} and args:
            try:
                return None if args[0] is None else abs(args[0])
            except (TypeError, ValueError, OverflowError):
                return None
        if callee in {"dtcs:round", "round"} and args:
            try:
                return (
                    None
                    if args[0] is None
                    else round(
                        args[0],
                        int(args[1]) if len(args) > 1 and args[1] is not None else 0,
                    )
                )
            except (TypeError, ValueError, OverflowError):
                return None
        if callee in {"dtcs:floor", "floor"} and args:
            try:
                return None if args[0] is None else math.floor(args[0])
            except (TypeError, ValueError, OverflowError):
                return None
        if callee in {"dtcs:ceil", "ceil"} and args:
            try:
                return None if args[0] is None else math.ceil(args[0])
            except (TypeError, ValueError, OverflowError):
                return None
        if callee in {"dtcs:power", "power"} and len(args) >= 2:
            try:
                return (
                    None
                    if args[0] is None or args[1] is None
                    else pow(args[0], args[1])
                )
            except (TypeError, ValueError, OverflowError):
                return None
        if callee in {"dtcs:sqrt", "sqrt"} and args:
            try:
                return None if args[0] is None else math.sqrt(args[0])
            except (TypeError, ValueError, OverflowError):
                return None
        if callee in {"dtcs:least", "least", "dtcs:greatest", "greatest"} and args:
            if any(value is None for value in args):
                return None
            try:
                return min(args) if callee.endswith("least") else max(args)
            except (TypeError, ValueError):
                return None
        if callee in {"dtcs:current_date", "current_date"}:
            return _dt.date.today()
        if callee in {"dtcs:current_timestamp", "current_timestamp"}:
            return _dt.datetime.now(_dt.UTC)
    if diagnostics is not None and kind == "call":
        callee = str(node.get("callee"))
        diagnostics.append(
            Diagnostic(
                "INFER_EVALUATION_UNSUPPORTED",
                Severity.ERROR,
                f"Preview evaluator does not support expression {callee!r}",
                phase="inference",
            )
        )
    return None


class InferredDataset:
    """A bounded, replayable data first relation with an inferred model."""

    def __init__(
        self,
        result: InferenceResult,
        *,
        name: str,
        frame: FrameExpr | None = None,
        root_schema: NormalizedSchema | None = None,
    ):
        self._result = result
        self.name = name
        self._root_schema = root_schema or result.schema
        self._frame = frame or FrameExpr(
            relation_id=name,
            root_input=name,
            schema_fields=tuple(f.name for f in result.schema.fields),
        )

    @property
    def schema(self) -> NormalizedSchema:
        return self._result.schema

    @property
    def model(self) -> type[Any]:
        return model_from_schema(self.schema, name=self.name)

    @property
    def diagnostics(self) -> tuple[Any, ...]:
        return self._result.diagnostics

    @property
    def provenance(self) -> dict[str, Any]:
        return dict(self._result.provenance)

    @property
    def replay(self):
        """Single-use continuation for a bounded one-shot source, if present."""
        return self._result.replay

    @property
    def observation(self):
        """Return the row-free observation suitable for plans and history."""
        return self._result.to_observation()

    @property
    def frame(self) -> FrameExpr:
        return self._frame

    def preview(self, limit: int = 10) -> list[dict[str, Any]]:
        return [dict(row) for row in self._result.rows[: max(0, limit)]]

    def collect(self) -> list[dict[str, Any]]:
        return self.preview(len(self._result.rows))

    def to_records(self) -> list[dict[str, Any]]:
        return self.collect()

    def definition(self) -> PipelineDefinition:
        """Build the normal row-free ETLantic authoring definition."""
        errors = [
            item
            for item in self.diagnostics
            if getattr(
                getattr(item, "severity", None),
                "value",
                getattr(item, "severity", None),
            )
            == Severity.ERROR.value
            or (
                isinstance(item, Mapping)
                and str(item.get("severity", "")).lower() == "error"
            )
        ]
        if errors:
            raise ValueError(
                "inference diagnostics contain errors; durable export is not qualified"
            )
        if self.replay is not None:
            raise ValueError(
                "durable inference definitions require a replayable source binding; "
                "the inspected source is a one-shot bounded stream"
            )
        if any(
            action.action
            in {
                "dtcs:join",
                "dtcs:union",
                "dtcs:intersect",
                "dtcs:except",
            }
            for action in self._frame.actions
        ):
            raise ValueError(
                "durable inference definitions require explicit bindings for every input; "
                "multi-input join/union export is not supported by this facade"
            )

        def make_contract(schema: NormalizedSchema, suffix: str) -> ContractDefinition:
            contract_id = f"contract:{schema.identity}:{suffix}"
            return ContractDefinition(
                identity=contract_id,
                name=f"{self.name}_{suffix}",
                fields=tuple(
                    FieldSpec(
                        name=field.name,
                        type=field.logical_type,
                        nullable=field.nullable,
                        required=field.required,
                    )
                    for field in schema.fields
                ),
                metadata={"etlantic.inference": self.observation.to_dict()},
            )

        # Materialize one contract for each relation state.  A step may alter
        # projection, names, or inferred types; pointing every node at the
        # final contract makes a serialized definition impossible to rebind.
        state_schemas: list[NormalizedSchema] = [self._root_schema]
        for index in range(1, len(self._frame.actions) + 1):
            prefix = FrameExpr(
                relation_id=self._frame.actions[index - 1].action_id,
                root_input=self._frame.root_input,
                actions=self._frame.actions[:index],
                functions=frozenset().union(
                    *(action.functions for action in self._frame.actions[:index])
                ),
                profiles=frozenset().union(
                    *(action.profiles for action in self._frame.actions[:index])
                ),
                schema_fields=(
                    self._frame.schema_fields
                    if index == len(self._frame.actions)
                    else None
                ),
            )
            state_schemas.append(
                forward_schema(
                    prefix,
                    self._root_schema,
                    max_diagnostics=int(
                        self.provenance.get("limits", {}).get("max_diagnostics", 100)
                    ),
                )
            )
        contracts = [
            make_contract(schema, "source" if index == 0 else f"step_{index}")
            for index, schema in enumerate(state_schemas)
        ]
        contract_ids = [contract.identity for contract in contracts]
        transformations = tuple(
            TransformationDefinition(
                identity=action.action_id,
                name=action.action,
                portable_plan={
                    "action": action.action,
                    "action_id": action.action_id,
                    "target": action.target,
                    "parameters": action.parameters,
                    "path": action.path,
                    "functions": sorted(action.functions),
                    "profiles": sorted(action.profiles),
                },
                ports=(
                    PortDefinitionSpec(
                        name="input",
                        direction="input",
                        contract_id=contract_ids[index],
                    ),
                    PortDefinitionSpec(
                        name="output",
                        direction="output",
                        contract_id=contract_ids[index + 1],
                    ),
                ),
                implementation_refs=(
                    ImplementationRef(
                        engine="local",
                        identity=f"portable:{action.action_id}",
                        kind="portable",
                    ),
                ),
                metadata={"etlantic.inference": {"lineage_path": action.path}},
            )
            for index, action in enumerate(self._frame.actions)
        )
        source_name = f"{self.name}_source"
        sink_name = f"{self.name}_output"
        nodes_list = [
            NodeDefinition(
                name=source_name,
                kind="source",
                identity=f"source:{self.schema.identity}",
                contract_id=contract_ids[0],
                outputs=(
                    PortDefinitionSpec(
                        name="output", direction="output", contract_id=contract_ids[0]
                    ),
                ),
                asset=self.name,
                bindings={"source": self.name},
                metadata={"etlantic.inference": self.observation.to_dict()},
            )
        ]
        edges: list[EdgeDefinition] = []
        previous_name = source_name
        for index, action in enumerate(self._frame.actions, start=1):
            step_name = f"{self.name}_step_{index}"
            nodes_list.append(
                NodeDefinition(
                    name=step_name,
                    kind="step",
                    identity=f"step:{action.action_id}",
                    contract_id=contract_ids[index],
                    transformation_id=action.action_id,
                    transformation_name=action.action,
                    inputs=(
                        PortDefinitionSpec(
                            name="input",
                            direction="input",
                            contract_id=contract_ids[index - 1],
                        ),
                    ),
                    outputs=(
                        PortDefinitionSpec(
                            name="output",
                            direction="output",
                            contract_id=contract_ids[index],
                        ),
                    ),
                    metadata={
                        "etlantic.inference": {
                            "action_id": action.action_id,
                            "path": action.path,
                            "parameters": action.parameters,
                        }
                    },
                )
            )
            edges.append(
                EdgeDefinition(
                    producer_node=previous_name,
                    producer_port="output",
                    consumer_node=step_name,
                    consumer_port="input",
                    producer_contract_id=contract_ids[index - 1],
                    consumer_contract_id=contract_ids[index],
                )
            )
            previous_name = step_name
        nodes_list.append(
            NodeDefinition(
                name=sink_name,
                kind="sink",
                identity=f"sink:{self.name}",
                contract_id=contract_ids[-1],
                inputs=(
                    PortDefinitionSpec(
                        name="input", direction="input", contract_id=contract_ids[-1]
                    ),
                ),
                asset=self.name,
                bindings={"target": self.name},
            )
        )
        edges.append(
            EdgeDefinition(
                producer_node=previous_name,
                producer_port="output",
                consumer_node=sink_name,
                consumer_port="input",
                producer_contract_id=contract_ids[-1],
                consumer_contract_id=contract_ids[-1],
            )
        )
        return PipelineDefinition(
            pipeline_id=f"inferred:{self.name}",
            pipeline_name=self.name,
            contracts=tuple(contracts),
            transformations=transformations,
            nodes=tuple(nodes_list),
            edges=tuple(edges),
            provenance={
                "source": "etlantic.inference",
                "observation": self.observation.to_dict(),
            },
            metadata={"etlantic.lineage": self.schema.metadata.get("lineage", {})},
        )

    def plan(self) -> PipelineDefinition:
        """Return the validated authoring definition used by plan consumers."""
        return self.definition()

    def _new(
        self,
        rows: list[dict[str, Any]],
        frame: FrameExpr,
        schema: NormalizedSchema | None = None,
        replay: Any | None = None,
        extra_diagnostics: tuple[Diagnostic, ...] = (),
    ) -> InferredDataset:
        observed = infer_records(
            rows, identity=self._root_schema.identity, retain_rows=True
        )
        final_schema = schema or observed.schema
        transfer_diagnostics = tuple(
            Diagnostic(
                item.get("code", "INFER_BACKWARD_UNSUPPORTED"),
                Severity(item.get("severity", "warning")),
                item.get("message", "Unsupported schema transfer"),
                tuple(item.get("path", ())),
                phase="inference",
            )
            for item in final_schema.metadata.get("inference_diagnostics", ())
            if isinstance(item, Mapping)
        )
        runtime_diagnostics: list[Diagnostic] = []
        for field in final_schema.fields:
            if field.required and any(row.get(field.name) is None for row in rows):
                runtime_diagnostics.append(
                    Diagnostic(
                        "INFER_RUNTIME_EVALUATION",
                        Severity.ERROR,
                        f"Required field {field.name!r} evaluated to null",
                        path=(field.name,),
                        phase="inference",
                    )
                )
        all_diagnostics = (
            self._result.diagnostics
            + observed.diagnostics
            + transfer_diagnostics
            + extra_diagnostics
            + tuple(runtime_diagnostics)
        )
        max_diagnostics = int(
            self.provenance.get("limits", {}).get("max_diagnostics", 100)
            if isinstance(self.provenance.get("limits", {}), Mapping)
            else 100
        )
        bounded_diagnostics: list[Any] = []
        seen_diagnostics: set[tuple[str, tuple[str, ...], str]] = set()
        for diagnostic in all_diagnostics:
            if isinstance(diagnostic, Diagnostic):
                key = (diagnostic.code, tuple(diagnostic.path), diagnostic.message)
            elif isinstance(diagnostic, Mapping):
                key = (
                    str(diagnostic.get("code", "")),
                    tuple(str(item) for item in diagnostic.get("path", ())),
                    str(diagnostic.get("message", "")),
                )
            else:
                key = (str(diagnostic), (), "")
            if key in seen_diagnostics:
                continue
            seen_diagnostics.add(key)
            if len(bounded_diagnostics) >= max(1, max_diagnostics):
                break
            bounded_diagnostics.append(diagnostic)
        evidence_items: list[Any] = []
        seen_evidence: set[tuple[str, str]] = set()
        max_evidence = int(
            self.provenance.get("limits", {}).get("max_fields", 1000)
            if isinstance(self.provenance.get("limits", {}), Mapping)
            else 1000
        )
        for item in (*self._result.evidence, *observed.evidence):
            key = (str(getattr(item, "field", "")), str(getattr(item, "method", "")))
            if key in seen_evidence:
                continue
            seen_evidence.add(key)
            if len(evidence_items) >= max(1, max_evidence):
                break
            evidence_items.append(item)
        result = InferenceResult(
            final_schema,
            tuple(bounded_diagnostics),
            tuple(evidence_items),
            {
                **observed.provenance,
                **self.provenance,
                "preview_rows_observed": observed.provenance.get(
                    "rows_observed", len(rows)
                ),
                "preview_bytes_observed": observed.provenance.get("bytes_observed", 0),
                "sampled": bool(self.provenance.get("sampled", False))
                or bool(observed.provenance.get("sampled", False)),
            },
            observed.rows,
            replay,
            self._result.observed_schema or self._root_schema,
            self._result.target_hypothesis,
            self._result.target_observation,
        )
        return InferredDataset(
            result, name=self.name, frame=frame, root_schema=self._root_schema
        )

    def filter(self, condition: ColumnExpr) -> InferredDataset:
        expr = coerce_column(condition)
        frame = self._frame.filter(expr)
        evaluation_diagnostics: list[Diagnostic] = []
        replay = None
        if self._result.replay is not None:
            replay = self._result.replay.filter(
                lambda row: (
                    isinstance(row, Mapping)
                    and bool(_eval(expr.node, row, evaluation_diagnostics))
                )
            )
        return self._new(
            [
                row
                for row in self._result.rows
                if bool(_eval(expr.node, row, evaluation_diagnostics))
            ],
            frame,
            forward_schema(
                frame,
                self._root_schema,
                max_diagnostics=int(
                    self.provenance.get("limits", {}).get("max_diagnostics", 100)
                ),
            ),
            replay,
            tuple(evaluation_diagnostics),
        )

    def select(self, *columns: Any) -> InferredDataset:
        fields: list[tuple[str, Any]] = []
        evaluation_diagnostics: list[Diagnostic] = []
        for column in columns:
            if isinstance(column, str):
                fields.append((column, {"kind": "fieldRef", "target": column}))
            else:
                expr = coerce_column(column)
                fields.append((expr.alias_name or f"_col_{len(fields)}", expr.node))
        rows = [
            {name: _eval(node, row, evaluation_diagnostics) for name, node in fields}
            for row in self._result.rows
        ]
        frame = self._frame.project(*columns)
        replay = None
        if self._result.replay is not None:
            replay = self._result.replay.map(
                lambda row: (
                    {
                        name: _eval(node, row, evaluation_diagnostics)
                        for name, node in fields
                    }
                    if isinstance(row, Mapping)
                    else row
                )
            )
        return self._new(
            rows,
            frame,
            forward_schema(
                frame,
                self._root_schema,
                max_diagnostics=int(
                    self.provenance.get("limits", {}).get("max_diagnostics", 100)
                ),
            ),
            replay,
            tuple(evaluation_diagnostics),
        )

    project = select

    def withColumn(self, name: str, value: Any) -> InferredDataset:
        expr = coerce_column(value)
        evaluation_diagnostics: list[Diagnostic] = []
        rows = [
            {**row, name: _eval(expr.node, row, evaluation_diagnostics)}
            for row in self._result.rows
        ]
        frame = self._frame.withColumn(name, expr)
        replay = None
        if self._result.replay is not None:
            replay = self._result.replay.map(
                lambda row: (
                    {**row, name: _eval(expr.node, row, evaluation_diagnostics)}
                    if isinstance(row, Mapping)
                    else row
                )
            )
        return self._new(
            rows,
            frame,
            forward_schema(
                frame,
                self._root_schema,
                max_diagnostics=int(
                    self.provenance.get("limits", {}).get("max_diagnostics", 100)
                ),
            ),
            replay,
            tuple(evaluation_diagnostics),
        )

    def drop(self, *columns: str) -> InferredDataset:
        remove = set(columns)
        frame = self._frame.drop(*columns)
        replay = None
        if self._result.replay is not None:
            replay = self._result.replay.map(
                lambda row: (
                    {key: value for key, value in row.items() if key not in remove}
                    if isinstance(row, Mapping)
                    else row
                )
            )
        return self._new(
            [
                {k: v for k, v in row.items() if k not in remove}
                for row in self._result.rows
            ],
            frame,
            forward_schema(
                frame,
                self._root_schema,
                max_diagnostics=int(
                    self.provenance.get("limits", {}).get("max_diagnostics", 100)
                ),
            ),
            replay,
        )

    def join(
        self,
        other: InferredDataset,
        on: Any | None = None,
        how: str = "inner",
        **kwargs: Any,
    ) -> InferredDataset:
        """Reject unbound multi-input authoring explicitly.

        The symbolic ``FrameExpr`` supports joins, but a durable inference
        session must carry a binding and contract for each input.  Until the
        facade receives that second binding, fail before constructing a
        misleading single-source definition.
        """
        raise ValueError(
            "multi-input inference joins require explicit source bindings; use FrameExpr.join"
        )

    def union(self, other: InferredDataset) -> InferredDataset:
        raise ValueError(
            "multi-input inference unions require explicit source bindings; use FrameExpr.union"
        )

    def unionByName(
        self, other: InferredDataset, *, allowMissingColumns: bool = False
    ) -> InferredDataset:
        del allowMissingColumns
        return self.union(other)

    def rename(self, mapping: dict[str, str]) -> InferredDataset:
        frame = self._frame.rename(mapping)
        replay = None
        if self._result.replay is not None:
            replay = self._result.replay.map(
                lambda row: (
                    {mapping.get(key, key): value for key, value in row.items()}
                    if isinstance(row, Mapping)
                    else row
                )
            )
        return self._new(
            [
                {mapping.get(k, k): v for k, v in row.items()}
                for row in self._result.rows
            ],
            frame,
            forward_schema(
                frame,
                self._root_schema,
                max_diagnostics=int(
                    self.provenance.get("limits", {}).get("max_diagnostics", 100)
                ),
            ),
            replay,
        )

    def limit(self, count: int) -> InferredDataset:
        if count < 0:
            raise ValueError("limit count must be non-negative")
        frame = self._frame.limit(count)
        replay = None
        if self._result.replay is not None:
            replay = self._result.replay.limit(count)
        return self._new(
            list(self._result.rows[:count]),
            frame,
            forward_schema(
                frame,
                self._root_schema,
                max_diagnostics=int(
                    self.provenance.get("limits", {}).get("max_diagnostics", 100)
                ),
            ),
            replay,
        )

    def backfill_from(self, target_schema: NormalizedSchema) -> InferredDataset:
        result = _backfill_observation(
            self._result,
            TargetObservation(
                target_schema,
                "present",
                None,
                "provided",
            ),
        )
        return InferredDataset(
            result,
            name=self.name,
            frame=self._frame,
        )

    def check_write(self, target_schema: NormalizedSchema, *, mode: str = "append"):
        return check_write_compatibility(self.schema, target_schema, mode=mode)

    def propose_output(
        self,
        target: Any,
        *,
        identity: str | None = None,
        create_intent: bool = False,
    ) -> OutputProposal:
        """Return an explicit create proposal for an absent target."""
        observation = inspect_target(target, identity=identity or f"target:{self.name}")
        proposal_identity = identity or observation.identity or f"target:{self.name}"
        diagnostics = list(observation.diagnostics)
        if observation.exists == "present":
            diagnostics.append(
                Diagnostic(
                    "INFER_TARGET_CONFLICT",
                    Severity.ERROR,
                    "Output proposal requires an absent target",
                    phase="inference",
                )
            )
        elif observation.exists == "unknown":
            diagnostics.append(
                Diagnostic(
                    "INFER_TARGET_UNKNOWN",
                    Severity.ERROR,
                    "Target existence is unknown; creation cannot be proposed",
                    phase="inference",
                )
            )
        raw_capabilities = observation.metadata.get("capabilities", {})
        declared_capabilities: tuple[str, ...]
        if isinstance(raw_capabilities, Mapping):
            values = raw_capabilities.get(
                "operations", raw_capabilities.get("modes", ())
            )
            declared_capabilities = (
                tuple(str(item) for item in values)
                if isinstance(values, (list, tuple, set))
                else ()
            )
            if (
                raw_capabilities.get("create") is True
                and "create" not in declared_capabilities
            ):
                declared_capabilities = (*declared_capabilities, "create")
        elif isinstance(raw_capabilities, (list, tuple, set)):
            declared_capabilities = tuple(str(item) for item in raw_capabilities)
        else:
            declared_capabilities = ()
        if "create" not in declared_capabilities:
            diagnostics.append(
                Diagnostic(
                    "INFER_TARGET_CREATE_UNSUPPORTED",
                    Severity.ERROR,
                    "Target does not advertise create capability",
                    phase="inference",
                )
            )
        return OutputProposal(
            self.schema,
            proposal_identity,
            create_required=True,
            capabilities=declared_capabilities,
            diagnostics=tuple(diagnostics),
            create_intent=create_intent
            and observation.exists == "absent"
            and "create" in declared_capabilities,
        )


def from_records(
    records: Any,
    *,
    name: str = "records",
    hints: Mapping[str, Any] | None = None,
    limits: InferenceLimits | None = None,
) -> InferredDataset:
    return InferredDataset(
        infer_records(
            records, hints=hints, limits=limits, identity=name, retain_rows=True
        ),
        name=name,
    )


def from_records_for_target(
    records: Any,
    target: Any,
    *,
    name: str = "records",
    hints: Mapping[str, Any] | None = None,
    limits: InferenceLimits | None = None,
    expected_revision: str | None = None,
    revision_reader: Callable[[], Any] | None = None,
) -> InferredDataset:
    """Create a data first handle using an existing target as a type constraint."""
    return InferredDataset(
        infer_records_for_target(
            records,
            target,
            hints=hints,
            limits=limits,
            identity=name,
            retain_rows=True,
            expected_revision=expected_revision,
            revision_reader=revision_reader,
        ),
        name=name,
    )


def read_csv(
    path: str,
    *,
    name: str = "csv",
    options: Mapping[str, Any] | None = None,
    hints: Mapping[str, Any] | None = None,
    limits: InferenceLimits | None = None,
) -> InferredDataset:
    source_identity = _path_identity("csv", path) if name == "csv" else name
    return InferredDataset(
        infer_csv(
            path,
            options=options,
            hints=hints,
            limits=limits,
            identity=source_identity,
            retain_rows=True,
        ),
        name=name,
    )


def from_pandas(
    frame: Any,
    *,
    name: str = "pandas",
    hints: Mapping[str, Any] | None = None,
    limits: InferenceLimits | None = None,
) -> InferredDataset:
    limits = limits or InferenceLimits()
    return InferredDataset(
        infer_source(frame, identity=name, hints=hints, limits=limits), name=name
    )


def from_polars(
    frame: Any,
    *,
    name: str = "polars",
    hints: Mapping[str, Any] | None = None,
    limits: InferenceLimits | None = None,
) -> InferredDataset:
    limits = limits or InferenceLimits()
    return InferredDataset(
        infer_source(frame, identity=name, hints=hints, limits=limits), name=name
    )
