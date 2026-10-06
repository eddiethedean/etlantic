"""0.36 joint upgrade evidence: release baselines + current-reader burn-in."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from etlantic.authoring import pipeline_from_dict, pipeline_to_dict
from etlantic.reports.model import PipelineRunReport

ROOT = Path(__file__).resolve().parents[2]
BURN_IN = ROOT / "tests" / "fixtures" / "burn_in"
RELEASES = ROOT / "tests" / "fixtures" / "releases"


def test_034_to_035_pipeline_fixture_compatible() -> None:
    data = json.loads(
        (BURN_IN / "pipeline/v0_34/minimal.json").read_text(encoding="utf-8")
    )
    loaded = pipeline_from_dict(data, verify=True)
    rewritten = pipeline_to_dict(loaded, with_fingerprint=True)
    assert rewritten["fingerprint"] == data["fingerprint"]


def test_035_to_036_pipeline_fixture_compatible() -> None:
    data = json.loads(
        (BURN_IN / "pipeline/v0_35/minimal.json").read_text(encoding="utf-8")
    )
    loaded = pipeline_from_dict(data, verify=True)
    rewritten = pipeline_to_dict(loaded, with_fingerprint=True)
    assert rewritten["fingerprint"] == data["fingerprint"]


def test_035_bare_report_is_rejected_by_current_reader() -> None:
    data = json.loads(
        (RELEASES / "v0_35/known_defects/run_report_bare_metadata.json").read_text(
            encoding="utf-8"
        )
    )
    with pytest.raises(ValueError, match="unsupported legacy metadata key"):
        PipelineRunReport.from_dict(data)


def test_release_baseline_covers_thirteen_distributions() -> None:
    expected = {
        "etlantic",
        "etlantic-polars",
        "etlantic-pandas",
        "etlantic-sql",
        "etlantic-pyspark",
        "etlantic-airflow",
        "etlantic-prefect",
        "etlantic-keyring",
        "etlantic-sqlmodel",
        "etlantic-fastapi",
        "etlantic-datafusion",
        "etlantic-sparkforge",
        "medallantic",
    }
    for ver in ("v0_34", "v0_35"):
        payload = json.loads(
            (RELEASES / ver / "manifest.json").read_text(encoding="utf-8")
        )
        names = {p["package"] for p in payload["packages"]}
        assert names == expected
