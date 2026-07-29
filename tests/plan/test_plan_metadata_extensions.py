"""Plan metadata extension validation regressions."""

from __future__ import annotations

import copy
import json
import warnings
from pathlib import Path

import pytest

from etlantic.extensions import MAX_METADATA_BYTES
from etlantic.plan.model import PipelinePlan

_BURN_IN_PLAN = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "burn_in"
    / "plan"
    / "v0_26"
    / "sample_local.json"
)


def _load_burn_in_plan() -> dict:
    return json.loads(_BURN_IN_PLAN.read_text(encoding="utf-8"))


def test_burn_in_plan_loads_without_bare_key_warnings() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        plan = PipelinePlan.from_dict(_load_burn_in_plan())
    bare_warnings = [w for w in caught if "bare keys" in str(w.message)]
    assert bare_warnings == []
    assert plan.profile_snapshot.get("security_mode") == "development"


def test_graph_metadata_bare_plugin_key_warns_in_development() -> None:
    data = _load_burn_in_plan()
    data["logical_graph"]["metadata"] = {"plugin:custom": "ok", "bare": 1}
    with pytest.warns(UserWarning, match="logical_graph.metadata"):
        PipelinePlan.from_dict(data, verify=False)


def test_graph_metadata_bare_plugin_key_raises_in_production() -> None:
    data = _load_burn_in_plan()
    data["profile_snapshot"]["security_mode"] = "production"
    data["logical_graph"]["metadata"] = {"bare": 1}
    with pytest.raises(ValueError, match=r"logical_graph\.metadata"):
        PipelinePlan.from_dict(data, verify=False)


def test_production_name_requires_security_mode_production() -> None:
    data = _load_burn_in_plan()
    data["profile_snapshot"]["name"] = "production"
    data["profile_snapshot"]["security_mode"] = ""
    with pytest.raises(ValueError, match=r"security_mode"):
        PipelinePlan.from_dict(data, verify=False)


def test_region_metadata_rejects_oversized_payload() -> None:
    data = _load_burn_in_plan()
    if not data.get("regions"):
        data["regions"] = [
            {
                "identity": "region:local",
                "engine": "local",
                "node_names": ["raw"],
                "security_domain": "default",
                "metadata": {},
            }
        ]
    huge = "x" * (MAX_METADATA_BYTES + 1)
    data["regions"][0]["metadata"] = {"plugin:payload": huge}
    with pytest.raises(ValueError, match=r"region\.metadata"):
        PipelinePlan.from_dict(data, verify=False)


def test_boundary_metadata_validates() -> None:
    data = _load_burn_in_plan()
    boundary = {
        "identity": "boundary:test",
        "producer_node": "raw",
        "producer_port": "result",
        "reason": "collection_point",
        "security_domain": "default",
        "metadata": {"engine": "local", "bare_plugin": 1},
    }
    data["materialization_boundaries"] = [boundary]
    with pytest.warns(UserWarning, match="boundary.metadata"):
        PipelinePlan.from_dict(data, verify=False)


def test_artifact_metadata_validates() -> None:
    data = _load_burn_in_plan()
    if not data.get("output_resolutions"):
        pytest.skip("burn-in plan has no output_resolutions")
    data = copy.deepcopy(data)
    data["output_resolutions"][0]["artifact"]["metadata"] = {"bare": 1}
    with pytest.warns(UserWarning, match="artifact.metadata"):
        PipelinePlan.from_dict(data, verify=False)
