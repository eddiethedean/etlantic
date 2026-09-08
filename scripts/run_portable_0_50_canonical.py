#!/usr/bin/env python3
"""Run the unchanged authored 0.50 canonical pipeline on all seven engines."""

from __future__ import annotations

import asyncio
from typing import Any

from etlantic.testing.portable_transform_conformance import (
    default_frame_factory,
    normalize_rows,
    rows_from_frame,
)
from etlantic.transform.compiler import (
    TransformCompileContext,
    TransformExecutionContext,
    TransformPlanningContext,
)
from etlantic.transform.local_compiler import LocalTransformCompiler


def _plan() -> dict[str, Any]:
    return {
        "planIdentity": "dtcs.transform-plan/2",
        "inputs": {"orders": {}, "customers": {}, "bonus": {}},
        "actions": [
            {
                "id": "f",
                "kind": {
                    "id": "f",
                    "action": "dtcs:filter",
                    "target": "orders",
                    "parameters": {
                        "predicate": {
                            "kind": "binary",
                            "op": "gt",
                            "left": {
                                "kind": "fieldRef",
                                "scope": "field",
                                "target": "amount",
                            },
                            "right": {
                                "kind": "literal",
                                "value": {"type": "integer", "value": 0},
                            },
                        }
                    },
                },
            },
            {
                "id": "p",
                "kind": {
                    "id": "p",
                    "action": "dtcs:project",
                    "target": "f",
                    "parameters": {"fields": ["customer_id", "amount"]},
                },
            },
            {
                "id": "j",
                "kind": {
                    "id": "j",
                    "action": "dtcs:join",
                    "target": "p",
                    "parameters": {
                        "type": "left",
                        "right": "customers",
                        "leftKey": "customer_id",
                        "rightKey": "customer_id",
                        "collisionPolicy": "fail",
                    },
                },
            },
            {
                "id": "a",
                "kind": {
                    "id": "a",
                    "action": "dtcs:aggregate",
                    "target": "j",
                    "parameters": {
                        "groupBy": ["region"],
                        "aggregates": [
                            {
                                "name": "total",
                                "expression": {
                                    "kind": "call",
                                    "callee": "dtcs:sum",
                                    "args": [
                                        {
                                            "kind": "fieldRef",
                                            "scope": "field",
                                            "target": "amount",
                                        }
                                    ],
                                },
                            }
                        ],
                    },
                },
            },
            {
                "id": "u",
                "kind": {
                    "id": "u",
                    "action": "dtcs:union",
                    "target": "a",
                    "parameters": {"other": "bonus", "mode": "byName"},
                },
            },
            {
                "id": "s",
                "kind": {
                    "id": "s",
                    "action": "dtcs:sort",
                    "target": "u",
                    "parameters": {
                        "keys": [
                            {"column": "total", "direction": "desc", "nulls": "last"}
                        ]
                    },
                },
            },
            {
                "id": "d",
                "kind": {
                    "id": "d",
                    "action": "dtcs:deduplicate",
                    "target": "s",
                    "parameters": {},
                },
            },
            {
                "id": "l",
                "kind": {
                    "id": "l",
                    "action": "dtcs:limit",
                    "target": "d",
                    "parameters": {"count": 3},
                },
            },
        ],
        "outputs": {"result": {}},
        "requirements": {"dependencies": [{"from": "l", "to": "result"}]},
    }


def _inputs() -> dict[str, list[dict[str, Any]]]:
    return {
        "orders": [
            {"customer_id": 1, "amount": 10},
            {"customer_id": 2, "amount": 5},
            {"customer_id": 3, "amount": -1},
        ],
        "customers": [
            {"customer_id": 1, "region": "east"},
            {"customer_id": 2, "region": "west"},
        ],
        "bonus": [{"region": "north", "total": 99}],
    }


def _compilers() -> list[Any]:
    from etlantic_duckdb import create_transform_compiler as duckdb

    from etlantic_datafusion import create_transform_compiler as datafusion
    from etlantic_pandas import create_transform_compiler as pandas
    from etlantic_polars import create_transform_compiler as polars
    from etlantic_pyspark import create_transform_compiler as pyspark
    from etlantic_sql import create_transform_compiler as sql

    return [
        LocalTransformCompiler(),
        polars(),
        pandas(),
        sql(),
        pyspark(),
        datafusion(),
        duckdb(),
    ]


def main() -> int:
    plan = _plan()
    expected = normalize_rows(
        [
            {"region": "north", "total": 99},
            {"region": "east", "total": 10},
            {"region": "west", "total": 5},
        ]
    )
    for compiler in _compilers():
        factory = default_frame_factory(compiler.info.engine)
        try:
            planning = TransformPlanningContext(
                "qualification", "canonical", "qualification", compiler.info.engine
            )
            report = compiler.analyze(plan, context=planning)
            if not report.supported:
                raise AssertionError(f"{compiler.info.engine}: {report.findings!r}")
            compiled = compiler.compile(
                plan,
                context=TransformCompileContext(
                    "qualification",
                    "plan",
                    "canonical",
                    "qualification",
                    compiler.info.engine,
                ),
            )
            metadata: dict[str, Any] = {}
            session = getattr(
                getattr(factory, "_etlantic_handle", None), "session", None
            )
            if session is not None:
                metadata["spark_session"] = session
            bundle = asyncio.run(
                compiler.execute(
                    compiled,
                    inputs={name: factory(rows) for name, rows in _inputs().items()},
                    parameters={},
                    context=TransformExecutionContext(
                        "qualification",
                        "qualification",
                        "plan",
                        "canonical",
                        compiler.info.engine,
                        metadata=metadata,
                    ),
                )
            )
            actual = normalize_rows(rows_from_frame(bundle.valid["result"]))
            if actual != expected:
                raise AssertionError(
                    f"{compiler.info.engine}: normalized canonical result diverged"
                )
            print(f"{compiler.info.engine}: pass")
        finally:
            provider = getattr(factory, "_etlantic_provider", None)
            handle = getattr(factory, "_etlantic_handle", None)
            resource_context = getattr(factory, "_etlantic_ctx", None)
            if provider and handle and resource_context:
                provider.release(handle, resource_context)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
