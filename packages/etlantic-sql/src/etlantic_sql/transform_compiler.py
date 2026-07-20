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
)
from etlantic.transform.protocol import KERNEL_PROFILE_V1, RELATIONAL_PROFILE_V1
from etlantic_sql.compiler import SqlCompiler
from etlantic_sql.frame import SqlRelationFrame
from etlantic_sql.lowering.actions import (
    CLAIMED_ACTIONS,
    apply_action_to_query,
)

__version__ = "0.21.0"

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


class SqlTransformCompiler:
    """Compile ``dtcs.transform-plan/2`` kernel+relational IR to SQL IR."""

    def __init__(self) -> None:
        caps = TransformCapabilities(
            profiles=frozenset({KERNEL_PROFILE_V1, RELATIONAL_PROFILE_V1}),
            actions=CLAIMED_ACTIONS,
            functions=CLAIMED_FUNCTIONS,
            lazy=False,
            eager=True,
        )
        self._info = TransformCompilerInfo(
            name="etlantic-sql",
            version=__version__,
            engine="sql",
            compiler_protocol=COMPILER_PROTOCOL,
            capabilities=caps,
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
            requirements_from_plan,
            three_state_findings,
        )

        req = merge_requirements(requirements, requirements_from_plan(dict(definition)))
        report = match_requirements(req, self._info.capabilities)
        findings = list(report.findings)
        findings.extend(_analyze_modes(definition))
        findings.extend(three_state_findings(definition, self._info.capabilities))
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

        dialect, engine = _open_engine(context.metadata)
        compiler = SqlCompiler(dialect=dialect, supports_merge=False)
        frames: dict[str, SqlRelationFrame] = {}
        for name, value in inputs.items():
            frames[name] = _as_frame(value, name=name)
        for input_id in plan.get("inputs") or {}:
            if input_id not in frames and len(inputs) == 1:
                frames[str(input_id)] = _as_frame(
                    next(iter(inputs.values())), name=str(input_id)
                )

        with engine.begin() as conn:
            relations: dict[str, RelationRef] = {}
            relation_columns: dict[str, list[str]] = {}
            for name, frame in frames.items():
                table = _safe_table(name)
                _materialize_table(conn, table, frame.rows, dialect=dialect)
                relations[name] = RelationRef(name=table)
                relation_columns[name] = (
                    list(frame.rows[0].keys()) if frame.rows else list(frame.columns)
                )

            # Primary working relation: first declared input or sole frame.
            input_ids = list((plan.get("inputs") or {}).keys()) or list(frames.keys())
            if not input_ids:
                raise ValueError("Portable SQL plan has no inputs")
            current_name = str(input_ids[0])
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
                else:
                    if target not in relations:
                        raise KeyError(f"Missing action target relation {target!r}")
                    target_rel = relations[target]
                    target_cols = list(relation_columns[target])
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
                create_sql = (
                    f"CREATE TEMP TABLE {compiler.quote(step_table)} AS "
                    f"{compiled_sql.text}"
                )
                conn.execute(_text(create_sql), bound)
                current_rel = RelationRef(name=step_table)
                current_cols = out_cols
                relations[action_id] = current_rel
                relation_columns[action_id] = out_cols
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
                rows = [dict(row._mapping) for row in result]
                valid[out_name] = SqlRelationFrame(rows=rows, name=out_name)

        return TransformOutputBundle(
            valid=valid,
            metrics={
                "fused_steps": len(ctes),
                "logical_nodes": logical_nodes,
                "dialect": dialect,
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
        return SqlRelationFrame(rows=list(value), name=name)
    if hasattr(value, "to_dicts"):
        return SqlRelationFrame(rows=list(value.to_dicts()), name=name)
    raise TypeError(f"Unsupported SQL input frame type {type(value)!r}")


def _safe_table(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", str(name))
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"t_{cleaned}"
    return require_safe_identifier(cleaned)


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

    if not rows:
        conn.execute(text(f'CREATE TEMP TABLE "{table}" (dummy INTEGER)'))
        return
    columns = list(rows[0].keys())
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    col_defs = ", ".join(
        f'"{c}" {_sqlite_type([row.get(c) for row in rows])}' for c in columns
    )
    conn.execute(text(f'CREATE TEMP TABLE "{table}" ({col_defs})'))
    placeholders = ", ".join(f":{c}" for c in columns)
    col_list = ", ".join(f'"{c}"' for c in columns)
    insert = text(f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders})')
    for row in rows:
        payload = {c: row.get(c) for c in columns}
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
