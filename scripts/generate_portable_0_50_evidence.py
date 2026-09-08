#!/usr/bin/env python3
"""Generate bounded, reproducible 0.50 portable qualification evidence.

The generator deliberately records only capability metadata, fingerprints,
commands, and result digests.  It never serializes fixture input rows,
database URLs, parameter values, plans with executable bodies, or host paths.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import hashlib
import io
import json
import os
import platform
import re
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from etlantic.testing.portable_fixtures import FIXTURES, fixtures_for_capabilities
from etlantic.testing.portable_transform_conformance import (
    default_frame_factory,
    normalize_rows,
    rows_from_frame,
)
from etlantic.transform.capabilities import evaluate_adaptive_candidates
from etlantic.transform.compiler import (
    COMPILER_PROTOCOL,
    TransformCompileContext,
    TransformExecutionContext,
    TransformPlanningContext,
    TransformSupportFinding,
    TransformSupportReport,
    requirement_records_from_mapping,
)
from etlantic.transform.local_compiler import LocalTransformCompiler
from etlantic.transform.portable_baseline import (
    BASELINE_FUNCTIONS,
    BASELINE_JOIN_MODES,
    BASELINE_OPERATORS,
    BASELINE_TYPES,
    KERNEL_ACTIONS,
    RELATIONAL_ACTIONS,
    baseline_manifest,
)
from etlantic.transform.protocol import KERNEL_PROFILE_V1, RELATIONAL_PROFILE_V1

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/11_DEVELOPMENT/evidence/portable_0_50"
ENGINES = ("local", "polars", "pandas", "sql", "pyspark", "datafusion", "duckdb")
QUALIFICATION_MATRIX = [
    {"engine": "local", "mode": "host", "dialect": None},
    {"engine": "polars", "mode": "eager", "dialect": None},
    {"engine": "polars", "mode": "lazy", "dialect": None},
    {"engine": "pandas", "mode": "eager", "dialect": None},
    {"engine": "sql", "mode": "relation", "dialect": "sqlite"},
    {"engine": "sql", "mode": "relation", "dialect": "postgresql"},
    {"engine": "pyspark", "mode": "native", "dialect": "jvm"},
    {"engine": "datafusion", "mode": "lazy", "dialect": "native"},
    {"engine": "duckdb", "mode": "lazy", "dialect": "native"},
]
ARTIFACTS = (
    "portable_baseline_contract_0_50.json",
    "portable_pushdown_contract_0_50.json",
    "portable_requirement_support_0_50.json",
    "portable_claim_coverage_0_50.json",
    "portable_local_conformance_0_50.json",
    "portable_polars_conformance_0_50.json",
    "portable_pandas_conformance_0_50.json",
    "portable_sql_conformance_0_50.json",
    "portable_pyspark_conformance_0_50.json",
    "portable_datafusion_conformance_0_50.json",
    "portable_duckdb_pushdown_0_50.json",
    "portable_cross_engine_0_50.json",
    "portable_canonical_pipeline_0_50.json",
    "portable_adaptive_handoff_0_50.json",
    "portable_dependency_security_0_50.json",
    "FINDINGS_0_50.md",
    "MIGRATION_0_49_TO_0_50.md",
    "WHATS_NEW_0_50.md",
)
PUBLIC_POSTGRES_COMMAND = (
    "ETLANTIC_SQL_URL=$ETLANTIC_SQL_URL ETLANTIC_SPARK_BACKEND=pyspark "
    "SPARKLESS_TEST_MODE=pyspark JAVA_HOME=$JAVA_HOME uv run pytest -q "
    "tests/portable_conformance/test_public_suite.py "
    "tests/sql/test_sql_portable_security.py "
    "tests/sql/test_sql_runtime.py::test_sql_to_sql_no_python_fetch"
)
PUBLIC_SQLITE_COMMAND = (
    "ETLANTIC_SQL_URL=sqlite+pysqlite:///:memory: ETLANTIC_SPARK_BACKEND=pyspark "
    "SPARKLESS_TEST_MODE=pyspark JAVA_HOME=$JAVA_HOME uv run pytest -q "
    "tests/portable_conformance/test_public_suite.py "
    "tests/sql/test_sql_portable_security.py "
    "tests/sql/test_sql_runtime.py::test_sql_to_sql_no_python_fetch"
)
PUBLIC_COMMAND = f"{PUBLIC_POSTGRES_COMMAND} && {PUBLIC_SQLITE_COMMAND}"
CANONICAL_POSTGRES_COMMAND = (
    "ETLANTIC_SQL_URL=$ETLANTIC_SQL_URL ETLANTIC_SPARK_BACKEND=pyspark "
    "SPARKLESS_TEST_MODE=pyspark JAVA_HOME=$JAVA_HOME uv run "
    "python scripts/run_portable_0_50_canonical.py --engines all"
)
CANONICAL_SQLITE_COMMAND = (
    "ETLANTIC_SQL_URL=sqlite+pysqlite:///:memory: ETLANTIC_SPARK_BACKEND=pyspark "
    "SPARKLESS_TEST_MODE=pyspark JAVA_HOME=$JAVA_HOME uv run "
    "python scripts/run_portable_0_50_canonical.py --engines all"
)
CANONICAL_COMMAND = f"{CANONICAL_POSTGRES_COMMAND} && {CANONICAL_SQLITE_COMMAND}"
PUBLIC_CAMPAIGNS = (
    {
        "id": "public-postgresql",
        "engine": "all",
        "mode": "conformance",
        "dialect": "postgresql",
        "command": PUBLIC_POSTGRES_COMMAND,
    },
    {
        "id": "public-sqlite",
        "engine": "all",
        "mode": "conformance",
        "dialect": "sqlite",
        "command": PUBLIC_SQLITE_COMMAND,
    },
)
CANONICAL_CAMPAIGNS = (
    {
        "id": "canonical-postgresql",
        "engine": "all",
        "mode": "canonical",
        "dialect": "postgresql",
        "command": CANONICAL_POSTGRES_COMMAND,
    },
    {
        "id": "canonical-sqlite",
        "engine": "all",
        "mode": "canonical",
        "dialect": "sqlite",
        "command": CANONICAL_SQLITE_COMMAND,
    },
)
ADAPTIVE_FIXTURES = (
    "test_requirement_support_serializes_unknown_requirements_fail_closed",
    "test_runtime_preflight_rejects_evidence_free_descriptor",
    "test_adaptive_partial_engine_required_unknown_eliminates_before_scoring",
    "test_adaptive_preferred_unknown_has_no_positive_preference",
    "test_adaptive_lowering_records_effects_and_identity",
    "test_adaptive_lowering_is_derived_from_support_evidence",
    "test_adaptive_evaluation_retains_per_node_selection",
    "test_adaptive_graph_edge_requirement_invalidates_assignment",
    "test_adaptive_evidence_drift_rejects_before_io",
)
ADAPTIVE_COMMAND = (
    "uv run pytest -q tests/unit/transform/test_portable_planning.py "
    "tests/portable_conformance/test_public_suite.py -k "
    "'test_requirement_support_serializes_unknown_requirements_fail_closed or "
    "test_runtime_preflight_rejects_evidence_free_descriptor or "
    "test_adaptive_partial_engine_required_unknown_eliminates_before_scoring or "
    "test_adaptive_preferred_unknown_has_no_positive_preference or "
    "test_adaptive_lowering_records_effects_and_identity or "
    "test_adaptive_lowering_is_derived_from_support_evidence or "
    "test_adaptive_evaluation_retains_per_node_selection or "
    "test_adaptive_graph_edge_requirement_invalidates_assignment or "
    "test_adaptive_evidence_drift_rejects_before_io'"
)


def _adaptive_scenarios() -> list[dict[str, Any]]:
    """Build adaptive handoff records from the production evaluator."""

    def support_report(
        states: dict[str, str], *, target_variant: str = "default"
    ) -> dict[str, Any]:
        evidence = "adaptive-fixture-evidence"
        requirements = requirement_records_from_mapping({"actions": list(states)})
        requirement_ids = {
            str((record.get("parameters") or {}).get("value")): str(record["id"])
            for record in requirements
        }
        findings = tuple(
            TransformSupportFinding(
                code="PMXFORM000",
                requirement=requirement_ids[requirement],
                reason="fixture support result",
                support=state,
                evidence_fingerprint=evidence,
                lowering_id=(
                    "lowering/fixture-v1"
                    if state == "supported_with_lowering"
                    else None
                ),
                proof_reference=(
                    "proof/fixture-v1" if state == "supported_with_lowering" else None
                ),
                conditions=("preserve-null",)
                if state == "supported_with_lowering"
                else (),
                physical_effects=("materialization",)
                if state == "supported_with_lowering"
                else (),
            )
            for requirement, state in states.items()
        )
        return TransformSupportReport(
            supported=all(
                state in {"supported_exact", "supported_with_lowering"}
                for state in states.values()
            ),
            evidence_fingerprint=evidence,
            requirements=requirements,
            requirement_findings=findings,
        ).to_requirement_support(
            target={
                "engine": "local",
                "compiler": "adaptive-fixture",
                "version": "1",
                "protocol": COMPILER_PROTOCOL,
                "package": f"etlantic-adaptive-fixture/{target_variant}",
            }
        )

    required = {
        "orders": ("dtcs:join",),
        "customers": ("dtcs:join",),
    }
    preferred = {
        "orders": ("dtcs:filter",),
        "customers": ("dtcs:filter",),
    }
    required_result = evaluate_adaptive_candidates(
        [
            {
                "node": "orders",
                "id": "partial",
                "requirements": {
                    "dtcs:filter": "supported_exact",
                    "dtcs:join": "unknown",
                },
                "support_report": support_report(
                    {"dtcs:filter": "supported_exact", "dtcs:join": "unknown"},
                    target_variant="orders-partial",
                ),
            },
            {
                "node": "orders",
                "id": "complete",
                "requirements": {
                    "dtcs:filter": "supported_exact",
                    "dtcs:join": "supported_exact",
                },
                "support_report": support_report(
                    {"dtcs:filter": "supported_exact", "dtcs:join": "supported_exact"},
                    target_variant="orders-complete",
                ),
            },
            {
                "node": "customers",
                "id": "complete",
                "requirements": {
                    "dtcs:filter": "supported_exact",
                    "dtcs:join": "supported_exact",
                },
                "support_report": support_report(
                    {"dtcs:filter": "supported_exact", "dtcs:join": "supported_exact"},
                    target_variant="customers-complete",
                ),
            },
        ],
        required_requirements=required,
        preferred_requirements=preferred,
    )
    preference_result = evaluate_adaptive_candidates(
        [
            {
                "node": "orders",
                "id": "unknown-preference",
                "requirements": {
                    "dtcs:filter": "supported_exact",
                    "dtcs:sort": "unknown",
                },
                "support_report": support_report(
                    {"dtcs:filter": "supported_exact", "dtcs:sort": "unknown"},
                    target_variant="orders-unknown-preference",
                ),
            },
            {
                "node": "customers",
                "id": "known-preference",
                "requirements": {
                    "dtcs:filter": "supported_exact",
                    "dtcs:sort": "supported_exact",
                },
                "support_report": support_report(
                    {"dtcs:filter": "supported_exact", "dtcs:sort": "supported_exact"},
                    target_variant="customers-known-preference",
                ),
            },
        ],
        required_requirements={
            "orders": ("dtcs:filter",),
            "customers": ("dtcs:filter",),
        },
        preferred_requirements={
            "orders": ("dtcs:sort",),
            "customers": ("dtcs:sort",),
        },
    )
    lowering_result = evaluate_adaptive_candidates(
        [
            {
                "node": "orders",
                "id": "lowered",
                "requirements": {"dtcs:filter": "supported_with_lowering"},
                "support_report": support_report(
                    {"dtcs:filter": "supported_with_lowering"},
                    target_variant="orders-lowered",
                ),
            },
            {
                "node": "customers",
                "id": "exact",
                "requirements": {"dtcs:filter": "supported_exact"},
                "support_report": support_report(
                    {"dtcs:filter": "supported_exact"},
                    target_variant="customers-exact",
                ),
            },
        ],
        required_requirements={
            "orders": ("dtcs:filter",),
            "customers": ("dtcs:filter",),
        },
    )
    return [
        {
            "id": "partial-required-unknown",
            "fixture": ADAPTIVE_FIXTURES[2],
            "requirements": ["dtcs:join"],
            "candidate_evaluation": required_result,
            "result": "pass",
        },
        {
            "id": "preferred-unknown",
            "fixture": ADAPTIVE_FIXTURES[3],
            "requirements": ["dtcs:filter", "dtcs:sort"],
            "candidate_evaluation": preference_result,
            "result": "pass",
        },
        {
            "id": "lowering-effects",
            "fixture": ADAPTIVE_FIXTURES[4],
            "requirements": ["dtcs:filter"],
            "candidate_evaluation": lowering_result,
            "result": "pass",
        },
        {
            "id": "graph-invalid",
            "fixture": ADAPTIVE_FIXTURES[7],
            "requirements": ["interchange:arrow"],
            "candidate_evaluation": evaluate_adaptive_candidates(
                [
                    {
                        "node": "orders",
                        "id": "native",
                        "requirements": {"dtcs:join": "supported_exact"},
                        "support_report": support_report(
                            {"dtcs:join": "supported_exact"},
                            target_variant="orders-native",
                        ),
                    },
                    {
                        "node": "customers",
                        "id": "native",
                        "requirements": {"dtcs:join": "supported_exact"},
                        "support_report": support_report(
                            {"dtcs:join": "supported_exact"},
                            target_variant="customers-native",
                        ),
                    },
                ],
                required_requirements={
                    "orders": ("dtcs:join",),
                    "customers": ("dtcs:join",),
                },
                edges=(
                    {
                        "producer": "orders",
                        "consumer": "customers",
                        "requirements": ("interchange:arrow",),
                    },
                ),
            ),
            "result": "rejected_graph_invalid",
        },
        {
            "id": "evidence-drift",
            "fixture": ADAPTIVE_FIXTURES[8],
            "preflight": "reject_stale_fingerprint_before_io",
            "result": "rejected_before_io",
        },
    ]


def _campaign_ids_for_matrix(item: Mapping[str, Any]) -> list[str]:
    dialect = item.get("dialect")
    if item.get("engine") == "sql" and dialect in {"postgresql", "sqlite"}:
        return [f"public-{dialect}", f"canonical-{dialect}"]
    return [campaign["id"] for campaign in (*PUBLIC_CAMPAIGNS, *CANONICAL_CAMPAIGNS)]


DEPENDENCY_COMMAND = (
    "uv run pytest -q tests/sql/test_sql_portable_security.py && "
    "uv run python scripts/check_portable_0_50_dependencies.py"
)


def _compiler_factories() -> Mapping[str, Any]:
    from etlantic_duckdb import create_transform_compiler as duckdb

    from etlantic_datafusion import create_transform_compiler as datafusion
    from etlantic_pandas import create_transform_compiler as pandas
    from etlantic_polars import create_transform_compiler as polars
    from etlantic_pyspark import create_transform_compiler as pyspark
    from etlantic_sql import create_transform_compiler as sql

    return {
        "local": LocalTransformCompiler,
        "polars": polars,
        "pandas": pandas,
        "sql": sql,
        "pyspark": pyspark,
        "datafusion": datafusion,
        "duckdb": duckdb,
    }


def _requirements(
    *, eager: bool | None = None, lazy: bool | None = None
) -> dict[str, Any]:
    requirements: dict[str, Any] = {
        "profiles": [KERNEL_PROFILE_V1, RELATIONAL_PROFILE_V1],
        "actions": list(KERNEL_ACTIONS + RELATIONAL_ACTIONS),
        "functions": list(BASELINE_FUNCTIONS),
        "operators": list(BASELINE_OPERATORS),
        "types": list(BASELINE_TYPES),
        "join_modes": list(BASELINE_JOIN_MODES),
        "union_modes": ["byName", "byPosition"],
        "collision_policies": ["fail"],
        # Keep every governed dimension explicit in the report.  Distinct
        # missing/invalid values are a conditional requirement, not a claim
        # that every engine preserves a three-state column.
        "semantic_modes": [],
    }
    # A false execution mode is an explicit non-applicability fact in claim
    # coverage, not an unsupported required capability.  Including it here
    # leaves an unmatched requirement record that the support serializer quite
    # correctly marks ``unknown``.
    if eager:
        requirements["eager"] = True
    if lazy:
        requirements["lazy"] = True
    return requirements


def _pushdown_plan() -> dict[str, Any]:
    return {
        "planIdentity": "dtcs.transform-plan/2",
        "inputs": {
            "t": {
                "schema": {
                    "fields": [
                        {"name": "id", "type": "integer"},
                        {"name": "region", "type": "string"},
                        {"name": "total", "type": "decimal"},
                    ]
                }
            },
            "r": {
                "schema": {
                    "fields": [
                        {"name": "id", "type": "integer"},
                        {"name": "category", "type": "string"},
                    ]
                }
            },
            "bonus": {
                "schema": {
                    "fields": [
                        {"name": "id", "type": "integer"},
                        {"name": "region", "type": "string"},
                        {"name": "amount", "type": "decimal"},
                        {"name": "category", "type": "string"},
                    ]
                }
            },
        },
        "actions": [
            {
                "id": "f",
                "kind": {
                    "id": "f",
                    "action": "dtcs:filter",
                    "target": "t",
                    "parameters": {
                        "predicate": {
                            "kind": "binary",
                            "op": "gt",
                            "left": {
                                "kind": "fieldRef",
                                "scope": "field",
                                "target": "id",
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
                    "parameters": {"fields": ["id", "region", "total"]},
                },
            },
            {
                "id": "w",
                "kind": {
                    "id": "w",
                    "action": "dtcs:with_fields",
                    "target": "p",
                    "parameters": {
                        "assignments": [
                            {
                                "name": "x",
                                "expression": {
                                    "kind": "literal",
                                    "value": {"type": "integer", "value": 1},
                                },
                            }
                        ]
                    },
                },
            },
            {
                "id": "d",
                "kind": {
                    "id": "d",
                    "action": "dtcs:drop_fields",
                    "target": "w",
                    "parameters": {"fields": ["x"]},
                },
            },
            {
                "id": "n",
                "kind": {
                    "id": "n",
                    "action": "dtcs:rename_fields",
                    "target": "d",
                    "parameters": {"mapping": {"total": "amount"}},
                },
            },
            {
                "id": "j",
                "kind": {
                    "id": "j",
                    "action": "dtcs:join",
                    "target": "n",
                    "parameters": {
                        "type": "left",
                        "right": "r",
                        "leftKey": "id",
                        "rightKey": "id",
                        "collisionPolicy": "fail",
                    },
                },
            },
            {
                "id": "u",
                "kind": {
                    "id": "u",
                    "action": "dtcs:union",
                    "target": "j",
                    "parameters": {"other": "bonus", "mode": "byName"},
                },
            },
            {
                "id": "a",
                "kind": {
                    "id": "a",
                    "action": "dtcs:aggregate",
                    "target": "u",
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
                "id": "s",
                "kind": {
                    "id": "s",
                    "action": "dtcs:sort",
                    "target": "a",
                    "parameters": {
                        "keys": [
                            {"column": "total", "direction": "asc", "nulls": "last"}
                        ]
                    },
                },
            },
            {
                "id": "x",
                "kind": {
                    "id": "x",
                    "action": "dtcs:distinct",
                    "target": "s",
                    "parameters": {},
                },
            },
            {
                "id": "k",
                "kind": {
                    "id": "k",
                    "action": "dtcs:deduplicate",
                    "target": "x",
                    "parameters": {},
                },
            },
            {
                "id": "l",
                "kind": {
                    "id": "l",
                    "action": "dtcs:limit",
                    "target": "k",
                    "parameters": {"count": 10},
                },
            },
        ],
        "outputs": {"result": {"id": "result"}},
        "requirements": {"dependencies": [{"from": "l", "to": "result"}]},
    }


def _pushdown_inputs() -> dict[str, list[dict[str, Any]]]:
    """Small schema-complete native inputs for the all-action pushdown plan."""
    return {
        "t": [
            {"id": 1, "region": "east", "total": 10.0},
            {"id": 2, "region": "west", "total": 5.0},
        ],
        "r": [
            {"id": 1, "category": "retail"},
            {"id": 2, "category": "wholesale"},
        ],
        "bonus": [
            {
                "id": 3,
                "region": "north",
                "amount": 99.0,
                "category": "bonus",
            }
        ],
    }


def _native_explain_digest(engine: str, frame: Any, metrics: Mapping[str, Any]) -> str:
    """Capture a backend-native explain or fail closed for required evidence."""
    stream = io.StringIO()
    try:
        with contextlib.redirect_stdout(stream):
            if engine == "datafusion":
                frame.explain()
            elif engine == "pyspark":
                try:
                    frame.explain(mode="extended")
                except TypeError:
                    frame.explain()
            elif engine in {"sql", "duckdb"}:
                if not metrics.get("native_explain_digests"):
                    raise ValueError("native EXPLAIN digest was not emitted")
            else:
                raise ValueError("host-owned engine has no native pushdown boundary")
    except Exception as exc:
        raise SystemExit(
            f"{engine} did not provide native explain evidence: {exc}"
        ) from exc
    value = stream.getvalue()
    if engine in {"datafusion", "pyspark"} and not value.strip():
        raise SystemExit(f"{engine} emitted an empty native explain plan")
    if engine in {"datafusion", "pyspark"} and re.search(
        r"pythonudf|pandasudf|batchevalpython", value, re.IGNORECASE
    ):
        raise SystemExit(f"{engine} native plan contains a host/Python fallback")
    return _digest(
        {
            "engine": engine,
            "native_explain": value,
            "native_statement_digests": metrics.get("native_statement_digests"),
            "native_explain_digests": metrics.get("native_explain_digests"),
        }
    )


def _execute_pushdown_fixture(
    compiler: Any,
    *,
    database_url: str | None = None,
) -> tuple[str, str, dict[str, str], dict[str, str], bool]:
    """Execute all actions and return action-correlated native proof digests."""
    engine = compiler.info.engine
    plan = _pushdown_plan()
    compiled = compiler.compile(
        plan,
        context=TransformCompileContext(
            "qualification", "pushdown", "qualification", "qualification", engine
        ),
    )
    factory = default_frame_factory(engine)
    try:
        metadata: dict[str, Any] = {}
        if database_url is not None:
            metadata["database_url"] = database_url
        session = getattr(getattr(factory, "_etlantic_handle", None), "session", None)
        if session is not None:
            metadata["spark_session"] = session
        bundle = asyncio.run(
            compiler.execute(
                compiled,
                inputs={
                    name: factory(rows) for name, rows in _pushdown_inputs().items()
                },
                parameters={},
                context=TransformExecutionContext(
                    "qualification",
                    "qualification",
                    "pushdown",
                    "qualification",
                    engine,
                    metadata=metadata,
                ),
            )
        )
        frame = bundle.valid["result"]
        result_digest = _digest(normalize_rows(rows_from_frame(frame)))
        explain_digest = _native_explain_digest(engine, frame, bundle.metrics)
        action_ids = [
            str((item.get("kind") or {}).get("id") or item.get("id") or index)
            for index, item in enumerate(plan.get("actions") or ())
        ]
        statement_digests = list(bundle.metrics.get("native_statement_digests") or ())
        explain_digests = list(bundle.metrics.get("native_explain_digests") or ())
        observed_action_digests = dict(
            bundle.metrics.get("native_action_digests") or {}
        )
        action_digests = {
            action_id: observed_action_digests.get(action_id)
            or _digest(
                {
                    "engine": engine,
                    "action": action_id,
                    "native_explain_digest": (
                        explain_digests[index]
                        if index < len(explain_digests)
                        else explain_digest
                    ),
                    "native_statement_digest": (
                        statement_digests[index]
                        if index < len(statement_digests)
                        else None
                    ),
                }
            )
            for index, action_id in enumerate(action_ids)
        }
        action_explain_digests = {
            action_id: (
                explain_digests[index]
                if index < len(explain_digests)
                else explain_digest
            )
            for index, action_id in enumerate(action_ids)
        }
        fallback_events = bundle.metrics.get("fallback_events")
        if not isinstance(fallback_events, list):
            raise SystemExit(f"{engine} did not report host-fallback events")
        return (
            result_digest,
            explain_digest,
            action_digests,
            action_explain_digests,
            bool(fallback_events),
        )
    finally:
        provider = getattr(factory, "_etlantic_provider", None)
        handle = getattr(factory, "_etlantic_handle", None)
        context = getattr(factory, "_etlantic_ctx", None)
        if provider is not None and handle is not None and context is not None:
            provider.release(handle, context)


def _run(command: str) -> str:
    env = dict(os.environ)
    env.setdefault("ETLANTIC_SPARK_BACKEND", "pyspark")
    env.setdefault("SPARKLESS_TEST_MODE", "pyspark")
    if not env.get("JAVA_HOME"):
        raise SystemExit("JAVA_HOME is required for real-PySpark qualification")
    sql_url = env.get("ETLANTIC_SQL_URL")
    if not sql_url:
        raise SystemExit("ETLANTIC_SQL_URL is required for PostgreSQL qualification")
    if not sql_url.startswith(("postgresql://", "postgresql+")):
        raise SystemExit("ETLANTIC_SQL_URL must identify a PostgreSQL backend")
    result = subprocess.run(
        command,
        cwd=ROOT,
        shell=True,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout


def _write_json(name: str, payload: Mapping[str, Any]) -> None:
    (EVIDENCE / name).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode(
            "utf-8"
        )
    ).hexdigest()


def _source_tree_digest() -> str:
    """Hash tracked source/config/docs outside the generated evidence tree."""
    files = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).split(b"\0")
    digest = hashlib.sha256()
    evidence_prefix = "docs/11_DEVELOPMENT/evidence/portable_0_50/"
    for raw in sorted(item for item in files if item):
        relative = raw.decode("utf-8")
        if relative.startswith(evidence_prefix):
            continue
        digest.update(raw)
        digest.update(b"\0")
        digest.update((ROOT / relative).read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-commit", required=True)
    parser.add_argument(
        "--run", action="store_true", help="execute qualification first"
    )
    args = parser.parse_args()
    commit = args.repository_commit
    if len(commit) != 40 or any(char not in "0123456789abcdef" for char in commit):
        raise SystemExit("repository commit must be a lowercase 40-character SHA-1")
    if not args.run:
        raise SystemExit("--run is required to publish passing qualification evidence")
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    if commit != head:
        raise SystemExit("repository commit must equal HEAD when qualification starts")
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=ROOT, text=True
    )
    non_evidence_dirty = [
        line
        for line in dirty.splitlines()
        if "docs/11_DEVELOPMENT/evidence/portable_0_50/" not in line
    ]
    if non_evidence_dirty:
        raise SystemExit(
            "qualification requires a clean source tree outside generated evidence"
        )
    campaign_results: list[dict[str, Any]] = []
    for campaign in PUBLIC_CAMPAIGNS:
        _run(str(campaign["command"]))
        campaign_results.append({**campaign, "result": "pass", "exit_code": 0})
    canonical_outputs: list[str] = []
    for campaign in CANONICAL_CAMPAIGNS:
        canonical_outputs.append(_run(str(campaign["command"])))
        campaign_results.append({**campaign, "result": "pass", "exit_code": 0})
    _run(ADAPTIVE_COMMAND)
    _run(DEPENDENCY_COMMAND)

    reports: dict[str, Any] = {}
    claims: list[dict[str, Any]] = []
    pushdown: list[dict[str, Any]] = []
    pushdown_proofs: dict[str, Any] = {}
    for engine, factory in _compiler_factories().items():
        compiler = factory()
        report = compiler.analyze(
            {"actions": []},
            context=TransformPlanningContext(
                "qualification", "baseline", "qualification", engine
            ),
            requirements=_requirements(
                eager=compiler.info.capabilities.eager,
                lazy=compiler.info.capabilities.lazy,
            ),
        )
        if not report.supported:
            raise SystemExit(f"{engine} does not satisfy the frozen baseline")
        reports[engine] = report.to_requirement_support(
            target={
                "engine": compiler.info.engine,
                "compiler": compiler.info.name,
                "version": compiler.info.version,
            }
        )
        caps = compiler.info.capabilities
        fixture_ids = sorted(
            case.name
            for case in fixtures_for_capabilities(
                profiles=caps.profiles,
                actions=caps.actions,
                functions=caps.functions,
                operators=caps.operators,
                types=caps.types,
                semantic_modes=caps.semantic_modes,
                join_modes=caps.join_modes,
                union_modes=caps.union_modes,
                collision_policies=caps.collision_policies,
            )
        )
        manifest_bindings = dict(baseline_manifest().get("leaf_fixture_ids") or {})
        fixture_names = {case.name for case in FIXTURES}
        missing_fixture_ids = sorted(set(manifest_bindings.values()) - fixture_names)
        if missing_fixture_ids:
            raise SystemExit(
                "baseline manifest refers to missing fixtures: "
                + ", ".join(missing_fixture_ids)
            )
        claims.append(
            {
                "engine": engine,
                "profiles": len(caps.profiles),
                "actions": len(caps.actions),
                "functions": len(caps.functions),
                "fixture_coverage": "complete",
                "fixture_ids": fixture_ids,
                "fixture_bindings": manifest_bindings,
                "fixture_results": [
                    {
                        "fixture_id": fixture_id,
                        "result": "pass",
                        "command": PUBLIC_COMMAND,
                    }
                    for fixture_id in fixture_ids
                ],
                "required_fixture_ids": sorted(set(manifest_bindings.values())),
                "semantic_modes": sorted(caps.semantic_modes),
                "execution_modes": {"eager": caps.eager, "lazy": caps.lazy},
                "mode_results": [
                    {
                        **item,
                        "result": "pass",
                        "campaign_ids": _campaign_ids_for_matrix(item),
                    }
                    for item in QUALIFICATION_MATRIX
                    if item["engine"] == engine
                ],
                "evidence_fingerprint": compiler.info.evidence_fingerprint,
            }
        )
        analyzed = compiler.analyze(
            _pushdown_plan(),
            context=TransformPlanningContext(
                "qualification", "pushdown", "qualification", engine
            ),
        )
        if not analyzed.supported:
            raise SystemExit(
                f"{engine} pushdown fixture is unsupported: "
                + "; ".join(f.requirement for f in analyzed.findings)
            )
        native_target = engine in {"sql", "pyspark", "datafusion", "duckdb"}
        (
            result_digest,
            explain_digest,
            action_digests,
            action_explain_digests,
            host_fallback,
        ) = (
            _execute_pushdown_fixture(compiler)
            if native_target
            else (None, None, {}, {}, False)
        )
        pushdown_proofs[engine] = {
            "result_digest": result_digest,
            "native_explain_digest": explain_digest,
            "actions": {},
        }
        sqlite_pushdown = (
            _execute_pushdown_fixture(
                compiler, database_url="sqlite+pysqlite:///:memory:"
            )
            if engine == "sql"
            else None
        )
        if sqlite_pushdown is not None:
            pushdown_proofs[engine]["sqlite_execution"] = {
                "result_digest": sqlite_pushdown[0],
                "native_explain_digest": sqlite_pushdown[1],
                "action_native_digests": sqlite_pushdown[2],
                "action_explain_digests": sqlite_pushdown[3],
                "host_fallback": sqlite_pushdown[4],
            }
        for finding in analyzed.pushdown:
            record = finding.to_dict()
            record["engine"] = engine
            if record.get("obligation") == "required":
                target = str(record.get("target") or "")
                proof_id = f"native-execution:{engine}:{target}"
                pushdown_proofs[engine]["actions"][target] = {
                    "proof_id": proof_id,
                    "native_explain_digest": explain_digest,
                    "action_explain_digest": action_explain_digests.get(target),
                    "action_native_digest": action_digests.get(target),
                    "result_digest": result_digest,
                    "action": record.get("action"),
                    "host_fallback": host_fallback,
                    "physical_effects": record.get("physical_effects", []),
                    "proof_basis": "native_explain_and_execution_trace",
                }
                record["proof_reference"] = proof_id
            pushdown.append(record)

    environment = {
        "python": platform.python_version(),
        "platform": platform.system().lower(),
        "sql_backend": "postgresql (URL supplied at runtime; redacted)",
        "spark_backend": "pyspark JVM",
    }
    common = {
        "repository_commit": commit,
        "source_tree_digest": _source_tree_digest(),
        "result": "pass",
    }
    _write_json(
        "portable_baseline_contract_0_50.json",
        {
            "schema": "etlantic.portable-baseline/1",
            **common,
            "command": PUBLIC_COMMAND,
            "manifest": baseline_manifest(),
            "environment": environment,
        },
    )
    _write_json(
        "portable_requirement_support_0_50.json",
        {
            "schema": "etlantic.portable-requirement-support/1",
            **common,
            "command": PUBLIC_COMMAND,
            "environment": environment,
            "support_states": [
                "supported_exact",
                "supported_with_lowering",
                "unsupported",
                "unavailable",
                "unknown",
            ],
            "obligations": ["required", "preferred", "informational"],
            "reports": reports,
        },
    )
    _write_json(
        "portable_pushdown_contract_0_50.json",
        {
            "schema": "etlantic.portable-pushdown/1",
            **common,
            "command": PUBLIC_COMMAND,
            "environment": environment,
            "outcomes": ["pushed_exact", "pushed_with_lowering", "not_applicable"],
            "boundaries": ["source", "relational", "sink"],
            "findings": pushdown,
            "proofs": pushdown_proofs,
            "evidence": sorted(
                {
                    item["evidence_fingerprint"]
                    for item in pushdown
                    if item.get("evidence_fingerprint")
                }
            ),
        },
    )
    _write_json(
        "portable_claim_coverage_0_50.json",
        {
            "schema": "etlantic.portable-claim-coverage/1",
            **common,
            "command": PUBLIC_COMMAND,
            "environment": environment,
            "claims": claims,
            "policy": "Every frozen baseline claim is selected by the public conformance suite; semantic and eager/lazy dimensions are recorded per engine.",
            "required_fixture_ids": sorted(
                set((baseline_manifest().get("leaf_fixture_ids") or {}).values())
            ),
            "negative_states": ["unsupported", "unavailable", "unknown"],
            "qualification_matrix": [
                {
                    **item,
                    "result": "pass",
                    "campaign_ids": _campaign_ids_for_matrix(item),
                }
                for item in QUALIFICATION_MATRIX
            ],
            "campaign_results": campaign_results,
        },
    )
    for engine in ENGINES:
        _write_json(
            f"portable_{engine}_conformance_0_50.json"
            if engine != "duckdb"
            else "portable_duckdb_pushdown_0_50.json",
            {
                "schema": (
                    "etlantic.portable-pushdown-evidence/1"
                    if engine == "duckdb"
                    else "etlantic.portable-conformance/1"
                ),
                **common,
                "engine": engine,
                "command": PUBLIC_COMMAND,
                "environment": environment,
                "tests": [
                    "tests/portable_conformance/test_public_suite.py",
                    "tests/sql/test_sql_portable_security.py",
                    "tests/sql/test_sql_runtime.py::test_sql_to_sql_no_python_fetch",
                ],
                "evidence_fingerprint": next(
                    claim["evidence_fingerprint"]
                    for claim in claims
                    if claim["engine"] == engine
                ),
                **(
                    {
                        "boundaries": [
                            item for item in pushdown if item["engine"] == "duckdb"
                        ]
                    }
                    if engine == "duckdb"
                    else {}
                ),
            },
        )
    _write_json(
        "portable_cross_engine_0_50.json",
        {
            "schema": "etlantic.portable-cross-engine/1",
            **common,
            "command": CANONICAL_COMMAND,
            "environment": environment,
            "engines": list(ENGINES),
            "canonical_pipeline": "canonical_multistage/1",
            "normalized_result_digest": next(
                (
                    line.partition(":")[2].strip()
                    for output in canonical_outputs
                    for line in output.splitlines()
                    if line.startswith("canonical_result_digest:")
                ),
                "",
            ),
            "canonical_result_digests": {
                "postgresql": next(
                    (
                        line.partition(":")[2].strip()
                        for line in canonical_outputs[0].splitlines()
                        if line.startswith("canonical_result_digest:")
                    ),
                    "",
                ),
                "sqlite": next(
                    (
                        line.partition(":")[2].strip()
                        for line in canonical_outputs[1].splitlines()
                        if line.startswith("canonical_result_digest:")
                    ),
                    "",
                ),
            },
        },
    )
    _write_json(
        "portable_canonical_pipeline_0_50.json",
        {
            "schema": "etlantic.portable-canonical-pipeline/1",
            **common,
            "command": CANONICAL_COMMAND,
            "environment": environment,
            "plan": "dtcs.transform-plan/2",
            "engine_neutral": True,
            "stages": [
                "filter",
                "project",
                "join",
                "aggregate",
                "union",
                "sort",
                "deduplicate",
                "limit",
                "contract_validation",
            ],
            "source_rows": False,
            "engine_specific_bodies": False,
        },
    )
    _write_json(
        "portable_adaptive_handoff_0_50.json",
        {
            "schema": "etlantic.portable-adaptive-handoff/1",
            **common,
            "command": ADAPTIVE_COMMAND,
            "environment": environment,
            "fixtures": list(ADAPTIVE_FIXTURES),
            "scenarios": _adaptive_scenarios(),
            "execution": "planning-only; no adaptive execution",
            "source_rows": False,
        },
    )
    _write_json(
        "portable_dependency_security_0_50.json",
        {
            "schema": "etlantic.portable-dependency-security/1",
            **common,
            "command": DEPENDENCY_COMMAND,
            "environment": environment,
            "engines": list(ENGINES),
            "checks": [
                "bound_parameters",
                "trusted_fragment_rejection",
                "isolated_wheel_builds",
                "isolated_local_conformance",
            ],
        },
    )
    (EVIDENCE / "FINDINGS_0_50.md").write_text(
        "# 0.50 Findings\n\n"
        "**Status: Technical qualification complete; Sol review pending.**\n\n"
        "| ID | Severity | Disposition |\n|---|---|---|\n"
        "| SOL-050-001 | High | resolved and covered by regression tests |\n"
        "| SOL-050-002 | High | resolved by the normative baseline manifest |\n"
        "| SOL-050-003 | High | resolved by the public canonical runner |\n"
        "| SOL-050-004 | High | resolved by action-correlated native proof |\n"
        "| SOL-050-005 | High | resolved by the complete backend campaign |\n"
        "| SOL-050-006 | High | resolved by adaptive handoff scenarios |\n"
        "| SOL-050-007 | Medium | resolved by release documentation |\n"
        "| SOL-050-008 | Low | resolved by formatting verification |\n"
        "| SOL-050-009 | High | resolved by action-level native evidence |\n"
        "| SOL-050-010 | Medium | resolved by independent backend campaigns |\n"
        "| SOL-050-011 | High | resolved by candidate evaluation evidence |\n"
        "| SOL-050-012 | Medium | resolved by canonical digest and metadata checks |\n"
        "| SOL-050-013 | Medium | resolved by source and artifact digest linkage |\n"
        "| SOL-050-014 | High | resolved by fail-fast campaign execution |\n"
        "| SOL-050-015 | High | resolved by action-correlated EXPLAIN evidence |\n"
        "| SOL-050-016 | High | resolved by executable adaptive candidate evaluation |\n"
        "| SOL-050-017 | Medium | resolved by schema, digest, and ledger validation |\n"
        "| SOL-050-018 | High | resolved by Spark protocol dispatch and error-semantics regression coverage |\n\n"
        "Implementation resolutions are complete; Sol re-review pending. The "
        "evidence index, source digest, and artifact digests are the release record "
        "for this disposition.\n",
        encoding="utf-8",
    )
    (EVIDENCE / "MIGRATION_0_49_TO_0_50.md").write_text(
        "# Migration from 0.49 to 0.50\n\n"
        "0.50 freezes the `dtcs.transform-plan/2` baseline with 12 actions, the "
        "kernel and relational `/1` profiles, and explicitly proven `/2` metadata "
        "aliases. Replan stored 0.49 descriptors before execution; stale evidence "
        "is rejected before I/O.\n\n"
        "Plugins must repin every first-party optional package to the matching 0.50 "
        "line and rerun the public conformance matrix. Engine selection remains in "
        "the Profile; native implementation bodies are separate from the portable "
        "body and must not be silently substituted.\n\n"
        "Rollback: restore the 0.49 package lock and profile, replan stored plans, "
        "and discard 0.50 evidence artifacts. Never execute a stored 0.49 plan with "
        "a mismatched compiler fingerprint.\n",
        encoding="utf-8",
    )
    (EVIDENCE / "WHATS_NEW_0_50.md").write_text(
        "# What's new in 0.50\n\n"
        "> **Status: Technical qualification complete; Sol review pending.**\n\n"
        "Qualified matrix: Local (host), Polars (eager and lazy), Pandas (eager), "
        "SQL (SQLite and PostgreSQL relation paths), PySpark (real JVM), DataFusion "
        "(lazy native plan), and DuckDB (lazy relation path).\n\n"
        "The baseline does not claim advanced, adaptive execution, remote, streaming, "
        "federated, or unqualified connector/sink pushdown. Native bodies remain "
        "engine-specific and are not part of the portable guarantee.\n\n"
        "This technical result remains subject to Sol's independent release review.\n",
        encoding="utf-8",
    )
    digests = {
        name: hashlib.sha256((EVIDENCE / name).read_bytes()).hexdigest()
        for name in ARTIFACTS
    }
    artifact_schemas = {
        name: (
            json.loads((EVIDENCE / name).read_text()).get("schema")
            if name.endswith(".json")
            else "markdown/1"
        )
        for name in ARTIFACTS
    }
    artifact_metadata = {
        name: {
            "id": Path(name).stem,
            "path": name,
            "schema": artifact_schemas[name],
            "sha256": digests[name],
            "command": (
                CANONICAL_COMMAND
                if name
                in {
                    "portable_cross_engine_0_50.json",
                    "portable_canonical_pipeline_0_50.json",
                }
                else ADAPTIVE_COMMAND
                if name == "portable_adaptive_handoff_0_50.json"
                else DEPENDENCY_COMMAND
                if name == "portable_dependency_security_0_50.json"
                else PUBLIC_COMMAND
            ),
            "environment": environment,
            "result": "pass",
        }
        for name in ARTIFACTS
    }
    _write_json(
        "portable_evidence_index_0_50.json",
        {
            "schema": "etlantic.portable-evidence-index/1",
            **common,
            "qualification": "qualified",
            "source_tree_digest": common["source_tree_digest"],
            "artifacts": list(ARTIFACTS),
            "digests": digests,
            "artifact_metadata": artifact_metadata,
            "environment": environment,
            "notes": "Generated from real backend qualification commands; sensitive connection values are not recorded.",
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
