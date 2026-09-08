"""Portable DTCS compiler backed by Apache DataFusion."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from etlantic.transform.capabilities import (
    match_requirements,
    merge_requirements,
    portable_shape_findings,
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
    TransformPushdownFinding,
    TransformSupportFinding,
    TransformSupportReport,
)
from etlantic.transform.portable_baseline import (
    BASELINE_FUNCTIONS,
    BASELINE_OPERATORS,
    BASELINE_TYPES,
    KERNEL_ACTIONS,
    RELATIONAL_ACTIONS,
    baseline_manifest,
    normalize_action,
    normalize_operator,
)
from etlantic.transform.protocol import KERNEL_PROFILE_V1, RELATIONAL_PROFILE_V1

__version__ = "0.49.0"

_ACTIONS = frozenset(KERNEL_ACTIONS + RELATIONAL_ACTIONS)
_FUNCTIONS = frozenset(BASELINE_FUNCTIONS)
_OPERATORS = frozenset(BASELINE_OPERATORS)


class DataFusionTransformCompiler:
    """Analyze, compile, and execute portable relational plans."""

    def __init__(self) -> None:
        caps = TransformCapabilities(
            profiles=frozenset({KERNEL_PROFILE_V1, RELATIONAL_PROFILE_V1}),
            actions=_ACTIONS,
            functions=_FUNCTIONS,
            operators=_OPERATORS,
            types=frozenset(BASELINE_TYPES),
            # DataFusion cannot represent the distinct missing/invalid states
            # in its scalar columns, so those requirements fail closed.
            semantic_modes=frozenset(),
            lazy=True,
            eager=True,
        )
        evidence = hashlib.sha256(
            json.dumps(
                {
                    "baseline": baseline_manifest(),
                    "capabilities": caps.to_dict(),
                    "implementation": "datafusion-native/1",
                },
                sort_keys=True,
            ).encode()
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
            inferred = requirements_from_plan(dict(definition), include_extended=True)
        except (TypeError, ValueError, AttributeError):
            inferred = None
        req = merge_requirements(requirements, inferred)
        report = match_requirements(req, self.info.capabilities)
        findings = list(report.findings)
        findings.extend(three_state_findings(definition, self.info.capabilities))
        findings.extend(window_frame_findings(definition))
        findings.extend(windowed_aggregate_findings(definition))
        findings.extend(portable_shape_findings(definition))
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
        pushdown_findings: list[TransformPushdownFinding] = []
        for index, _ in enumerate(definition.get("actions") or ()):
            pushdown_findings.extend(
                (
                    TransformPushdownFinding(
                        boundary=f"relational:{index}",
                        outcome="pushed_exact" if not findings else "unknown",
                        reason=(
                            "lowered to a DataFusion native logical plan"
                            if not findings
                            else "pushdown unavailable until support failures are resolved"
                        ),
                        physical_effects=("native_logical_plan",),
                        evidence_fingerprint=self.info.evidence_fingerprint,
                    ),
                    TransformPushdownFinding(
                        boundary=f"source:{index}",
                        outcome="not_applicable",
                        reason="connector source pushdown is outside the native plan contract",
                        evidence_fingerprint=self.info.evidence_fingerprint,
                    ),
                    TransformPushdownFinding(
                        boundary=f"sink:{index}",
                        outcome="not_applicable",
                        reason="sink pushdown is outside the native plan contract",
                        evidence_fingerprint=self.info.evidence_fingerprint,
                    ),
                )
            )
        pushdown = tuple(pushdown_findings)
        return TransformSupportReport(
            not findings,
            tuple(findings),
            self.info.evidence_fingerprint,
            pushdown,
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
        if isinstance(value, Mapping):
            if value.get("type") in {"missing", "invalid"}:
                raise ValueError("DataFusion cannot preserve missing/invalid literals")
            value = value.get("value")
        return lit(value)
    if kind == "binary":
        left, right = (
            _expr(node.get("left"), col, f, lit, params),
            _expr(node.get("right"), col, f, lit, params),
        )
        op = normalize_operator(str(node.get("op")))
        if op == "eq":
            return left == right
        if op == "not_eq":
            return left != right
        if op == "gt":
            return left > right
        if op == "gte":
            return left >= right
        if op == "lt":
            return left < right
        if op == "lte":
            return left <= right
        if op == "and":
            return left & right
        if op == "or":
            return left | right
        if op == "add":
            return left + right
        if op == "subtract":
            return left - right
        if op == "multiply":
            return left * right
        if op == "divide":
            return left / right
        if op == "modulo":
            return left % right
        if op == "null_safe_eq":
            return (left == right).fill_null(False) | (left.is_null() & right.is_null())
        raise ValueError(f"unsupported binary operator: {op}")
    if kind == "unary":
        value = _expr(node.get("operand"), col, f, lit, params)
        op = normalize_operator(str(node.get("op")))
        if op == "negate":
            return lit(0) - value
        if op == "not":
            return ~value
        raise ValueError(f"unsupported unary operator: {op}")
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
            if len(args) < 2:
                raise ValueError("dtcs:substr requires value and start")
            # DTCS uses a zero-based start; DataFusion substring is one-based.
            start = args[1] + lit(1)
            return (
                f.substring(args[0], start, args[2])
                if len(args) >= 3
                else f.substring(args[0], start)
            )
        if name == "dtcs:concat_ws":
            if len(args) < 2:
                raise ValueError("dtcs:concat_ws requires a separator and value")
            separator_node = (node.get("args") or [])[0]
            separator_value = (
                separator_node.get("value", {}).get("value")
                if isinstance(separator_node, Mapping)
                and separator_node.get("kind") == "literal"
                and isinstance(separator_node.get("value"), Mapping)
                else None
            )
            if not isinstance(separator_value, str):
                raise ValueError("DataFusion concat_ws requires a literal separator")
            return f.concat_ws(separator_value, *args[1:])
        if name in {"dtcs:if_null", "dtcs:coalesce"}:
            return f.coalesce(*args)
        if name == "dtcs:is_null":
            return args[0].is_null()
        if name == "dtcs:null_if":
            return f.when(args[0] == args[1], lit(None)).otherwise(args[0])
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
            if len(args) < 3 or len(args) % 2 == 0:
                raise ValueError(
                    "dtcs:case_when requires condition/value pairs and an else value"
                )
            result = args[-1]
            for i in range(len(args) - 3, -1, -2):
                result = f.when(args[i], args[i + 1]).otherwise(result)
            return result
        if fn is not None:
            return fn(*args)
        raise ValueError(f"unsupported function: {name}")
    raise ValueError(f"unsupported expression kind: {kind}")


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
    action = normalize_action(action)
    if action == "dtcs:filter":
        return source.filter(_expr(p.get("predicate"), col, f, lit, params))
    if action == "dtcs:project":
        expressions = []
        for item in p.get("fields") or []:
            if isinstance(item, Mapping):
                expressions.append(
                    _expr(item.get("expression"), col, f, lit, params).alias(
                        str(item.get("name") or item.get("alias"))
                    )
                )
            else:
                expressions.append(col(str(item)))
        return source.select(*expressions)
    if action == "dtcs:with_fields":
        out = source
        for assignment in p.get("assignments") or []:
            out = out.with_column(
                str(assignment.get("name")),
                _expr(assignment.get("expression"), col, f, lit, params),
            )
        return out
    if action == "dtcs:drop_fields":
        return source.drop(*[str(x) for x in p.get("fields") or p.get("columns") or []])
    if action == "dtcs:rename_fields":
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
                    col(
                        str(key.get("field") or key.get("column") or key.get("name"))
                    ).sort(
                        ascending=str(key.get("direction", "asc")).lower() != "desc",
                        nulls_first=(
                            bool(key.get("nullsFirst"))
                            if "nullsFirst" in key
                            else str(key.get("nulls", "last")).lower() == "first"
                        ),
                    )
                )
            else:
                exprs.append(col(str(key)).sort())
        return source.sort(*exprs)
    if action == "dtcs:distinct":
        return source.distinct()
    if action == "dtcs:deduplicate":
        fields = p.get("keys") or p.get("fields") or p.get("subset")
        if fields:
            raise ValueError(
                "DataFusion deduplicate key subsets require native support"
            )
        return source.distinct()
    if action == "dtcs:union":
        mode = str(p.get("mode", "byName")).lower()
        if mode not in {"byname", "byposition"}:
            raise ValueError(f"unsupported union mode: {mode}")
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
        if isinstance(left_key, list) or isinstance(right_key, list):
            if (
                not isinstance(left_key, list)
                or not isinstance(right_key, list)
                or len(left_key) != len(right_key)
            ):
                raise ValueError("join key arity mismatch")
            raise ValueError("DataFusion composite joins require native support")
        if str(p.get("collisionPolicy", "fail")).lower() != "fail":
            raise ValueError("only collisionPolicy=fail is supported")
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
        join_right_key = str(right_key) if right_key else None
        for n in right_names:
            if n not in left_names and n != join_right_key:
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
            if name == "dtcs:count_distinct":
                if arg is None:
                    raise ValueError("count_distinct requires an expression")
                aggregate = f.count(arg, distinct=True)
            else:
                fn = {
                    "dtcs:sum": f.sum,
                    "dtcs:average": f.avg,
                    "dtcs:min": f.min,
                    "dtcs:max": f.max,
                    "dtcs:count": f.count,
                    "dtcs:count_all": f.count,
                }.get(name)
                if fn is None:
                    raise ValueError(f"unsupported aggregate function: {name}")
                aggregate = fn(arg) if arg is not None else fn()
            if aggregate is None:
                raise ValueError(f"unsupported aggregate function: {name}")
            aggs.append(aggregate.alias(str(item.get("name") or name.split(":")[-1])))
        return source.aggregate(group, aggs)
    raise ValueError(f"unsupported action: {action}")
