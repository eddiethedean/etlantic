"""0.36 security + compatibility adversarial gates (036-A*)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from etlantic.authoring import pipeline_from_dict
from etlantic.authoring.upgrade import UnsupportedPipelineSchemaError
from etlantic.extensions import (
    MAX_METADATA_BYTES,
    MAX_METADATA_DEPTH,
    migrate_report_metadata_keys,
    validate_extension_metadata,
)
from etlantic.reports.model import PipelineRunReport

BURN_IN = Path(__file__).resolve().parents[1] / "fixtures" / "burn_in"
RELEASES = Path(__file__).resolve().parents[1] / "fixtures" / "releases"


def test_secret_like_keys_rejected_in_report_metadata() -> None:
    with pytest.raises(ValueError, match=r"secret|password|token"):
        validate_extension_metadata(
            {"etlantic.demo": {"password": "x"}},
            path="metadata",
            strict=False,
        )


def test_bare_report_keys_migrate_without_warnings() -> None:
    path = RELEASES / "v0_35/known_defects/run_report_bare_metadata.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    report = PipelineRunReport.from_dict(data)
    assert "prefect_run_id" not in report.metadata
    assert report.metadata.get("etlantic.prefect.run_id") == "legacy-run-id-0350"
    again = migrate_report_metadata_keys(dict(report.metadata))
    assert again == report.metadata


def test_oversized_metadata_fail_closed() -> None:
    huge = {"etlantic.blob": "x" * (MAX_METADATA_BYTES + 10)}
    with pytest.raises(ValueError, match="size budget"):
        validate_extension_metadata(huge, path="metadata", strict=False)


def test_deeply_nested_metadata_fail_closed() -> None:
    node: dict = {}
    cur = node
    for _ in range(MAX_METADATA_DEPTH + 2):
        cur["etlantic.child"] = {}
        cur = cur["etlantic.child"]
    with pytest.raises(ValueError, match="nesting depth"):
        validate_extension_metadata(node, path="metadata", strict=False)


def test_unknown_pipeline_schema_fail_closed() -> None:
    path = BURN_IN / "pipeline/v0_36/minimal.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["schema"] = "etlantic.pipeline/99"
    with pytest.raises(
        (UnsupportedPipelineSchemaError, ValueError), match="Unsupported"
    ):
        pipeline_from_dict(data)


def test_hostile_pipeline_password_metadata_fail_closed() -> None:
    path = BURN_IN / "pipeline/v0_36/minimal.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["metadata"] = {"password": "leak"}
    with pytest.raises(ValueError):
        pipeline_from_dict(data)


def test_release_manifests_present_and_hash_verified_shape() -> None:
    for ver in ("v0_34", "v0_35", "v0_36"):
        manifest = RELEASES / ver / "manifest.json"
        assert manifest.is_file(), manifest
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        assert payload.get("schema") == "etlantic.release_baseline/1"
        assert payload.get("release")
        if ver != "v0_36":
            packages = payload.get("packages") or []
            assert packages
            for pkg in packages:
                assert "error" not in pkg
                files = pkg.get("files") or []
                assert files
                assert all(f.get("sha256") for f in files)
