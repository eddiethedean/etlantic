"""0.24 → 0.25 burn-in fixtures for etlantic.pipeline/1.

Golden documents under ``tests/fixtures/burn_in/pipeline/v0_24/`` capture
0.24 wire semantics on schema id ``etlantic.pipeline/1``. 0.25 must read and
rewrite them without a schema-id bump (no wire-schema reset).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from etlantic.authoring import (
    PIPELINE_SCHEMA,
    pipeline_definition,
    pipeline_fingerprint,
    pipeline_from_dict,
    pipeline_to_dict,
    pipeline_to_json,
)
from etlantic.authoring.upgrade import UnsupportedPipelineSchemaError

FIXTURE_DIR = (
    Path(__file__).resolve().parents[1] / "fixtures" / "burn_in" / "pipeline" / "v0_24"
)


def _fixture_paths() -> list[Path]:
    return sorted(p for p in FIXTURE_DIR.glob("*.json") if p.name != "manifest.json")


@pytest.mark.parametrize("path", _fixture_paths(), ids=lambda p: p.stem)
def test_old_reader_new_writer_round_trip(path: Path) -> None:
    """Load a 0.24 golden document, rewrite with 0.25 codecs, reload."""
    original = json.loads(path.read_text(encoding="utf-8"))
    assert original["schema"] == PIPELINE_SCHEMA
    loaded = pipeline_from_dict(original, verify=True)
    assert loaded.schema == PIPELINE_SCHEMA
    assert loaded.fingerprint == original["fingerprint"]

    rewritten = pipeline_to_dict(loaded, with_fingerprint=True)
    assert rewritten["schema"] == PIPELINE_SCHEMA
    assert rewritten["fingerprint"] == original["fingerprint"]

    again = pipeline_from_dict(rewritten, verify=True)
    assert pipeline_fingerprint(again) == original["fingerprint"]
    assert pipeline_to_json(loaded, indent=None) == pipeline_to_json(again, indent=None)


@pytest.mark.parametrize("path", _fixture_paths(), ids=lambda p: p.stem)
def test_new_reader_old_writer_compatible(path: Path) -> None:
    """0.25-built definitions stay on etlantic.pipeline/1 (0.24-compatible)."""
    original = json.loads(path.read_text(encoding="utf-8"))
    loaded = pipeline_from_dict(original, verify=True)
    # Rebuild via dict → definition → dict (new writer path).
    rebuilt = pipeline_from_dict(pipeline_to_dict(loaded), verify=True)
    assert rebuilt.schema == PIPELINE_SCHEMA
    doc = pipeline_to_dict(rebuilt)
    # Documented 0.24-compatible reader rules: same schema id + verify fingerprint.
    accepted = pipeline_from_dict(doc, verify=True)
    assert accepted.pipeline_id == loaded.pipeline_id
    assert {n.name for n in accepted.nodes} == {n.name for n in loaded.nodes}


def test_unknown_schema_still_fail_closed() -> None:
    path = FIXTURE_DIR / "minimal.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["schema"] = "etlantic.pipeline/99"
    with pytest.raises(
        (ValueError, UnsupportedPipelineSchemaError), match="Unsupported"
    ):
        pipeline_from_dict(data, verify=True)


def test_hostile_secret_still_fail_closed() -> None:
    path = FIXTURE_DIR / "minimal.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["metadata"] = {"password": "hunter2"}
    with pytest.raises(ValueError, match=r"forbidden|secret"):
        pipeline_from_dict(data, verify=True)


def test_new_writer_emits_pipeline_schema_v1() -> None:
    defn = pipeline_definition("burnin:fresh", "Fresh", fingerprint=True)
    doc = pipeline_to_dict(defn)
    assert doc["schema"] == PIPELINE_SCHEMA
    assert pipeline_from_dict(doc, verify=True).fingerprint == doc["fingerprint"]
