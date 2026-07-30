"""Minimal 0.35 facade provenance / definition extension burn-in fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from examples.memory_customers import CustomerPipeline

from etlantic.authoring import (
    FACADE_PROTOCOL_VERSION,
    definition_from_pipeline,
    definition_provenance,
    inspect_definition,
    pipeline_from_dict,
    pipeline_to_dict,
)

pytest.importorskip("medallantic")

from medallantic.migrate import generate_from_path

FIXTURES = (
    Path(__file__).resolve().parents[1]
    / "medallantic"
    / "fixtures"
    / "sparkforge"
    / "bronze_only_auto.json"
)


def test_old_reader_new_writer_definition_provenance() -> None:
    """New writer stamps provenance; reader round-trip preserves extension bag."""
    defn = definition_from_pipeline(CustomerPipeline)
    stamped = definition_provenance(
        defn,
        generator_id="test.burn_in",
        source_fingerprint="deadbeef",
        facade_identity="medallantic",
        action="attach",
    )
    assert stamped is not None
    blob = pipeline_to_dict(stamped)
    # Simulate old reader: load dict without understanding provenance semantics.
    restored = pipeline_from_dict(blob)
    read = definition_provenance(restored, action="read")
    assert read is not None
    assert read.generator_id == "test.burn_in"
    assert read.facade_protocol_version == FACADE_PROTOCOL_VERSION
    summary = inspect_definition(restored)
    assert summary.generator_id == "test.burn_in"


def test_new_reader_old_writer_without_provenance() -> None:
    """Definitions without provenance still inspect cleanly (old writer)."""
    defn = definition_from_pipeline(CustomerPipeline)
    blob = pipeline_to_dict(defn)
    # Strip any accidental provenance.
    blob["extensions"] = {
        k: v
        for k, v in dict(blob.get("extensions") or {}).items()
        if k != "etlantic.definition_provenance"
    }
    restored = pipeline_from_dict(blob)
    assert definition_provenance(restored, action="read") is None
    summary = inspect_definition(restored)
    assert summary.generator_id is None
    assert summary.node_names


def test_medallantic_generated_definition_extension_matrix() -> None:
    """Generated Medallantic definitions carry plugin + provenance extensions."""
    result = generate_from_path(FIXTURES, require_auto=True)
    assert result.definition is not None
    blob = pipeline_to_dict(result.definition)
    assert "plugin:medallantic" in dict(blob.get("extensions") or {}) or (
        "etlantic.definition_provenance" in dict(blob.get("extensions") or {})
    )
    # Round-trip JSON as another process would.
    text = json.dumps(blob)
    restored = pipeline_from_dict(json.loads(text))
    prov = definition_provenance(restored, action="read")
    assert prov is not None
    assert prov.facade_protocol_version == FACADE_PROTOCOL_VERSION
