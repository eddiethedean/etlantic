"""Pure-Python portable evaluator for the built-in local engine."""

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
)
from etlantic.transform.compiler import (
    CompiledTransform,
    TransformCapabilities,
    TransformCompileContext,
    TransformCompilerInfo,
    TransformExecutionContext,
    TransformOutputBundle,
    TransformPlanningContext,
    TransformSupportReport,
)
from etlantic.transform.protocol import KERNEL_PROFILE_V1, RELATIONAL_PROFILE_V1

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


class LocalTransformCompiler:
    def __init__(self) -> None:
        caps = TransformCapabilities(
            profiles=frozenset({KERNEL_PROFILE_V1, RELATIONAL_PROFILE_V1}),
            actions=_ACTIONS,
            functions=_FUNCTIONS,
            operators=frozenset(
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
            ),
            semantic_modes=frozenset({"three_state_distinct"}),
            lazy=False,
            eager=True,
        )
        self._info = TransformCompilerInfo(
            name="etlantic-local",
            version="0.49.0",
            engine="local",
            capabilities=caps,
            evidence_fingerprint=hashlib.sha256(
                json.dumps(caps.to_dict(), sort_keys=True).encode()
            ).hexdigest(),
        )

    @property
    def info(self):
        return self._info

    def analyze(
        self,
        definition: Mapping[str, Any],
        *,
        context: TransformPlanningContext,
        requirements: Mapping[str, Sequence[str]] | None = None,
    ) -> TransformSupportReport:
        req = merge_requirements(requirements, requirements_from_plan(dict(definition)))
        report = match_requirements(req, self.info.capabilities)
        findings = list(report.findings) + three_state_findings(
            definition, self.info.capabilities
        )
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
                context.pipeline_id,
                context.step_name,
                context.profile_name,
                context.engine,
            ),
            requirements=requirements,
        )
        if not report.supported:
            raise ValueError(
                "Cannot compile unsupported local plan: "
                + "; ".join(f.reason for f in report.findings)
            )
        text = json.dumps(definition, sort_keys=True, separators=(",", ":"))
        return CompiledTransform(
            self.info.name,
            self.info.version,
            "local",
            hashlib.sha256(text.encode()).hexdigest(),
            tuple((definition.get("outputs") or {}).keys()) or ("result",),
            tuple((definition.get("parameters") or {}).keys()),
            {
                "target_ir": "python-records/1",
                "evidence_fingerprint": self.info.evidence_fingerprint,
            },
            dict(definition),
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
        relations = {str(k): _rows(v) for k, v in inputs.items()}
        input_ids = list((plan.get("inputs") or {}).keys())
        if len(relations) == 1 and input_ids and input_ids[0] not in relations:
            relations[input_ids[0]] = next(iter(relations.values()))
        for index, action in enumerate(plan.get("actions") or []):
            kind = action.get("kind") or {}
            target = str(kind.get("target") or "")
            source = (
                relations.get(target) if target else next(iter(relations.values()), [])
            )
            out = _apply(
                source,
                str(kind.get("action") or ""),
                kind.get("parameters") or {},
                relations,
                parameters,
            )
            relations[str(kind.get("id") or action.get("id") or f"a{index}")] = out
        acts = plan.get("actions") or []
        fallback = str(
            (((acts[-1].get("kind") or {}).get("id")) if acts else None)
            or (input_ids[0] if input_ids else next(iter(relations), ""))
        )
        deps = (plan.get("requirements") or {}).get("dependencies") or []
        outputs = {}
        for port in compiled.output_ports:
            name = next(
                (str(d.get("from")) for d in deps if d.get("to") == port), fallback
            )
            outputs[port] = relations.get(name, relations.get(fallback, []))
        return TransformOutputBundle(
            valid=outputs,
            metrics={
                "engine": "local",
                "lazy": False,
                "evidence_fingerprint": self.info.evidence_fingerprint,
            },
        )


def _rows(value):
    if isinstance(value, list):
        return [dict(x) if isinstance(x, Mapping) else x for x in value]
    if hasattr(value, "to_dicts"):
        return value.to_dicts()
    return list(value) if value is not None else []


def _eval(node, row, params):
    if not isinstance(node, Mapping):
        return node
    k = node.get("kind")
    if k == "fieldRef":
        return (
            params.get(str(node.get("target")))
            if node.get("scope") == "parameter"
            else row.get(str(node.get("target")))
        )
    if k == "literal":
        v = node.get("value")
        return v.get("value") if isinstance(v, Mapping) else v
    if k == "unary":
        v = _eval(node.get("operand"), row, params)
        return -v if node.get("op") == "neg" else not bool(v)
    if k == "binary":
        a, b = (
            _eval(node.get("left"), row, params),
            _eval(node.get("right"), row, params),
        )
        op = node.get("op")
        if op == "and":
            return bool(a) and bool(b)
        if op == "or":
            return bool(a) or bool(b)
        if op == "null_safe_eq":
            return (a == b) or (a is None and b is None)
        return {
            "eq": lambda: a == b,
            "neq": lambda: a != b,
            "gt": lambda: a > b,
            "gte": lambda: a >= b,
            "lt": lambda: a < b,
            "lte": lambda: a <= b,
            "add": lambda: a + b,
            "sub": lambda: a - b,
            "mul": lambda: a * b,
            "div": lambda: a / b,
            "mod": lambda: a % b,
        }.get(op, lambda: False)()
    if k == "call":
        n = node.get("callee")
        a = [_eval(x, row, params) for x in node.get("args") or []]
        if n == "dtcs:lower":
            return str(a[0]).lower() if a[0] is not None else None
        if n == "dtcs:upper":
            return str(a[0]).upper() if a[0] is not None else None
        if n in {"dtcs:coalesce", "dtcs:if_null"}:
            return next((x for x in a if x is not None), None)
        if n == "dtcs:is_null":
            return a[0] is None
        if n == "dtcs:contains":
            return a[1] in a[0] if a[0] is not None and a[1] is not None else False
        if n == "dtcs:starts_with":
            return str(a[0]).startswith(str(a[1]))
        if n == "dtcs:ends_with":
            return str(a[0]).endswith(str(a[1]))
        if n == "dtcs:length":
            return len(a[0]) if a[0] is not None else None
        if n == "dtcs:concat":
            return "".join(str(x) for x in a if x is not None)
        if n == "dtcs:concat_ws":
            return str(a[0]).join(str(x) for x in a[1:] if x is not None)
        if n == "dtcs:replace":
            return str(a[0]).replace(str(a[1]), str(a[2]))
        if n == "dtcs:substr":
            return (
                str(a[0])[int(a[1]) : int(a[1]) + int(a[2])]
                if len(a) > 2
                else str(a[0])[int(a[1]) :]
            )
        if n == "dtcs:in":
            return a[0] in a[1:]
        if n == "dtcs:case_when":
            for i in range(0, len(a) - 1, 2):
                if a[i]:
                    return a[i + 1]
            return a[-1] if a else None
        if n == "dtcs:null_if":
            return None if a[0] == a[1] else a[0]
        import math

        return {
            "dtcs:abs": abs,
            "dtcs:round": round,
            "dtcs:floor": math.floor,
            "dtcs:ceil": math.ceil,
            "dtcs:power": pow,
            "dtcs:sqrt": math.sqrt,
            "dtcs:least": min,
            "dtcs:greatest": max,
        }.get(n, lambda *x: None)(*a)
    return None


def _apply(rows, action, p, relations, params):
    if action == "dtcs:filter":
        return [r for r in rows if _eval(p.get("predicate"), r, params)]
    if action == "dtcs:project":
        return [{str(k): r.get(str(k)) for k in p.get("fields") or []} for r in rows]
    if action == "dtcs:with_fields":
        return [
            {
                **r,
                **{
                    str(a.get("name")): _eval(a.get("expression"), r, params)
                    for a in p.get("assignments") or []
                },
            }
            for r in rows
        ]
    if action == "dtcs:drop":
        return [
            {
                k: v
                for k, v in r.items()
                if k not in set(p.get("fields") or p.get("columns") or [])
            }
            for r in rows
        ]
    if action == "dtcs:rename":
        m = p.get("mapping") or {}
        return [{str(m.get(k, k)): v for k, v in r.items()} for r in rows]
    if action == "dtcs:limit":
        return rows[: int(p.get("count", p.get("n", 0)))]
    if action in {"dtcs:distinct", "dtcs:deduplicate"}:
        out = []
        seen = set()
        for r in rows:
            key = tuple(sorted(r.items()))
            if key not in seen:
                seen.add(key)
                out.append(r)
        return out
    if action == "dtcs:sort":
        keys = p.get("keys") or p.get("fields") or []
        out = list(rows)
        for key in reversed(keys if isinstance(keys, list) else [keys]):
            name = key.get("field") if isinstance(key, Mapping) else key
            desc = (
                isinstance(key, Mapping)
                and str(key.get("direction", "asc")).lower() == "desc"
            )
            out.sort(
                key=lambda r: (r.get(str(name)) is None, r.get(str(name))), reverse=desc
            )
        return out
    if action == "dtcs:union":
        return rows + _rows(relations.get(str(p.get("other")), []))
    if action == "dtcs:join":
        right = _rows(relations.get(str(p.get("right")), []))
        lk = str(p.get("leftKey"))
        rk = str(p.get("rightKey") or lk)
        out = []
        for left_row in rows:
            for right_row in right:
                if left_row.get(lk) == right_row.get(rk):
                    out.append(
                        {
                            **left_row,
                            **{k: v for k, v in right_row.items() if k not in left_row},
                        }
                    )
        return out
    if action == "dtcs:aggregate":
        groups = p.get("groupBy") or []
        aggs = p.get("aggregates") or []
        buckets = {}
        for r in rows:
            buckets.setdefault(tuple(r.get(str(g)) for g in groups), []).append(r)
        out = []
        for key, members in buckets.items():
            item = {str(g): v for g, v in zip(groups, key, strict=True)}
            for a in aggs:
                expression = a.get("expression") or {}
                fn = (
                    a.get("function")
                    or a.get("callee")
                    or expression.get("callee")
                    or "dtcs:count_all"
                )
                args = expression.get("args") or []
                field = (
                    a.get("field")
                    or a.get("column")
                    or (
                        args[0].get("target")
                        if args and isinstance(args[0], Mapping)
                        else None
                    )
                )
                vals = [m.get(str(field)) for m in members] if field else members
                vals = [v for v in vals if v is not None]
                item[str(a.get("name") or fn.split(":")[-1])] = (
                    len(members)
                    if fn == "dtcs:count_all"
                    else len(vals)
                    if fn in {"dtcs:count", "dtcs:count_distinct"}
                    else sum(vals)
                    if fn == "dtcs:sum"
                    else (
                        sum(vals) / len(vals) if fn == "dtcs:average" and vals else None
                    )
                    if fn == "dtcs:average"
                    else min(vals)
                    if fn == "dtcs:min" and vals
                    else max(vals)
                    if fn == "dtcs:max" and vals
                    else None
                )
            out.append(item)
        return out
    return rows
