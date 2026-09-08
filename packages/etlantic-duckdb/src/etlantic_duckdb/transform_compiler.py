"""Closed-plan DuckDB portable transform compiler."""

from __future__ import annotations

import hashlib
import inspect
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Any

from etlantic.sql.helpers import require_safe_identifier
from etlantic.sql.protocol import RelationRef, SqlExecutionContext, TransactionOutcome
from etlantic.transform.capabilities import (
    match_requirements,
    merge_requirements,
    portable_arithmetic_findings,
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
    relational_pushdown_findings,
    requirement_records_from_mapping,
)
from etlantic.transform.portable_baseline import (
    BASELINE_FUNCTION_ARITIES,
    BASELINE_FUNCTIONS,
    BASELINE_JOIN_MODES,
    BASELINE_OPERATORS,
    BASELINE_TYPES,
    KERNEL_ACTIONS,
    RELATIONAL_ACTIONS,
    normalize_operator,
)
from etlantic.transform.protocol import KERNEL_PROFILE_V1, RELATIONAL_PROFILE_V1
from etlantic_duckdb.dialect import DuckDBCompiler
from etlantic_duckdb.frame import DuckDBFrame
from etlantic_duckdb.plugin import DuckDBSqlPlugin

__version__ = "0.49.0"

_ACTIONS = frozenset(KERNEL_ACTIONS + RELATIONAL_ACTIONS)
_FUNCTIONS = frozenset(BASELINE_FUNCTIONS)


def create_transform_compiler() -> DuckDBTransformCompiler:
    return DuckDBTransformCompiler()


class DuckDBTransformCompiler:
    def __init__(self) -> None:
        caps = TransformCapabilities(
            profiles=frozenset({KERNEL_PROFILE_V1, RELATIONAL_PROFILE_V1}),
            actions=_ACTIONS,
            functions=_FUNCTIONS,
            operators=frozenset(BASELINE_OPERATORS),
            types=frozenset(BASELINE_TYPES),
            join_modes=frozenset(BASELINE_JOIN_MODES),
            union_modes=frozenset({"byName", "byPosition"}),
            collision_policies=frozenset({"fail"}),
            lazy=True,
            eager=True,
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
                    "schema_fields": _schema_fields,
                    "declared_column_types": _declared_column_types,
                    "explicit_duck_type": _explicit_duck_type,
                    "duck_type_for_schema": _duck_type_for_schema,
                    "native_duck_type": _native_duck_type,
                    "analyze_definition": _analyze_definition,
                    "analyze_expression": _analyze_expression,
                    "analyze_declared_inputs": _analyze_declared_inputs,
                    "analyze_action": _analyze_action,
                    "analyze_outputs": _analyze_outputs,
                    "finding": _finding,
                    "identifier_finding": _identifier_finding,
                    "sequence": _sequence,
                }.items()
            },
            "native_duckdb_types": sorted(_NATIVE_DUCKDB_TYPES),
            "supported_expression_operators": sorted(_SUPPORTED_EXPR_OPERATORS),
            "function_arities": {
                name: list(arity) for name, arity in sorted(_FUNCTION_ARITIES.items())
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
        shape_findings = _analyze_definition(
            definition, evidence_fingerprint=self._info.evidence_fingerprint
        )
        try:
            inferred_requirements = requirements_from_plan(
                dict(definition), include_extended=True
            )
        except (AttributeError, TypeError, ValueError):
            # Shape findings retain the precise path. Requirement extraction
            # must not turn malformed IR into an unstructured exception.
            inferred_requirements = None
        req = merge_requirements(requirements, inferred_requirements)
        if not self._info.capabilities.profiles:
            # Inferred baseline profiles describe the plan vocabulary, not a
            # claim by this partial compiler. Preserve explicitly supplied
            # profile requirements so callers still get a fail-closed result.
            req = dict(req)
            req["profiles"] = list((requirements or {}).get("profiles") or ())
        report = match_requirements(req, self._info.capabilities)
        findings = list(report.findings)
        findings.extend(three_state_findings(definition, self._info.capabilities))
        findings.extend(shape_findings)
        findings.extend(portable_arithmetic_findings(definition))
        findings = [
            finding
            if finding.evidence_fingerprint is not None
            else replace(finding, evidence_fingerprint=self._info.evidence_fingerprint)
            for finding in findings
        ]
        return TransformSupportReport(
            supported=not findings,
            findings=tuple(findings),
            evidence_fingerprint=self._info.evidence_fingerprint,
            pushdown=relational_pushdown_findings(
                definition, evidence_fingerprint=self._info.evidence_fingerprint
            ),
            requirements=requirement_records_from_mapping(req),
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
        input_specs = plan.get("inputs") or {}
        for name, value in inputs.items():
            declared_spec = input_specs.get(str(name))
            if declared_spec is None and len(inputs) == 1 and len(input_specs) == 1:
                declared_spec = next(iter(input_specs.values()))
            relation, names = _input_relation(
                plugin,
                session,
                str(name),
                value,
                step_name=context.step_name,
                attempt=context.attempt,
                declared_spec=declared_spec,
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
        native_statement_digests: list[str] = []
        for index, action in enumerate(plan.get("actions") or ()):
            kind = action.get("kind") or {}
            target_name = str(kind.get("target") or "")
            if target_name and target_name not in relations:
                raise ValueError(f"missing DuckDB action relation {target_name!r}")
            source = relations[target_name] if target_name else current
            source_columns = columns[target_name] if target_name else current_columns
            current, out_cols, statement_digest = _apply_action(
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
            native_statement_digests.append(statement_digest)
            action_id = str(
                (action.get("kind") or {}).get("id") or action.get("id") or f"a{index}"
            )
            relations[action_id] = current
            columns[action_id] = out_cols
            current_columns = out_cols
        lineage = (plan.get("requirements") or {}).get("dependencies") or []
        actions = plan.get("actions") or []
        last_action = actions[-1] if actions else None
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
                    fields = (
                        plugin.inspect_relation(relation, context=fetch_context).get(
                            "fields"
                        )
                        or ()
                    )
                    frame_columns = [str(field["name"]) for field in fields]
                    frame_types = {
                        str(field["name"]): str(field["type"])
                        for field in fields
                        if field.get("name") is not None and field.get("type")
                    }
                    if not frame_columns and fetched.records:
                        frame_columns = list(fetched.records[0])
                    frame_cache[cache_key] = _ResultFrame(
                        fetched.records or [],
                        columns=frame_columns,
                        column_types=frame_types,
                    )
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
                "native_statement_digests": native_statement_digests,
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
    declared_spec: Any = None,
) -> tuple[RelationRef, list[str], str]:
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
    rows = [
        {
            str(key): item_value
            for key, item_value in (
                item.model_dump() if hasattr(item, "model_dump") else dict(item)
            ).items()
        }
        for item in rows
    ]
    schema_fields = _schema_fields(declared_spec)
    declared_columns = list(
        dict.fromkeys(str(field["name"]) for field in schema_fields)
    )
    declared_columns.extend(
        column
        for column in dict.fromkeys(
            str(column) for column in (getattr(value, "columns", ()) or ())
        )
        if column not in declared_columns
    )
    for row in rows:
        for column in row:
            column = str(column)
            if column not in declared_columns:
                declared_columns.append(column)
    if not rows and not declared_columns:
        raise ValueError(
            f"DuckDB portable input {name!r} is empty and has no declared schema"
        )
    column_types = _declared_column_types(value, schema_fields)
    if not rows:
        missing_types = [
            column for column in declared_columns if column not in column_types
        ]
        if missing_types:
            raise ValueError(
                f"DuckDB portable input {name!r} is empty and lacks declared types "
                f"for: {', '.join(missing_types)}"
            )
    relation = RelationRef(
        name=(
            f"pl_in_{_safe(session.run_id)}_{_safe(step_name)}"
            f"_{int(attempt)}_{_safe(name)}"
        )
    )
    ordered_rows = [
        {column: row.get(column) for column in declared_columns} for row in rows
    ]
    loaded = plugin.load_records(
        ordered_rows,
        target=relation,
        context=SqlExecutionContext(
            run_id=session.run_id,
            pipeline_id="portable",
            plan_id="portable",
            step_name=name,
            engine="duckdb",
        ),
        column_types=column_types,
        temporary=True,
    )
    if loaded.outcome is not TransactionOutcome.COMMITTED:
        detail = "; ".join(
            str(
                item.get("message")
                or item.get("code")
                or "DuckDB portable input load failed"
            )
            for item in loaded.diagnostics
        )
        raise RuntimeError(detail or "DuckDB portable input load did not commit")
    return relation, declared_columns


def _schema_fields(spec: Any) -> list[dict[str, Any]]:
    if not isinstance(spec, Mapping):
        return []
    schema = spec.get("schema") if isinstance(spec.get("schema"), Mapping) else spec
    fields = schema.get("fields") if isinstance(schema, Mapping) else None
    return [
        {str(key): value for key, value in field.items()}
        for field in fields or ()
        if isinstance(field, Mapping) and field.get("name")
    ]


def _declared_column_types(
    value: Any, schema_fields: list[dict[str, Any]]
) -> dict[str, str]:
    types: dict[str, str] = {}
    for field in schema_fields:
        type_name = field.get("type")
        if type_name is None:
            continue
        duck_type = _duck_type_for_schema(type_name)
        if duck_type is None:
            raise ValueError(f"unsupported DuckDB declared type {type_name!r}")
        types[str(field["name"])] = duck_type
    explicit = getattr(value, "column_types", None)
    if isinstance(explicit, Mapping):
        for name, type_name in explicit.items():
            if type_name is None:
                continue
            duck_type = _explicit_duck_type(type_name)
            if duck_type is None:
                raise ValueError(f"unsupported DuckDB declared type {type_name!r}")
            types[str(name)] = duck_type
    schema = getattr(value, "schema", None)
    if isinstance(schema, Mapping):
        for name, type_name in schema.items():
            if type_name is None:
                continue
            duck_type = _explicit_duck_type(type_name)
            if duck_type is None:
                raise ValueError(f"unsupported DuckDB declared type {type_name!r}")
            types[str(name)] = duck_type
    return types


_NATIVE_DUCKDB_TYPES = frozenset(
    {
        "BOOLEAN",
        "TINYINT",
        "SMALLINT",
        "INTEGER",
        "BIGINT",
        "HUGEINT",
        "UTINYINT",
        "USMALLINT",
        "UINTEGER",
        "UBIGINT",
        "UHUGEINT",
        "FLOAT",
        "DOUBLE",
        "REAL",
        "DECIMAL",
        "DATE",
        "TIME",
        "TIMETZ",
        "TIME WITH TIME ZONE",
        "TIMESTAMP",
        "TIMESTAMPTZ",
        "TIMESTAMP WITH TIME ZONE",
        "INTERVAL",
        "VARCHAR",
        "TEXT",
        "JSON",
        "UUID",
        "BLOB",
    }
)


def _native_duck_type(type_name: Any) -> str | None:
    text = str(type_name).strip().upper()
    if text in _NATIVE_DUCKDB_TYPES:
        return text
    if re.fullmatch(r"DECIMAL\s*\(\s*\d+(?:\s*,\s*\d+)?\s*\)", text):
        return re.sub(r"\s+", "", text)
    return None


def _explicit_duck_type(type_name: Any) -> str | None:
    return _native_duck_type(type_name) or _duck_type_for_schema(type_name)


def _duck_type_for_schema(type_name: Any) -> str | None:
    if type_name is None:
        return None
    raw_text = str(type_name).strip()
    if not raw_text:
        return None
    if raw_text.isupper():
        native_type = _native_duck_type(raw_text)
        if native_type is not None:
            return native_type
    text = raw_text.lower()
    if not text:
        return None
    if text in {"bool", "boolean"} or re.fullmatch(r"bool(?:ean)?\d+", text):
        return "BOOLEAN"
    if text in {"int", "integer", "long"} or re.fullmatch(r"int\d+", text):
        return "BIGINT"
    native_type = _native_duck_type(text)
    if native_type is not None:
        return native_type
    if text in {"float", "double", "number", "real"} or re.fullmatch(
        r"float(?:16|32|64)", text
    ):
        return "DOUBLE"
    if text in {"datetime", "timestamp"} or re.fullmatch(
        r"datetime64(?:\[[^\]]+\])?", text
    ):
        return "TIMESTAMP"
    if text in {"date", "date32", "date64"}:
        return "DATE"
    if text in {"time", "time32", "time64"}:
        return "TIME"
    if re.fullmatch(r"decimal(?:\s*\(\s*\d+(?:\s*,\s*\d+)?\s*\))?", text):
        return text.upper().replace(" ", "")
    if text in {"json", "object", "map", "array", "list"} or text.startswith(
        ("list[", "list<", "struct[", "struct<", "map[", "map<")
    ):
        return "JSON"
    if text in {"str", "string", "varchar", "text", "utf8"}:
        return "VARCHAR"
    return None


_SUPPORTED_EXPR_OPERATORS = frozenset(BASELINE_OPERATORS)
_FUNCTION_ARITIES = dict(BASELINE_FUNCTION_ARITIES)


def _finding(
    requirement: str,
    reason: str,
    path: str,
    evidence_fingerprint: str | None,
    *,
    code: str = "PMDUCK303",
    obligation: str | None = None,
) -> TransformSupportFinding:
    return TransformSupportFinding(
        code=code,
        requirement=requirement,
        reason=reason,
        expression_path=path,
        obligation=obligation
        if obligation in {"required", "preferred", "informational"}
        else "required",
        support="unsupported",
        evidence_fingerprint=evidence_fingerprint,
    )


def _identifier_finding(
    value: Any,
    *,
    path: str,
    evidence_fingerprint: str | None,
) -> TransformSupportFinding | None:
    if not isinstance(value, str) or not value:
        return _finding(
            "identifier",
            "SQL identifiers must be non-empty strings",
            path,
            evidence_fingerprint,
        )
    try:
        require_safe_identifier(value)
    except ValueError:
        return _finding(
            "identifier",
            "identifier is outside the DuckDB safe identifier policy",
            path,
            evidence_fingerprint,
        )
    return None


def _column_findings(
    value: Any,
    *,
    path: str,
    available_fields: set[str] | None,
    evidence_fingerprint: str | None,
) -> list[TransformSupportFinding]:
    """Validate an identifier and, when known, resolve it against a schema."""
    finding = _identifier_finding(
        value, path=path, evidence_fingerprint=evidence_fingerprint
    )
    if finding is not None:
        return [finding]
    if available_fields is not None and str(value) not in available_fields:
        return [
            _finding(
                f"column:{value}",
                "column is not declared by the source relation",
                path,
                evidence_fingerprint,
            )
        ]
    return []


def _analyze_expression(
    node: Any,
    *,
    path: str,
    evidence_fingerprint: str | None,
    available_fields: set[str] | None = None,
) -> list[TransformSupportFinding]:
    if isinstance(node, str):
        return _column_findings(
            node,
            path=path,
            available_fields=available_fields,
            evidence_fingerprint=evidence_fingerprint,
        )
    if isinstance(node, (int, float, bool)):
        return []
    if not isinstance(node, Mapping):
        return [
            _finding(
                "expression",
                "expression must use a supported closed-IR shape",
                path,
                evidence_fingerprint,
            )
        ]

    kind = node.get("kind") or node.get("type")
    if kind in {"fieldRef", "field"}:
        name = node.get("target") or node.get("name")
        if node.get("scope") == "parameter":
            if isinstance(name, str) and name:
                return []
            return [
                _finding(
                    "parameter",
                    "parameter references require a non-empty name",
                    path,
                    evidence_fingerprint,
                )
            ]
        return _column_findings(
            name,
            path=path,
            available_fields=available_fields,
            evidence_fingerprint=evidence_fingerprint,
        )
    if kind == "literal":
        return []
    if kind == "call":
        findings: list[TransformSupportFinding] = []
        callee = node.get("callee")
        if not isinstance(callee, str) or not callee:
            findings.append(
                _finding(
                    "function",
                    "function calls require a non-empty callee",
                    f"{path}.callee",
                    evidence_fingerprint,
                )
            )
        elif callee not in _FUNCTIONS and callee != "dtcs:in":
            findings.append(
                _finding(
                    f"function:{callee}",
                    "function is not implemented by the DuckDB compiler",
                    path,
                    evidence_fingerprint,
                )
            )
        args = node.get("args") or ()
        if isinstance(args, (str, bytes)) or not isinstance(args, Sequence):
            findings.append(
                _finding(
                    f"function:{callee}:arguments",
                    "function arguments must be a sequence",
                    f"{path}.args",
                    evidence_fingerprint,
                )
            )
            return findings
        arity = _FUNCTION_ARITIES.get(str(callee))
        if arity is not None:
            minimum, maximum = arity
            if len(args) < minimum or (maximum is not None and len(args) > maximum):
                findings.append(
                    _finding(
                        f"function:{callee}:arity",
                        "function argument count is unsupported",
                        f"{path}.args",
                        evidence_fingerprint,
                    )
                )
        for index, argument in enumerate(args):
            findings.extend(
                _analyze_expression(
                    argument,
                    path=f"{path}.args[{index}]",
                    evidence_fingerprint=evidence_fingerprint,
                    available_fields=available_fields,
                )
            )
        return findings
    if kind in {"binary", "operator"}:
        findings = []
        operator = normalize_operator(str(node.get("op") or ""))
        if operator not in _SUPPORTED_EXPR_OPERATORS:
            findings.append(
                _finding(
                    f"operator:{operator or '<missing>'}",
                    "expression operator is not implemented by the DuckDB compiler",
                    f"{path}.op",
                    evidence_fingerprint,
                )
            )
        for side in ("left", "right"):
            findings.extend(
                _analyze_expression(
                    node.get(side),
                    path=f"{path}.{side}",
                    evidence_fingerprint=evidence_fingerprint,
                    available_fields=available_fields,
                )
            )
        return findings
    if kind == "unary":
        operator = normalize_operator(str(node.get("op") or ""))
        findings = []
        if operator not in {"not", "negate"}:
            findings.append(
                _finding(
                    f"operator:{operator or '<missing>'}",
                    "expression operator is not implemented by the DuckDB compiler",
                    f"{path}.op",
                    evidence_fingerprint,
                )
            )
        findings.extend(
            _analyze_expression(
                node.get("operand"),
                path=f"{path}.operand",
                evidence_fingerprint=evidence_fingerprint,
                available_fields=available_fields,
            )
        )
        return findings
    return [
        _finding(
            f"expression:{kind or '<missing>'}",
            "expression kind is not implemented by the DuckDB compiler",
            path,
            evidence_fingerprint,
        )
    ]


def _sequence(
    value: Any,
    *,
    requirement: str,
    path: str,
    evidence_fingerprint: str | None,
) -> tuple[Sequence[Any] | None, list[TransformSupportFinding]]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        return None, [
            _finding(
                requirement,
                f"{requirement} must be a sequence",
                path,
                evidence_fingerprint,
            )
        ]
    return value, []


def _analyze_definition(
    definition: Mapping[str, Any],
    *,
    evidence_fingerprint: str | None,
) -> list[TransformSupportFinding]:
    inputs = definition.get("inputs") or {}
    findings = _analyze_declared_inputs(
        inputs, evidence_fingerprint=evidence_fingerprint
    )
    input_names = [str(name) for name in inputs] if isinstance(inputs, Mapping) else []
    available_relations = set(input_names)
    relation_columns: dict[str, set[str] | None] = (
        {str(name): _declared_fields(spec) for name, spec in inputs.items()}
        if isinstance(inputs, Mapping)
        else {}
    )
    actions, action_findings = _sequence(
        definition.get("actions") or (),
        requirement="actions",
        path="actions",
        evidence_fingerprint=evidence_fingerprint,
    )
    findings.extend(action_findings)
    if actions is None:
        return findings

    current_relation_name = input_names[0] if input_names else None
    for index, action in enumerate(actions):
        path = f"actions[{index}]"
        if not isinstance(action, Mapping):
            findings.append(
                _finding(
                    "action",
                    "portable actions must be mappings",
                    path,
                    evidence_fingerprint,
                )
            )
            continue
        kind = action.get("kind") or {}
        if not isinstance(kind, Mapping):
            findings.append(
                _finding(
                    "action.kind",
                    "action kind must be a mapping",
                    f"{path}.kind",
                    evidence_fingerprint,
                )
            )
            continue
        name = kind.get("action")
        action_path = str(kind.get("id") or path)
        params = kind.get("parameters") or {}
        if not isinstance(params, Mapping):
            findings.append(
                _finding(
                    f"action:{name}:parameters",
                    "action parameters must be a mapping",
                    f"{path}.kind.parameters",
                    evidence_fingerprint,
                )
            )
            continue
        if name not in _ACTIONS:
            findings.append(
                _finding(
                    f"action:{name or '<missing>'}",
                    "action is not implemented by the DuckDB compiler",
                    f"{path}.kind.action",
                    evidence_fingerprint,
                )
            )
            continue
        target = kind.get("target")
        if target and str(target) not in available_relations:
            findings.append(
                _finding(
                    f"action.target:{target}",
                    "action target does not identify an available relation",
                    f"{path}.kind.target",
                    evidence_fingerprint,
                )
            )
        target_name = str(target) if target else None
        current_relation = target_name or current_relation_name
        source_columns = (
            relation_columns.get(current_relation) if current_relation else None
        )
        findings.extend(
            _analyze_action(
                str(name),
                params,
                path=path,
                action_path=action_path,
                available_relations=available_relations,
                source_columns=source_columns,
                relation_columns=relation_columns,
                evidence_fingerprint=evidence_fingerprint,
            )
        )
        output_relation = str(kind.get("id") or action.get("id") or f"a{index}")
        available_relations.add(output_relation)
        relation_columns[output_relation] = _action_output_fields(
            str(name),
            params,
            source_columns=source_columns,
            relation_columns=relation_columns,
        )
        current_relation_name = output_relation
    findings.extend(
        _analyze_outputs(
            definition,
            available_relations=available_relations,
            evidence_fingerprint=evidence_fingerprint,
        )
    )
    return findings


def _declared_fields(spec: Any) -> set[str] | None:
    """Return declared field names, or None when the schema is intentionally open."""
    if not isinstance(spec, Mapping):
        return None
    schema = spec.get("schema") if isinstance(spec.get("schema"), Mapping) else spec
    if not isinstance(schema, Mapping) or "fields" not in schema:
        return None
    fields = schema.get("fields")
    if not isinstance(fields, Sequence) or isinstance(fields, (str, bytes)):
        return None
    return {
        str(field.get("name"))
        for field in fields
        if isinstance(field, Mapping) and isinstance(field.get("name"), str)
    }


def _action_output_fields(
    name: str,
    params: Mapping[str, Any],
    *,
    source_columns: set[str] | None,
    relation_columns: Mapping[str, set[str] | None],
) -> set[str] | None:
    """Approximate output columns for subsequent static resolution."""
    if source_columns is None:
        return None
    if name in {
        "dtcs:filter",
        "dtcs:limit",
        "dtcs:sort",
        "dtcs:distinct",
        "dtcs:deduplicate",
    }:
        return set(source_columns)
    if name == "dtcs:project":
        return {
            str(item.get("name")) if isinstance(item, Mapping) else str(item)
            for item in params.get("fields") or ()
            if (isinstance(item, str) and item)
            or (isinstance(item, Mapping) and item.get("name"))
        }
    if name == "dtcs:with_fields":
        output = set(source_columns)
        for item in params.get("assignments") or ():
            if isinstance(item, Mapping) and item.get("name"):
                output.add(str(item["name"]))
        return output
    if name == "dtcs:aggregate":
        output = {
            str(field)
            for field in params.get("groupBy") or ()
            if isinstance(field, str)
        }
        output.update(
            str(item["name"])
            for item in params.get("aggregates") or params.get("aggregations") or ()
            if isinstance(item, Mapping) and item.get("name")
        )
        return output
    if name == "dtcs:join":
        right = params.get("right")
        right_columns = relation_columns.get(str(right)) if right else None
        if right_columns is None:
            return None
        right_key = params.get("rightKey")
        return set(source_columns) | {
            column for column in right_columns if column != right_key
        }
    if name == "dtcs:union":
        other = params.get("other")
        other_columns = relation_columns.get(str(other)) if other else None
        if other_columns is None:
            return None
        mode = str(params.get("mode") or "byName").lower()
        if mode == "byposition":
            return set(source_columns)
        return set(source_columns) | set(other_columns)
    return set(source_columns)


def _analyze_declared_inputs(
    inputs: Any, *, evidence_fingerprint: str | None
) -> list[TransformSupportFinding]:
    if not isinstance(inputs, Mapping):
        return [
            _finding(
                "inputs",
                "portable inputs must be a mapping",
                "inputs",
                evidence_fingerprint,
            )
        ]
    findings: list[TransformSupportFinding] = []
    for input_name, spec in inputs.items():
        path = f"inputs.{input_name}"
        if not isinstance(spec, Mapping):
            findings.append(
                _finding(
                    "input.schema",
                    "portable input declarations must be mappings",
                    path,
                    evidence_fingerprint,
                )
            )
            continue
        schema = spec.get("schema") if "schema" in spec else spec
        if not isinstance(schema, Mapping):
            findings.append(
                _finding(
                    "input.schema",
                    "portable input schema must be a mapping",
                    f"{path}.schema",
                    evidence_fingerprint,
                )
            )
            continue
        fields = schema.get("fields")
        if fields is None:
            continue
        field_items, item_findings = _sequence(
            fields,
            requirement="input.schema.fields",
            path=f"{path}.schema.fields",
            evidence_fingerprint=evidence_fingerprint,
        )
        findings.extend(item_findings)
        if field_items is None:
            continue
        for index, field in enumerate(field_items):
            field_path = f"{path}.schema.fields[{index}]"
            if not isinstance(field, Mapping):
                findings.append(
                    _finding(
                        "input.schema.field",
                        "schema field declarations must be mappings",
                        field_path,
                        evidence_fingerprint,
                    )
                )
                continue
            identifier = _identifier_finding(
                field.get("name"),
                path=f"{field_path}.name",
                evidence_fingerprint=evidence_fingerprint,
            )
            if identifier is not None:
                findings.append(identifier)
            type_name = field.get("type")
            if type_name is not None and _duck_type_for_schema(type_name) is None:
                findings.append(
                    _finding(
                        f"type:{type_name}",
                        "declared type is not supported by DuckDB lowering",
                        f"{field_path}.type",
                        evidence_fingerprint,
                    )
                )
    return findings


def _analyze_action(
    name: str,
    params: Mapping[str, Any],
    *,
    path: str,
    action_path: str,
    available_relations: set[str],
    source_columns: set[str] | None,
    relation_columns: Mapping[str, set[str] | None],
    evidence_fingerprint: str | None,
) -> list[TransformSupportFinding]:
    base = f"{path}.kind.parameters"
    if name == "dtcs:filter":
        return _analyze_expression(
            params.get("predicate"),
            path=f"{base}.predicate",
            evidence_fingerprint=evidence_fingerprint,
            available_fields=source_columns,
        )
    if name in {"dtcs:project", "dtcs:with_fields", "dtcs:sort"}:
        key = {
            "dtcs:project": "fields",
            "dtcs:with_fields": "assignments",
            "dtcs:sort": "by" if params.get("by") else "keys",
        }[name]
        items, findings = _sequence(
            params.get(key) or (),
            requirement=f"{name.removeprefix('dtcs:')}.{key}",
            path=f"{base}.{key}",
            evidence_fingerprint=evidence_fingerprint,
        )
        if items is None:
            return findings
        if name == "dtcs:project" and not items:
            findings.append(
                _finding(
                    "project.fields",
                    "project requires at least one field",
                    f"{base}.fields",
                    evidence_fingerprint,
                )
            )
        for index, item in enumerate(items):
            item_path = f"{base}.{key}[{index}]"
            if name == "dtcs:sort":
                if isinstance(item, Mapping) and isinstance(
                    item.get("expression"), Mapping
                ):
                    findings.extend(
                        _analyze_expression(
                            item["expression"],
                            path=f"{item_path}.expression",
                            evidence_fingerprint=evidence_fingerprint,
                            available_fields=source_columns,
                        )
                    )
                else:
                    value = item.get("column") if isinstance(item, Mapping) else item
                    findings.extend(
                        _column_findings(
                            value,
                            path=item_path,
                            available_fields=source_columns,
                            evidence_fingerprint=evidence_fingerprint,
                        )
                    )
                continue
            if isinstance(item, str):
                if name == "dtcs:with_fields":
                    findings.append(
                        _finding(
                            "with_fields.assignment",
                            "with_fields assignments must be mappings",
                            item_path,
                            evidence_fingerprint,
                        )
                    )
                else:
                    identifier = _column_findings(
                        item,
                        path=item_path,
                        available_fields=source_columns,
                        evidence_fingerprint=evidence_fingerprint,
                    )
                    findings.extend(identifier)
                continue
            if not isinstance(item, Mapping):
                findings.append(
                    _finding(
                        f"{name.removeprefix('dtcs:')}.item",
                        "action items must be identifier strings or expression mappings",
                        item_path,
                        evidence_fingerprint,
                    )
                )
                continue
            identifier = _identifier_finding(
                item.get("name"),
                path=f"{item_path}.name",
                evidence_fingerprint=evidence_fingerprint,
            )
            if identifier is not None:
                findings.append(identifier)
            findings.extend(
                _analyze_expression(
                    item.get("expression"),
                    path=f"{item_path}.expression",
                    evidence_fingerprint=evidence_fingerprint,
                    available_fields=source_columns,
                )
            )
        return findings
    if name == "dtcs:limit":
        count = params.get("count", params.get("n", 0))
        try:
            valid = int(count) >= 0
        except (TypeError, ValueError):
            valid = False
        return (
            []
            if valid
            else [
                _finding(
                    "limit.count",
                    "limit count must be a non-negative integer",
                    f"{base}.count",
                    evidence_fingerprint,
                )
            ]
        )
    if name == "dtcs:join":
        findings = []
        collision = str(params.get("collisionPolicy") or "fail")
        if collision != "fail":
            findings.append(
                _finding(
                    f"join.collisionPolicy:{collision}",
                    "DuckDB compiler only supports fail-closed join collisions",
                    action_path,
                    evidence_fingerprint,
                    code="PMDUCK302",
                    obligation="required",
                )
            )
        right_relation = params.get("right")
        if not isinstance(right_relation, str) or not right_relation:
            findings.append(
                _finding(
                    "join.right",
                    "join requires a right relation identity",
                    f"{base}.right",
                    evidence_fingerprint,
                )
            )
        elif right_relation not in available_relations:
            findings.append(
                _finding(
                    f"join.right:{right_relation}",
                    "join right side does not identify an available relation",
                    f"{base}.right",
                    evidence_fingerprint,
                )
            )
        right_columns = (
            relation_columns.get(str(right_relation)) if right_relation else None
        )
        join_type = str(params.get("type") or "inner").lower()
        if join_type == "outer":
            join_type = "full"
        if join_type != "cross":
            for key in ("leftKey", "rightKey"):
                identifier = _column_findings(
                    params.get(key),
                    path=f"{base}.{key}",
                    available_fields=(
                        source_columns if key == "leftKey" else right_columns
                    ),
                    evidence_fingerprint=evidence_fingerprint,
                )
                findings.extend(identifier)
        if (
            collision == "fail"
            and join_type not in {"semi", "anti"}
            and source_columns is not None
            and right_columns is not None
        ):
            overlap = sorted(
                source_columns
                & right_columns
                - {str(params.get("leftKey")), str(params.get("rightKey"))}
            )
            if overlap:
                findings.append(
                    _finding(
                        "join.collision",
                        f"join column collision would occur for: {', '.join(overlap)}",
                        f"{base}.collisionPolicy",
                        evidence_fingerprint,
                        code="PMDUCK302",
                        obligation="required",
                    )
                )
        if join_type not in BASELINE_JOIN_MODES:
            findings.append(
                _finding(
                    f"join.type:{join_type}",
                    "join type is not implemented by the DuckDB compiler",
                    f"{base}.type",
                    evidence_fingerprint,
                )
            )
        return findings
    if name == "dtcs:union":
        findings = []
        other = params.get("other")
        if not isinstance(other, str) or not other:
            findings.append(
                _finding(
                    "union.other",
                    "union requires an other relation identity",
                    f"{base}.other",
                    evidence_fingerprint,
                )
            )
        elif other not in available_relations:
            findings.append(
                _finding(
                    f"union.other:{other}",
                    "union other side does not identify an available relation",
                    f"{base}.other",
                    evidence_fingerprint,
                )
            )
        mode = str(params.get("mode") or "byName")
        if mode.lower() not in {"byname", "byposition"}:
            findings.append(
                _finding(
                    f"union.mode:{mode}",
                    "union mode is not implemented by the DuckDB compiler",
                    f"{base}.mode",
                    evidence_fingerprint,
                )
            )
        if mode.lower() == "byposition" and params.get("allowMissingColumns"):
            findings.append(
                _finding(
                    "union.allowMissingColumns",
                    "byPosition union cannot allow missing columns",
                    f"{base}.allowMissingColumns",
                    evidence_fingerprint,
                )
            )
        return findings
    if name == "dtcs:aggregate":
        findings = []
        group_by, group_findings = _sequence(
            params.get("groupBy") or (),
            requirement="aggregate.groupBy",
            path=f"{base}.groupBy",
            evidence_fingerprint=evidence_fingerprint,
        )
        aggregates, aggregate_findings = _sequence(
            params.get("aggregates") or params.get("aggregations") or (),
            requirement="aggregate.aggregates",
            path=f"{base}.aggregates",
            evidence_fingerprint=evidence_fingerprint,
        )
        findings.extend(group_findings)
        findings.extend(aggregate_findings)
        if group_by is not None:
            for index, field in enumerate(group_by):
                identifier = _column_findings(
                    field,
                    path=f"{base}.groupBy[{index}]",
                    available_fields=source_columns,
                    evidence_fingerprint=evidence_fingerprint,
                )
                findings.extend(identifier)
        if aggregates is not None:
            for index, aggregate in enumerate(aggregates):
                aggregate_path = f"{base}.aggregates[{index}]"
                if not isinstance(aggregate, Mapping):
                    findings.append(
                        _finding(
                            "aggregate.expression",
                            "aggregate expressions must be mappings",
                            aggregate_path,
                            evidence_fingerprint,
                        )
                    )
                    continue
                identifier = _identifier_finding(
                    aggregate.get("name"),
                    path=f"{aggregate_path}.name",
                    evidence_fingerprint=evidence_fingerprint,
                )
                if identifier is not None:
                    findings.append(identifier)
                findings.extend(
                    _analyze_expression(
                        aggregate.get("expression"),
                        path=f"{aggregate_path}.expression",
                        evidence_fingerprint=evidence_fingerprint,
                        available_fields=source_columns,
                    )
                )
        if not group_by and not aggregates:
            findings.append(
                _finding(
                    "aggregate",
                    "aggregate requires grouping fields or aggregate expressions",
                    base,
                    evidence_fingerprint,
                )
            )
        return findings
    return []


def _analyze_outputs(
    definition: Mapping[str, Any],
    *,
    available_relations: set[str],
    evidence_fingerprint: str | None,
) -> list[TransformSupportFinding]:
    outputs = definition.get("outputs") or {}
    if not isinstance(outputs, Mapping):
        return [
            _finding(
                "outputs",
                "portable outputs must be a mapping",
                "outputs",
                evidence_fingerprint,
            )
        ]
    requirements = definition.get("requirements") or {}
    if not isinstance(requirements, Mapping):
        return [
            _finding(
                "requirements",
                "portable requirements must be a mapping",
                "requirements",
                evidence_fingerprint,
            )
        ]
    dependencies = requirements.get("dependencies") or ()
    dependency_items, findings = _sequence(
        dependencies,
        requirement="requirements.dependencies",
        path="requirements.dependencies",
        evidence_fingerprint=evidence_fingerprint,
    )
    if dependency_items is None:
        return findings
    for index, dependency in enumerate(dependency_items):
        path = f"requirements.dependencies[{index}]"
        if not isinstance(dependency, Mapping):
            findings.append(
                _finding(
                    "requirements.dependency",
                    "output dependencies must be mappings",
                    path,
                    evidence_fingerprint,
                )
            )
            continue
        source = dependency.get("from")
        target = dependency.get("to")
        if not isinstance(source, str) or source not in available_relations:
            findings.append(
                _finding(
                    f"output.source:{source or '<missing>'}",
                    "output dependency source is not an available relation",
                    f"{path}.from",
                    evidence_fingerprint,
                )
            )
        if not isinstance(target, str) or (
            target not in outputs and target not in available_relations
        ):
            findings.append(
                _finding(
                    f"output.target:{target or '<missing>'}",
                    "output dependency target is not a declared output",
                    f"{path}.to",
                    evidence_fingerprint,
                )
            )
    return findings


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
    elif name == "dtcs:deduplicate":
        keys = params.get("keys") or params.get("fields") or params.get("subset") or ()
        key_names = [
            str(item.get("field") or item.get("column"))
            if isinstance(item, Mapping)
            else str(item)
            for item in keys
        ]
        if not key_names:
            query = f"SELECT DISTINCT * FROM {source}"
        else:
            partition = ", ".join(
                plugin.quote_identifier(column) for column in key_names
            )
            columns = ", ".join(plugin.quote_identifier(column) for column in names)
            query = (
                f"SELECT {columns} FROM (SELECT *, ROW_NUMBER() OVER "
                f"(PARTITION BY {partition}) AS __etlantic_row_number FROM {source}) "
                "WHERE __etlantic_row_number = 1"
            )
    elif name == "dtcs:limit":
        count = int(params.get("count", params.get("n", 0)))
        if count < 0:
            raise ValueError("limit must be non-negative")
        query = f"SELECT * FROM {source} LIMIT {count}"
    elif name == "dtcs:sort":
        items = params.get("by") or params.get("keys") or ()
        order = []
        for item in items:
            column = (
                _expr(item["expression"], parameters, bound_params)
                if isinstance(item, Mapping)
                and isinstance(item.get("expression"), Mapping)
                else plugin.quote_identifier(
                    str(item.get("column") if isinstance(item, Mapping) else item)
                )
            )
            desc = (
                bool(item.get("descending"))
                if isinstance(item, Mapping) and "descending" in item
                else isinstance(item, Mapping)
                and str(item.get("direction", "asc")).lower() == "desc"
            )
            nulls = (
                str(item.get("nulls", "last")).upper()
                if isinstance(item, Mapping)
                else "LAST"
            )
            if nulls not in {"FIRST", "LAST"}:
                raise ValueError(f"unsupported DuckDB null ordering {nulls!r}")
            order.append(f"{column} {'DESC' if desc else 'ASC'} NULLS {nulls}")
        query = (
            f"SELECT * FROM {source} ORDER BY {', '.join(order)}"
            if order
            else f"SELECT * FROM {source}"
        )
    elif name == "dtcs:union":
        other_name = str(params.get("other") or "")
        if other_name not in relations:
            raise ValueError(f"missing DuckDB union relation {other_name!r}")
        other = relations[other_name]
        other_columns = relation_columns.get(other_name, [])
        mode = str(params.get("mode") or "byName").lower()
        allow_missing = bool(params.get("allowMissingColumns", False))
        if mode == "byposition":
            if allow_missing:
                raise ValueError("byPosition union cannot allow missing columns")
            if len(names) != len(other_columns):
                raise ValueError(
                    "byPosition union inputs have incompatible field counts"
                )
            right_projection = ", ".join(
                f"{plugin.quote_identifier(column)} AS {plugin.quote_identifier(alias)}"
                for column, alias in zip(other_columns, names, strict=True)
            )
            query = (
                f"SELECT * FROM {source} UNION ALL SELECT {right_projection} "
                f"FROM {plugin.quote_identifier(other.name)}"
            )
        elif mode == "byname":
            if not allow_missing and set(names) != set(other_columns):
                raise ValueError("union inputs have incompatible fields")
            out_names = list(dict.fromkeys([*names, *other_columns]))

            def projection(columns: Sequence[str]) -> str:
                known = set(columns)
                return ", ".join(
                    plugin.quote_identifier(column)
                    if column in known
                    else f"NULL AS {plugin.quote_identifier(column)}"
                    for column in out_names
                )

            query = (
                f"SELECT {projection(names)} FROM {source} UNION ALL SELECT "
                f"{projection(other_columns)} FROM {plugin.quote_identifier(other.name)}"
            )
        else:
            raise ValueError(f"unsupported DuckDB union mode {mode!r}")
    elif name == "dtcs:join":
        right_name = str(params.get("right"))
        if right_name not in relations:
            raise ValueError(f"missing DuckDB join relation {right_name!r}")
        right = relations[right_name]
        right_columns = relation_columns.get(right_name, [])
        left_key = params.get("leftKey")
        right_key = params.get("rightKey")
        join_type = str(params.get("type") or "inner").lower()
        if join_type == "outer":
            join_type = "full"
        if join_type not in BASELINE_JOIN_MODES:
            raise ValueError(f"unsupported DuckDB join type {join_type!r}")
        if join_type != "cross" and (not left_key or not right_key):
            raise ValueError("DuckDB joins require leftKey and rightKey")
        overlap = set(names) & set(right_columns) - {str(left_key), str(right_key)}
        if (
            overlap
            and join_type not in {"semi", "anti"}
            and str(params.get("collisionPolicy") or "fail") == "fail"
        ):
            raise ValueError(f"join column collision: {sorted(overlap)}")
        if join_type in {"semi", "anti"}:
            condition = _join_condition(
                plugin,
                left_key=str(left_key),
                right_key=str(right_key),
                null_safe=bool(params.get("nullSafe", False)),
            )
            keyword = "EXISTS" if join_type == "semi" else "NOT EXISTS"
            query = (
                f"SELECT l.* FROM {source} AS l WHERE {keyword} "
                f"(SELECT 1 FROM {plugin.quote_identifier(right.name)} AS r WHERE {condition})"
            )
            out_names = list(names)
        elif join_type == "cross":
            left_exprs = [f"l.{plugin.quote_identifier(column)}" for column in names]
            right_exprs = [
                f"r.{plugin.quote_identifier(column)}"
                for column in right_columns
                if column not in names
            ]
            out_names = list(names) + [
                column for column in right_columns if column not in names
            ]
            query = (
                f"SELECT {', '.join(left_exprs + right_exprs)} FROM {source} AS l "
                f"CROSS JOIN {plugin.quote_identifier(right.name)} AS r"
            )
        else:
            left_exprs = [f"l.{plugin.quote_identifier(column)}" for column in names]
            if join_type in {"right", "full"} and left_key == right_key:
                key = plugin.quote_identifier(str(left_key))
                left_exprs = [
                    f"COALESCE(l.{key}, r.{key}) AS {key}"
                    if column == left_key
                    else expression
                    for column, expression in zip(names, left_exprs, strict=True)
                ]
            right_exprs = [
                f"r.{plugin.quote_identifier(column)}"
                for column in right_columns
                if column not in names
            ]
            out_names = list(names) + [
                column for column in right_columns if column not in names
            ]
            join_sql = {
                "inner": "INNER",
                "left": "LEFT",
                "right": "RIGHT",
                "full": "FULL",
            }[join_type]
            condition = _join_condition(
                plugin,
                left_key=str(left_key),
                right_key=str(right_key),
                null_safe=bool(params.get("nullSafe", False)),
            )
            query = (
                f"SELECT {', '.join(left_exprs + right_exprs)} FROM {source} AS l "
                f"{join_sql} JOIN {plugin.quote_identifier(right.name)} AS r ON {condition}"
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
    return target, out_names, hashlib.sha256(statement.encode("utf-8")).hexdigest()


def _join_condition(
    plugin: DuckDBSqlPlugin,
    *,
    left_key: str,
    right_key: str,
    null_safe: bool,
) -> str:
    operator = "IS NOT DISTINCT FROM" if null_safe else "="
    return (
        f"l.{plugin.quote_identifier(left_key)} {operator} "
        f"r.{plugin.quote_identifier(right_key)}"
    )


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
            arg_sql: list[str] = []
            arg_binding_groups: list[list[Any]] = []
            for arg in node.get("args") or ():
                captured: list[Any] = []
                arg_sql.append(_expr(arg, parameters, captured))
                bindings.extend(captured)
                arg_binding_groups.append(captured)
            args = arg_sql
            if callee == "count_all":
                return "COUNT(*)"
            if callee == "count_distinct":
                return f"COUNT(DISTINCT {', '.join(args)})"
            if callee == "in":
                if len(args) < 2:
                    raise ValueError(
                        "dtcs:in requires a value and at least one candidate"
                    )
                return f"({args[0]} IN ({', '.join(args[1:])}))"
            if callee == "substr":
                if len(args) == 2:
                    return f"SUBSTR({args[0]}, {args[1]} + 1)"
                return f"SUBSTR({args[0]}, {args[1]} + 1, {args[2]})"
            if callee == "case_when":
                if len(args) < 3 or len(args) % 2 == 0:
                    raise ValueError(
                        "dtcs:case_when requires condition/value pairs and an else"
                    )
                clauses = " ".join(
                    f"WHEN {condition} THEN {value}"
                    for condition, value in zip(args[::2][:-1], args[1::2], strict=True)
                )
                return f"CASE {clauses} ELSE {args[-1]} END"
            if callee == "is_null":
                return f"({args[0]} IS NULL)"
            if callee == "contains":
                return f"CONTAINS({args[0]}, {args[1]})"
            if callee == "starts_with":
                return f"STARTS_WITH({args[0]}, {args[1]})"
            if callee == "ends_with":
                return f"ENDS_WITH({args[0]}, {args[1]})"
            names = {
                "sum": "SUM",
                "average": "AVG",
                "min": "MIN",
                "max": "MAX",
                "count": "COUNT",
                "lower": "LOWER",
                "upper": "UPPER",
                "concat": "CONCAT",
                "concat_ws": "CONCAT_WS",
                "replace": "REPLACE",
                "length": "LENGTH",
                "abs": "ABS",
                "round": "ROUND",
                "floor": "FLOOR",
                "ceil": "CEIL",
                "sqrt": "SQRT",
                "power": "POWER",
                "least": "LEAST",
                "greatest": "GREATEST",
                "coalesce": "COALESCE",
                "if_null": "COALESCE",
                "null_if": "NULLIF",
            }
            function = names.get(callee)
            if function is None:
                raise ValueError(f"unsupported DuckDB function {callee!r}")
            value = f"{function}({', '.join(args)})"
            if callee not in {
                "coalesce",
                "if_null",
                "null_if",
                "is_null",
                "sum",
                "average",
                "min",
                "max",
                "count",
                "count_all",
                "count_distinct",
            }:
                null_check = " OR ".join(f"({arg} IS NULL)" for arg in args)
                # The argument placeholders occur once in the null check and
                # once in the function call; bind each value for both uses.
                for captured in arg_binding_groups:
                    bindings.extend(captured)
                value = f"CASE WHEN {null_check} THEN NULL ELSE {value} END"
            return value
        if kind in {"binary", "operator"}:
            op = {
                "eq": "=",
                "not_eq": "<>",
                "gt": ">",
                "gte": ">=",
                "lt": "<",
                "lte": "<=",
                "and": "AND",
                "or": "OR",
                "add": "+",
                "subtract": "-",
                "multiply": "*",
                "divide": "/",
                "modulo": "%",
            }.get(normalize_operator(str(node.get("op"))))
            if normalize_operator(str(node.get("op"))) == "null_safe_eq":
                return (
                    f"({_expr(node.get('left'), parameters, bindings)} IS NOT DISTINCT FROM "
                    f"{_expr(node.get('right'), parameters, bindings)})"
                )
            if op is None:
                raise ValueError(f"unsupported expression operator {node.get('op')!r}")
            return (
                f"({_expr(node.get('left'), parameters, bindings)} {op} "
                f"{_expr(node.get('right'), parameters, bindings)})"
            )
        if kind == "unary":
            op = normalize_operator(str(node.get("op") or ""))
            operand = _expr(node.get("operand"), parameters, bindings)
            if op == "not":
                return f"(NOT {operand})"
            if op == "negate":
                return f"(-{operand})"
            raise ValueError(f"unsupported expression operator {node.get('op')!r}")
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
