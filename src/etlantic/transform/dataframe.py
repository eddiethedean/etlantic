"""Symbolic DataFrame expressions for portable authoring."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from etlantic.transform.column import ColumnExpr, ParameterRef, coerce_column
from etlantic.transform.protocol import (
    PROFILE_COMPLEX_VALUES,
    PROFILE_RELATIONAL_EXTENDED,
    PROFILE_RESHAPE,
    RELATIONAL_PROFILE_V1,
    RELATIONAL_PROFILE_V2,
)


@dataclass(frozen=True, slots=True)
class FrameAction:
    """One dataset Semantic Action in a FrameExpr lineage."""

    action_id: str
    action: str
    target: str
    parameters: dict[str, Any] = field(default_factory=dict)
    functions: frozenset[str] = field(default_factory=frozenset)
    profiles: frozenset[str] = field(default_factory=frozenset)
    path: str = ""


@dataclass(frozen=True, slots=True)
class FrameExpr:
    """Symbolic relation built from an input port or prior actions."""

    relation_id: str
    root_input: str
    actions: tuple[FrameAction, ...] = ()
    functions: frozenset[str] = field(default_factory=frozenset)
    profiles: frozenset[str] = field(default_factory=frozenset)
    schema_fields: tuple[str, ...] | None = None

    def _extend(
        self,
        *,
        action: str,
        parameters: dict[str, Any],
        functions: frozenset[str] = frozenset(),
        profiles: frozenset[str] = frozenset(),
        path: str = "",
        schema_fields: tuple[str, ...] | None = None,
    ) -> FrameExpr:
        action_id = f"a{len(self.actions) + 1}_{action.split(':')[-1]}"
        frame_action = FrameAction(
            action_id=action_id,
            action=action,
            target=self.relation_id,
            parameters=parameters,
            functions=functions,
            profiles=profiles,
            path=path or action,
        )
        return FrameExpr(
            relation_id=action_id,
            root_input=self.root_input,
            actions=(*self.actions, frame_action),
            functions=self.functions | functions,
            profiles=self.profiles | profiles,
            schema_fields=schema_fields
            if schema_fields is not None
            else self.schema_fields,
        )

    def filter(self, condition: ColumnExpr) -> FrameExpr:
        cond = coerce_column(condition)
        return self._extend(
            action="dtcs:filter",
            parameters={"predicate": cond.node},
            functions=cond.functions,
            profiles=cond.profiles,
            path=f"filter:{cond.path}",
        )

    def select(self, *cols: Any) -> FrameExpr:
        return self.project(*cols)

    def project(self, *cols: Any) -> FrameExpr:
        fields: list[Any] = []
        functions: set[str] = set()
        profiles: set[str] = set()
        names: list[str] = []
        for col in cols:
            if isinstance(col, str):
                fields.append(col)
                names.append(col)
                continue
            expr = coerce_column(col)
            functions |= expr.functions
            profiles |= expr.profiles
            if expr.alias_name:
                fields.append({"name": expr.alias_name, "expression": expr.node})
                names.append(expr.alias_name)
            else:
                fields.append({"expression": expr.node})
        return self._extend(
            action="dtcs:project",
            parameters={"fields": fields},
            functions=frozenset(functions),
            profiles=frozenset(profiles),
            path="project",
            schema_fields=tuple(names) if names else None,
        )

    def withColumn(self, name: str, col: Any) -> FrameExpr:
        return self.withColumns({name: col})

    def withColumns(self, cols: dict[str, Any]) -> FrameExpr:
        from etlantic.transform.column import with_column_assignment

        assignments = []
        functions: set[str] = set()
        profiles: set[str] = set()
        for name, value in cols.items():
            expr = coerce_column(value)
            functions |= expr.functions
            profiles |= expr.profiles
            if expr.window is not None:
                profiles |= set(getattr(expr.window, "profiles", ()))
            assignments.append(with_column_assignment(name, expr))
        names = list(self.schema_fields or ())
        for name in cols:
            if name not in names:
                names.append(name)
        return self._extend(
            action="dtcs:with_fields",
            parameters={"assignments": assignments},
            functions=frozenset(functions),
            profiles=frozenset(profiles),
            path="with_fields",
            schema_fields=tuple(names) if names else None,
        )

    def drop(self, *cols: str) -> FrameExpr:
        names = tuple(c for c in (self.schema_fields or ()) if c not in cols) or None
        return self._extend(
            action="dtcs:drop_fields",
            parameters={"fields": list(cols)},
            path="drop_fields",
            schema_fields=names,
        )

    def withColumnRenamed(self, existing: str, new: str) -> FrameExpr:
        return self.rename({existing: new})

    def rename(self, mapping: dict[str, str]) -> FrameExpr:
        names = list(self.schema_fields or ())
        if names:
            names = [mapping.get(n, n) for n in names]
        return self._extend(
            action="dtcs:rename_fields",
            parameters={"mapping": mapping},
            path="rename_fields",
            schema_fields=tuple(names) if names else None,
        )

    def distinct(self) -> FrameExpr:
        return self._extend(
            action="dtcs:distinct",
            parameters={},
            profiles=frozenset({RELATIONAL_PROFILE_V1, RELATIONAL_PROFILE_V2}),
            path="distinct",
        )

    def limit(self, n: int) -> FrameExpr:
        return self._extend(
            action="dtcs:limit",
            parameters={"count": n},
            profiles=frozenset({RELATIONAL_PROFILE_V1, RELATIONAL_PROFILE_V2}),
            path=f"limit:{n}",
        )

    def orderBy(self, *cols: Any) -> FrameExpr:
        return self.sort(*cols)

    def sort(self, *cols: Any) -> FrameExpr:
        keys = []
        functions: set[str] = set()
        profiles: set[str] = {RELATIONAL_PROFILE_V1, RELATIONAL_PROFILE_V2}
        for col in cols:
            expr = coerce_column(col)
            functions |= expr.functions
            profiles |= expr.profiles
            key: dict[str, Any] = {"expression": expr.node}
            if expr.sort_direction:
                key["direction"] = expr.sort_direction
            if expr.nulls:
                key["nulls"] = expr.nulls
            keys.append(key)
        return self._extend(
            action="dtcs:sort",
            parameters={"keys": keys},
            functions=frozenset(functions),
            profiles=frozenset(profiles),
            path="sort",
        )

    def join(
        self,
        other: FrameExpr,
        on: Any | None = None,
        how: str = "inner",
        *,
        null_safe: bool = False,
        collision_policy: str = "fail",
    ) -> FrameExpr:
        parameters: dict[str, Any] = {
            "right": other.relation_id,
            "type": how,
            "nullSafe": null_safe,
            "collisionPolicy": collision_policy,
        }
        functions: set[str] = set()
        if on is not None:
            if isinstance(on, str):
                parameters["leftKey"] = on
                parameters["rightKey"] = on
            elif isinstance(on, (list, tuple)) and all(isinstance(x, str) for x in on):
                parameters["leftKey"] = list(on)
                parameters["rightKey"] = list(on)
            else:
                expr = coerce_column(on)
                parameters["predicate"] = expr.node
                functions |= expr.functions
        # Merge other frame actions into lineage by requiring other.root actions first.
        # Builder flattens both action lists when the joined frame is used.
        merged_actions = (*other.actions, *self.actions)
        action_id = f"a{len(merged_actions) + 1}_join"
        join_action = FrameAction(
            action_id=action_id,
            action="dtcs:join",
            target=self.relation_id,
            parameters=parameters,
            functions=frozenset(functions),
            profiles=frozenset({RELATIONAL_PROFILE_V1, RELATIONAL_PROFILE_V2}),
            path=f"join:{how}",
        )
        return FrameExpr(
            relation_id=action_id,
            root_input=self.root_input,
            actions=(*merged_actions, join_action),
            functions=self.functions | other.functions | frozenset(functions),
            profiles=self.profiles
            | other.profiles
            | frozenset({RELATIONAL_PROFILE_V1, RELATIONAL_PROFILE_V2}),
            schema_fields=self.schema_fields,
        )

    def union(self, other: FrameExpr) -> FrameExpr:
        return self._union(other, mode="byPosition")

    def unionByName(
        self, other: FrameExpr, *, allowMissingColumns: bool = False
    ) -> FrameExpr:
        return self._union(
            other,
            mode="byName",
            allow_missing=allowMissingColumns,
        )

    def _union(
        self, other: FrameExpr, *, mode: str, allow_missing: bool = False
    ) -> FrameExpr:
        merged_actions = (*other.actions, *self.actions)
        action_id = f"a{len(merged_actions) + 1}_union"
        action = FrameAction(
            action_id=action_id,
            action="dtcs:union",
            target=self.relation_id,
            parameters={
                "other": other.relation_id,
                "mode": mode,
                "allowMissingColumns": allow_missing,
            },
            profiles=frozenset({RELATIONAL_PROFILE_V1, RELATIONAL_PROFILE_V2}),
            path=f"union:{mode}",
        )
        return FrameExpr(
            relation_id=action_id,
            root_input=self.root_input,
            actions=(*merged_actions, action),
            functions=self.functions | other.functions,
            profiles=self.profiles
            | other.profiles
            | frozenset({RELATIONAL_PROFILE_V1, RELATIONAL_PROFILE_V2}),
            schema_fields=self.schema_fields,
        )

    def groupBy(self, *cols: Any) -> GroupedData:
        keys = []
        functions: set[str] = set()
        for col in cols:
            if isinstance(col, str):
                keys.append(col)
            else:
                expr = coerce_column(col)
                functions |= expr.functions
                keys.append(
                    expr.node
                    if expr.alias_name is None
                    else {"name": expr.alias_name, "expression": expr.node}
                )
        return GroupedData(
            frame=self,
            group_keys=tuple(keys),
            functions=frozenset(functions),
            profiles=frozenset({RELATIONAL_PROFILE_V1, RELATIONAL_PROFILE_V2}),
        )

    def dropDuplicates(self, *cols: str) -> FrameExpr:
        parameters: dict[str, Any] = {}
        if cols:
            parameters["keys"] = list(cols)
        return self._extend(
            action="dtcs:deduplicate",
            parameters=parameters,
            profiles=frozenset({RELATIONAL_PROFILE_V1, RELATIONAL_PROFILE_V2}),
            path="deduplicate",
        )

    def explode(self, column: str) -> FrameExpr:
        return self._extend(
            action="dtcs:explode",
            parameters={"field": column},
            profiles=frozenset({PROFILE_RESHAPE, PROFILE_COMPLEX_VALUES}),
            path=f"explode:{column}",
        )

    def intersect(self, other: FrameExpr) -> FrameExpr:
        return self._set_op(other, "dtcs:intersect")

    def exceptAll(self, other: FrameExpr) -> FrameExpr:
        return self._set_op(other, "dtcs:except")

    def _set_op(self, other: FrameExpr, action: str) -> FrameExpr:
        merged_actions = (*other.actions, *self.actions)
        action_id = f"a{len(merged_actions) + 1}_{action.split(':')[-1]}"
        frame_action = FrameAction(
            action_id=action_id,
            action=action,
            target=self.relation_id,
            parameters={"other": other.relation_id},
            profiles=frozenset({PROFILE_RELATIONAL_EXTENDED}),
            path=action,
        )
        return FrameExpr(
            relation_id=action_id,
            root_input=self.root_input,
            actions=(*merged_actions, frame_action),
            functions=self.functions | other.functions,
            profiles=self.profiles
            | other.profiles
            | frozenset({PROFILE_RELATIONAL_EXTENDED}),
            schema_fields=self.schema_fields,
        )

    def sample(self, fraction: float, *, seed: int | None = None) -> FrameExpr:
        parameters: dict[str, Any] = {"fraction": fraction}
        if seed is not None:
            parameters["seed"] = seed
        return self._extend(
            action="dtcs:sample",
            parameters=parameters,
            profiles=frozenset({PROFILE_RELATIONAL_EXTENDED}),
            path="sample",
        )


@dataclass(frozen=True, slots=True)
class GroupedData:
    """Result of groupBy awaiting aggregation."""

    frame: FrameExpr
    group_keys: tuple[Any, ...]
    functions: frozenset[str] = field(default_factory=frozenset)
    profiles: frozenset[str] = field(default_factory=frozenset)

    def agg(self, *exprs: Any, **named: Any) -> FrameExpr:
        aggregates = []
        functions: set[str] = set(self.functions)
        profiles: set[str] = set(self.profiles)
        items: list[tuple[str | None, Any]] = [(None, e) for e in exprs]
        items.extend((name, value) for name, value in named.items())
        for name, value in items:
            expr = coerce_column(value)
            functions |= expr.functions
            profiles |= expr.profiles
            entry: dict[str, Any] = {"expression": expr.node}
            alias = name or expr.alias_name
            if alias:
                entry["name"] = alias
            aggregates.append(entry)
        return self.frame._extend(
            action="dtcs:aggregate",
            parameters={"groupBy": list(self.group_keys), "aggregates": aggregates},
            functions=frozenset(functions),
            profiles=frozenset(
                profiles | {RELATIONAL_PROFILE_V1, RELATIONAL_PROFILE_V2}
            ),
            path="aggregate",
        )


def input_frame(
    name: str, *, schema_fields: tuple[str, ...] | None = None
) -> FrameExpr:
    """Create a FrameExpr bound to a transformation input port."""
    return FrameExpr(relation_id=name, root_input=name, schema_fields=schema_fields)


def parameter_ref(name: str) -> ParameterRef:
    """Create a symbolic parameter reference."""
    return ParameterRef(name=name)
