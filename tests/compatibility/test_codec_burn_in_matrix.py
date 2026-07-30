"""Cross-artifact quadruple-minor codec burn-in matrix."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from etlantic.capabilities import (
    CAPABILITY_VOCABULARY_VERSION,
    PluginCapabilities,
)
from etlantic.interchange.tabular.descriptor import InterchangeDescriptor
from etlantic.interchange.tabular.mechanisms import SCHEMA as INTERCHANGE_SCHEMA
from etlantic.plan.model import PLAN_SCHEMA, PipelinePlan
from etlantic.plan.upgrade import UnsupportedPlanSchemaError, upgrade_plan_dict
from etlantic.profile import Profile
from etlantic.reports.model import REPORT_SCHEMA, PipelineRunReport
from etlantic.reports.upgrade import UnsupportedReportSchemaError, upgrade_report_dict

BURN_IN = Path(__file__).resolve().parents[1] / "fixtures" / "burn_in"
VERSIONS = (
    "v0_24",
    "v0_25",
    "v0_26",
    "v0_27",
    "v0_34",
    "v0_35",
    "v0_36",
)


def _load(rel: str) -> dict:
    return json.loads((BURN_IN / rel).read_text(encoding="utf-8"))


@pytest.mark.parametrize("version", VERSIONS)
def test_plan_old_reader_new_writer(version: str) -> None:
    data = _load(f"plan/{version}/sample_local.json")
    assert data["schema"] == PLAN_SCHEMA
    plan = PipelinePlan.from_dict(data)
    rewritten = plan.to_dict()
    assert rewritten["schema"] == PLAN_SCHEMA
    again = PipelinePlan.from_dict(rewritten)
    assert again.fingerprint == plan.fingerprint
    assert upgrade_plan_dict(data)["schema"] == PLAN_SCHEMA


def test_plan_unknown_schema_fail_closed() -> None:
    data = _load("plan/v0_24/sample_local.json")
    data["schema"] = "etlantic.plan/99"
    with pytest.raises((ValueError, UnsupportedPlanSchemaError), match="Unsupported"):
        PipelinePlan.from_dict(data)


@pytest.mark.parametrize("version", VERSIONS)
def test_run_report_old_reader_new_writer(version: str) -> None:
    data = _load(f"run_report/{version}/sample_succeeded.json")
    assert data["schema"] == REPORT_SCHEMA
    report = PipelineRunReport.from_dict(data)
    rewritten = report.to_dict()
    assert rewritten["schema"] == REPORT_SCHEMA
    again = PipelineRunReport.from_dict(rewritten)
    assert again.run_id == report.run_id
    assert again.status == report.status
    assert upgrade_report_dict(data)["schema"] == REPORT_SCHEMA


def test_run_report_unknown_schema_fail_closed() -> None:
    data = _load("run_report/v0_24/sample_succeeded.json")
    data["schema"] = "etlantic.run_report/99"
    with pytest.raises((ValueError, UnsupportedReportSchemaError), match="Unsupported"):
        PipelineRunReport.from_dict(data)


@pytest.mark.parametrize("version", VERSIONS)
def test_profile_json_round_trip(version: str) -> None:
    data = _load(f"profile/{version}/development_local.json")
    profile = Profile.from_dict(data)
    rewritten = profile.to_dict()
    again = Profile.from_dict(rewritten)
    assert again.name == profile.name
    assert again.security_mode == profile.security_mode
    assert again.dataframe_engine == profile.dataframe_engine


@pytest.mark.parametrize("version", VERSIONS)
def test_capabilities_vocabulary_round_trip(version: str) -> None:
    data = _load(f"capabilities/{version}/local_dataframe.json")
    assert data["vocabulary_version"] == CAPABILITY_VOCABULARY_VERSION
    caps = PluginCapabilities.from_dict(data)
    rewritten = caps.to_dict()
    again = PluginCapabilities.from_dict(rewritten)
    assert again.vocabulary_version == CAPABILITY_VOCABULARY_VERSION
    assert again.engine == caps.engine


def test_capabilities_unknown_major_rejected_by_compat_helper() -> None:
    from etlantic.capabilities import vocabulary_major_compatible

    assert vocabulary_major_compatible("etlantic.capabilities/1")
    assert vocabulary_major_compatible("etlantic.capabilities/1.2")
    assert not vocabulary_major_compatible("etlantic.capabilities/2")


@pytest.mark.parametrize("version", VERSIONS)
def test_interchange_descriptor_round_trip(version: str) -> None:
    from etlantic.interchange.tabular.select import select_mechanism

    data = _load(f"interchange/{version}/polars_pandas_arrow.json")
    assert data["schema"] == INTERCHANGE_SCHEMA
    desc = InterchangeDescriptor.from_dict(data)
    rewritten = desc.to_dict()
    again = InterchangeDescriptor.from_dict(rewritten)
    assert again.schema == INTERCHANGE_SCHEMA
    assert again.mechanism == desc.mechanism
    assert again.schema_fingerprint == desc.schema_fingerprint
    selected, _reason = select_mechanism(
        set(data["producer_caps"]),
        set(data["consumer_caps"]),
        durable=False,
        already_collecting=True,
        pyarrow_available=True,
    )
    assert selected.value == data["mechanism"]


def test_interchange_unknown_schema_fail_closed() -> None:
    from etlantic.interchange.tabular import InterchangeDescriptorError

    data = _load("interchange/v0_24/polars_pandas_arrow.json")
    data["schema"] = "etlantic.interchange/99"
    with pytest.raises(InterchangeDescriptorError, match="Unsupported"):
        InterchangeDescriptor.from_dict(data)


@pytest.mark.parametrize("version", ("v0_34", "v0_35", "v0_36"))
def test_quality_expression_round_trip(version: str) -> None:
    from etlantic.quality.serialize import quality_from_dict, quality_to_dict

    data = _load(f"quality/{version}/sample_expression.json")
    assert data["schema"] == "etlantic.quality/1"
    expr = quality_from_dict(data)
    again = quality_from_dict(quality_to_dict(expr))
    assert quality_to_dict(again)["schema"] == "etlantic.quality/1"
