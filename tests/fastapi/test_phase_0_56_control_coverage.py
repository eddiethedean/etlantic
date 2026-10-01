"""Fail-closed public field and command coverage for phase 0.56."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("etlantic_fastapi")

from scripts.check_phase_0_56_control_coverage import (
    INVENTORY_PATH,
    validate_inventory,
)


def _inventory() -> dict[str, Any]:
    return json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))


def test_public_control_inventory_covers_every_cp_operation_and_field() -> None:
    errors = validate_inventory(_inventory())
    assert errors == []


def test_omitting_a_public_control_fails_qualification() -> None:
    inventory = _inventory()
    inventory["operations"].pop()

    errors = validate_inventory(inventory)

    assert any(error.startswith("unmapped public operations:") for error in errors)


def test_managed_schedule_policy_fields_are_visible_in_openapi_inventory() -> None:
    operation = next(
        row
        for row in _inventory()["operations"]
        if row["operation_id"] == "cp_create_schedule"
    )
    request_paths = {
        field["path"] for field in operation["fields"] if field["surface"] == "request"
    }
    assert "revision_selector" in request_paths
    assert "spec<anyOf:0>.kind" in request_paths
    assert "parameter_refs<anyOf:0>.*" in request_paths
    assert "secret_refs<anyOf:0>.*<anyOf:0>.version" in request_paths
    assert "workload_identity<anyOf:0>.issuer" in request_paths


def test_downgrading_a_public_control_or_omitting_a_field_fails_qualification() -> None:
    inventory = _inventory()
    operation = next(
        row for row in inventory["operations"] if row["operation_id"] == "cp_submit_run"
    )
    operation["coverage"] = "unavailable"
    operation["fields"].pop()

    errors = validate_inventory(inventory)

    assert any(
        error == "cp_submit_run: coverage may not be downgraded" for error in errors
    )
    assert any(
        error == "cp_submit_run: fields is stale or incomplete" for error in errors
    )


def test_inventory_and_evidence_references_are_repository_relative() -> None:
    assert Path(INVENTORY_PATH).is_file()
