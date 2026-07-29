"""Medallantic M6 operations tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

pytest.importorskip("medallantic")

from etlantic.plan import plan_pipeline
from etlantic.reports.model import PipelineRunReport, RunSummary, StepRunReport
from etlantic.runtime.events import LifecycleEvent
from etlantic.runtime.request import RunIntent
from etlantic.runtime.state import RunStatus, StepStatus
from etlantic.testing.production_conformance import assert_production_conformance
from medallantic import MedallionBuilder
from medallantic.explain import explain_medallion_plan
from medallantic.lifecycle_views import group_events_by_layer, layer_run_summary
from medallantic.profiles import (
    medallion_development_profile,
    medallion_production_profile,
    medallion_test_profile,
)

pytestmark = pytest.mark.medallantic


def _sample_builder() -> MedallionBuilder:
    return (
        MedallionBuilder("ops-sample", schema="demo", engine="local")
        .bronze("orders", asset="bronze_orders")
        .silver("clean_orders", source="orders", asset="silver_orders")
    )


def test_explain_medallion_plan_includes_layers() -> None:
    lowered = _sample_builder().lower()
    plan = plan_pipeline(lowered.pipeline_cls, profile=lowered.profile)
    plan = lowered.enrich_plan(plan)
    explained = explain_medallion_plan(plan, definition=lowered.definition)
    assert explained["schema"] == "medallantic.explain/1"
    assert "layers" in explained
    assert explained["layers"].get("clean_orders") == "silver"


def test_layer_lifecycle_views() -> None:
    events = [
        LifecycleEvent(
            kind="step_completed",
            run_id="r1",
            pipeline_id="p1",
            step_name="silver_clean",
            annotations={"layer": "silver"},
        )
    ]
    grouped = group_events_by_layer(events, {"silver_clean": "silver"})
    assert "silver" in grouped
    report = PipelineRunReport(
        pipeline_id="p1",
        plan_id="plan",
        run_id="r1",
        intent=RunIntent.STANDARD,
        profile="test",
        status=RunStatus.SUCCEEDED,
        started_at=datetime.now(UTC),
        steps=(
            StepRunReport(
                step_id="silver_clean",
                step_name="silver_clean",
                status=StepStatus.SUCCEEDED,
                started_at=datetime.now(UTC),
            ),
        ),
        summary=RunSummary(total_steps=1, succeeded=1),
    )
    summary = layer_run_summary(report, {"silver_clean": "silver"})
    assert summary["layers"]["silver"]["succeeded"] == 1


def test_medallion_profile_templates() -> None:
    dev = medallion_development_profile()
    assert dev.run_history_provider == "file"
    test = medallion_test_profile()
    assert test.security_mode == "test"
    prod = medallion_production_profile(
        plugin_allowlist={"etlantic-polars": "==0.34.0"},
        assets={"source": "json"},
    )
    assert_production_conformance(prod)
