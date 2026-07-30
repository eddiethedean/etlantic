"""Medallantic M7 migration inventory and safe generation tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("medallantic")

from etlantic.authoring import (
    FACADE_PROTOCOL_VERSION,
    definition_provenance,
    inspect_definition,
)
from medallantic.diagnostics import MDL200_INVENTORY, MDL210_MANUAL, MDL230_GENERATED
from medallantic.migrate import generate_from_path, scan_project
from medallantic.migrate.generate import GENERATOR_ID

pytestmark = pytest.mark.medallantic

FIXTURES = Path(__file__).parent / "fixtures"
SPARKFORGE = FIXTURES / "sparkforge"
SQL = FIXTURES / "sql_pipeline_builder"


def test_scan_project_finds_json_ir() -> None:
    report = scan_project(FIXTURES)
    paths = {a.path for a in report.artifacts}
    assert any(p.endswith("ecommerce.json") or "ecommerce" in p for p in paths)
    assert any("bronze_only_auto.json" in p for p in paths)
    assert report.to_dict()["counts"]["total"] >= 2
    assert any(d.code == MDL200_INVENTORY for d in report.diagnostics)
    blob = json.dumps(report.to_dict())
    assert "password" not in blob.lower()


def test_convertibility_classes() -> None:
    report = scan_project(SPARKFORGE)
    by_name = {Path(a.path).name: a for a in report.artifacts}
    auto = by_name.get("bronze_only_auto.json")
    assert auto is not None
    assert auto.convertibility == "auto"
    ecommerce = by_name.get("ecommerce_equivalent.json")
    assert ecommerce is not None
    assert ecommerce.convertibility == "manual"
    assert MDL210_MANUAL in ecommerce.diagnostic_codes


def test_generate_native_definition_auto_safe() -> None:
    result = generate_from_path(SPARKFORGE / "bronze_only_auto.json", require_auto=True)
    assert result.definition is not None
    assert result.convertibility == "auto"
    assert any(d.code == MDL230_GENERATED for d in result.diagnostics)
    prov = definition_provenance(result.definition, action="read")
    assert prov is not None
    assert prov.generator_id == GENERATOR_ID
    assert prov.facade_protocol_version == FACADE_PROTOCOL_VERSION
    assert result.source_fingerprint
    assert prov.source_fingerprint == result.source_fingerprint
    # Provenance path labels must be relative (fingerprint-stable across hosts).
    assert prov.extras.get("source_path")
    assert not Path(str(prov.extras["source_path"])).is_absolute()
    summary = inspect_definition(result.definition)
    assert summary.pipeline_id
    assert "orders" in summary.node_names or summary.node_names


def test_generate_fingerprint_stable_for_absolute_vs_relative_path() -> None:
    from etlantic.authoring import pipeline_fingerprint

    rel = SPARKFORGE / "bronze_only_auto.json"
    abs_path = rel.resolve()
    a = generate_from_path(rel, require_auto=True)
    b = generate_from_path(abs_path, require_auto=True)
    assert a.definition is not None and b.definition is not None
    assert pipeline_fingerprint(a.definition) == pipeline_fingerprint(b.definition)


def test_generate_refuses_manual_when_require_auto() -> None:
    result = generate_from_path(
        SPARKFORGE / "ecommerce_equivalent.json", require_auto=True
    )
    assert result.definition is None
    assert result.convertibility == "manual"


def test_analysis_does_not_import_project_python(tmp_path: Path) -> None:
    evil = tmp_path / "evil_pipeline.py"
    evil.write_text(
        "raise SystemExit('imported untrusted code')\npipeline_builder = object()\n",
        encoding="utf-8",
    )
    # Static scan must succeed without executing the module.
    report = scan_project(tmp_path)
    assert len(report.artifacts) == 1
    assert report.artifacts[0].convertibility == "manual"
    assert "no_untrusted_import" in report.artifacts[0].notes


def test_cli_inventory_smoke() -> None:
    from medallantic.__main__ import main

    code = main(["migrate", "inventory", str(SPARKFORGE)])
    assert code == 0


def test_sql_builder_fixture_inventoried() -> None:
    report = scan_project(SQL)
    assert report.artifacts
    # sql fixtures share IR shape; engine/sql markers classify builder kind.
    assert any(a.step_count >= 1 for a in report.artifacts)
