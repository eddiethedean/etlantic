"""SQL portable transform compiler (kernel + relational claims)."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Mapping, Sequence
from typing import Any

from etlantic.sql.helpers import require_safe_identifier
from etlantic.sql.protocol import CteDef, RelationRef, SqlExecutionContext
from etlantic.transform.capabilities import match_requirements
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
    capabilities_fingerprint,
    relational_pushdown_findings,
    requirement_records_from_mapping,
)
from etlantic.transform.portable_baseline import BASELINE_OPERATORS, BASELINE_TYPES
from etlantic.transform.protocol import KERNEL_PROFILE_V1, RELATIONAL_PROFILE_V1
from etlantic_sql.compiler import SqlCompiler
from etlantic_sql.frame import SqlRelationFrame
from etlantic_sql.lowering.actions import (
    CLAIMED_ACTIONS,
    apply_action_to_query,
)

__version__ = "0.50.0"

KERNEL_FUNCTIONS = frozenset(
    {
        "dtcs:lower",
        "dtcs:upper",
        "dtcs:concat",
        "dtcs:concat_ws",
        "dtcs:substr",
        "dtcs:replace",
        "dtcs:length",
        "dtcs:contains",
        "dtcs:starts_with",
        "dtcs:ends_with",
        "dtcs:case_when",
        "dtcs:coalesce",
        "dtcs:if_null",
        "dtcs:null_if",
        "dtcs:is_null",
        "dtcs:abs",
        "dtcs:round",
        "dtcs:floor",
        "dtcs:ceil",
        "dtcs:power",
        "dtcs:sqrt",
        "dtcs:least",
        "dtcs:greatest",
    }
)

RELATIONAL_FUNCTIONS = frozenset(
    {
        "dtcs:sum",
        "dtcs:average",
        "dtcs:min",
        "dtcs:max",
        "dtcs:count",
        "dtcs:count_all",
        "dtcs:count_distinct",
    }
)

CLAIMED_FUNCTIONS = KERNEL_FUNCTIONS | RELATIONAL_FUNCTIONS

_JOIN_TYPES = frozenset(
    {"inner", "left", "right", "full", "semi", "anti", "cross", "outer"}
)
_COLLISION_POLICIES = frozenset({"fail"})
_UNION_MODES = frozenset({"byName", "byPosition"})


def create_transform_compiler() -> SqlTransformCompiler:
    """Entry-point factory for ``etlantic.transform_compilers``."""
    return SqlTransformCompiler()


def _environment_identity(dialect: str | None = None) -> dict[str, str]:
    """Return the SQL runtime identity used for planning evidence."""
    if dialect is None:
        url = os.environ.get("ETLANTIC_SQL_URL", "")
        dialect = url.split(":", 1)[0].split("+", 1)[0] if url else "unknown"
    return {"dialect": dialect or "unknown", "runtime": "sqlalchemy"}


class SqlTransformCompiler:
    """Compile ``dtcs.transform-plan/2`` kernel+relational IR to SQL IR."""

    def __init__(self, dialect: str | None = None) -> None:
        environment = _environment_identity(dialect)
        caps = TransformCapabilities(
            profiles=frozenset({KERNEL_PROFILE_V1, RELATIONAL_PROFILE_V1}),
            actions=CLAIMED_ACTIONS,
            functions=CLAIMED_FUNCTIONS,
            operators=frozenset(BASELINE_OPERATORS),
            types=frozenset(BASELINE_TYPES),
            join_modes=frozenset(
                {"inner", "left", "right", "full", "semi", "anti", "cross"}
            ),
            union_modes=frozenset({"byName", "byPosition"}),
            collision_policies=frozenset({"fail"}),
            # Relational kernels stay as SqlQuery / relation handles (lazy).
            # Callable / row materialization remains available (eager).
            lazy=True,
            eager=True,
        )
        self._info = TransformCompilerInfo(
            name="etlantic-sql",
            version=__version__,
            engine="sql",
            implementation="sql-native/1",
            package="etlantic-sql",
            compiler_protocol=COMPILER_PROTOCOL,
            capabilities=caps,
            evidence_fingerprint=capabilities_fingerprint(
                caps,
                compiler="etlantic-sql",
                implementation="sql-native/1",
                package="etlantic-sql",
                version=__version__,
                engine="sql",
                environment=environment,
            ),
            environment=environment,
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
        from etlantic.transform.capabilities import (
            merge_requirements,
            portable_arithmetic_findings,
            portable_shape_findings,
            requirements_from_plan,
            three_state_findings,
        )

        req = merge_requirements(
            requirements,
            requirements_from_plan(dict(definition), include_extended=True),
        )
        report = match_requirements(req, self._info.capabilities)
        findings = list(report.findings)
        findings.extend(_analyze_modes(definition))
        findings.extend(three_state_findings(definition, self._info.capabilities))
        findings.extend(portable_shape_findings(definition))
        findings.extend(portable_arithmetic_findings(definition))
        # Reject trusted SQL fragments in portable definitions.
        blob = json.dumps(definition, sort_keys=True)
        if "trusted_fragment" in blob or "TrustedSqlFragment" in blob:
            findings.append(
                TransformSupportFinding(
                    code="PMXFORM301",
                    requirement="trusted_sql",
                    reason="Trusted SQL fragments are forbidden in portable definitions",
                )
            )
        return TransformSupportReport(
            supported=not findings,
            findings=tuple(findings),
            evidence_fingerprint=self._info.evidence_fingerprint,
            pushdown=relational_pushdown_findings(
                definition,
                evidence_fingerprint=self._info.evidence_fingerprint,
                physical_effects=("materialization", "lost_fusion"),
                supported_actions=self._info.capabilities.actions,
            ),
            requirements=requirement_records_from_mapping(req, definition=definition),
            requirement_findings=report.requirement_findings,
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
            findings = "; ".join(
                f"{f.requirement}: {f.reason}" for f in report.findings
            )
            raise ValueError(f"Cannot compile unsupported plan: {findings}")
        from etlantic.transform.protocol import PLAN_PROTOCOL

        canonical = json.dumps(definition, sort_keys=True, separators=(",", ":"))
        fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        outputs = tuple((definition.get("outputs") or {}).keys()) or ("result",)
        params = _parameter_names(definition)
        return CompiledTransform(
            compiler_name=self._info.name,
            compiler_version=self._info.version,
            engine="sql",
            ir_fingerprint=fingerprint,
            output_ports=outputs,
            parameter_names=params,
            explain={
                "planIdentity": definition.get("planIdentity") or PLAN_PROTOCOL,
                "profile": definition.get("profile"),
                "actions": [
                    (a.get("kind") or {}).get("action")
                    for a in (definition.get("actions") or [])
                ],
                "target_ir": "etlantic.sql/1",
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
            raise ValueError("Compiled transform missing native plan")
        from etlantic.transform.capabilities import validate_portable_runtime_parameters

        validate_portable_runtime_parameters(plan, parameters)

        dialect, engine = _open_engine(context.metadata)
        compiler = SqlCompiler(
            dialect=dialect,
            supports_merge=str(dialect).startswith("postgresql"),
        )
        frames: dict[str, SqlRelationFrame] = {}
        for name, value in inputs.items():
            frames[name] = _as_frame(value, name=name)
        for input_id in plan.get("inputs") or {}:
            if input_id not in frames and len(inputs) == 1:
                frames[str(input_id)] = _as_frame(
                    next(iter(inputs.values())), name=str(input_id)
                )

        with engine.begin() as conn:
            if dialect == "sqlite":
                driver = conn.connection.driver_connection
                driver.create_function(
                    "ETLANTIC_UNICODE_LOWER",
                    1,
                    lambda value: None if value is None else str(value).lower(),
                    deterministic=True,
                )
                driver.create_function(
                    "ETLANTIC_UNICODE_UPPER",
                    1,
                    lambda value: None if value is None else str(value).upper(),
                    deterministic=True,
                )
            relations: dict[str, RelationRef] = {}
            relation_columns: dict[str, list[str]] = {}
            relation_boolean_columns: dict[str, set[str]] = {}
            native_statement_digests: list[str] = []
            native_explain_digests: list[str] = []
            native_action_digests: dict[str, str] = {}
            for name, frame in frames.items():
                table = _safe_table(name)
                _materialize_table(conn, table, frame.rows, dialect=dialect)
                relations[name] = RelationRef(name=table)
                relation_columns[name] = (
                    list(frame.rows[0].keys()) if frame.rows else list(frame.columns)
                )
                relation_boolean_columns[name] = _infer_boolean_columns(frame.rows)

            # Primary working relation: first declared input or sole frame.
            input_ids = list((plan.get("inputs") or {}).keys()) or list(frames.keys())
            if not input_ids:
                raise ValueError("Portable SQL plan has no inputs")
            current_name = str(input_ids[0])
            current_source = current_name
            current_rel = relations[current_name]
            current_cols = list(relation_columns[current_name])
            ctes: list[CteDef] = []
            logical_nodes: list[str] = []

            for index, action in enumerate(plan.get("actions") or []):
                kind = action.get("kind") or {}
                action_id = str(kind.get("id") or action.get("id") or f"a{index}")
                logical_nodes.append(action_id)
                target = kind.get("target")
                if target is None:
                    target_rel = current_rel
                    target_cols = current_cols
                    target_source = current_source
                else:
                    if target not in relations:
                        raise KeyError(f"Missing action target relation {target!r}")
                    target_rel = relations[target]
                    target_cols = list(relation_columns[target])
                    target_source = str(target)
                query, out_cols = apply_action_to_query(
                    target_rel,
                    target_cols,
                    action,
                    parameters=dict(parameters),
                    relations=relations,
                    relation_columns=relation_columns,
                )
                step_table = _safe_table(f"step_{index}_{action_id}")
                compiled_sql = compiler.compile_query(
                    query,
                    context=SqlExecutionContext(
                        run_id=context.run_id,
                        pipeline_id=context.pipeline_id,
                        plan_id=context.plan_id,
                        step_name=context.step_name,
                        engine="sql",
                    ),
                )
                bound = dict(compiled_sql.metadata.get("_bound_params") or {})
                explain_rows = conn.execute(
                    _text(f"EXPLAIN {compiled_sql.text}"), bound
                ).fetchall()
                explain_digest = hashlib.sha256(
                    repr([tuple(row) for row in explain_rows]).encode("utf-8")
                ).hexdigest()
                create_sql = (
                    f"CREATE TEMP TABLE {compiler.quote(step_table)} AS "
                    f"{compiled_sql.text}"
                )
                conn.execute(_text(create_sql), bound)
                statement_digest = hashlib.sha256(
                    create_sql.encode("utf-8")
                ).hexdigest()
                native_statement_digests.append(statement_digest)
                native_explain_digests.append(explain_digest)
                native_action_digests[action_id] = hashlib.sha256(
                    f"{statement_digest}:{explain_digest}".encode()
                ).hexdigest()
                current_rel = RelationRef(name=step_table)
                current_cols = out_cols
                current_source = action_id
                relations[action_id] = current_rel
                relation_columns[action_id] = out_cols
                relation_boolean_columns[action_id] = _action_boolean_columns(
                    kind,
                    inherited=relation_boolean_columns.get(target_source, set()),
                    relation_boolean_columns=relation_boolean_columns,
                    output_columns=out_cols,
                )
                ctes.append(CteDef(name=step_table, query=query))

            valid: dict[str, SqlRelationFrame] = {}
            lineage = (plan.get("requirements") or {}).get("dependencies") or []
            for out_name in compiled.output_ports:
                source = None
                for dep in lineage:
                    if dep.get("to") == out_name:
                        source = dep.get("from")
                        break
                if source is None:
                    actions = plan.get("actions") or []
                    if actions:
                        last = actions[-1].get("kind") or {}
                        source = last.get("id") or actions[-1].get("id")
                if source is None or source not in relations:
                    raise KeyError(f"Cannot resolve output {out_name!r}")
                result_sql = (
                    f"SELECT * FROM "
                    f"{compiler.quote(require_safe_identifier(relations[source].name))}"
                )
                result = conn.execute(_text(result_sql))
                boolean_columns = relation_boolean_columns.get(str(source), set())
                rows = [
                    {
                        key: bool(value)
                        if key in boolean_columns and value is not None
                        else value
                        for key, value in row._mapping.items()
                    }
                    for row in result
                ]
                valid[out_name] = SqlRelationFrame(rows=rows, name=out_name)

        return TransformOutputBundle(
            valid=valid,
            metrics={
                "fused_steps": len(ctes),
                "logical_nodes": logical_nodes,
                "dialect": dialect,
                "native_statement_digests": native_statement_digests,
                "native_explain_digests": native_explain_digests,
                "native_action_digests": native_action_digests,
                "fallback_events": [],
            },
        )


def _text(sql: str) -> Any:
    from sqlalchemy import text

    return text(sql)


def _open_engine(metadata: Mapping[str, Any]) -> tuple[str, Any]:
    from sqlalchemy import create_engine

    if "sqlalchemy_engine" in metadata:
        engine = metadata["sqlalchemy_engine"]
        dialect = str(metadata.get("sql_dialect") or engine.dialect.name)
        return dialect, engine
    url = (
        metadata.get("database_url")
        or os.environ.get("ETLANTIC_SQL_URL")
        or os.environ.get("DATABASE_URL")
    )
    if url:
        engine = create_engine(str(url))
        return engine.dialect.name, engine
    # Conformance / local default: in-memory SQLite (PostgreSQL via env for gate).
    engine = create_engine("sqlite+pysqlite:///:memory:")
    return "sqlite", engine


def _as_frame(value: Any, *, name: str) -> SqlRelationFrame:
    if isinstance(value, SqlRelationFrame):
        if not value.name:
            value.name = name
        return value
    if isinstance(value, list):
        return SqlRelationFrame(
            rows=[
                item.model_dump()
                if hasattr(item, "model_dump")
                else dict(item)
                if isinstance(item, Mapping)
                else item
                for item in value
            ],
            name=name,
        )
    if hasattr(value, "to_dicts"):
        return SqlRelationFrame(rows=list(value.to_dicts()), name=name)
    raise TypeError(f"Unsupported SQL input frame type {type(value)!r}")


def _safe_table(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", str(name))
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"t_{cleaned}"
    return require_safe_identifier(cleaned)


def _infer_boolean_columns(rows: list[dict[str, Any]]) -> set[str]:
    if not rows:
        return set()
    return {
        name
        for name in rows[0]
        if (values := [row.get(name) for row in rows if row.get(name) is not None])
        and all(isinstance(value, bool) for value in values)
    }


def _expression_is_boolean(node: Any) -> bool:
    if not isinstance(node, Mapping):
        return isinstance(node, bool)
    kind = node.get("kind")
    if kind == "literal":
        value = node.get("value")
        return isinstance(value, Mapping) and value.get("type") == "boolean"
    if kind == "binary":
        return str(node.get("op")) in {
            "eq",
            "neq",
            "not_eq",
            "lt",
            "lte",
            "gt",
            "gte",
            "and",
            "or",
            "null_safe_eq",
        }
    if kind == "unary":
        return node.get("op") == "not"
    if kind != "call":
        return False
    callee = str(node.get("callee") or "")
    if callee in {
        "dtcs:contains",
        "dtcs:ends_with",
        "dtcs:in",
        "dtcs:is_null",
        "dtcs:starts_with",
    }:
        return True
    args = list(node.get("args") or ())
    if callee == "dtcs:case_when":
        values = args[1::2]
        if len(args) % 2:
            values.append(args[-1])
        return bool(values) and all(_expression_is_boolean(value) for value in values)
    if callee in {"dtcs:coalesce", "dtcs:if_null", "dtcs:null_if"}:
        return bool(args) and all(_expression_is_boolean(value) for value in args)
    return False


def _action_boolean_columns(
    kind: Mapping[str, Any],
    *,
    inherited: set[str],
    relation_boolean_columns: Mapping[str, set[str]],
    output_columns: list[str],
) -> set[str]:
    action = str(kind.get("action") or "")
    params = kind.get("parameters") or {}
    result = set(inherited)
    if action == "dtcs:project":
        result = set()
        for item in params.get("fields") or ():
            if isinstance(item, str) and item in inherited:
                result.add(item)
            elif isinstance(item, Mapping):
                name = str(item.get("name") or "")
                if (
                    "expression" in item and _expression_is_boolean(item["expression"])
                ) or ("expression" not in item and name in inherited):
                    result.add(name)
    elif action == "dtcs:with_fields":
        for item in params.get("assignments") or ():
            if not isinstance(item, Mapping):
                continue
            name = str(item.get("name") or "")
            result.discard(name)
            if _expression_is_boolean(item.get("expression")):
                result.add(name)
    elif action == "dtcs:drop_fields":
        result -= {
            str(name) for name in (params.get("fields") or params.get("names") or ())
        }
    elif action == "dtcs:rename_fields":
        mapping = params.get("mapping") or {}
        if isinstance(mapping, list):
            renamed = {
                str(item["from"]): str(item["to"])
                for item in mapping
                if isinstance(item, Mapping) and "from" in item and "to" in item
            }
        else:
            renamed = {str(key): str(value) for key, value in dict(mapping).items()}
        result = {renamed.get(name, name) for name in result}
    elif action == "dtcs:join":
        result |= relation_boolean_columns.get(str(params.get("right")), set())
    elif action == "dtcs:aggregate":
        result &= {str(name) for name in (params.get("groupBy") or ())}
    return result & set(output_columns)


def _sqlite_type(values: list[Any]) -> str:
    non_null = [v for v in values if v is not None]
    if not non_null:
        return "TEXT"
    if all(isinstance(v, bool) for v in non_null):
        return "INTEGER"
    if all(isinstance(v, int) and not isinstance(v, bool) for v in non_null):
        return "INTEGER"
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in non_null):
        return "REAL"
    return "TEXT"


def _materialize_table(
    conn: Any, table: str, rows: list[dict[str, Any]], *, dialect: str
) -> None:
    from decimal import Decimal

    from sqlalchemy import text

    from etlantic_sql.dialect_postgresql import quote_identifier

    safe_table = require_safe_identifier(table)
    table_sql = quote_identifier(safe_table, dialect=dialect)
    if not rows:
        conn.execute(text(f"CREATE TEMP TABLE {table_sql} (dummy INTEGER)"))
        return
    columns = list(rows[0].keys())
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    safe_columns = [require_safe_identifier(str(c)) for c in columns]
    col_defs = ", ".join(
        f"{quote_identifier(c, dialect=dialect)} "
        f"{_sqlite_type([row.get(c) for row in rows])}"
        for c in safe_columns
    )
    conn.execute(text(f"CREATE TEMP TABLE {table_sql} ({col_defs})"))
    placeholders = ", ".join(f":{c}" for c in safe_columns)
    col_list = ", ".join(quote_identifier(c, dialect=dialect) for c in safe_columns)
    insert = text(f"INSERT INTO {table_sql} ({col_list}) VALUES ({placeholders})")
    for row in rows:
        payload = {c: row.get(c) for c in safe_columns}
        for key, value in list(payload.items()):
            if isinstance(value, Decimal):
                payload[key] = float(value)
            elif value is not None and not isinstance(value, (str, int, float, bool)):
                payload[key] = str(value)
        conn.execute(insert, payload)


def _parameter_names(definition: Mapping[str, Any]) -> tuple[str, ...]:
    names: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("kind") == "fieldRef" and node.get("scope") == "parameter":
                names.append(str(node.get("target")))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(definition)
    return tuple(dict.fromkeys(names))


def _analyze_modes(definition: Mapping[str, Any]) -> list[TransformSupportFinding]:
    findings: list[TransformSupportFinding] = []
    for action in definition.get("actions") or []:
        kind = action.get("kind") or {}
        name = kind.get("action")
        params = kind.get("parameters") or {}
        path = str(kind.get("id") or action.get("id") or name)
        if name == "dtcs:join":
            how = str(params.get("type") or "inner")
            if how == "outer":
                how = "full"
            if how not in _JOIN_TYPES:
                findings.append(
                    TransformSupportFinding(
                        code="PMXFORM201",
                        requirement=f"join.type:{how}",
                        reason=f"Unsupported join type {how!r}",
                        expression_path=path,
                    )
                )
            collision = str(params.get("collisionPolicy") or "fail")
            if collision not in _COLLISION_POLICIES:
                findings.append(
                    TransformSupportFinding(
                        code="PMXFORM202",
                        requirement=f"join.collisionPolicy:{collision}",
                        reason=("SQL relational compiler claims fail collision only"),
                        expression_path=path,
                    )
                )
            if params.get("predicate") is not None and params.get("leftKey") is None:
                findings.append(
                    TransformSupportFinding(
                        code="PMXFORM301",
                        requirement="action:dtcs:join:predicate",
                        reason="predicate joins are not implemented",
                        expression_path=path,
                    )
                )
        if name == "dtcs:union":
            mode = str(params.get("mode") or "byPosition")
            if mode not in _UNION_MODES:
                findings.append(
                    TransformSupportFinding(
                        code="PMXFORM203",
                        requirement=f"union.mode:{mode}",
                        reason=f"Unsupported union mode {mode!r}",
                        expression_path=path,
                    )
                )
            if mode == "byPosition" and bool(params.get("allowMissingColumns")):
                findings.append(
                    TransformSupportFinding(
                        code="PMXFORM301",
                        requirement="action:dtcs:union:allowMissingColumns",
                        reason=(
                            "allowMissingColumns is not supported for byPosition unions"
                        ),
                        expression_path=path,
                    )
                )
        if name not in CLAIMED_ACTIONS and name is not None:
            findings.append(
                TransformSupportFinding(
                    code="PMXFORM101",
                    requirement=str(name),
                    reason="Action not claimed by SQL portable compiler",
                    expression_path=path,
                )
            )
    return findings
