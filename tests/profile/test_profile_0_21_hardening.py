"""Regression tests for 0.21 PMCFG111 and production metadata fail-closed."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from etlantic.profile import Profile, load_profile
from etlantic.project import resolve_project_profile, write_minimal_etlantic_toml


def test_empty_assets_does_not_bypass_legacy_bindings() -> None:
    with pytest.raises(ValueError, match="PMCFG111"):
        Profile.from_dict(
            {
                "name": "legacy",
                "security_mode": "development",
                "assets": {},
                "bindings": {"customers": "memory"},
            }
        )


def test_empty_assets_with_legacy_opt_in() -> None:
    profile = Profile.from_dict(
        {
            "name": "legacy",
            "security_mode": "development",
            "assets": {},
            "bindings": {"customers": "memory"},
        },
        accept_legacy_bindings=True,
    )
    assert profile.assets["customers"] == "memory"


def test_inferred_production_enforces_strict_metadata() -> None:
    with pytest.raises(ValueError, match="namespace"):
        Profile.from_dict(
            {
                "name": "production",
                "metadata": {"bare_key": "value"},
            }
        )


def test_accept_legacy_bindings_via_resolve_project_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "profiles").mkdir()
    profile_path = tmp_path / "profiles" / "development.json"
    profile_path.write_text(
        json.dumps(
            {
                "name": "development",
                "security_mode": "development",
                "bindings": {"rows": "memory"},
            }
        ),
        encoding="utf-8",
    )
    write_minimal_etlantic_toml(tmp_path / "etlantic.toml", project="demo")
    with pytest.raises(ValueError, match="PMCFG111"):
        resolve_project_profile("development", start=tmp_path)
    loaded, source = resolve_project_profile(
        "development",
        start=tmp_path,
        accept_legacy_bindings=True,
    )
    assert loaded.assets["rows"] == "memory"
    assert "profiles" in source


def test_load_profile_accept_legacy(tmp_path: Path) -> None:
    path = tmp_path / "legacy.json"
    path.write_text(
        json.dumps(
            {
                "name": "legacy",
                "security_mode": "development",
                "bindings": {"a": "memory"},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="PMCFG111"):
        load_profile(path)
    assert load_profile(path, accept_legacy_bindings=True).assets["a"] == "memory"


def test_from_plan_snapshot_accepts_wire_bindings() -> None:
    profile = Profile(name="dev", security_mode="development", assets={"a": "memory"})
    snap = profile.to_plan_snapshot()
    assert "bindings" in snap
    restored = Profile.from_plan_snapshot(snap)
    assert restored.assets["a"] == "memory"

    empty = Profile(name="empty", security_mode="development")
    restored_empty = Profile.from_plan_snapshot(empty.to_plan_snapshot())
    assert restored_empty.assets == {}


def test_init_production_rejects_bare_metadata() -> None:
    with pytest.raises(ValueError, match="namespace"):
        Profile(
            name="prod",
            security_mode="production",
            metadata={"bare_key": "value"},
        )


def test_init_production_accepts_namespaced_metadata() -> None:
    profile = Profile(
        name="prod",
        security_mode="production",
        metadata={"plugin:owner": "team-a"},
    )
    assert profile.metadata["plugin:owner"] == "team-a"
