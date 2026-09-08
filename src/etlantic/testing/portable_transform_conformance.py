"""Public portable transform compiler conformance suite (0.14)."""

from __future__ import annotations

import asyncio
import math
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from etlantic.testing.portable_fixtures.corpus import (
    FIXTURES,
    FixtureCase,
    covered_capability_keys,
    fixtures_for_capabilities,
    mandatory_capability_keys,
)
from etlantic.transform.compiler import (
    TransformCompileContext,
    TransformExecutionContext,
    TransformPlanningContext,
)
from etlantic.transform.portable_baseline import (
    BASELINE_FUNCTIONS,
    BASELINE_JOIN_MODES,
    BASELINE_OPERATORS,
    BASELINE_TYPES,
    KERNEL_ACTIONS,
    RELATIONAL_ACTIONS,
)
from etlantic.transform.protocol import KERNEL_PROFILE_V1, RELATIONAL_PROFILE_V1

FrameFactory = Callable[[list[dict[str, Any]]], Any]


def normalize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Stable cross-engine row normalization for conformance compares."""

    def _norm_value(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, float) and math.isnan(value):
            return None
        item_method = getattr(value, "item", None)
        if callable(item_method):
            try:
                return _norm_value(item_method())
            except Exception:
                pass
        return value

    cleaned: list[dict[str, Any]] = []
    for row in rows:
        item = {k: _norm_value(row[k]) for k in sorted(row)}
        cleaned.append(item)
    return sorted(
        cleaned,
        key=lambda r: tuple(str(r.get(k)) for k in sorted(r)),
    )


def default_frame_factory(engine: str) -> FrameFactory:
    """Build an input frame factory for a known reference engine."""
    engine = engine.lower()
    if engine == "local":
        return lambda rows: list(rows)
    if engine == "datafusion":
        import pyarrow as pa

        from datafusion import SessionContext

        session = SessionContext()

        def _datafusion(rows: list[dict[str, Any]]) -> Any:
            return session.from_arrow(pa.Table.from_pylist(rows))

        _datafusion._etlantic_session = session  # type: ignore[attr-defined]
        return _datafusion
    if engine == "polars":
        import polars as pl

        def _polars(rows: list[dict[str, Any]]) -> Any:
            return pl.DataFrame(rows)

        return _polars
    if engine == "pandas":
        import pandas as pd

        def _pandas(rows: list[dict[str, Any]]) -> Any:
            return pd.DataFrame(rows)

        return _pandas
    if engine in {"pyspark", "spark"}:
        from etlantic.spark.provider import ResourceContext, SparkSessionRequest
        from etlantic_pyspark import create_provider
        from etlantic_pyspark.sparkless_shim import install

        install()
        provider = create_provider()
        ctx = ResourceContext(run_id="conformance", pipeline_id="c", plan_id="p")
        handle = provider.acquire(
            SparkSessionRequest(app_name="portable-conformance", master="local[1]"),
            ctx,
        )
        session = handle.session

        def _spark(rows: list[dict[str, Any]]) -> Any:
            if not rows:
                from pyspark.sql.types import StructType

                return session.createDataFrame([], schema=StructType([]))
            return session.createDataFrame(rows)

        _spark._etlantic_provider = provider  # type: ignore[attr-defined]
        _spark._etlantic_handle = handle  # type: ignore[attr-defined]
        _spark._etlantic_ctx = ctx  # type: ignore[attr-defined]
        return _spark
    if engine == "sql":
        from etlantic_sql.frame import SqlRelationFrame

        def _sql(rows: list[dict[str, Any]]) -> Any:
            return SqlRelationFrame(rows=list(rows))

        return _sql
    if engine == "duckdb":
        from etlantic_duckdb.frame import DuckDBFrame

        def _duckdb(rows: list[dict[str, Any]]) -> Any:
            return DuckDBFrame(rows=list(rows))

        return _duckdb
    raise ValueError(f"No default frame factory for engine {engine!r}")


def rows_from_frame(frame: Any) -> list[dict[str, Any]]:
    """Convert a compiler output frame to list[dict]."""
    if isinstance(frame, list):
        return [
            dict(row)
            if isinstance(row, Mapping)
            else row.model_dump()
            if hasattr(row, "model_dump")
            else dict(row)
            for row in frame
        ]
    if hasattr(frame, "to_dicts"):
        return list(frame.to_dicts())
    if hasattr(frame, "to_dict") and hasattr(frame, "columns"):
        # pandas
        return list(frame.to_dict(orient="records"))
    if hasattr(frame, "collect"):
        collected = frame.collect()
        if collected and hasattr(collected[0], "to_pylist"):
            return [row for batch in collected for row in batch.to_pylist()]
        return [
            row.asDict() if hasattr(row, "asDict") else dict(row) for row in collected
        ]
    raise TypeError(f"Unsupported output frame type {type(frame)!r}")


def run_portable_transform_conformance_suite(
    compiler: Any,
    *,
    profiles: Sequence[str] | None = None,
    to_frame: FrameFactory | None = None,
    enforce_fixture_coverage: bool = True,
) -> None:
    """Run capability-selected portable transform conformance for ``compiler``.

    The suite selects mandatory fixtures for every advertised profile/action/
    function claim. Compilers must pass every selected fixture (or correctly
    reject unsupported modes at analyze time). When
    ``enforce_fixture_coverage`` is true, claiming kernel/relational profiles
    or individual actions/functions without a matching fixture fails the suite.
    """
    info = compiler.info
    caps = info.capabilities
    if caps.profiles & caps.partial_profiles:
        raise AssertionError("a profile cannot be both qualified and partial")
    claimed_profiles = frozenset(profiles or caps.profiles)
    claimed_actions = frozenset(caps.actions)
    claimed_functions = frozenset(caps.functions)
    claimed_operators = frozenset(caps.operators)
    claimed_types = frozenset(caps.types)
    claimed_semantic_modes = frozenset(caps.semantic_modes)
    claimed_join_modes = frozenset(caps.join_modes)
    claimed_union_modes = frozenset(caps.union_modes)
    claimed_collision_policies = frozenset(caps.collision_policies)

    # A frozen baseline profile is a complete claim, not a label for a small
    # subset.  Partial implementations must use ``partial_profiles`` and may
    # still advertise their concrete action/function subset.
    if (
        KERNEL_PROFILE_V1 in claimed_profiles
        or RELATIONAL_PROFILE_V1 in claimed_profiles
    ):
        required_actions: set[str] = set(KERNEL_ACTIONS)
        if RELATIONAL_PROFILE_V1 in claimed_profiles:
            required_actions.update(RELATIONAL_ACTIONS)
        missing = sorted(
            [f"action:{item}" for item in required_actions - claimed_actions]
            + [
                f"function:{item}"
                for item in set(BASELINE_FUNCTIONS) - claimed_functions
            ]
            + [
                f"operator:{item}"
                for item in set(BASELINE_OPERATORS) - claimed_operators
            ]
            # ``missing``/``invalid`` are only meaningful with the explicit
            # three-state semantic claim and are covered by the negative
            # fixture below rather than a positive baseline fixture.
            + [
                f"type:{item}"
                for item in (set(BASELINE_TYPES) - {"missing", "invalid"})
                - claimed_types
            ]
            + [
                f"join_mode:{item}"
                for item in BASELINE_JOIN_MODES
                if item not in claimed_join_modes
            ]
            + [
                f"union_mode:{item}"
                for item in ("byName", "byPosition")
                if item not in claimed_union_modes
            ]
            + [
                "collision_policy:fail"
                if "fail" not in claimed_collision_policies
                else ""
            ]
        )
        missing = [item for item in missing if item]
        if missing:
            raise AssertionError(
                "Baseline profile claim is incomplete: " + ", ".join(missing)
            )

    selected = fixtures_for_capabilities(
        profiles=claimed_profiles,
        actions=claimed_actions,
        functions=claimed_functions,
        operators=claimed_operators,
        types=claimed_types,
        semantic_modes=claimed_semantic_modes,
        join_modes=claimed_join_modes,
        union_modes=claimed_union_modes,
        collision_policies=claimed_collision_policies,
    )
    if enforce_fixture_coverage:
        known_actions = {
            action for case in FIXTURES for action in case.required_actions
        } | set(KERNEL_ACTIONS + RELATIONAL_ACTIONS)
        known_functions = {
            function for case in FIXTURES for function in case.required_functions
        } | set(BASELINE_FUNCTIONS)
        unknown = sorted(
            [f"action:{x}" for x in claimed_actions if x not in known_actions]
            + [f"function:{x}" for x in claimed_functions if x not in known_functions]
        )
        if unknown:
            raise AssertionError(
                "Claims have no recognized contract vocabulary: " + ", ".join(unknown)
            )
        required = mandatory_capability_keys(
            profiles=claimed_profiles,
            actions=claimed_actions,
            functions=claimed_functions,
            operators=claimed_operators,
            types=(
                claimed_types
                if "three_state_distinct" in claimed_semantic_modes
                else claimed_types - {"missing", "invalid"}
            ),
            semantic_modes=claimed_semantic_modes,
            join_modes=claimed_join_modes,
            union_modes=claimed_union_modes,
            collision_policies=claimed_collision_policies,
        )
        covered = covered_capability_keys(selected)
        missing = sorted(required - covered)
        if missing:
            raise AssertionError(
                "Claimed capabilities lack mandatory conformance fixtures: "
                + ", ".join(missing)
            )

    factory = to_frame or default_frame_factory(info.engine)
    planning = TransformPlanningContext(
        pipeline_id="conformance",
        step_name="step",
        profile_name="conformance",
        engine=info.engine,
    )
    try:
        for case in selected:
            _run_case(compiler, case, planning=planning, to_frame=factory)
    finally:
        _release_spark_factory(factory)


def _release_spark_factory(factory: FrameFactory) -> None:
    provider = getattr(factory, "_etlantic_provider", None)
    handle = getattr(factory, "_etlantic_handle", None)
    ctx = getattr(factory, "_etlantic_ctx", None)
    if provider is not None and handle is not None and ctx is not None:
        provider.release(handle, ctx)


def _run_case(
    compiler: Any,
    case: FixtureCase,
    *,
    planning: TransformPlanningContext,
    to_frame: FrameFactory,
) -> None:
    required_profiles = sorted(case.required_profiles)
    if (
        case.required_profiles
        and case.required_profiles.issubset(compiler.info.capabilities.partial_profiles)
        and not compiler.info.capabilities.profiles
    ):
        # Partial implementations are selected by concrete claims; the
        # baseline profile itself is not a requirement of a subset fixture.
        required_profiles = []
    requirements: Mapping[str, Sequence[str]] = {
        "profiles": required_profiles,
        "actions": sorted(case.required_actions),
        "functions": sorted(case.required_functions),
        "operators": sorted(case.required_operators),
        "types": sorted(case.required_types),
        "semantic_modes": sorted(case.required_semantic_modes),
        "join_modes": sorted(case.required_join_modes),
        "union_modes": sorted(case.required_union_modes),
        "collision_policies": sorted(case.required_collision_policies),
    }
    report = compiler.analyze(case.plan, context=planning, requirements=requirements)
    if case.expect_unsupported:
        assert report.supported is False, f"{case.name}: expected unsupported"
        if case.unsupported_requirement_substr:
            assert any(
                case.unsupported_requirement_substr in f.requirement
                for f in report.findings
            ), f"{case.name}: missing unsupported finding"
        return

    assert report.supported is True, f"{case.name}: analyze unsupported: " + "; ".join(
        f"{f.requirement}: {f.reason}" for f in report.findings
    )
    compiled = compiler.compile(
        case.plan,
        context=TransformCompileContext(
            pipeline_id="conformance",
            plan_id="plan",
            step_name="step",
            profile_name="conformance",
            engine=compiler.info.engine,
        ),
        requirements=requirements,
    )
    # Plans/explain must remain secret-free.
    explain = compiled.explain or {}
    blob = str(explain)
    assert "password" not in blob.lower()
    assert "secret" not in blob.lower() or "secret-free" in blob.lower()

    inputs = {name: to_frame(rows) for name, rows in case.inputs.items()}
    metadata: dict[str, Any] = {}
    session = getattr(getattr(to_frame, "_etlantic_handle", None), "session", None)
    if session is not None:
        metadata["spark_session"] = session
    bundle = asyncio.run(
        compiler.execute(
            compiled,
            inputs=inputs,
            parameters=dict(case.parameters or {}),
            context=TransformExecutionContext(
                run_id="conformance",
                pipeline_id="conformance",
                plan_id="plan",
                step_name="step",
                engine=compiler.info.engine,
                metadata=metadata,
            ),
        )
    )
    frame = next(iter(bundle.valid.values()))
    got = normalize_rows(rows_from_frame(frame))
    expected = normalize_rows(list(case.expected or []))
    assert got == expected, f"{case.name}: {got!r} != {expected!r}"
