# pyright: reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownVariableType=false
"""Finite application stop/quarantine/replan; no new queue or kill-switch API."""

import anyio
import pytest

pytest.importorskip("polars")
pytest.importorskip("pandas")
pytest.importorskip("pyarrow")

from examples.adaptive_reference import Reference, candidate, demonstrate

from etlantic.plan import plan_from_json, plan_pipeline, plan_to_json
from etlantic.registry import PlanningContext
from etlantic.runtime.adaptive_admission import admit_adaptive_plan
from etlantic.runtime.request import RunRequest

pytestmark = [pytest.mark.polars, pytest.mark.pandas]


def test_application_stop_quarantines_bytes_and_replans_explicit(tmp_path):
    runtime, profile, stored = candidate(tmp_path)
    original = plan_to_json(stored)
    queued = [original]
    accepting_adaptive = False
    quarantine = []
    while queued:
        submitted = queued.pop()
        if not accepting_adaptive:
            quarantine.append(submitted)
    assert quarantine == [original]
    assert plan_from_json(quarantine[0]).schema == "etlantic.plan/2"
    # Editing the authoring Profile is not revocation of a stored request.
    explicit_profile = profile.with_updates(
        execution_strategy="explicit",
        implementation_overrides={
            node.name: "polars" if i < 3 else "pandas"
            for i, node in enumerate(Reference.build_graph().nodes)
        },
    )
    admit_adaptive_plan(
        stored, request=RunRequest(), runtime=runtime, workspace=tmp_path
    )
    explicit = plan_pipeline(
        Reference,
        context=PlanningContext.create(explicit_profile, registry=runtime.registry),
    )
    assert explicit.schema == "etlantic.plan/1"
    assert plan_to_json(stored) == original
    assert not list(tmp_path.iterdir())


def test_public_example_finite_cleanup(tmp_path):
    anyio.run(demonstrate, tmp_path)
    assert sorted(path.name for path in tmp_path.iterdir()) == ["raw.parquet"]
