"""Pure-Python portable evaluator for the built-in local engine."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from typing import Any, cast

from etlantic.transform.capabilities import (
    match_requirements,
    merge_requirements,
    portable_shape_findings,
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
    host_pushdown_findings,
    requirement_records_from_mapping,
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
from etlantic.transform.protocol import (
    INVALID,
    KERNEL_PROFILE_V1,
    MISSING,
    RELATIONAL_PROFILE_V1,
)

_ACTIONS = frozenset(KERNEL_ACTIONS + RELATIONAL_ACTIONS)
_FUNCTIONS = frozenset(BASELINE_FUNCTIONS)


class LocalTransformCompiler:
    def __init__(self) -> None:
        caps = TransformCapabilities(
            profiles=frozenset({KERNEL_PROFILE_V1, RELATIONAL_PROFILE_V1}),
            actions=_ACTIONS,
            functions=_FUNCTIONS,
            operators=frozenset(BASELINE_OPERATORS),
            types=frozenset(BASELINE_TYPES),
            # Missing/invalid values are rejected by the baseline analyser;
            # Local does not claim to preserve the distinct state in rows.
            semantic_modes=frozenset(),
            join_modes=frozenset(
                {"inner", "left", "right", "full", "semi", "anti", "cross"}
            ),
            union_modes=frozenset({"byName", "byPosition"}),
            collision_policies=frozenset({"fail"}),
            lazy=False,
            eager=True,
        )
        self._info = TransformCompilerInfo(
            name="etlantic-local",
            version="0.49.0",
            engine="local",
            capabilities=caps,
            evidence_fingerprint=hashlib.sha256(
                json.dumps(
                    {
                        "baseline": baseline_manifest(),
                        "capabilities": caps.to_dict(),
                        "implementation": "python-records/1",
                    },
                    sort_keys=True,
                ).encode()
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
        req = merge_requirements(
            requirements,
            requirements_from_plan(dict(definition), include_extended=True),
        )
        report = match_requirements(req, self.info.capabilities)
        findings = list(report.findings) + three_state_findings(
            definition, self.info.capabilities
        )
        findings.extend(portable_shape_findings(definition))
        return TransformSupportReport(
            not findings,
            tuple(findings),
            self.info.evidence_fingerprint,
            host_pushdown_findings(
                definition, evidence_fingerprint=self.info.evidence_fingerprint
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
        relations: dict[str, list[dict[str, Any]]] = {
            str(k): _rows(v) for k, v in inputs.items()
        }
        input_ids = list((plan.get("inputs") or {}).keys())
        if len(relations) == 1 and input_ids and input_ids[0] not in relations:
            relations[input_ids[0]] = next(iter(relations.values()))
        for index, action in enumerate(plan.get("actions") or []):
            kind = action.get("kind") or {}
            target = str(kind.get("target") or "")
            source = (
                relations.get(target, [])
                if target
                else next(iter(relations.values()), [])
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
            if name not in relations:
                raise ValueError(f"unresolved output dependency: {name}")
            outputs[port] = relations[name]
        return TransformOutputBundle(
            valid=outputs,
            metrics={
                "engine": "local",
                "lazy": False,
                "evidence_fingerprint": self.info.evidence_fingerprint,
            },
        )


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        values = value
    elif hasattr(value, "to_dicts"):
        return value.to_dicts()
    else:
        values = list(value) if value is not None else []
    return [
        dict(x)
        if isinstance(x, Mapping)
        else x.model_dump()
        if hasattr(x, "model_dump")
        else dict(x)
        for x in values
    ]


def _eval(node: Any, row: Mapping[str, Any], params: Mapping[str, Any]) -> Any:
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
        value = node.get("value")
        if isinstance(value, Mapping):
            kind = value.get("type")
            if kind == "missing":
                return MISSING
            if kind == "invalid":
                return INVALID
            return value.get("value")
        return value
    if k == "unary":
        v = _eval(node.get("operand"), row, params)
        op = normalize_operator(str(node.get("op")))
        if op == "negate":
            return None if v is None else -v
        if op == "not":
            return None if v is None else not bool(v)
        raise ValueError(f"unsupported unary operator: {op}")
    if k == "binary":
        a, b = (
            _eval(node.get("left"), row, params),
            _eval(node.get("right"), row, params),
        )
        op = normalize_operator(str(node.get("op")))
        if op == "null_safe_eq":
            return a == b
        if op in {"and", "or"}:
            if op == "and":
                return (
                    False
                    if a is False or b is False
                    else None
                    if a is None or b is None
                    else bool(a and b)
                )
            return (
                True
                if a is True or b is True
                else None
                if a is None or b is None
                else bool(a or b)
            )
        if (
            a is None
            or b is None
            or a is MISSING
            or b is MISSING
            or a is INVALID
            or b is INVALID
        ):
            return None
        operations = {
            "eq": lambda: a == b,
            "not_eq": lambda: a != b,
            "gt": lambda: a > b,
            "gte": lambda: a >= b,
            "lt": lambda: a < b,
            "lte": lambda: a <= b,
            "add": lambda: a + b,
            "subtract": lambda: a - b,
            "multiply": lambda: a * b,
            "divide": lambda: a / b,
            "modulo": lambda: a % b,
        }
        if op == "in":
            return a in b if isinstance(b, (list, tuple, set, frozenset)) else False
        if op not in operations:
            raise ValueError(f"unsupported binary operator: {op}")
        return operations[op]()
    if k == "call":
        n = node.get("callee")
        a = [_eval(x, row, params) for x in node.get("args") or []]
        # The portable baseline uses SQL-style null propagation for scalar
        # functions.  Null-aware functions are the explicit exceptions.
        if n not in {
            "dtcs:coalesce",
            "dtcs:if_null",
            "dtcs:is_null",
            "dtcs:case_when",
        } and any(value is None for value in a):
            return None
        if n == "dtcs:lower":
            return str(a[0]).lower() if a[0] is not None else None
        if n == "dtcs:upper":
            return str(a[0]).upper() if a[0] is not None else None
        if n in {"dtcs:coalesce", "dtcs:if_null"}:
            return next((x for x in a if x is not None), None)
        if n == "dtcs:is_null":
            return a[0] is None
        if n == "dtcs:contains":
            return a[1] in a[0]
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
            return None if a[0] is None else str(a[0]).replace(str(a[1]), str(a[2]))
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
        if n == "dtcs:abs":
            return abs(a[0]) if a and a[0] is not None else None
        if n == "dtcs:round":
            return round(a[0]) if len(a) == 1 else round(a[0], int(a[1]))
        if n == "dtcs:floor":
            return math.floor(a[0]) if a and a[0] is not None else None
        if n == "dtcs:ceil":
            return math.ceil(a[0]) if a and a[0] is not None else None
        if n == "dtcs:power":
            return (
                pow(a[0], a[1])
                if len(a) > 1 and a[0] is not None and a[1] is not None
                else None
            )
        if n == "dtcs:sqrt":
            return math.sqrt(a[0]) if a and a[0] is not None else None
        if n == "dtcs:least":
            return min(a)
        if n == "dtcs:greatest":
            return max(a)
        if n in {
            "dtcs:sum",
            "dtcs:average",
            "dtcs:min",
            "dtcs:max",
            "dtcs:count",
            "dtcs:count_all",
            "dtcs:count_distinct",
        }:
            raise ValueError(
                f"aggregate function is not valid in scalar expression: {n}"
            )
        raise ValueError(f"unsupported function: {n}")
    raise ValueError(f"unsupported expression kind: {k}")


def _apply(
    rows: list[dict[str, Any]],
    action: str,
    p: Mapping[str, Any],
    relations: Mapping[str, list[dict[str, Any]]],
    params: Mapping[str, Any],
) -> list[dict[str, Any]]:
    action = normalize_action(action)
    if action == "dtcs:filter":
        return [r for r in rows if _eval(p.get("predicate"), r, params) is True]
    if action == "dtcs:project":
        out = []
        for row in rows:
            projected: dict[str, Any] = {}
            for field in p.get("fields") or []:
                if isinstance(field, Mapping):
                    name = str(field.get("name") or field.get("alias"))
                    projected[name] = _eval(field.get("expression"), row, params)
                else:
                    name = str(field)
                    projected[name] = row.get(name)
            out.append(projected)
        return out
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
    if action == "dtcs:drop_fields":
        return [
            {
                k: v
                for k, v in r.items()
                if k not in set(p.get("fields") or p.get("columns") or [])
            }
            for r in rows
        ]
    if action == "dtcs:rename_fields":
        m = p.get("mapping") or {}
        return [{str(m.get(k, k)): v for k, v in r.items()} for r in rows]
    if action == "dtcs:limit":
        return rows[: int(p.get("count", p.get("n", 0)))]
    if action in {"dtcs:distinct", "dtcs:deduplicate"}:
        fields = p.get("keys") or p.get("fields") or p.get("subset")
        key_fields = [
            str(x.get("field") or x.get("column")) if isinstance(x, Mapping) else str(x)
            for x in fields or []
        ]
        out = []
        seen = set()
        for r in rows:
            values = (
                tuple((k, repr(r.get(k))) for k in key_fields)
                if key_fields
                else tuple((k, repr(v)) for k, v in sorted(r.items()))
            )
            key = repr(values)
            if key not in seen:
                seen.add(key)
                out.append(r)
        return out
    if action == "dtcs:sort":
        keys = p.get("keys") or p.get("fields") or []
        out = list(rows)
        for key in reversed(keys if isinstance(keys, list) else [keys]):
            name = (
                (key.get("field") or key.get("column") or key.get("name"))
                if isinstance(key, Mapping)
                else key
            )
            desc = (
                isinstance(key, Mapping)
                and str(key.get("direction", "asc")).lower() == "desc"
            )
            nulls = (
                str(key.get("nulls", "last")) if isinstance(key, Mapping) else "last"
            )
            if nulls == "first":
                non_null = [r for r in out if r.get(str(name)) is not None]
                null_rows = [r for r in out if r.get(str(name)) is None]
                non_null.sort(key=lambda r: cast(Any, r.get(str(name))), reverse=desc)
                out = null_rows + non_null
            else:
                non_null = [r for r in out if r.get(str(name)) is not None]
                null_rows = [r for r in out if r.get(str(name)) is None]
                non_null.sort(key=lambda r: cast(Any, r.get(str(name))), reverse=desc)
                out = non_null + null_rows
        return out
    if action == "dtcs:union":
        right = relations.get(str(p.get("other")), [])
        mode = str(p.get("mode", "byName")).lower()
        left_names = list(dict.fromkeys(k for row in rows for k in row))
        right_names = list(dict.fromkeys(k for row in right for k in row))
        allow_missing = bool(p.get("allowMissingColumns", False))
        if mode == "byposition":
            if allow_missing:
                raise ValueError(
                    "allowMissingColumns is not supported for byPosition unions"
                )
            if left_names and right_names and len(left_names) != len(right_names):
                raise ValueError(
                    "byPosition union inputs have incompatible field counts"
                )
            names = left_names or right_names
            if any(len(row) != len(names) for row in [*rows, *right]):
                raise ValueError("byPosition union rows have incompatible field counts")
            return rows + [
                {name: value for name, value in zip(names, r.values(), strict=True)}
                for r in right
            ]
        names = list(dict.fromkeys([*left_names, *right_names]))
        if not allow_missing and rows and right and set(left_names) != set(right_names):
            raise ValueError("union inputs have incompatible fields")
        return [{name: r.get(name) for name in names} for r in [*rows, *right]]
    if action == "dtcs:join":
        right = relations.get(str(p.get("right")), [])
        how = str(p.get("type", "inner")).lower()
        if how == "outer":
            how = "full"
        if how not in {"inner", "left", "right", "full", "semi", "anti", "cross"}:
            raise ValueError(f"unsupported join type: {how}")
        left_keys = p.get("leftKey") or p.get("leftKeys")
        right_keys = p.get("rightKey") or p.get("rightKeys") or left_keys
        left_keys = [left_keys] if isinstance(left_keys, str) else list(left_keys or [])
        right_keys = (
            [right_keys] if isinstance(right_keys, str) else list(right_keys or [])
        )
        null_safe = bool(p.get("nullSafe", False))

        def matches(left_row: Mapping[str, Any], right_row: Mapping[str, Any]) -> bool:
            if how == "cross":
                return True
            if len(left_keys) != len(right_keys):
                raise ValueError("join key arity mismatch")
            pairs = zip(left_keys, right_keys, strict=True)
            for left_key, right_key in pairs:
                a, b = left_row.get(str(left_key)), right_row.get(str(right_key))
                if a is None or b is None:
                    if not (null_safe and a is None and b is None):
                        return False
                elif a != b:
                    return False
            return True

        collision = str(p.get("collisionPolicy", "fail")).lower()
        left_fields = {k for row in rows for k in row}
        right_fields = {k for row in right for k in row}
        collisions = left_fields & right_fields
        if collision != "fail":
            raise ValueError("only collisionPolicy=fail is supported")
        collisions -= {
            str(left_key)
            for left_key, right_key in zip(left_keys, right_keys, strict=True)
            if str(left_key) == str(right_key)
        }
        if collisions and how not in {"semi", "anti"}:
            raise ValueError(f"join field collision: {sorted(collisions)}")
        out: list[dict[str, Any]] = []
        matched_right: set[int] = set()
        for left_row in rows:
            matches_for_left = [
                (i, rr) for i, rr in enumerate(right) if matches(left_row, rr)
            ]
            if (how == "semi" and matches_for_left) or (
                how == "anti" and not matches_for_left
            ):
                out.append(dict(left_row))
            elif how not in {"semi", "anti"}:
                for i, right_row in matches_for_left:
                    matched_right.add(i)
                    out.append({**left_row, **right_row})
                if how in {"left", "full"} and not matches_for_left:
                    right_only = right_fields - left_fields
                    out.append({**left_row, **{k: None for k in right_only}})
        if how in {"right", "full"}:
            for i, right_row in enumerate(right):
                if i not in matched_right:
                    left_only = left_fields - right_fields
                    out.append({**{k: None for k in left_only}, **right_row})
        return out
    if action == "dtcs:aggregate":
        groups = p.get("groupBy") or []
        aggs = p.get("aggregates") or p.get("aggregations") or []
        buckets: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
        for r in rows:
            buckets.setdefault(tuple(r.get(str(g)) for g in groups), []).append(r)
        if not buckets and not groups:
            buckets[()] = []
        out: list[dict[str, Any]] = []
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
                vals: list[Any] = list(
                    [_eval(args[0], m, params) for m in members]
                    if args
                    else ([m.get(str(field)) for m in members] if field else members)
                )
                vals = [v for v in vals if v is not None]
                item[str(a.get("name") or fn.split(":")[-1])] = (
                    len(members)
                    if fn == "dtcs:count_all"
                    else len(vals)
                    if fn == "dtcs:count"
                    else len(set(repr(v) for v in vals))
                    if fn == "dtcs:count_distinct"
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
    raise ValueError(f"unsupported action: {action}")
