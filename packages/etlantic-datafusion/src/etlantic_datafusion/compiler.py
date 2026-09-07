"""Portable DTCS compiler backed by Apache DataFusion."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from etlantic.transform.capabilities import (
    match_requirements,
    merge_requirements,
    requirements_from_plan,
    three_state_findings,
    window_frame_findings,
    windowed_aggregate_findings,
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

__version__ = "0.49.0"

_ACTIONS = frozenset(
    {
        "dtcs:filter",
        "dtcs:project",
        "dtcs:with_fields",
        "dtcs:drop",
        "dtcs:rename",
        "dtcs:limit",
        "dtcs:sort",
        "dtcs:aggregate",
        "dtcs:join",
        "dtcs:union",
        "dtcs:distinct",
        "dtcs:deduplicate",
    }
)
_FUNCTIONS = frozenset(
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
        "dtcs:sum",
        "dtcs:average",
        "dtcs:min",
        "dtcs:max",
        "dtcs:count",
        "dtcs:count_all",
        "dtcs:count_distinct",
        "dtcs:in",
    }
)
_OPERATORS = frozenset(
    {
        "eq",
        "neq",
        "gt",
        "gte",
        "lt",
        "lte",
        "and",
        "or",
        "add",
        "sub",
        "mul",
        "div",
        "mod",
        "neg",
        "not",
        "in",
        "null_safe_eq",
    }
)


class DataFusionTransformCompiler:
    """Analyze, compile, and execute portable relational plans."""

    def __init__(self) -> None:
        caps = TransformCapabilities(
            profiles=frozenset({KERNEL_PROFILE_V1, RELATIONAL_PROFILE_V1}),
            actions=_ACTIONS,
            functions=_FUNCTIONS,
            operators=_OPERATORS,
            semantic_modes=frozenset({"three_state_distinct"}),
            lazy=True,
            eager=True,
        )
        evidence = hashlib.sha256(
            json.dumps(caps.to_dict(), sort_keys=True).encode()
        ).hexdigest()
        self._info = TransformCompilerInfo(
            name="etlantic-datafusion",
            version=__version__,
            engine="datafusion",
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
        try:
            inferred = requirements_from_plan(dict(definition))
        except (TypeError, ValueError, AttributeError):
            inferred = None
        req = merge_requirements(requirements, inferred)
        report = match_requirements(req, self.info.capabilities)
        findings = list(report.findings)
        findings.extend(three_state_findings(definition, self.info.capabilities))
        findings.extend(window_frame_findings(definition))
        findings.extend(windowed_aggregate_findings(definition))
        findings = [
            TransformSupportFinding(
                code=f.code,
                requirement=f.requirement,
                reason=f.reason,
                expression_path=f.expression_path,
                obligation=f.obligation,
                support=f.support,
                lowering_id=f.lowering_id,
                conditions=f.conditions,
                physical_effects=f.physical_effects,
                evidence_fingerprint=self.info.evidence_fingerprint,
            )
            for f in findings
        ]
        return TransformSupportReport(
            not findings, tuple(findings), self.info.evidence_fingerprint
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
                "Cannot compile unsupported DataFusion plan: "
                + "; ".join(f.reason for f in report.findings)
            )
        canonical = json.dumps(definition, sort_keys=True, separators=(",", ":"))
        return CompiledTransform(
            compiler_name=self.info.name,
            compiler_version=self.info.version,
            engine="datafusion",
            ir_fingerprint=hashlib.sha256(canonical.encode()).hexdigest(),
            output_ports=tuple((definition.get("outputs") or {}).keys()) or ("result",),
            parameter_names=tuple((definition.get("parameters") or {}).keys()),
            explain={
                "target_ir": "datafusion/1",
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
        try:
            import datafusion.functions as f  # noqa: I001
            from datafusion import col, lit
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "DataFusion execution requires etlantic-datafusion[datafusion]"
            ) from exc
        plan = compiled.native_plan
        if not isinstance(plan, dict):
            raise ValueError("DataFusion compiled transform has no closed plan")
        relations: dict[str, Any] = {}
        for name, value in inputs.items():
            relations[str(name)] = value
        input_ids = list((plan.get("inputs") or {}).keys())
        if len(relations) == 1 and input_ids and input_ids[0] not in relations:
            relations[input_ids[0]] = next(iter(relations.values()))
        for index, action in enumerate(plan.get("actions") or ()):
            kind = action.get("kind") or {}
            action_name = str(kind.get("action") or "")
            target = str(kind.get("target") or "")
            source = (
                relations.get(target)
                if target
                else next(iter(relations.values()), None)
            )
            if source is None:
                raise ValueError(f"missing DataFusion action relation {target!r}")
            out = _apply_action(
                source,
                action_name,
                kind.get("parameters") or {},
                relations,
                col,
                f,
                lit,
                parameters,
            )
            action_id = str(kind.get("id") or action.get("id") or f"a{index}")
            relations[action_id] = out
        actions = plan.get("actions") or []
        fallback = str(
            ((actions[-1].get("kind") or {}).get("id") if actions else None)
            or (input_ids[0] if input_ids else next(iter(relations), ""))
        )
        dependencies = (plan.get("requirements") or {}).get("dependencies") or []
        outputs: dict[str, Any] = {}
        for port in compiled.output_ports:
            source_name = next(
                (
                    str(d.get("from"))
                    for d in dependencies
                    if d.get("to") == port and d.get("from") is not None
                ),
                fallback,
            )
            if source_name not in relations:
                raise ValueError(f"cannot resolve DataFusion output {port!r}")
            outputs[port] = relations[source_name]
        return TransformOutputBundle(
            valid=outputs,
            metrics={
                "engine": "datafusion",
                "lazy": True,
                "evidence_fingerprint": self.info.evidence_fingerprint,
            },
        )


def _expr(
    node: Any, col: Any, f: Any, lit: Any, params: Mapping[str, Any] | None = None
) -> Any:
    if not isinstance(node, Mapping):
        return lit(node)
    kind = node.get("kind")
    if kind == "fieldRef":
        return (
            lit((params or {}).get(str(node.get("target"))))
            if node.get("scope") == "parameter"
            else col(str(node.get("target")))
        )
    if kind == "literal":
        value = node.get("value")
        return lit(value.get("value") if isinstance(value, Mapping) else value)
    if kind == "binary":
        left, right = (
            _expr(node.get("left"), col, f, lit, params),
            _expr(node.get("right"), col, f, lit, params),
        )
        op = str(node.get("op"))
        return {
            "eq": left == right,
            "neq": left != right,
            "gt": left > right,
            "gte": left >= right,
            "lt": left < right,
            "lte": left <= right,
            "and": left & right,
            "or": left | right,
            "add": left + right,
            "sub": left - right,
            "mul": left * right,
            "div": left / right,
            "mod": left % right,
            "null_safe_eq": (
                (left == right).fill_null(False) | (left.is_null() & right.is_null())
            ),
        }.get(op, left == right)
    if kind == "unary":
        value = _expr(node.get("operand"), col, f, lit, params)
        return -value if node.get("op") == "neg" else ~value
    if kind == "call":
        name = str(node.get("callee"))
        args = [_expr(a, col, f, lit, params) for a in node.get("args") or []]
        fn = {
            "dtcs:lower": f.lower,
            "dtcs:upper": f.upper,
            "dtcs:concat": f.concat,
            "dtcs:concat_ws": f.concat_ws,
            "dtcs:replace": f.replace,
            "dtcs:length": f.length,
            "dtcs:starts_with": f.starts_with,
            "dtcs:ends_with": f.ends_with,
            "dtcs:abs": f.abs,
            "dtcs:round": f.round,
            "dtcs:floor": f.floor,
            "dtcs:ceil": f.ceil,
            "dtcs:power": f.power,
            "dtcs:sqrt": f.sqrt,
            "dtcs:coalesce": f.coalesce,
            "dtcs:sum": f.sum,
            "dtcs:average": f.avg,
            "dtcs:min": f.min,
            "dtcs:max": f.max,
            "dtcs:count": f.count,
        }.get(name)
        if name == "dtcs:substr":
            return f.substring(*args) if len(args) >= 3 else f.substr(*args)
        if name in {"dtcs:if_null", "dtcs:coalesce"}:
            return f.coalesce(*args)
        if name == "dtcs:is_null":
            return args[0].is_null()
        if name == "dtcs:contains":
            return f.instr(*args) > lit(0)
        if name == "dtcs:in":
            return f.in_list(args[0], args[1:])
        if name in {"dtcs:least", "dtcs:greatest"}:
            result = args[0]
            for candidate in args[1:]:
                result = (
                    f.when(result <= candidate, result).otherwise(candidate)
                    if name.endswith("least")
                    else f.when(result >= candidate, result).otherwise(candidate)
                )
            return result
        if name == "dtcs:case_when":
            result = args[-1]
            for i in range(len(args) - 2, -1, -2):
                result = f.when(args[i], args[i + 1]).otherwise(result)
            return result
        if fn is not None:
            return fn(*args)
        return lit(None)
    return lit(None)


def _apply_action(
    source: Any,
    action: str,
    p: Mapping[str, Any],
    relations: Mapping[str, Any],
    col: Any,
    f: Any,
    lit: Any,
    params: Mapping[str, Any] | None = None,
) -> Any:
    if action == "dtcs:filter":
        return source.filter(_expr(p.get("predicate"), col, f, lit, params))
    if action == "dtcs:project":
        return source.select(*[col(str(x)) for x in p.get("fields") or []])
    if action == "dtcs:with_fields":
        out = source
        for assignment in p.get("assignments") or []:
            out = out.with_column(
                str(assignment.get("name")),
                _expr(assignment.get("expression"), col, f, lit, params),
            )
        return out
    if action == "dtcs:drop":
        return source.drop(*[str(x) for x in p.get("fields") or p.get("columns") or []])
    if action == "dtcs:rename":
        names = p.get("mapping") or p.get("fields") or {}
        schema = source.schema()
        return source.select(
            *[col(str(n)).alias(str(names.get(n, n))) for n in schema.names]
        )
    if action == "dtcs:limit":
        return source.limit(int(p.get("count", p.get("n", 0))))
    if action == "dtcs:sort":
        keys = p.get("keys") or p.get("fields") or []
        exprs = []
        for key in keys:
            if isinstance(key, Mapping):
                exprs.append(
                    col(str(key.get("field") or key.get("name"))).sort(
                        ascending=str(key.get("direction", "asc")).lower() != "desc",
                        nulls_first=bool(key.get("nullsFirst", True)),
                    )
                )
            else:
                exprs.append(col(str(key)).sort())
        return source.sort(*exprs)
    if action == "dtcs:distinct":
        return source.distinct()
    if action == "dtcs:deduplicate":
        return source.distinct()
    if action == "dtcs:union":
        return source.union(
            relations[str(p.get("other"))], distinct=bool(p.get("distinct", False))
        )
    if action == "dtcs:join":
        right = relations[str(p.get("right"))]
        how = str(p.get("type", "inner"))
        left_key, right_key = p.get("leftKey"), p.get("rightKey")
        # Qualify both sides to avoid DataFusion's ambiguous duplicate-column
        # resolution, then restore the logical names deterministically.
        left_names = list(source.schema().names)
        right_names = list(right.schema().names)
        left_tmp = source.select(*[col(n).alias("__etl_left_" + n) for n in left_names])
        right_tmp = right.select(
            *[col(n).alias("__etl_right_" + n) for n in right_names]
        )
        if left_key and right_key:
            joined = left_tmp.join(
                right_tmp,
                left_on=["__etl_left_" + str(left_key)],
                right_on=["__etl_right_" + str(right_key)],
                how=how,
            )
        else:
            joined = left_tmp.join(right_tmp, on=[], how=how)
        expressions = [col("__etl_left_" + n).alias(n) for n in left_names]
        for n in right_names:
            if n not in left_names:
                expressions.append(col("__etl_right_" + n).alias(n))
        return joined.select(*expressions)
    if action == "dtcs:aggregate":
        group = [col(str(x)) for x in p.get("groupBy") or p.get("group_by") or []]
        aggs = []
        for item in p.get("aggregates") or []:
            expression = item.get("expression") or {}
            name = str(
                item.get("function")
                or item.get("callee")
                or expression.get("callee")
                or "dtcs:count_all"
            )
            args = expression.get("args") or []
            field = (
                item.get("field")
                or item.get("column")
                or (
                    args[0].get("target")
                    if args and isinstance(args[0], Mapping)
                    else None
                )
            )
            arg = col(str(field)) if field else None
            fn = {
                "dtcs:sum": f.sum,
                "dtcs:average": f.avg,
                "dtcs:min": f.min,
                "dtcs:max": f.max,
                "dtcs:count": f.count,
            }.get(name, f.count)
            aggs.append(
                (fn(arg) if arg is not None else fn()).alias(
                    str(item.get("name") or name.split(":")[-1])
                )
            )
        return source.aggregate(group, aggs)
    return source
