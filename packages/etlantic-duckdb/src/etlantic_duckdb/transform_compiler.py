"""Closed-plan DuckDB portable transform compiler."""

from __future__ import annotations

import hashlib
import inspect
import json
from collections.abc import Mapping, Sequence
from typing import Any

from etlantic.sql.protocol import RelationRef, SqlExecutionContext, TransactionOutcome
from etlantic.transform.capabilities import (
    match_requirements,
    merge_requirements,
    requirements_from_plan,
    three_state_findings,
)
from etlantic.transform.compiler import (
    COMPILER_PROTOCOL,
    CompiledTransform,
    TransformCapabilities,
    TransformCompileContext,
    TransformCompilerInfo,
    TransformExecutionContext,
    TransformOutputBundle,
    TransformPlanningContext,
    TransformSupportFinding,
    TransformSupportReport,
)
from etlantic.transform.protocol import KERNEL_PROFILE_V1, RELATIONAL_PROFILE_V1
from etlantic_duckdb.dialect import DuckDBCompiler
from etlantic_duckdb.frame import DuckDBFrame
from etlantic_duckdb.plugin import DuckDBSqlPlugin

__version__ = "0.48.0"

_ACTIONS = frozenset(
    {
        "dtcs:filter",
        "dtcs:project",
        "dtcs:with_fields",
        "dtcs:limit",
        "dtcs:sort",
        "dtcs:aggregate",
        "dtcs:join",
    }
)
_FUNCTIONS = frozenset(
    {
        "dtcs:lower",
        "dtcs:coalesce",
        "dtcs:sum",
        "dtcs:count_all",
    }
)


def create_transform_compiler() -> DuckDBTransformCompiler:
    return DuckDBTransformCompiler()


class DuckDBTransformCompiler:
    def __init__(self) -> None:
        caps = TransformCapabilities(
            profiles=frozenset({KERNEL_PROFILE_V1, RELATIONAL_PROFILE_V1}),
            actions=_ACTIONS,
            functions=_FUNCTIONS,
            lazy=True,
            eager=False,
        )
        evidence_payload = {
            "capabilities": caps.to_dict(),
            "compiler_source": inspect.getsource(DuckDBTransformCompiler),
            "dialect_source": inspect.getsource(DuckDBCompiler),
            "lowering_sources": {
                name: inspect.getsource(function)
                for name, function in {
                    "input_relation": _input_relation,
                    "apply_action": _apply_action,
                    "expr": _expr,
                    "safe_identifier": _safe,
                }.items()
            },
            "evidence_schema": "etlantic-duckdb-evidence/1",
        }
        evidence = hashlib.sha256(
            json.dumps(evidence_payload, sort_keys=True).encode()
        ).hexdigest()
        self._info = TransformCompilerInfo(
            name="etlantic-duckdb",
            version=__version__,
            engine="duckdb",
            compiler_protocol=COMPILER_PROTOCOL,
            capabilities=caps,
            evidence_fingerprint=evidence,
        )

    @property
    def info(self) -> TransformCompilerInfo:
        return self._info

    def analyze(
        self,
        definition: Mapping[str, Any],
        *,
        context: TransformPlanningContext,
        requirements: Mapping[str, Sequence[str]] | None = None,
    ) -> TransformSupportReport:
        req = merge_requirements(requirements, requirements_from_plan(dict(definition)))
        report = match_requirements(req, self._info.capabilities)
        findings = list(report.findings)
        findings.extend(three_state_findings(definition, self._info.capabilities))
        for index, action in enumerate(definition.get("actions") or ()):
            kind = action.get("kind") or {}
            name = kind.get("action")
            params = kind.get("parameters") or {}
            if name == "dtcs:union":
                findings.append(
                    TransformSupportFinding(
                        code="PMDUCK301",
                        requirement=f"action:{name}",
                        reason="DuckDB phase 0.49 compiler requires explicit relation lowering for joins/unions",
                        expression_path=str(kind.get("id") or f"actions[{index}]"),
                        obligation=str(name),
                        support="unsupported",
                        evidence_fingerprint=self._info.evidence_fingerprint,
                    )
                )
            if (
                name == "dtcs:join"
                and str(params.get("collisionPolicy") or "fail") != "fail"
            ):
                findings.append(
                    TransformSupportFinding(
                        code="PMDUCK302",
                        requirement=f"join.collisionPolicy:{params.get('collisionPolicy')}",
                        reason="DuckDB compiler only supports fail-closed join collisions",
                        expression_path=str(kind.get("id") or f"actions[{index}]"),
                        obligation="join.collisionPolicy",
                        support="unsupported",
                        evidence_fingerprint=self._info.evidence_fingerprint,
                    )
                )
        return TransformSupportReport(
            supported=not findings,
            findings=tuple(findings),
            evidence_fingerprint=self._info.evidence_fingerprint,
        )

    def compile(
        self,
        definition: Mapping[str, Any],
        *,
        context: TransformCompileContext,
        requirements: Mapping[str, Sequence[str]] | None = None,
    ) -> CompiledTransform:
        report = self.analyze(
            definition,
            context=TransformPlanningContext(
                pipeline_id=context.pipeline_id,
                step_name=context.step_name,
                profile_name=context.profile_name,
                engine=context.engine,
            ),
            requirements=requirements,
        )
        if not report.supported:
            raise ValueError(
                "Cannot compile unsupported DuckDB plan: "
                + "; ".join(f"{f.requirement}: {f.reason}" for f in report.findings)
            )
        canonical = json.dumps(definition, sort_keys=True, separators=(",", ":"))
        fingerprint = hashlib.sha256(canonical.encode()).hexdigest()
        return CompiledTransform(
            compiler_name=self.info.name,
            compiler_version=self.info.version,
            engine="duckdb",
            ir_fingerprint=fingerprint,
            output_ports=tuple((definition.get("outputs") or {}).keys()) or ("result",),
            parameter_names=_parameter_names(definition),
            explain={
                "planIdentity": definition.get("planIdentity"),
                "profile": definition.get("profile"),
                "target_ir": "etlantic.sql/1",
                "evidence_fingerprint": self.info.evidence_fingerprint,
            },
            native_plan=dict(definition),
        )

    async def execute(
        self,
        compiled: CompiledTransform,
        *,
        inputs: Mapping[str, Any],
        parameters: Mapping[str, Any],
        context: TransformExecutionContext,
    ) -> TransformOutputBundle:
        plan = compiled.native_plan
        if not isinstance(plan, dict):
            raise ValueError("Compiled DuckDB transform has no closed plan")
        plugin = context.metadata.get("_sql_plugin") or context.metadata.get(
            "_duckdb_plugin"
        )
        if not isinstance(plugin, DuckDBSqlPlugin):
            plugin = DuckDBSqlPlugin()
        session = plugin.connections.session(context.run_id)
        relations: dict[str, RelationRef] = {}
        columns: dict[str, list[str]] = {}
        for name, value in inputs.items():
            relation, names = _input_relation(
                plugin,
                session,
                str(name),
                value,
                step_name=context.step_name,
                attempt=context.attempt,
            )
            relations[str(name)] = relation
            columns[str(name)] = names
        input_ids = list((plan.get("inputs") or {}).keys()) or list(relations)
        if not input_ids:
            raise ValueError("DuckDB portable plan has no inputs")
        current_name = str(input_ids[0])
        if current_name not in relations and len(relations) == 1:
            relations[current_name] = next(iter(relations.values()))
            columns[current_name] = next(iter(columns.values()))
        current = relations[current_name]
        current_columns = columns[current_name]
        for index, action in enumerate(plan.get("actions") or ()):
            kind = action.get("kind") or {}
            target_name = str(kind.get("target") or "")
            if target_name and target_name not in relations:
                raise ValueError(f"missing DuckDB action relation {target_name!r}")
            source = relations[target_name] if target_name else current
            source_columns = columns[target_name] if target_name else current_columns
            current, out_cols = _apply_action(
                plugin,
                session,
                source,
                source_columns,
                action,
                parameters=dict(parameters),
                relations=relations,
                relation_columns=columns,
                relation_prefix=(
                    f"pl_{_safe(session.run_id)}_{_safe(context.step_name)}"
                    f"_{int(context.attempt)}"
                ),
            )
            action_id = str(
                (action.get("kind") or {}).get("id") or action.get("id") or f"a{index}"
            )
            relations[action_id] = current
            columns[action_id] = out_cols
            current_columns = out_cols
        lineage = (plan.get("requirements") or {}).get("dependencies") or []
        last_action = plan.get("actions")[-1] if plan.get("actions") else None
        last_kind = (last_action or {}).get("kind") or {}
        fallback_source = str(
            last_kind.get("id")
            or (last_action or {}).get("id")
            or next(iter(relations), "")
        )
        output_relations: dict[str, RelationRef] = {}
        for output_name in compiled.output_ports:
            source_name = next(
                (
                    str(dep.get("from"))
                    for dep in lineage
                    if dep.get("to") == output_name and dep.get("from") is not None
                ),
                fallback_source,
            )
            relation = relations.get(source_name)
            if relation is None:
                raise ValueError(
                    f"Cannot resolve DuckDB portable output {output_name!r} "
                    f"from relation {source_name!r}"
                )
            output_relations[output_name] = relation

        if context.metadata.get("_return_handles"):
            outputs: dict[str, Any] = output_relations
        else:
            frame_cache: dict[str, _ResultFrame] = {}
            fetch_context = SqlExecutionContext(
                run_id=context.run_id,
                pipeline_id=context.pipeline_id,
                plan_id=context.plan_id,
                step_name=context.step_name,
                engine="duckdb",
                attempt=context.attempt,
            )
            for _output_name, relation in output_relations.items():
                cache_key = relation.qualified_name
                if cache_key not in frame_cache:
                    fetched = plugin.fetch_records(
                        relation, params={}, context=fetch_context
                    )
                    if fetched.outcome is not TransactionOutcome.COMMITTED:
                        detail = "; ".join(
                            str(
                                item.get("message")
                                or item.get("code")
                                or "DuckDB portable fetch failed"
                            )
                            for item in fetched.diagnostics
                        )
                        raise RuntimeError(
                            detail or "DuckDB portable fetch did not commit"
                        )
                    frame_cache[cache_key] = _ResultFrame(fetched.records or [])
            outputs = {
                output_name: frame_cache[relation.qualified_name]
                for output_name, relation in output_relations.items()
            }
        return TransformOutputBundle(
            valid=outputs,
            metrics={
                "engine": "duckdb",
                "lazy": True,
                "evidence_fingerprint": self.info.evidence_fingerprint,
            },
        )


def _input_relation(
    plugin: DuckDBSqlPlugin,
    session: Any,
    name: str,
    value: Any,
    *,
    step_name: str,
    attempt: int,
) -> tuple[RelationRef, list[str]]:
    if isinstance(value, RelationRef):
        info = plugin.inspect_relation(
            value,
            context=SqlExecutionContext(
                run_id=session.run_id,
                pipeline_id="portable",
                plan_id="portable",
                step_name=name,
                engine="duckdb",
            ),
        )
        return value, [str(field["name"]) for field in info.get("fields") or ()]
    rows = (
        value.to_dicts()
        if hasattr(value, "to_dicts")
        else list(value)
        if isinstance(value, list)
        else None
    )
    if rows is None:
        raise TypeError(f"Unsupported DuckDB portable input {type(value)!r}")
    declared_columns = list(getattr(value, "columns", ()) or ())
    if not rows and not declared_columns:
        raise ValueError(
            f"DuckDB portable input {name!r} is empty and has no declared schema"
        )
    relation = RelationRef(
        name=(
            f"pl_in_{_safe(session.run_id)}_{_safe(step_name)}"
            f"_{int(attempt)}_{_safe(name)}"
        )
    )
    plugin.load_records(
        rows,
        target=relation,
        context=SqlExecutionContext(
            run_id=session.run_id,
            pipeline_id="portable",
            plan_id="portable",
            step_name=name,
            engine="duckdb",
        ),
    )
    if not rows:
        session.execute(
            f"CREATE TEMP TABLE {plugin.quote_identifier(relation.name)} ("
            + ", ".join(
                f"{plugin.quote_identifier(column)} VARCHAR"
                for column in declared_columns
            )
            + ")"
        )
    return relation, list(rows[0]) if rows else declared_columns


_ResultFrame = DuckDBFrame


def _apply_action(
    plugin: DuckDBSqlPlugin,
    session: Any,
    current: RelationRef,
    names: list[str],
    action: Mapping[str, Any],
    *,
    parameters: dict[str, Any],
    relations: dict[str, RelationRef],
    relation_columns: dict[str, list[str]],
    relation_prefix: str,
) -> tuple[RelationRef, list[str]]:
    kind = action.get("kind") or {}
    name = kind.get("action")
    params = kind.get("parameters") or {}
    bound_params: list[Any] = []
    source = plugin.quote_identifier(current.name)
    out_names = list(names)
    if name == "dtcs:filter":
        query = (
            f"SELECT * FROM {source} WHERE "
            f"{_expr(params.get('predicate'), parameters, bound_params)}"
        )
    elif name == "dtcs:project":
        fields = params.get("fields") or []
        exprs = []
        out_names = []
        for field in fields:
            if isinstance(field, str):
                exprs.append(plugin.quote_identifier(field))
                out_names.append(field)
            else:
                alias = str(field.get("name"))
                exprs.append(
                    f"{_expr(field.get('expression'), parameters, bound_params)} AS "
                    f"{plugin.quote_identifier(alias)}"
                )
                out_names.append(alias)
        query = f"SELECT {', '.join(exprs)} FROM {source}"
    elif name == "dtcs:with_fields":
        exprs = [plugin.quote_identifier(col) for col in names]
        for assignment in params.get("assignments") or ():
            col = str(assignment["name"])
            exprs = [
                item
                for item in exprs
                if not item.endswith(plugin.quote_identifier(col))
            ]
            exprs.append(
                f"{_expr(assignment.get('expression'), parameters, bound_params)} AS {plugin.quote_identifier(col)}"
            )
            if col not in out_names:
                out_names.append(col)
        query = f"SELECT {', '.join(exprs)} FROM {source}"
    elif name == "dtcs:drop_fields":
        drop = {str(item) for item in params.get("fields") or params.get("names") or ()}
        out_names = [col for col in names if col not in drop]
        query = f"SELECT {', '.join(plugin.quote_identifier(col) for col in out_names)} FROM {source}"
    elif name == "dtcs:rename_fields":
        mapping = {
            str(key): str(value)
            for key, value in dict(params.get("mapping") or {}).items()
        }
        out_names = [mapping.get(col, col) for col in names]
        query = (
            "SELECT "
            + ", ".join(
                f"{plugin.quote_identifier(col)} AS {plugin.quote_identifier(mapping.get(col, col))}"
                for col in names
            )
            + f" FROM {source}"
        )
    elif name == "dtcs:distinct":
        query = f"SELECT DISTINCT * FROM {source}"
    elif name == "dtcs:limit":
        count = int(params.get("count", params.get("n", 0)))
        if count < 0:
            raise ValueError("limit must be non-negative")
        query = f"SELECT * FROM {source} LIMIT {count}"
    elif name == "dtcs:sort":
        items = params.get("by") or params.get("keys") or ()
        order = []
        for item in items:
            col = str(item.get("column") if isinstance(item, dict) else item)
            desc = bool(item.get("descending")) if isinstance(item, dict) else False
            order.append(f"{plugin.quote_identifier(col)} {'DESC' if desc else 'ASC'}")
        query = (
            f"SELECT * FROM {source} ORDER BY {', '.join(order)}"
            if order
            else f"SELECT * FROM {source}"
        )
    elif name == "dtcs:join":
        right_name = str(params.get("right"))
        if right_name not in relations:
            raise ValueError(f"missing DuckDB join relation {right_name!r}")
        right = relations[right_name]
        right_columns = relation_columns.get(right_name, [])
        left_key = params.get("leftKey")
        right_key = params.get("rightKey")
        if not left_key or not right_key:
            raise ValueError("DuckDB joins require leftKey and rightKey")
        join_type = str(params.get("type") or "inner").upper()
        if join_type == "OUTER":
            join_type = "FULL"
        if join_type not in {"INNER", "LEFT", "RIGHT", "FULL"}:
            raise ValueError(f"unsupported DuckDB join type {join_type!r}")
        overlap = set(names) & set(right_columns) - {str(left_key), str(right_key)}
        if overlap and str(params.get("collisionPolicy") or "fail") == "fail":
            raise ValueError(f"join column collision: {sorted(overlap)}")
        left_exprs = [f"l.{plugin.quote_identifier(col)}" for col in names]
        right_exprs = [
            f"r.{plugin.quote_identifier(col)}"
            for col in right_columns
            if col not in names
        ]
        out_names = list(names) + [col for col in right_columns if col not in names]
        query = (
            f"SELECT {', '.join(left_exprs + right_exprs)} FROM {source} AS l "
            f"{join_type} JOIN {plugin.quote_identifier(right.name)} AS r ON "
            f"l.{plugin.quote_identifier(str(left_key))} = "
            f"r.{plugin.quote_identifier(str(right_key))}"
        )
    elif name == "dtcs:aggregate":
        group_by = [str(item) for item in params.get("groupBy") or ()]
        aggregate_items = params.get("aggregates") or params.get("aggregations") or ()
        projections = [plugin.quote_identifier(item) for item in group_by]
        out_names = list(group_by)
        for item in aggregate_items:
            alias = str(item["name"])
            projections.append(
                f"{_expr(item.get('expression'), parameters, bound_params)} AS "
                f"{plugin.quote_identifier(alias)}"
            )
            out_names.append(alias)
        query = f"SELECT {', '.join(projections)} FROM {source}"
        if group_by:
            query += " GROUP BY " + ", ".join(
                plugin.quote_identifier(item) for item in group_by
            )
    else:
        raise ValueError(f"DuckDB action {name!r} is not implemented")
    target = RelationRef(name=f"{relation_prefix}_{_safe(str(kind.get('id') or name))}")
    statement = f"CREATE TEMP TABLE {plugin.quote_identifier(target.name)} AS {query}"
    session.execute(statement, bound_params if bound_params else None)
    return target, out_names


def _expr(node: Any, parameters: dict[str, Any], bindings: list[Any]) -> str:
    if node is None:
        raise ValueError("expression is required")
    if isinstance(node, str):
        return '"' + node.replace('"', '""') + '"'
    if isinstance(node, (int, float, bool)):
        bindings.append(node)
        return "?"
    if isinstance(node, dict):
        kind = node.get("kind") or node.get("type")
        if kind in {"fieldRef", "field"}:
            if node.get("scope") == "parameter":
                name = str(node.get("target") or node.get("name"))
                if name not in parameters:
                    raise ValueError(f"missing DuckDB transform parameter {name!r}")
                bindings.append(parameters[name])
                return "?"
            return (
                '"'
                + str(node.get("target") or node.get("name")).replace('"', '""')
                + '"'
            )
        if kind == "literal":
            value = node.get("value")
            if isinstance(value, dict) and "value" in value:
                value = value["value"]
            bindings.append(value)
            return "?"
        if kind == "call":
            callee = str(node.get("callee", "")).removeprefix("dtcs:").lower()
            args = ", ".join(
                _expr(arg, parameters, bindings) for arg in node.get("args") or ()
            )
            if callee == "count_all":
                return "COUNT(*)"
            if callee == "count_distinct":
                return f"COUNT(DISTINCT {args})"
            names = {
                "sum": "SUM",
                "average": "AVG",
                "min": "MIN",
                "max": "MAX",
                "count": "COUNT",
                "lower": "LOWER",
                "upper": "UPPER",
                "length": "LENGTH",
                "abs": "ABS",
                "round": "ROUND",
                "floor": "FLOOR",
                "ceil": "CEIL",
                "sqrt": "SQRT",
                "coalesce": "COALESCE",
                "if_null": "COALESCE",
                "null_if": "NULLIF",
            }
            function = names.get(callee)
            if function is None:
                raise ValueError(f"unsupported DuckDB function {callee!r}")
            return f"{function}({args})"
        if kind in {"binary", "operator"}:
            op = {
                "eq": "=",
                "neq": "<>",
                "gt": ">",
                "gte": ">=",
                "lt": "<",
                "lte": "<=",
                "and": "AND",
                "or": "OR",
            }.get(str(node.get("op")))
            if op is None:
                raise ValueError(f"unsupported expression operator {node.get('op')!r}")
            return (
                f"({_expr(node.get('left'), parameters, bindings)} {op} "
                f"{_expr(node.get('right'), parameters, bindings)})"
            )
    raise ValueError(f"unsupported DuckDB expression {node!r}")


def _safe(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char == "_" else "_" for char in value)
    prefix = cleaned[:48] if cleaned else "value"
    if prefix[0].isdigit():
        prefix = f"t_{prefix[:46]}"
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def _parameter_names(definition: Mapping[str, Any]) -> tuple[str, ...]:
    names: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            if value.get("kind") == "fieldRef" and value.get("scope") == "parameter":
                names.append(str(value.get("target")))
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(definition)
    return tuple(dict.fromkeys(names))
