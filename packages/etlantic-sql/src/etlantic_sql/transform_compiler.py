"""SQL portable transform compiler (kernel + relational claims)."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Mapping, Sequence
from decimal import Decimal, localcontext
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
from etlantic_sql.unicode_data import (
    UNICODE_DATA_FINGERPRINT,
    UNICODE_DATA_VERSION,
    unicode_case,
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


def _dialect_from_url(url: str) -> str:
    """Return the SQLAlchemy dialect name encoded by a database URL."""
    return url.split(":", 1)[0].split("+", 1)[0].lower()


def _unicode_runtime_matches_pinned() -> bool:
    """Return whether host Unicode data matches the SQL compiler's pinned data."""
    import unicodedata

    return unicodedata.unidata_version == UNICODE_DATA_VERSION


def create_transform_compiler() -> SqlTransformCompiler:
    """Entry-point factory for ``etlantic.transform_compilers``."""
    return SqlTransformCompiler()


def _environment_identity(dialect: str | None = None) -> dict[str, str]:
    """Return the SQL runtime identity used for planning evidence."""
    if dialect is None:
        url = os.environ.get("ETLANTIC_SQL_URL") or os.environ.get("DATABASE_URL")
        dialect = _dialect_from_url(url) if url else "sqlite"
    dialect = _dialect_from_url(str(dialect or "sqlite"))
    environment = {
        "dialect": dialect,
        "runtime": "sqlalchemy",
    }
    if dialect in {"sqlite", "postgresql"}:
        environment.update(
            {
                "unicode": UNICODE_DATA_VERSION,
                "unicode_fingerprint": UNICODE_DATA_FINGERPRINT,
            }
        )
    elif dialect in {"unknown", ""}:
        environment["unicode"] = "unknown"
    else:
        environment["unicode"] = "backend-defined"
    return environment


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
            implementation="sql-native/2",
            package="etlantic-sql",
            compiler_protocol=COMPILER_PROTOCOL,
            capabilities=caps,
            evidence_fingerprint=capabilities_fingerprint(
                caps,
                compiler="etlantic-sql",
                implementation="sql-native/2",
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
        blob = json.dumps(definition, sort_keys=True)
        if not _unicode_runtime_matches_pinned() and (
            "dtcs:lower" in blob or "dtcs:upper" in blob
        ):
            findings.append(
                TransformSupportFinding(
                    code="PMXFORM304",
                    requirement=f"environment:unicode:{UNICODE_DATA_VERSION}",
                    reason=(
                        "SQL portable casing is pinned to Unicode "
                        f"{UNICODE_DATA_VERSION}, but the host runtime uses a "
                        "different Unicode database"
                    ),
                )
            )
        # Reject trusted SQL fragments in portable definitions.
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
                    lambda value: (
                        None
                        if value is None
                        else unicode_case(str(value), mode="lower")
                    ),
                    deterministic=True,
                )
                driver.create_function(
                    "ETLANTIC_UNICODE_UPPER",
                    1,
                    lambda value: (
                        None
                        if value is None
                        else unicode_case(str(value), mode="upper")
                    ),
                    deterministic=True,
                )
                driver.create_aggregate("ETLANTIC_DECIMAL_SUM", 1, _DecimalSumAggregate)
                driver.create_aggregate(
                    "ETLANTIC_DECIMAL_AVERAGE", 1, _DecimalAverageAggregate
                )
                driver.create_aggregate("ETLANTIC_DECIMAL_MIN", 1, _DecimalMinAggregate)
                driver.create_aggregate("ETLANTIC_DECIMAL_MAX", 1, _DecimalMaxAggregate)
            relations: dict[str, RelationRef] = {}
            relation_columns: dict[str, list[str]] = {}
            relation_boolean_columns: dict[str, set[str]] = {}
            relation_non_boolean_columns: dict[str, set[str]] = {}
            relation_decimal_columns: dict[str, set[str]] = {}
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
                bool_columns, non_bool_columns = _infer_column_types(frame.rows)
                relation_boolean_columns[name] = bool_columns
                relation_non_boolean_columns[name] = non_bool_columns
                relation_decimal_columns[name] = _infer_decimal_columns(frame.rows)

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
                    dialect=dialect,
                    decimal_columns=relation_decimal_columns.get(target_source, set()),
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
                bool_columns, non_bool_columns = _action_column_types(
                    kind,
                    inherited_boolean=relation_boolean_columns.get(
                        target_source, set()
                    ),
                    inherited_non_boolean=relation_non_boolean_columns.get(
                        target_source, set()
                    ),
                    relation_boolean_columns=relation_boolean_columns,
                    relation_non_boolean_columns=relation_non_boolean_columns,
                    relation_columns=relation_columns,
                    output_columns=out_cols,
                    parameters=parameters,
                )
                relation_boolean_columns[action_id] = bool_columns
                relation_non_boolean_columns[action_id] = non_bool_columns
                relation_decimal_columns[action_id] = _action_decimal_columns(
                    kind,
                    inherited_decimal=relation_decimal_columns.get(
                        target_source, set()
                    ),
                    relation_decimal_columns=relation_decimal_columns,
                    relation_columns=relation_columns,
                    output_columns=out_cols,
                    parameters=parameters,
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
                decimal_columns = relation_decimal_columns.get(str(source), set())
                rows = [
                    {
                        key: bool(value)
                        if key in boolean_columns and value is not None
                        else Decimal(str(value))
                        if key in decimal_columns and value is not None
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
        dialect = engine.dialect.name
        return dialect, engine
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


def _infer_column_types(rows: list[dict[str, Any]]) -> tuple[set[str], set[str]]:
    """Infer definite boolean and definite non-boolean columns across all rows."""
    columns = {name for row in rows for name in row}
    booleans: set[str] = set()
    non_booleans: set[str] = set()
    for name in columns:
        values = [row.get(name) for row in rows if row.get(name) is not None]
        if not values:
            continue
        if all(isinstance(value, bool) for value in values):
            booleans.add(name)
        else:
            non_booleans.add(name)
    return booleans, non_booleans


def _infer_decimal_columns(rows: list[dict[str, Any]]) -> set[str]:
    """Identify input columns whose non-null values are exact Decimals."""
    from decimal import Decimal

    columns = {name for row in rows for name in row}
    return {
        name
        for name in columns
        if any(isinstance(row.get(name), Decimal) for row in rows)
    }


def _expression_decimal_type(
    node: Any,
    *,
    inherited_decimal: set[str],
    parameters: Mapping[str, Any] | None = None,
) -> bool:
    from decimal import Decimal

    if not isinstance(node, Mapping):
        return isinstance(node, Decimal)
    kind = node.get("kind")
    if kind == "fieldRef":
        if node.get("scope") == "parameter":
            target = node.get("target")
            return isinstance(
                (parameters or {}).get(target) if isinstance(target, str) else None,
                Decimal,
            )
        return str(node.get("target")) in inherited_decimal
    if kind == "literal":
        value = node.get("value")
        return isinstance(value, Mapping) and value.get("type") == "decimal"
    if kind == "binary":
        if str(node.get("op")) not in {
            "add",
            "sub",
            "subtract",
            "mul",
            "multiply",
            "div",
            "divide",
            "modulo",
        }:
            return False
        return _expression_decimal_type(
            node.get("left"), inherited_decimal=inherited_decimal, parameters=parameters
        ) or _expression_decimal_type(
            node.get("right"),
            inherited_decimal=inherited_decimal,
            parameters=parameters,
        )
    if kind == "unary":
        return _expression_decimal_type(
            node.get("operand", node.get("expr")),
            inherited_decimal=inherited_decimal,
            parameters=parameters,
        )
    if kind == "call":
        callee = str(node.get("callee") or "")
        if callee in {
            "dtcs:contains",
            "dtcs:starts_with",
            "dtcs:ends_with",
            "dtcs:in",
            "dtcs:is_null",
            "dtcs:is_missing",
            "dtcs:is_invalid",
            "dtcs:to_string",
        }:
            return False
        args = list(node.get("args") or ())
        if callee == "dtcs:case_when":
            args = args[1::2] + (args[-1:] if len(args) % 2 else [])
        return any(
            _expression_decimal_type(
                child, inherited_decimal=inherited_decimal, parameters=parameters
            )
            for child in args
        )
    return False


def _action_decimal_columns(
    kind: Mapping[str, Any],
    *,
    inherited_decimal: set[str],
    relation_decimal_columns: Mapping[str, set[str]],
    relation_columns: Mapping[str, list[str]],
    output_columns: list[str],
    parameters: Mapping[str, Any] | None = None,
) -> set[str]:
    action = str(kind.get("action") or "")
    params = kind.get("parameters") or {}
    decimal_columns = set(inherited_decimal)
    if action == "dtcs:project":
        decimal_columns = set()
        for item in params.get("fields") or ():
            if isinstance(item, str):
                if item in inherited_decimal:
                    decimal_columns.add(item)
            elif isinstance(item, Mapping):
                name = str(item.get("name") or "")
                expression = item.get("expression")
                if expression is None:
                    if name in inherited_decimal:
                        decimal_columns.add(name)
                elif _expression_decimal_type(
                    expression,
                    inherited_decimal=inherited_decimal,
                    parameters=parameters,
                ):
                    decimal_columns.add(name)
    elif action == "dtcs:with_fields":
        for item in params.get("assignments") or ():
            if not isinstance(item, Mapping):
                continue
            name = str(item.get("name") or "")
            decimal_columns.discard(name)
            if _expression_decimal_type(
                item.get("expression"),
                inherited_decimal=inherited_decimal,
                parameters=parameters,
            ):
                decimal_columns.add(name)
    elif action == "dtcs:drop_fields":
        decimal_columns -= {
            str(name) for name in (params.get("fields") or params.get("names") or ())
        }
    elif action == "dtcs:rename_fields":
        mapping = params.get("mapping") or {}
        if isinstance(mapping, list):
            mapping = {
                str(item["from"]): str(item["to"])
                for item in mapping
                if isinstance(item, Mapping) and "from" in item and "to" in item
            }
        decimal_columns = {str(mapping.get(name, name)) for name in decimal_columns}
    elif action in {"dtcs:join", "dtcs:union"}:
        other = str(params.get("right") or params.get("other"))
        other_decimal = relation_decimal_columns.get(other, set())
        if (
            action == "dtcs:union"
            and str(params.get("mode") or "byPosition") == "byPosition"
        ):
            names = relation_columns.get(other, [])
            decimal_columns.update(
                output_columns[index]
                for index, name in enumerate(names)
                if index < len(output_columns) and name in other_decimal
            )
        else:
            decimal_columns.update(other_decimal)
    elif action == "dtcs:aggregate":
        group_by = {str(name) for name in (params.get("groupBy") or ())}
        decimal_columns &= group_by
        for item in params.get("aggregates") or ():
            if not isinstance(item, Mapping):
                continue
            name = str(item.get("name") or item.get("alias") or "")
            expression = item.get("expression") or item.get("field")
            if _expression_decimal_type(
                expression,
                inherited_decimal=inherited_decimal,
                parameters=parameters,
            ) and str(
                item.get("function")
                or item.get("op")
                or (expression.get("callee") if isinstance(expression, Mapping) else "")
                or ""
            ).removeprefix("dtcs:").lower() in {
                "sum",
                "average",
                "avg",
                "min",
                "max",
            }:
                decimal_columns.add(name)
    return decimal_columns & set(output_columns)


class _DecimalAggregate:
    def __init__(self) -> None:
        self.values: list[Decimal] = []

    def step(self, value: Any) -> None:
        if value is not None:
            self.values.append(
                value if isinstance(value, Decimal) else Decimal(str(value))
            )


class _DecimalSumAggregate(_DecimalAggregate):
    def finalize(self) -> str | None:
        if not self.values:
            return None
        with localcontext() as context:
            context.prec = max(
                100, *(len(value.as_tuple().digits) for value in self.values)
            )
            return str(sum(self.values, Decimal(0)))


class _DecimalAverageAggregate(_DecimalAggregate):
    def finalize(self) -> str | None:
        if not self.values:
            return None
        with localcontext() as context:
            context.prec = max(
                100, *(len(value.as_tuple().digits) for value in self.values)
            )
            return str(sum(self.values, Decimal(0)) / Decimal(len(self.values)))


class _DecimalMinAggregate(_DecimalAggregate):
    def finalize(self) -> str | None:
        return str(min(self.values)) if self.values else None


class _DecimalMaxAggregate(_DecimalAggregate):
    def finalize(self) -> str | None:
        return str(max(self.values)) if self.values else None


def _expression_boolean_type(
    node: Any,
    *,
    inherited_boolean: set[str],
    parameters: Mapping[str, Any] | None = None,
) -> bool | None:
    """Return True/False for definite boolean/non-boolean, None when unknown/null."""
    if not isinstance(node, Mapping):
        return bool(node) if isinstance(node, bool) else False
    kind = node.get("kind")
    if kind == "fieldRef":
        if node.get("scope") == "parameter":
            target = node.get("target")
            if (
                isinstance(target, str)
                and parameters is not None
                and target in parameters
            ):
                value = parameters[target]
                if isinstance(value, bool):
                    return True
                if value is None:
                    return None
                return False
            return None
        if node.get("scope") not in {None, "field", "column"}:
            return None
        return True if node.get("target") in inherited_boolean else None
    if kind == "literal":
        value = node.get("value")
        if not isinstance(value, Mapping):
            return None
        value_type = value.get("type")
        if value_type == "boolean":
            return True
        if value_type in {"null", "missing"} or value.get("value") is None:
            return None
        return False
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
    elif callee in {"dtcs:coalesce", "dtcs:if_null", "dtcs:null_if"}:
        values = args
    else:
        return False
    if not values:
        return None
    types = [
        _expression_boolean_type(
            value,
            inherited_boolean=inherited_boolean,
            parameters=parameters,
        )
        for value in values
    ]
    if any(value is False for value in types):
        return False
    if any(value is True for value in types):
        return all(value in {True, None} for value in types)
    return None


def _expression_is_null_literal(node: Any) -> bool:
    if not isinstance(node, Mapping) or node.get("kind") != "literal":
        return False
    value = node.get("value")
    return isinstance(value, Mapping) and value.get("type") in {"null", "missing"}


def _action_column_types(
    kind: Mapping[str, Any],
    *,
    inherited_boolean: set[str],
    inherited_non_boolean: set[str],
    relation_boolean_columns: Mapping[str, set[str]],
    relation_non_boolean_columns: Mapping[str, set[str]],
    relation_columns: Mapping[str, list[str]],
    output_columns: list[str],
    parameters: Mapping[str, Any] | None = None,
) -> tuple[set[str], set[str]]:
    action = str(kind.get("action") or "")
    params = kind.get("parameters") or {}
    booleans = set(inherited_boolean)
    non_booleans = set(inherited_non_boolean)
    if action == "dtcs:project":
        booleans = set()
        non_booleans = set()
        for item in params.get("fields") or ():
            if isinstance(item, str):
                if item in inherited_boolean:
                    booleans.add(item)
                elif item in inherited_non_boolean:
                    non_booleans.add(item)
            elif isinstance(item, Mapping):
                name = str(item.get("name") or "")
                if "expression" in item:
                    expression = item["expression"]
                    expression_type = _expression_boolean_type(
                        expression,
                        inherited_boolean=inherited_boolean,
                        parameters=parameters,
                    )
                    if expression_type is True:
                        booleans.add(name)
                    elif expression_type is False or not _expression_is_null_literal(
                        expression
                    ):
                        non_booleans.add(name)
                elif name in inherited_boolean:
                    booleans.add(name)
                elif name in inherited_non_boolean:
                    non_booleans.add(name)
    elif action == "dtcs:with_fields":
        for item in params.get("assignments") or ():
            if not isinstance(item, Mapping):
                continue
            name = str(item.get("name") or "")
            booleans.discard(name)
            non_booleans.discard(name)
            expression = item.get("expression")
            expression_type = _expression_boolean_type(
                expression,
                inherited_boolean=inherited_boolean,
                parameters=parameters,
            )
            if expression_type is True:
                booleans.add(name)
            elif expression_type is False or not _expression_is_null_literal(
                expression
            ):
                non_booleans.add(name)
    elif action == "dtcs:drop_fields":
        dropped = {
            str(name) for name in (params.get("fields") or params.get("names") or ())
        }
        booleans -= dropped
        non_booleans -= dropped
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
        booleans = {renamed.get(name, name) for name in booleans}
        non_booleans = {renamed.get(name, name) for name in non_booleans}
    elif action in {"dtcs:join", "dtcs:union"}:
        other = str(params.get("right") or params.get("other"))
        if (
            action == "dtcs:union"
            and str(params.get("mode") or "byPosition") == "byPosition"
        ):
            # Align right-side type metadata to left-side output names by
            # ordinal, matching the SQL union projection.
            right_types = relation_boolean_columns.get(other, set())
            right_non_types = relation_non_boolean_columns.get(other, set())
            right_names = relation_columns.get(other, [])
            for index, name in enumerate(right_names):
                if index >= len(output_columns):
                    break
                if name in right_types:
                    booleans.add(output_columns[index])
                elif name in right_non_types:
                    non_booleans.add(output_columns[index])
        else:
            booleans |= relation_boolean_columns.get(other, set())
            non_booleans |= relation_non_boolean_columns.get(other, set())
    elif action == "dtcs:aggregate":
        group_by = {str(name) for name in (params.get("groupBy") or ())}
        booleans &= group_by
        non_booleans = set(output_columns) - booleans
    booleans &= set(output_columns)
    non_booleans = (non_booleans & set(output_columns)) - booleans
    return booleans, non_booleans


def _sqlite_type(values: list[Any], *, dialect: str = "sqlite") -> str:
    non_null = [v for v in values if v is not None]
    if not non_null:
        return "TEXT"
    from decimal import Decimal

    if any(isinstance(v, Decimal) for v in non_null):
        return "NUMERIC" if dialect == "postgresql" else "TEXT"
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
        f"{_sqlite_type([row.get(c) for row in rows], dialect=dialect)}"
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
                if dialect == "sqlite":
                    payload[key] = str(value)
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
