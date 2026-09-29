# pyright: reportPrivateUsage=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnnecessaryIsInstance=false
"""User friendly data first inference facade."""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import re
import time
import weakref
from collections.abc import Callable, Iterable, Mapping
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
from typing import Any, cast

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
from etlantic.schema_drift import NormalizedSchema, revisions_equal
from etlantic.transform.column import ColumnExpr, coerce_column
from etlantic.transform.dataframe import FrameAction, FrameExpr
from etlantic.transform.evaluation import (
    ExpressionEvaluationError,
    evaluate_expression,
)

from .durable import (
    _retain_file_source,
    _safe_file_identity,
    file_binding,
    provider_binding,
    rebind_definition,
    records_binding,
    register_source_factory,
    source_factory,
    target_binding,
    validate_source_binding,
    validate_source_binding_against_definition,
    validate_target_binding,
)
from .records import _estimate_size, _path_identity, infer_csv, infer_records
from .sources import infer_parquet, infer_source
from .targets import (
    _backfill_observation,
    _safe_target_identity,
    _target_field_has_omission_value,
    check_write_compatibility,
    infer_records_for_target,
    inspect_target,
)
from .transfer import combine_schemas, forward_schema
from .types import (
    InferenceLimits,
    InferenceResult,
    OutputProposal,
    TargetObservation,
    WriteCompatibility,
)

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


def _target_cast_action(
    source_schema: NormalizedSchema,
    target_schema: NormalizedSchema,
    root_input: str,
) -> FrameAction | None:
    """Create an explicit executable cast boundary for target backfills."""
    target_fields = {field.name: field for field in target_schema.fields}
    casts = [
        (field.name, target_fields[field.name].logical_type)
        for field in source_schema.fields
        if field.name in target_fields
        and field.logical_type != target_fields[field.name].logical_type
        and target_schema.metadata.get("conditional_casts", {}).get(field.name)
        == target_fields[field.name].logical_type
    ]
    if not casts:
        return None
    assignments = [
        {
            "name": name,
            "expression": {
                "kind": "call",
                "callee": "dtcs:cast",
                "args": [
                    {"kind": "fieldRef", "target": name},
                    {
                        "kind": "literal",
                        "value": {"type": "string", "value": logical_type},
                    },
                ],
            },
        }
        for name, logical_type in casts
    ]
    payload = {"action": "dtcs:with_fields", "assignments": assignments}
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:8]
    return FrameAction(
        action_id=f"{root_input}__target_cast_{digest}",
        action="dtcs:with_fields",
        target=root_input,
        parameters={"assignments": assignments},
        functions=frozenset({"dtcs:cast"}),
        path="target_cast",
    )


class _EvaluationDiagnostics(list[Diagnostic]):
    """Bounded runtime diagnostics that can refresh their owning result."""

    def __init__(self) -> None:
        super().__init__()
        self._on_change: Callable[[], None] | None = None
        self._subscribers: list[Callable[[], None]] = []

    def bind(self, on_change: Callable[[], None]) -> None:
        self._on_change = on_change

    def subscribe(self, on_change: Callable[[], None]) -> None:
        if on_change not in self._subscribers:
            self._subscribers.append(on_change)

    def notify_subscribers(self) -> None:
        for subscriber in tuple(self._subscribers):
            subscriber()

    def append(self, diagnostic: Diagnostic) -> None:
        super().append(diagnostic)
        if self._on_change is not None:
            self._on_change()
        self.notify_subscribers()


def _eval(
    node: Any,
    row: Mapping[str, Any],
    diagnostics: list[Diagnostic] | None = None,
    *,
    max_diagnostics: int = 100,
) -> Any:
    """Evaluate a preview expression through the shared scalar policy."""
    limit = max(1, max_diagnostics)

    def record(error: ExpressionEvaluationError) -> None:
        if diagnostics is None:
            return
        code = {
            "conversion": "INFER_RUNTIME_CONVERSION",
            "unsupported": "INFER_EVALUATION_UNSUPPORTED",
        }.get(error.code, "INFER_RUNTIME_EVALUATION")
        message = str(error)
        key = (code, (), message)
        if len(diagnostics) >= limit or any(
            (item.code, tuple(item.path), item.message) == key for item in diagnostics
        ):
            return
        diagnostics.append(
            Diagnostic(
                code,
                Severity.ERROR,
                message,
                phase="inference",
            )
        )

    return evaluate_expression(node, row, on_error=record)


def _multi_preview(
    left: tuple[dict[str, Any], ...],
    right: tuple[dict[str, Any], ...],
    action: FrameAction,
    *,
    max_rows: int,
    max_materialized_bytes: int | None,
    left_fields: tuple[str, ...],
    right_fields: tuple[str, ...],
    output_fields: tuple[str, ...],
) -> tuple[list[dict[str, Any]], bool]:
    """Evaluate only already retained rows under a strict preview work cap."""
    if max_rows <= 0:
        return [], bool(left or right)
    params = action.parameters
    output: list[dict[str, Any]] = []
    bytes_observed = 0

    def append(row: dict[str, Any]) -> bool:
        nonlocal bytes_observed
        try:
            item_bytes = _estimate_size(
                row,
                max_bytes=(
                    max_materialized_bytes - bytes_observed
                    if max_materialized_bytes is not None
                    else None
                ),
            )
        except Exception:
            return False
        if (
            max_materialized_bytes is not None
            and bytes_observed + item_bytes > max_materialized_bytes
        ):
            return False
        output.append(row)
        bytes_observed += item_bytes
        return True

    if action.action == "dtcs:union":
        if params.get("mode") == "byPosition":
            names = list(output_fields)
            for row in left:
                if len(output) >= max_rows:
                    return output, True
                if not append(dict(row)):
                    return output, True
            for row in right:
                if len(output) >= max_rows:
                    return output, True
                if len(row) == len(names) and not append(
                    dict(zip(names, row.values(), strict=True))
                ):
                    return output, True
            return output, False
        names = list(output_fields)
        for row in (*left, *right):
            if len(output) >= max_rows:
                return output, True
            if not append({name: row.get(name) for name in names}):
                return output, True
        return output, False
    if action.action != "dtcs:join" or len(left) * len(right) > 100_000:
        return [], True
    how = str(params.get("type", "inner")).lower()
    if how == "outer":
        how = "full"
    left_keys = params.get("leftKey", ())
    right_keys = params.get("rightKey", left_keys)
    left_keys = [left_keys] if isinstance(left_keys, str) else list(left_keys)
    right_keys = [right_keys] if isinstance(right_keys, str) else list(right_keys)
    left_names = set(left_fields)
    right_names = set(right_fields)
    matched_right: set[int] = set()

    def matches(left_row: Mapping[str, Any], right_row: Mapping[str, Any]) -> bool:
        if how == "cross":
            return True
        if len(left_keys) != len(right_keys) or not left_keys:
            return False
        for left_key, right_key in zip(left_keys, right_keys, strict=True):
            a, b = left_row.get(str(left_key)), right_row.get(str(right_key))
            if a is None or b is None:
                if not (params.get("nullSafe") is True and a is None and b is None):
                    return False
            elif a != b:
                return False
        return True

    for left_row in left:
        has_match = False
        for index, right_row in enumerate(right):
            if not matches(left_row, right_row):
                continue
            has_match = True
            if how in {"semi", "anti"}:
                break
            matched_right.add(index)
            if len(output) >= max_rows or not append({**left_row, **right_row}):
                return output, True
        if (how == "semi" and has_match) or (how == "anti" and not has_match):
            if len(output) >= max_rows or not append(dict(left_row)):
                return output, True
        elif (
            how in {"left", "full"}
            and not has_match
            and (
                len(output) >= max_rows
                or not append(
                    {**left_row, **{name: None for name in right_names - left_names}}
                )
            )
        ):
            return output, True
    if how in {"right", "full"}:
        for index, right_row in enumerate(right):
            if index not in matched_right and (
                len(output) >= max_rows
                or not append(
                    {**{name: None for name in left_names - right_names}, **right_row}
                )
            ):
                return output, True
    return output, False


class InferredDataset:
    """A bounded, replayable data first relation with an inferred model."""

    def __init__(
        self,
        result: InferenceResult,
        *,
        name: str,
        frame: FrameExpr | None = None,
        root_schema: NormalizedSchema | None = None,
        source_binding: Mapping[str, Any] | None = None,
        target_binding_payload: Mapping[str, Any] | None = None,
        target_revision_reader: Callable[[], Any] | None = None,
        target_write_mode: str = "append",
        source_owner: Any | None = None,
        diagnostic_tracker: _EvaluationDiagnostics | None = None,
        parents: tuple[InferredDataset, InferredDataset] | None = None,
        combine_action: FrameAction | None = None,
    ):
        self._result = result
        self._diagnostic_tracker = diagnostic_tracker
        self._root_schema = root_schema or result.schema
        self._source_binding = dict(source_binding or records_binding(name))
        self._source_owner = source_owner
        self._parents = parents
        self._combine_action = combine_action
        self.name = (
            _safe_file_identity(name)
            if self._source_binding.get("kind") in {"file", "provider", "records"}
            else name
        )
        self._target_revision_reader = target_revision_reader
        observation = result.target_observation
        target_requirements = (
            observation.schema.to_dict()
            if observation is not None and observation.schema is not None
            else None
        )
        self._target_binding = dict(
            target_binding_payload
            or target_binding(
                observation,
                identity=(
                    observation.identity
                    if observation is not None and observation.identity is not None
                    else (
                        "target:unresolved"
                        if observation is not None
                        else f"target:{self.name}"
                    )
                ),
                requirements=target_requirements,
                write_mode=target_write_mode,
            )
        )
        self._frame = frame or FrameExpr(
            relation_id=self.name,
            root_input=self.name,
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

    def definition(
        self, *, _allow_unresolved_source: bool = False
    ) -> PipelineDefinition:
        """Build the normal row-free ETLantic authoring definition."""
        if self._parents is not None:
            if _allow_unresolved_source:
                raise ValueError(
                    "INFER_SOURCE_REBIND: multi-input sources must be bound individually"
                )
            return self._multi_definition()
        source_kind = self._source_binding.get("kind")
        if source_kind == "provider" and not _allow_unresolved_source:
            raise ValueError(
                "INFER_SOURCE_UNSUPPORTED: provider source definitions require "
                "an explicit durable rebind"
            )
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
            error_codes = sorted(
                {str(item.code) for item in errors if isinstance(item, Diagnostic)}
            )
            raise ValueError(
                "inference diagnostics contain errors; durable export is not "
                f"qualified ({', '.join(error_codes) or 'unknown diagnostic'})"
            )
        if (
            self._result.target_observation is not None
            and self._target_binding.get("identity") == "target:unresolved"
        ):
            raise ValueError(
                "INFER_TARGET_IDENTITY_UNKNOWN: durable target bindings require "
                "a stable identity or address"
            )
        self._check_target_revision()
        validate_target_binding(self._target_binding, check_capabilities=False)
        if source_kind == "file" and not _allow_unresolved_source:
            validate_source_binding(self._source_binding)
        factory_key = str(self._source_binding.get("factory_key") or "")
        has_registered_factory = (
            source_kind == "records" and source_factory(factory_key) is not None
        )
        can_reopen_source = (
            source_kind == "file" or has_registered_factory or _allow_unresolved_source
        )
        if (
            self.replay is not None
            and not can_reopen_source
            and bool(self.provenance.get("sampled", False))
        ):
            raise ValueError(
                "durable inference definitions require a reopenable source binding; "
                "the inspected source is a one-shot bounded stream"
            )
        if (
            source_kind == "records"
            and not has_registered_factory
            and not _allow_unresolved_source
        ):
            raise ValueError(
                "INFER_SOURCE_UNRESOLVABLE: register a source factory before "
                "exporting a records definition"
            )
        if self.replay is not None and not can_reopen_source:
            raise ValueError(
                "durable inference definitions require a reopenable source binding; "
                "the inspected source is a one-shot bounded stream"
            )
        if self.provenance.get("sampled") is True and not _allow_unresolved_source:
            raise ValueError(
                "INFER_SOURCE_SCHEMA_UNVERIFIED: a truncated source observation "
                "cannot establish a durable source contract; inspect the full "
                "source or rebind to a reviewed schema"
            )
        # Target backfill is a write-boundary hypothesis.  It must never
        # replace the observed source contract used by the serialized graph.
        source_schema = self._result.observed_schema or self._root_schema
        if any(field.logical_type == "unknown" for field in source_schema.fields):
            raise ValueError(
                "INFER_SOURCE_SCHEMA_UNKNOWN: durable export requires observed "
                "or explicitly hinted source field types"
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
        target_cast = _target_cast_action(
            source_schema, self._root_schema, self._frame.root_input
        )
        definition_actions = list(self._frame.actions)
        if target_cast is not None:
            if definition_actions:
                definition_actions[0] = replace(
                    definition_actions[0], target=target_cast.action_id
                )
            definition_actions.insert(0, target_cast)

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
                metadata={
                    "etlantic.inference": {
                        "observed_schema": source_schema.to_dict(),
                        "source_binding": self._source_binding,
                    }
                },
            )

        # Materialize one contract for each relation state.  A step may alter
        # projection, names, or inferred types; pointing every node at the
        # final contract makes a serialized definition impossible to rebind.
        state_schemas: list[NormalizedSchema] = [source_schema]
        for index in range(1, len(definition_actions) + 1):
            prefix = FrameExpr(
                relation_id=definition_actions[index - 1].action_id,
                root_input=self._frame.root_input,
                actions=tuple(definition_actions[:index]),
                functions=frozenset().union(
                    *(action.functions for action in definition_actions[:index])
                ),
                profiles=frozenset().union(
                    *(action.profiles for action in definition_actions[:index])
                ),
                schema_fields=(
                    self._frame.schema_fields
                    if index == len(definition_actions)
                    else None
                ),
            )
            state_schemas.append(
                forward_schema(
                    prefix,
                    source_schema,
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
        target_observation = self._result.target_observation
        if target_observation is not None:
            target_for_check: Any = target_observation
            if (
                target_observation.exists == "present"
                and target_observation.schema is not None
                and not target_observation.diagnostics
                and target_observation.inspector in {"provided", "normalized"}
                and isinstance(target_observation.metadata, Mapping)
                and isinstance(target_observation.schema.metadata, Mapping)
            ):
                schema_metadata = {
                    **target_observation.schema.metadata,
                    **target_observation.metadata,
                }
                if target_observation.revision is not None:
                    schema_metadata["revision"] = target_observation.revision
                target_for_check = NormalizedSchema(
                    target_observation.schema.identity,
                    target_observation.schema.fields,
                    schema_metadata,
                )
            compatibility = check_write_compatibility(
                state_schemas[-1],
                target_for_check,
                mode=str(self._target_binding.get("write_mode", "append")),
                expected_revision=self._target_binding.get("revision"),
            )
            if not compatibility.compatible or compatibility.casts:
                codes = {item.code for item in compatibility.diagnostics}
                if compatibility.casts:
                    codes.add("INFER_RUNTIME_CONVERSION")
                raise ValueError(
                    "INFER_TARGET_WRITE_UNQUALIFIED: durable export is not "
                    f"compatible with the target ({', '.join(sorted(codes)) or 'unknown'})"
                )
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
            for index, action in enumerate(definition_actions)
        )
        source_name = f"{self.name}_source"
        sink_name = f"{self.name}_output"
        nodes_list = [
            NodeDefinition(
                name=source_name,
                kind="source",
                identity=f"source:{source_schema.identity}",
                contract_id=contract_ids[0],
                outputs=(
                    PortDefinitionSpec(
                        name="output", direction="output", contract_id=contract_ids[0]
                    ),
                ),
                asset=self.name,
                bindings={"source": self._source_binding},
                metadata={
                    "etlantic.inference": {
                        "observed_schema": source_schema.to_dict(),
                        "source_binding": self._source_binding,
                    }
                },
            )
        ]
        edges: list[EdgeDefinition] = []
        previous_name = source_name
        for index, action in enumerate(definition_actions, start=1):
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
                bindings={"target": self._target_binding},
                metadata={
                    "etlantic.inference": {
                        "target_requirements": self._target_binding.get("requirements"),
                        "target_revision": self._target_binding.get("revision"),
                        "write_mode": self._target_binding.get("write_mode"),
                    }
                },
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
        definition = PipelineDefinition(
            pipeline_id=_inferred_pipeline_id(self.name, self._source_binding),
            pipeline_name=self.name,
            contracts=tuple(contracts),
            transformations=transformations,
            nodes=tuple(nodes_list),
            edges=tuple(edges),
            provenance={
                "source": "etlantic.inference",
                "observation": self.observation.to_dict(),
            },
            metadata={
                "etlantic.lineage": self.schema.metadata.get("lineage", {}),
                "etlantic.inference": {
                    "observed_schema": source_schema.to_dict(),
                    "target_binding": self._target_binding,
                },
            },
            runtime_source_leases=(
                (self._source_owner,) if self._source_owner is not None else ()
            ),
        )
        if source_kind in {"file", "records"} and not _allow_unresolved_source:
            validate_source_binding_against_definition(definition, self._source_binding)
        from etlantic.authoring.serialize import pipeline_fingerprint

        fingerprinted_definition = definition.with_fingerprint(
            pipeline_fingerprint(definition)
        )
        # Source validation and compatibility construction can take time; fence
        # the final artifact against a target revision change during that work.
        self._check_target_revision()
        return fingerprinted_definition

    def rebind_source(
        self, source: str, *, format: str | None = None
    ) -> PipelineDefinition:
        """Return a definition explicitly rebound to a local source."""
        if (
            self._source_binding.get("kind") == "file"
            and self.provenance.get("sampled") is True
        ):
            raise ValueError(
                "INFER_SOURCE_SCHEMA_UNVERIFIED: a truncated file observation "
                "cannot be rebound using its unverified schema"
            )
        return rebind_definition(
            self.definition(_allow_unresolved_source=True),
            source=source,
            format=format,
        )

    def _multi_definition(self) -> PipelineDefinition:
        """Serialize both parent graphs and every edge into one definition."""
        parents = self._parents
        combine_action = self._combine_action
        if parents is None or combine_action is None:
            raise ValueError("INFER_SOURCE_REBIND: multi-input graph is incomplete")
        errors = [
            item
            for item in self.diagnostics
            if getattr(getattr(item, "severity", None), "value", None) == "error"
        ]
        if errors:
            codes = ", ".join(sorted({item.code for item in errors}))
            raise ValueError(f"multi-input inference is not qualified ({codes})")
        if self.provenance.get("sampled") is True:
            raise ValueError(
                "INFER_SOURCE_SCHEMA_UNVERIFIED: multi-input sources must be fully inspected"
            )
        left, right = (parent.definition() for parent in parents)
        if left.pipeline_id == right.pipeline_id:
            raise ValueError(
                "INFER_LINEAGE_COLLISION: multi-input source identities collide"
            )

        def parent_graph(
            definition: PipelineDefinition,
        ) -> tuple[list[NodeDefinition], list[EdgeDefinition], str, str]:
            sinks = [node for node in definition.nodes if node.kind == "sink"]
            if len(sinks) != 1 or sinks[0].contract_id is None:
                raise ValueError("INFER_SOURCE_REBIND: parent graph needs one sink")
            terminal = [
                edge for edge in definition.edges if edge.consumer_node == sinks[0].name
            ]
            if len(terminal) != 1:
                raise ValueError(
                    "INFER_SOURCE_REBIND: parent graph has no terminal edge"
                )
            return (
                [node for node in definition.nodes if node.kind != "sink"],
                [
                    edge
                    for edge in definition.edges
                    if edge.consumer_node != sinks[0].name
                ],
                terminal[0].producer_node,
                sinks[0].contract_id,
            )

        left_nodes, left_edges, left_producer, left_contract = parent_graph(left)
        right_nodes, right_edges, right_producer, right_contract = parent_graph(right)
        existing_node_names = [node.name for node in (*left_nodes, *right_nodes)]
        existing_contract_ids = [
            contract.identity for contract in (*left.contracts, *right.contracts)
        ]
        existing_transform_ids = [
            transform.identity
            for transform in (*left.transformations, *right.transformations)
        ]
        if (
            len(set(existing_node_names)) != len(existing_node_names)
            or len(set(existing_contract_ids)) != len(existing_contract_ids)
            or len(set(existing_transform_ids)) != len(existing_transform_ids)
        ):
            raise ValueError("INFER_LINEAGE_COLLISION: parent graph identities collide")

        def contract(schema: NormalizedSchema, suffix: str) -> ContractDefinition:
            return ContractDefinition(
                identity=f"contract:{self.name}:{suffix}",
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
            )

        contracts = [*left.contracts, *right.contracts]
        join_contract = contract(self._root_schema, "combined")
        contracts.append(join_contract)
        join_step_name = f"{self.name}_combine"
        nodes = [*left_nodes, *right_nodes]
        edges = [*left_edges, *right_edges]
        transformations = [*left.transformations, *right.transformations]
        join_plan = {
            "action": combine_action.action,
            "action_id": combine_action.action_id,
            "target": combine_action.target,
            "parameters": combine_action.parameters,
            "path": combine_action.path,
            "functions": sorted(combine_action.functions),
            "profiles": sorted(combine_action.profiles),
        }
        transformations.append(
            TransformationDefinition(
                identity=combine_action.action_id,
                name=combine_action.action,
                portable_plan=join_plan,
                ports=(
                    PortDefinitionSpec("left", "input", left_contract),
                    PortDefinitionSpec("right", "input", right_contract),
                    PortDefinitionSpec("output", "output", join_contract.identity),
                ),
                implementation_refs=(
                    ImplementationRef(
                        engine="local",
                        identity=f"portable:{combine_action.action_id}",
                        kind="portable",
                    ),
                ),
            )
        )
        nodes.append(
            NodeDefinition(
                name=join_step_name,
                kind="step",
                identity=f"step:{combine_action.action_id}",
                contract_id=join_contract.identity,
                transformation_id=combine_action.action_id,
                transformation_name=combine_action.action,
                inputs=(
                    PortDefinitionSpec("left", "input", left_contract),
                    PortDefinitionSpec("right", "input", right_contract),
                ),
                outputs=(
                    PortDefinitionSpec("output", "output", join_contract.identity),
                ),
            )
        )
        edges.extend(
            (
                EdgeDefinition(
                    left_producer,
                    "output",
                    join_step_name,
                    "left",
                    left_contract,
                    left_contract,
                ),
                EdgeDefinition(
                    right_producer,
                    "output",
                    join_step_name,
                    "right",
                    right_contract,
                    right_contract,
                ),
            )
        )
        previous_name = join_step_name
        previous_contract = join_contract.identity
        for index, action in enumerate(self._frame.actions, start=1):
            prefix = FrameExpr(
                relation_id=action.action_id,
                root_input=self._frame.root_input,
                actions=self._frame.actions[:index],
            )
            output_schema = forward_schema(
                prefix, self._root_schema, max_diagnostics=self._max_diagnostics()
            )
            output_contract = contract(output_schema, f"step_{index}")
            contracts.append(output_contract)
            step_name = f"{self.name}_step_{index}"
            transformations.append(
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
                        PortDefinitionSpec("input", "input", previous_contract),
                        PortDefinitionSpec(
                            "output", "output", output_contract.identity
                        ),
                    ),
                    implementation_refs=(
                        ImplementationRef(
                            engine="local",
                            identity=f"portable:{action.action_id}",
                            kind="portable",
                        ),
                    ),
                )
            )
            nodes.append(
                NodeDefinition(
                    name=step_name,
                    kind="step",
                    identity=f"step:{action.action_id}",
                    contract_id=output_contract.identity,
                    transformation_id=action.action_id,
                    transformation_name=action.action,
                    inputs=(PortDefinitionSpec("input", "input", previous_contract),),
                    outputs=(
                        PortDefinitionSpec(
                            "output", "output", output_contract.identity
                        ),
                    ),
                )
            )
            edges.append(
                EdgeDefinition(
                    previous_name,
                    "output",
                    step_name,
                    "input",
                    previous_contract,
                    previous_contract,
                )
            )
            previous_name = step_name
            previous_contract = output_contract.identity
        sink_name = f"{self.name}_output"
        nodes.append(
            NodeDefinition(
                name=sink_name,
                kind="sink",
                identity=f"sink:{self.name}",
                contract_id=previous_contract,
                inputs=(PortDefinitionSpec("input", "input", previous_contract),),
                asset=self.name,
                bindings={"target": self._target_binding},
            )
        )
        edges.append(
            EdgeDefinition(
                previous_name,
                "output",
                sink_name,
                "input",
                previous_contract,
                previous_contract,
            )
        )
        definition = PipelineDefinition(
            pipeline_id=f"inferred:{self.name}",
            pipeline_name=self.name,
            contracts=tuple(contracts),
            transformations=tuple(transformations),
            nodes=tuple(nodes),
            edges=tuple(edges),
            provenance={
                "source": "etlantic.inference",
                "observation": self.observation.to_dict(),
            },
            metadata={"etlantic.lineage": self.schema.metadata.get("lineage", {})},
            runtime_source_leases=(
                *left.runtime_source_leases,
                *right.runtime_source_leases,
            ),
        )
        from etlantic.authoring.serialize import pipeline_fingerprint

        return definition.with_fingerprint(pipeline_fingerprint(definition))

    def _check_target_revision(self) -> None:
        reader = self._target_revision_reader
        expected = self._target_binding.get("revision")
        if reader is None:
            return
        if expected is None:
            raise ValueError(
                "INFER_TARGET_REVISION_UNKNOWN: target revision is missing; "
                "publication cannot be fenced"
            )
        try:
            current = reader()
            if hasattr(current, "__await__"):
                raise TypeError("revision_reader returned an awaitable; use async API")
        except Exception as exc:
            raise ValueError(
                "INFER_TARGET_REVISION_UNKNOWN: target revision could not be "
                "rechecked before publication"
            ) from exc
        if not revisions_equal(current, expected, right_is_fingerprint=True):
            raise ValueError(
                "INFER_TARGET_STALE: target revision changed after schema inspection"
            )

    def plan(self) -> PipelineDefinition:
        """Return the validated authoring definition used by plan consumers."""
        return self.definition()

    def _max_diagnostics(self) -> int:
        limits = self.provenance.get("limits", {})
        if not isinstance(limits, Mapping):
            return 100
        return max(1, int(limits.get("max_diagnostics", 100)))

    def _new(
        self,
        rows: Iterable[dict[str, Any]],
        frame: FrameExpr,
        schema: NormalizedSchema | None = None,
        replay: Any | None = None,
        extra_diagnostics: tuple[Diagnostic, ...] | _EvaluationDiagnostics = (),
    ) -> InferredDataset:
        raw_limits = self.provenance.get("limits")
        limits = (
            InferenceLimits.from_dict(dict(raw_limits))
            if isinstance(raw_limits, Mapping)
            else InferenceLimits()
        )
        observed = infer_records(
            rows,
            identity=self._root_schema.identity,
            limits=limits,
            retain_rows=True,
        )
        preview_rows = observed.rows
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
            if field.required and any(field.name not in row for row in preview_rows):
                runtime_diagnostics.append(
                    Diagnostic(
                        "INFER_RUNTIME_EVALUATION",
                        Severity.ERROR,
                        f"Required field {field.name!r} is missing",
                        path=(field.name,),
                        phase="inference",
                    )
                )
            if not field.nullable and any(
                field.name in row and row[field.name] is None for row in preview_rows
            ):
                runtime_diagnostics.append(
                    Diagnostic(
                        "INFER_RUNTIME_EVALUATION",
                        Severity.ERROR,
                        f"Non-nullable field {field.name!r} evaluated to null",
                        path=(field.name,),
                        phase="inference",
                    )
                )
        static_diagnostics: tuple[Any, ...] = (
            observed.diagnostics + transfer_diagnostics + tuple(runtime_diagnostics)
        )
        max_diagnostics = self._max_diagnostics()

        def bounded_diagnostics(
            primary: tuple[Any, ...], secondary: tuple[Any, ...]
        ) -> tuple[Any, ...]:
            bounded: list[Any] = []
            seen: set[tuple[str, tuple[str, ...], str]] = set()
            for diagnostic in (*primary, *secondary):
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
                if key in seen:
                    continue
                seen.add(key)
                if len(bounded) >= max(1, max_diagnostics):
                    break
                bounded.append(diagnostic)
            return tuple(bounded)

        current_evaluation_diagnostics = tuple(extra_diagnostics)
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
            bounded_diagnostics(
                current_evaluation_diagnostics,
                self._result.diagnostics + static_diagnostics,
            ),
            tuple(evidence_items),
            {
                **observed.provenance,
                **self.provenance,
                "preview_rows_observed": observed.provenance.get(
                    "rows_observed", len(preview_rows)
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

        def refresh_diagnostics() -> None:
            result.diagnostics = bounded_diagnostics(
                tuple(extra_diagnostics),
                self._result.diagnostics + static_diagnostics,
            )

        diagnostic_tracker = (
            extra_diagnostics
            if isinstance(extra_diagnostics, _EvaluationDiagnostics)
            else _EvaluationDiagnostics()
        )

        def refresh_after_parent_change() -> None:
            refresh_diagnostics()
            diagnostic_tracker.notify_subscribers()

        diagnostic_tracker.bind(refresh_diagnostics)
        if self._diagnostic_tracker is not None:
            self._diagnostic_tracker.subscribe(refresh_after_parent_change)
        return InferredDataset(
            result,
            name=self.name,
            frame=frame,
            root_schema=self._root_schema,
            source_binding=self._source_binding,
            target_binding_payload=self._target_binding,
            target_revision_reader=self._target_revision_reader,
            source_owner=self._source_owner,
            diagnostic_tracker=diagnostic_tracker,
            parents=self._parents,
            combine_action=self._combine_action,
        )

    def filter(self, condition: ColumnExpr) -> InferredDataset:
        expr = coerce_column(condition)
        frame = self._frame.filter(expr)
        evaluation_diagnostics = _EvaluationDiagnostics()
        max_diagnostics = self._max_diagnostics()
        replay = None
        if self._result.replay is not None:
            replay = self._result.replay.filter(
                lambda row: (
                    isinstance(row, Mapping)
                    and _eval(
                        expr.node,
                        row,
                        evaluation_diagnostics,
                        max_diagnostics=max_diagnostics,
                    )
                    is True
                )
            )
        return self._new(
            (
                row
                for row in self._result.rows
                if _eval(
                    expr.node,
                    row,
                    evaluation_diagnostics,
                    max_diagnostics=max_diagnostics,
                )
                is True
            ),
            frame,
            forward_schema(
                frame,
                self._root_schema,
                max_diagnostics=int(
                    self.provenance.get("limits", {}).get("max_diagnostics", 100)
                ),
            ),
            replay,
            evaluation_diagnostics,
        )

    def select(self, *columns: Any) -> InferredDataset:
        fields: list[tuple[str, Any]] = []
        evaluation_diagnostics = _EvaluationDiagnostics()
        max_diagnostics = self._max_diagnostics()
        for column in columns:
            if isinstance(column, str):
                fields.append((column, {"kind": "fieldRef", "target": column}))
            else:
                expr = coerce_column(column)
                fields.append((expr.alias_name or f"_col_{len(fields)}", expr.node))
        rows = (
            {
                name: _eval(
                    node,
                    row,
                    evaluation_diagnostics,
                    max_diagnostics=max_diagnostics,
                )
                for name, node in fields
            }
            for row in self._result.rows
        )
        frame = self._frame.project(*columns)
        replay = None
        if self._result.replay is not None:
            replay = self._result.replay.map(
                lambda row: (
                    {
                        name: _eval(
                            node,
                            row,
                            evaluation_diagnostics,
                            max_diagnostics=max_diagnostics,
                        )
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
            evaluation_diagnostics,
        )

    project = select

    def withColumn(self, name: str, value: Any) -> InferredDataset:
        expr = coerce_column(value)
        evaluation_diagnostics = _EvaluationDiagnostics()
        max_diagnostics = self._max_diagnostics()
        rows = (
            {
                **row,
                name: _eval(
                    expr.node,
                    row,
                    evaluation_diagnostics,
                    max_diagnostics=max_diagnostics,
                ),
            }
            for row in self._result.rows
        )
        frame = self._frame.withColumn(name, expr)
        replay = None
        if self._result.replay is not None:
            replay = self._result.replay.map(
                lambda row: (
                    {
                        **row,
                        name: _eval(
                            expr.node,
                            row,
                            evaluation_diagnostics,
                            max_diagnostics=max_diagnostics,
                        ),
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
            evaluation_diagnostics,
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
            (
                {k: v for k, v in row.items() if k not in remove}
                for row in self._result.rows
            ),
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
        """Combine two independently bound inferred sources."""
        if not isinstance(other, InferredDataset):
            raise TypeError("join requires another InferredDataset")
        if self.name == other.name:
            raise ValueError("INFER_LINEAGE_COLLISION: join inputs need distinct names")
        if on is not None and not (
            isinstance(on, str)
            or (
                isinstance(on, (list, tuple))
                and all(isinstance(item, str) for item in on)
            )
        ):
            raise ValueError("INFER_BACKWARD_UNSUPPORTED: join requires named keys")
        combined_frame = self._frame.join(other._frame, on=on, how=how, **kwargs)
        return self._combine(other, combined_frame.actions[-1])

    def union(self, other: InferredDataset) -> InferredDataset:
        if not isinstance(other, InferredDataset):
            raise TypeError("union requires another InferredDataset")
        if self.name == other.name:
            raise ValueError(
                "INFER_LINEAGE_COLLISION: union inputs need distinct names"
            )
        combined_frame = self._frame.union(other._frame)
        return self._combine(other, combined_frame.actions[-1])

    def unionByName(
        self, other: InferredDataset, *, allowMissingColumns: bool = False
    ) -> InferredDataset:
        if not isinstance(other, InferredDataset):
            raise TypeError("unionByName requires another InferredDataset")
        if self.name == other.name:
            raise ValueError(
                "INFER_LINEAGE_COLLISION: union inputs need distinct names"
            )
        combined_frame = self._frame.unionByName(
            other._frame, allowMissingColumns=allowMissingColumns
        )
        return self._combine(other, combined_frame.actions[-1])

    def _combine(self, other: InferredDataset, action: FrameAction) -> InferredDataset:
        schema = combine_schemas(
            self.schema,
            other.schema,
            action,
            max_diagnostics=min(self._max_diagnostics(), other._max_diagnostics()),
        )
        diagnostics = tuple(
            Diagnostic(
                str(item.get("code", "INFER_BACKWARD_UNSUPPORTED")),
                Severity(str(item.get("severity", "error"))),
                str(item.get("message", "Multi-input schema transfer failed")),
                tuple(item.get("path", ())),
                phase="inference",
            )
            for item in schema.metadata.get("inference_diagnostics", ())
            if isinstance(item, Mapping)
        )
        output_name = f"{self.name}_{other.name}_{action.action.split(':')[-1]}"
        left_limits_raw = self.provenance.get("limits")
        right_limits_raw = other.provenance.get("limits")
        left_limits = (
            InferenceLimits.from_dict(dict(left_limits_raw))
            if isinstance(left_limits_raw, Mapping)
            else InferenceLimits()
        )
        right_limits = (
            InferenceLimits.from_dict(dict(right_limits_raw))
            if isinstance(right_limits_raw, Mapping)
            else InferenceLimits()
        )
        max_rows = min(left_limits.max_rows, right_limits.max_rows)
        materialized_limits = [
            limit.max_materialized_bytes
            if limit.max_materialized_bytes is not None
            else limit.max_bytes
            for limit in (left_limits, right_limits)
        ]
        finite_materialized_limits = [
            limit for limit in materialized_limits if limit is not None
        ]
        max_materialized_bytes = (
            min(finite_materialized_limits) if finite_materialized_limits else None
        )
        preview, preview_limited = _multi_preview(
            self._result.rows,
            other._result.rows,
            action,
            max_rows=max_rows,
            max_materialized_bytes=max_materialized_bytes,
            left_fields=tuple(field.name for field in self.schema.fields),
            right_fields=tuple(field.name for field in other.schema.fields),
            output_fields=tuple(field.name for field in schema.fields),
        )
        preview_bytes_observed = sum(_estimate_size(row) for row in preview)
        preview_diagnostics = (
            (
                Diagnostic(
                    "INFER_LIMIT",
                    Severity.WARNING,
                    "Multi-input preview reached a configured inference limit",
                    phase="inference",
                ),
            )
            if preview_limited
            else ()
        )
        combined_limits = replace(
            left_limits,
            max_rows=max_rows,
            max_fields=min(left_limits.max_fields, right_limits.max_fields),
            max_diagnostics=min(
                left_limits.max_diagnostics, right_limits.max_diagnostics
            ),
            max_materialized_bytes=max_materialized_bytes,
        )
        result = InferenceResult(
            schema,
            (*self.diagnostics, *other.diagnostics, *diagnostics, *preview_diagnostics),
            provenance={
                "source": "multi_input",
                "method": action.action,
                "sampled": self.provenance.get("sampled") is True
                or other.provenance.get("sampled") is True
                or preview_limited,
                "limits": combined_limits.to_dict(),
                "preview_rows_observed": len(preview),
                "preview_bytes_observed": preview_bytes_observed,
            },
            rows=preview,
            observed_schema=schema,
        )
        return InferredDataset(
            result,
            name=output_name,
            frame=FrameExpr(
                relation_id=action.action_id,
                root_input=action.action_id,
                schema_fields=tuple(field.name for field in schema.fields),
            ),
            root_schema=schema,
            parents=(self, other),
            combine_action=action,
        )

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
            (
                {mapping.get(k, k): v for k, v in row.items()}
                for row in self._result.rows
            ),
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
        if self._parents is not None:
            raise ValueError(
                "INFER_BACKWARD_UNSUPPORTED: multi-input target backfill requires "
                "an explicit post-combine cast"
            )
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
            # Keep the observed source schema in ``result.observed_schema``
            # while using the target-guided schema as the frame root.  This
            # lets definition() emit an executable cast from the observed
            # source contract into the backfilled contract before applying
            # any subsequent actions.
            root_schema=result.schema,
            source_binding=self._source_binding,
            source_owner=self._source_owner,
            target_binding_payload=target_binding(
                None,
                identity=target_schema.identity,
                requirements=target_schema.to_dict(),
                write_mode="append",
            ),
            target_revision_reader=self._target_revision_reader,
        )

    def check_write(
        self, target_schema: NormalizedSchema, *, mode: str = "append"
    ) -> WriteCompatibility:
        compatibility = check_write_compatibility(self.schema, target_schema, mode=mode)
        if _source_inference_failed(self):
            return _early_write_compatibility(compatibility, self)

        observation = self._result.target_observation
        same_target = (
            observation is not None
            and observation.schema is not None
            and observation.schema.fields == target_schema.fields
        )
        validation_state = self._result.provenance.get("target_validation")
        if same_target and validation_state in {"failed", "stale"}:
            validation_diagnostics = tuple(
                diagnostic
                for diagnostic in self.diagnostics
                if isinstance(diagnostic, Diagnostic)
                and diagnostic.severity == Severity.ERROR
            )
            return replace(
                compatibility,
                compatible=False,
                diagnostics=(*compatibility.diagnostics, *validation_diagnostics),
            )

        if self._result.provenance.get("sampled") is not True:
            return _early_write_compatibility(compatibility, self)

        if same_target and validation_state == "complete":
            return compatibility

        replay = self._result.replay
        if (
            not same_target
            or validation_state != "prefix_only"
            or replay is None
            or not replay.available
        ):
            diagnostic = Diagnostic(
                "INFER_TARGET_UNKNOWN",
                Severity.ERROR,
                "Sampled source cannot enforce all-values constraints for the requested target schema",
                phase="inference",
            )
            return replace(
                compatibility,
                compatible=False,
                diagnostics=(*compatibility.diagnostics, diagnostic),
            )

        validation_obligations: list[dict[str, Any]] = []
        for field in target_schema.fields:
            # The sampled prefix cannot prove that an otherwise absent target
            # field will not appear later, so every declared target type is an
            # all-values replay obligation.
            constraints: list[str] = ["target_type"]
            if field.required and not _target_field_has_omission_value(field):
                constraints.append("required_presence")
            if not field.nullable:
                constraints.append("nullability")
            if constraints:
                validation_obligations.append(
                    {
                        "field": field.name,
                        "validation": "all_values",
                        "constraints": constraints,
                        "on_failure": "error",
                    }
                )

        # Also fence the row's field set: a late field outside the target
        # schema is incompatible even when the target schema is empty.
        validation_obligations.append(
            {
                "field": "*",
                "validation": "all_values",
                "constraints": ["no_unexpected_fields"],
                "on_failure": "error",
            }
        )

        obligations = (*compatibility.obligations, *validation_obligations)
        return replace(compatibility, obligations=obligations)

    def propose_output(
        self,
        target: Any,
        *,
        identity: str | None = None,
        create_intent: bool = False,
    ) -> OutputProposal:
        """Return an explicit create proposal for an absent target."""
        observation = inspect_target(target, identity=identity)
        proposal_identity = (
            _safe_target_identity(identity) if identity else observation.identity
        )
        diagnostics = list(observation.diagnostics)
        if proposal_identity is None and not any(
            getattr(item, "code", None) == "INFER_TARGET_IDENTITY_UNKNOWN"
            for item in diagnostics
        ):
            proposal_identity = "target:unresolved"
            diagnostics.append(
                Diagnostic(
                    "INFER_TARGET_IDENTITY_UNKNOWN",
                    Severity.ERROR,
                    "Output proposal requires a stable target identity",
                    phase="inference",
                )
            )
        elif proposal_identity is None:
            proposal_identity = "target:unresolved"
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
    source_factory: Callable[[], Any] | None = None,
    source_key: str | None = None,
) -> InferredDataset:
    safe_name = _safe_file_identity(name)
    result = infer_records(
        records, hints=hints, limits=limits, identity=safe_name, retain_rows=True
    )
    snapshot = (
        _bounded_materialized_snapshot(records, limits)
        if source_factory is None and source_key is None
        else None
    )
    factory_key = _records_factory_key(
        safe_name, source_key, records, source_factory, snapshot=snapshot
    )
    source_owner = _register_records_source(
        factory_key,
        records,
        source_factory,
        schema=result.schema,
        snapshot=snapshot,
    )
    return InferredDataset(
        result,
        name=safe_name,
        source_binding=records_binding(
            safe_name, factory_key=factory_key, hints=hints, limits=limits
        ),
        source_owner=source_owner,
    )


def from_records_for_target(
    records: Any,
    target: Any,
    *,
    name: str = "records",
    hints: Mapping[str, Any] | None = None,
    limits: InferenceLimits | None = None,
    target_identity: str | None = None,
    expected_revision: str | None = None,
    revision_reader: Callable[[], Any] | None = None,
    source_factory: Callable[[], Any] | None = None,
    source_key: str | None = None,
    write_mode: str = "append",
) -> InferredDataset:
    """Create a data-first handle using a target as a type constraint.

    ``target_identity`` is required for durable export when the target payload
    does not carry a stable identity or address.
    """
    safe_name = _safe_file_identity(name)
    result = infer_records_for_target(
        records,
        target,
        hints=hints,
        limits=limits,
        identity=safe_name,
        target_identity=target_identity,
        retain_rows=True,
        expected_revision=expected_revision,
        revision_reader=revision_reader,
    )
    if revision_reader is None and callable(getattr(target, "inspect_schema", None)):
        # Preserve the provider as a read-only revision source for the final
        # publication fence. A supplied observation or schema is a pinned
        # snapshot and cannot be re-inspected automatically.
        def provider_revision_reader() -> str | None:
            observation = inspect_target(target, identity=target_identity)
            if observation.exists != "present" or observation.diagnostics:
                raise ValueError("target can no longer be inspected")
            return observation.revision

        revision_reader = provider_revision_reader

    snapshot = (
        _bounded_materialized_snapshot(records, limits)
        if source_factory is None and source_key is None
        else None
    )
    factory_key = _records_factory_key(
        safe_name, source_key, records, source_factory, snapshot=snapshot
    )
    source_owner = _register_records_source(
        factory_key,
        records,
        source_factory,
        schema=result.observed_schema or result.schema,
        snapshot=snapshot,
    )
    return InferredDataset(
        result,
        name=safe_name,
        source_binding=records_binding(
            safe_name, factory_key=factory_key, hints=hints, limits=limits
        ),
        source_owner=source_owner,
        target_revision_reader=revision_reader,
        target_write_mode=write_mode,
    )


def _records_factory_key(
    name: str,
    source_key: str | None,
    records: Any,
    source_factory: Callable[[], Any] | None,
    *,
    snapshot: tuple[dict[str, Any], ...] | None = None,
) -> str:
    if source_key is not None:
        if not str(source_key):
            raise ValueError("source_key must not be empty")
        return str(source_key)
    if source_factory is not None:
        raise ValueError(
            "source_key is required when source_factory is supplied so the "
            "durable binding remains deterministic"
        )
    if snapshot is None:
        return f"{name}:stream"
    payload = json.dumps(
        [_canonical_snapshot_value(row) for row in snapshot],
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]
    return f"{name}:snapshot:{digest}"


def _bounded_materialized_snapshot(
    records: Any, limits: InferenceLimits | None
) -> tuple[dict[str, Any], ...] | None:
    """Copy only a fully bounded materialized source for durable replay.

    A materialized source is eligible for an implicit factory only when the
    complete source fits the same row, byte, and time limits used for
    inference.  Otherwise export must use an explicit factory or rebind.
    """
    if isinstance(records, Mapping):
        items: Any = (records,)
    elif isinstance(records, (list, tuple)):
        if limits is not None and len(records) > limits.max_rows:
            return None
        items = records
    else:
        return None
    effective_limits = limits or InferenceLimits()
    if effective_limits.max_rows < len(items):
        return None
    started_at = time.monotonic()
    bytes_observed = 0
    snapshot: list[dict[str, Any]] = []
    try:
        for item in items:
            if effective_limits.timeout_seconds is not None and (
                time.monotonic() - started_at >= effective_limits.timeout_seconds
            ):
                return None
            if not isinstance(item, Mapping):
                return None
            item_bytes = _estimate_size(item)
            if (
                effective_limits.max_bytes is not None
                and bytes_observed + item_bytes > effective_limits.max_bytes
            ):
                return None
            bytes_observed += item_bytes
            snapshot.append(deepcopy(dict(item)))
    except Exception:
        return None
    try:
        for row in snapshot:
            _canonical_snapshot_value(row)
    except (TypeError, ValueError):
        # An arbitrary object cannot be represented safely by a deterministic,
        # collision-resistant row-free binding.  Leave the source unresolved
        # rather than falling back to a string representation.
        return None
    return tuple(snapshot)


def _canonical_snapshot_value(value: Any) -> Any:
    """Encode snapshot values without collapsing distinct Python types."""
    if value is None:
        return {"type": "null", "value": None}
    if isinstance(value, bool):
        return {"type": "bool", "value": value}
    if isinstance(value, int):
        return {"type": "int", "value": str(value)}
    if isinstance(value, float):
        return {"type": "float", "value": value.hex()}
    if isinstance(value, Decimal):
        return {"type": "decimal", "value": str(value)}
    if isinstance(value, str):
        return {"type": "str", "value": value}
    if isinstance(value, _dt.datetime):
        return {"type": "datetime", "value": value.isoformat()}
    if isinstance(value, _dt.date):
        return {"type": "date", "value": value.isoformat()}
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {"type": "bytes", "value": bytes(value).hex()}
    if isinstance(value, Mapping):
        items = [
            [_canonical_snapshot_value(key), _canonical_snapshot_value(item)]
            for key, item in value.items()
        ]
        items.sort(
            key=lambda item: json.dumps(item[0], sort_keys=True, separators=(",", ":"))
        )
        return {"type": "mapping", "items": items}
    if isinstance(value, (list, tuple)):
        return {
            "type": "tuple" if isinstance(value, tuple) else "list",
            "items": [_canonical_snapshot_value(item) for item in value],
        }
    if isinstance(value, (set, frozenset)):
        items = [_canonical_snapshot_value(item) for item in value]
        items.sort(
            key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":"))
        )
        return {
            "type": "frozenset" if isinstance(value, frozenset) else "set",
            "items": items,
        }
    value_type = type(value)
    raise TypeError(
        "materialized source snapshots do not support arbitrary values of "
        f"type {value_type.__module__}.{value_type.__qualname__}"
    )


_DEFAULT_SOURCE_NAMES = frozenset({"records", "csv", "json", "pandas", "polars"})


def _inferred_pipeline_id(name: str, binding: Mapping[str, Any]) -> str:
    """Give default data-first sources a stable identity of their own."""
    if name not in _DEFAULT_SOURCE_NAMES:
        return f"inferred:{name}"
    identity_payload = {
        "kind": binding.get("kind"),
        "identity": binding.get("identity"),
        "factory_key": binding.get("factory_key"),
        "format": binding.get("format"),
        "uri": binding.get("uri"),
        "provider": binding.get("provider"),
    }
    encoded = json.dumps(
        identity_payload, sort_keys=True, separators=(",", ":"), default=str
    )
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:20]
    return f"inferred:{name}:{digest}"


class _SnapshotOwner:
    """Keep an implicit records snapshot alive only with its dataset."""

    __slots__ = ("__weakref__", "snapshot")

    def __init__(self, snapshot: tuple[dict[str, Any], ...]):
        self.snapshot = snapshot


class _SnapshotFactory:
    """Weak-owner factory used for implicit, process-local record snapshots."""

    __slots__ = ("_key", "_owner_ref")

    def __init__(self, key: str, owner: _SnapshotOwner):
        self._key = key
        self._owner_ref = weakref.ref(owner, self._owner_released)

    @property
    def key(self) -> str:
        return self._key

    def owner(self) -> _SnapshotOwner | None:
        return self._owner_ref()

    def _owner_released(self, _owner_ref: weakref.ReferenceType[Any]) -> None:
        from .durable import unregister_source_factory

        unregister_source_factory(self._key, expected_factory=self)

    def __call__(self) -> list[dict[str, Any]]:
        owner = self._owner_ref()
        if owner is None:
            raise ValueError("implicit records source is no longer available")
        try:
            return [deepcopy(row) for row in owner.snapshot]
        except Exception as exc:
            raise ValueError(
                "implicit records snapshot is no longer replayable"
            ) from exc


def _register_records_source(
    factory_key: str,
    records: Any,
    factory: Callable[[], Any] | None,
    *,
    schema: NormalizedSchema,
    snapshot: tuple[dict[str, Any], ...] | None = None,
) -> _SnapshotOwner | None:
    if factory is not None:
        registered_factory = factory
        source_owner: _SnapshotOwner | None = None
        if isinstance(factory, _SnapshotFactory):
            source_owner = factory.owner()
            if source_owner is not None and factory.key != factory_key:
                registered_factory = _SnapshotFactory(factory_key, source_owner)
        register_source_factory(factory_key, registered_factory, schema=schema)
        return source_owner
    if snapshot is None:
        return None
    owner = _SnapshotOwner(snapshot)
    register_source_factory(
        factory_key, _SnapshotFactory(factory_key, owner), schema=schema
    )
    return owner


def read_csv(
    path: str,
    *,
    name: str = "csv",
    options: Mapping[str, Any] | None = None,
    hints: Mapping[str, Any] | None = None,
    limits: InferenceLimits | None = None,
) -> InferredDataset:
    source_identity = (
        _path_identity("csv", path) if name == "csv" else _safe_file_identity(name)
    )
    source_binding = file_binding(
        "csv",
        path,
        identity=source_identity,
        options=options,
        hints=hints,
        limits=limits,
    )
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
        source_binding=source_binding,
        source_owner=_retain_file_source(source_binding["uri"], path),
    )


def read_json(
    path: str,
    *,
    name: str = "json",
    lines: bool = False,
    hints: Mapping[str, Any] | None = None,
    limits: InferenceLimits | None = None,
) -> InferredDataset:
    """Read a JSON array or JSON Lines source with a durable file binding."""
    from .records import infer_json

    source_identity = _path_identity("jsonl" if lines else "json", path)
    source_binding = file_binding(
        "jsonl" if lines else "json",
        path,
        identity=source_identity,
        lines=lines,
        hints=hints,
        limits=limits,
    )
    return InferredDataset(
        infer_json(
            path,
            lines=lines,
            hints=hints,
            limits=limits,
            identity=source_identity,
            retain_rows=True,
        ),
        name=name,
        source_binding=source_binding,
        source_owner=_retain_file_source(source_binding["uri"], path),
    )


def read_parquet(
    path: str,
    *,
    name: str = "parquet",
    limits: InferenceLimits | None = None,
) -> InferredDataset:
    """Inspect a Parquet footer and retain a durable local file binding."""
    source_identity = (
        _path_identity("parquet", path)
        if name == "parquet"
        else _safe_file_identity(name)
    )
    source_binding = file_binding(
        "parquet", path, identity=source_identity, limits=limits
    )
    return InferredDataset(
        infer_parquet(path, identity=source_identity, limits=limits),
        name=name,
        source_binding=source_binding,
        source_owner=_retain_file_source(source_binding["uri"], path),
    )


def from_pandas(
    frame: Any,
    *,
    name: str = "pandas",
    hints: Mapping[str, Any] | None = None,
    limits: InferenceLimits | None = None,
) -> InferredDataset:
    limits = limits or InferenceLimits()
    safe_name = _safe_file_identity(name)
    return InferredDataset(
        infer_source(frame, identity=safe_name, hints=hints, limits=limits),
        name=safe_name,
        source_binding=provider_binding(safe_name, "pandas"),
    )


def from_polars(
    frame: Any,
    *,
    name: str = "polars",
    hints: Mapping[str, Any] | None = None,
    limits: InferenceLimits | None = None,
) -> InferredDataset:
    limits = limits or InferenceLimits()
    safe_name = _safe_file_identity(name)
    return InferredDataset(
        infer_source(frame, identity=safe_name, hints=hints, limits=limits),
        name=safe_name,
        source_binding=provider_binding(safe_name, "polars"),
    )


def _early_write_compatibility(
    compatibility: WriteCompatibility, dataset: InferredDataset
) -> WriteCompatibility:
    source_diagnostics = tuple(
        diagnostic
        for diagnostic in dataset.diagnostics
        if _is_error_diagnostic(diagnostic)
    )
    if not _source_inference_failed(dataset):
        return compatibility
    if not source_diagnostics:
        source_diagnostics = (_source_inference_error(),)
    return replace(
        compatibility,
        compatible=False,
        diagnostics=(*compatibility.diagnostics, *source_diagnostics),
    )


def _source_inference_failed(dataset: InferredDataset) -> bool:
    provenance = dataset.provenance
    return (
        provenance.get("source_validation") == "failed"
        or provenance.get("inspection") == "failed"
        or any(_is_error_diagnostic(item) for item in dataset.diagnostics)
    )


def _is_error_diagnostic(diagnostic: Any) -> bool:
    if isinstance(diagnostic, Diagnostic):
        severity: Any = diagnostic.severity
    elif isinstance(diagnostic, Mapping):
        severity = cast(Mapping[str, Any], diagnostic).get("severity")
    else:
        severity = getattr(diagnostic, "severity", None)
    return getattr(severity, "value", severity) == Severity.ERROR.value


def _source_inference_error() -> Diagnostic:
    return Diagnostic(
        "INFER_SOURCE_INVALID",
        Severity.ERROR,
        "Source inference failed beyond the retained diagnostic limit",
        phase="inference",
    )
