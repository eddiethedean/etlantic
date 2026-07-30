"""Golden before/after definition fingerprints for SparkForge IR migration (M7)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("medallantic")

from etlantic.authoring import (
    inspect_definition,
    pipeline_fingerprint,
    plan_pipeline_like,
)
from medallantic.migrate import generate_from_path

pytestmark = pytest.mark.medallantic

FIXTURES = Path(__file__).parent / "fixtures"
GOLDENS = FIXTURES / "goldens"
SPARKFORGE = FIXTURES / "sparkforge"
SQL = FIXTURES / "sql_pipeline_builder"


def _definition_golden_payload(path: Path) -> dict:
    result = generate_from_path(path, require_auto=False)
    assert result.definition is not None
    summary = inspect_definition(result.definition)
    return {
        "source": path.name,
        "pipeline_id": result.definition.pipeline_id,
        "definition_fingerprint": pipeline_fingerprint(result.definition),
        "node_names": list(summary.node_names),
        "assets": list(summary.assets),
        "source_fingerprint": result.source_fingerprint,
        "generator_id": "medallantic.migrate.generate",
        "convertibility": result.convertibility,
    }


@pytest.mark.parametrize(
    ("ir_path", "golden_name"),
    [
        (SPARKFORGE / "bronze_only_auto.json", "sparkforge_bronze_only_auto"),
        (SPARKFORGE / "ecommerce_equivalent.json", "sparkforge_ecommerce"),
        (SQL / "ecommerce_equivalent.json", "sql_ecommerce"),
    ],
    ids=["sparkforge_bronze_auto", "sparkforge_ecommerce", "sql_ecommerce"],
)
def test_golden_migration_definition_fingerprint(
    ir_path: Path, golden_name: str
) -> None:
    payload = _definition_golden_payload(ir_path)
    golden_path = GOLDENS / f"{golden_name}.definition.json"
    if not golden_path.exists():
        golden_path.parent.mkdir(parents=True, exist_ok=True)
        golden_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    expected = json.loads(golden_path.read_text(encoding="utf-8"))
    assert payload["definition_fingerprint"] == expected["definition_fingerprint"]
    assert payload["node_names"] == expected["node_names"]
    assert payload["generator_id"] == expected["generator_id"]


def test_sparkforge_plan_golden_when_plannable() -> None:
    """Plan fingerprint golden for auto-safe local IR (differential-ready)."""
    path = SPARKFORGE / "bronze_only_auto.json"
    result = generate_from_path(path, require_auto=True)
    assert result.adaptation is not None
    plan = plan_pipeline_like(
        result.adaptation.pipeline_cls,
        profile=result.adaptation.profile,
    )
    payload = {
        "source": path.name,
        "plan_fingerprint": plan.fingerprint,
    }
    golden_path = GOLDENS / "bronze_only_auto.plan.json"
    if not golden_path.exists():
        golden_path.parent.mkdir(parents=True, exist_ok=True)
        golden_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    expected = json.loads(golden_path.read_text(encoding="utf-8"))
    assert payload["plan_fingerprint"] == expected["plan_fingerprint"]
