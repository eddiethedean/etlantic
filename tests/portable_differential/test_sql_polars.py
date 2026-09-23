# pyright: reportAttributeAccessIssue=false, reportMissingImports=false, reportMissingTypeStubs=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Differential: SQL portable compiler vs Polars on shared fixture intersection."""

from __future__ import annotations

import asyncio

import pytest

from etlantic.testing import run_portable_transform_conformance_suite
from etlantic.testing.portable_fixtures.corpus import fixtures_for_capabilities
from etlantic.testing.portable_transform_conformance import (
    normalize_rows,
    rows_from_frame,
)
from etlantic.transform.compiler import (
    TransformCompileContext,
    TransformExecutionContext,
    TransformPlanningContext,
)
from etlantic.transform.protocol import KERNEL_PROFILE_V1, RELATIONAL_PROFILE_V1

pytestmark = [pytest.mark.sql, pytest.mark.polars]


def test_sql_matches_polars_on_shared_fixtures() -> None:
    pytest.importorskip("sqlalchemy")
    pytest.importorskip("polars")
    import polars as pl

    from etlantic_polars import create_transform_compiler as polars_compiler
    from etlantic_sql import create_transform_compiler as sql_compiler
    from etlantic_sql.frame import SqlRelationFrame

    sql = sql_compiler()
    polars_c = polars_compiler()
    run_portable_transform_conformance_suite(sql)
    run_portable_transform_conformance_suite(polars_c)

    cases = fixtures_for_capabilities(
        profiles=frozenset({KERNEL_PROFILE_V1, RELATIONAL_PROFILE_V1}),
        actions=sql.info.capabilities.actions & polars_c.info.capabilities.actions,
        functions=sql.info.capabilities.functions
        & polars_c.info.capabilities.functions,
    )
    planning = TransformPlanningContext(
        pipeline_id="diff",
        step_name="step",
        profile_name="diff",
        engine="sql",
    )

    async def _run() -> None:
        for case in cases:
            if case.expect_unsupported:
                continue
            requirements = {
                "profiles": sorted(case.required_profiles),
                "actions": sorted(case.required_actions),
                "functions": sorted(case.required_functions),
            }
            for compiler, engine, to_frame in (
                (sql, "sql", lambda rows: SqlRelationFrame(rows=list(rows))),
                (polars_c, "polars", pl.DataFrame),
            ):
                report = compiler.analyze(
                    case.plan, context=planning, requirements=requirements
                )
                assert report.supported, case.name
                compiled = compiler.compile(
                    case.plan,
                    context=TransformCompileContext(
                        pipeline_id="diff",
                        plan_id="p",
                        step_name="step",
                        profile_name="diff",
                        engine=engine,
                    ),
                    requirements=requirements,
                )
                bundle = await compiler.execute(
                    compiled,
                    inputs={n: to_frame(r) for n, r in case.inputs.items()},
                    parameters=dict(case.parameters or {}),
                    context=TransformExecutionContext(
                        run_id="diff",
                        pipeline_id="diff",
                        plan_id="p",
                        step_name="step",
                        engine=engine,
                    ),
                )
                got = normalize_rows(rows_from_frame(next(iter(bundle.valid.values()))))
                expected = normalize_rows(list(case.expected or []))
                assert got == expected, f"{engine}:{case.name}"

    asyncio.run(_run())
