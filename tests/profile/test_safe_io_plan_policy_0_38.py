"""SafeIoPlanPolicy and path-free local-files SourcePlan (0.38)."""

from __future__ import annotations

import json
from pathlib import Path

import anyio
import pytest

from etlantic.connectors.local_files import LocalFilesSourceConnector
from etlantic.io_policy import SafeIoPlanPolicy, SafeIoPolicy, sanitize_safe_io_for_plan
from etlantic.profile import Profile


def test_safe_io_plan_policy_omits_approved_roots(tmp_path: Path) -> None:
    runtime = {
        "approved_roots": [str(tmp_path / "landing")],
        "root_refs": ["landing"],
        "symlink_policy": "reject",
        "max_read_bytes": 1024,
    }
    plan = SafeIoPlanPolicy.from_safe_io(runtime)
    data = plan.to_dict()
    assert "approved_roots" not in data
    assert data["root_refs"] == ["landing"]
    assert data["fail_on_symlink"] is True
    assert data["symlink_policy"] == "reject"
    encoded = json.dumps(data)
    assert str(tmp_path) not in encoded
    assert str(tmp_path / "landing") not in encoded


def test_profile_plan_snapshot_strips_absolute_safe_io_roots(tmp_path: Path) -> None:
    abs_root = str(tmp_path.resolve())
    profile = Profile(
        name="dev",
        security_mode="development",
        assets={"rows": "memory://rows"},
        safe_io={
            "approved_roots": [abs_root],
            "root_refs": ["landing"],
            "symlink_policy": "reject",
        },
    )
    snap = profile.to_plan_snapshot()
    safe = snap["safe_io"]
    assert "approved_roots" not in safe
    assert abs_root not in json.dumps(snap)
    assert safe.get("root_refs") == ["landing"]
    assert safe.get("fail_on_symlink") is True


def test_sanitize_empty_safe_io_preserves_empty() -> None:
    assert sanitize_safe_io_for_plan({}) == {}
    assert sanitize_safe_io_for_plan(None) == {}


def test_safe_io_plan_root_refs_are_atomic_relative_aliases() -> None:
    assert SafeIoPlanPolicy.from_safe_io({"root_refs": "landing"}).root_refs == (
        "landing",
    )
    for unsafe_ref in ("/var/landing", "C:\\landing", "../landing", ""):
        with pytest.raises(ValueError, match="relative"):
            SafeIoPlanPolicy.from_safe_io({"root_refs": [unsafe_ref]})


def test_source_plan_has_no_absolute_landing_root(tmp_path: Path) -> None:
    abs_root = str(tmp_path.resolve())
    connector = LocalFilesSourceConnector()
    policy = SafeIoPolicy.for_root(tmp_path)
    binding = {
        "provider": "local-files",
        "format": "csv",
        "root": abs_root,  # absolute — must not appear in plan artifact
        "root_ref": "landing",
        "glob": "*.csv",
        "mode": "snapshot",
    }

    async def _run() -> None:
        plan = await connector.plan_read(
            binding=binding,
            context={"run_id": "p1", "safe_io": policy},
        )
        payload = plan.to_dict()
        encoded = json.dumps(payload)
        assert abs_root not in encoded
        assert payload["listing_intent"]["root_ref"] == "landing"
        assert (
            "root" not in payload["listing_intent"]
            or not Path(str(payload["listing_intent"].get("root") or ".")).is_absolute()
        )

    anyio.run(_run)


def test_source_plan_keeps_relative_root() -> None:
    connector = LocalFilesSourceConnector()

    async def _run() -> None:
        plan = await connector.plan_read(
            binding={
                "provider": "local-files",
                "format": "csv",
                "root": "inbox",
                "root_ref": "landing",
                "glob": "*.csv",
                "mode": "snapshot",
            },
            context={"run_id": "p2"},
        )
        assert plan.listing_intent["root_ref"] == "landing"
        assert plan.listing_intent.get("root") == "inbox"

    anyio.run(_run)
