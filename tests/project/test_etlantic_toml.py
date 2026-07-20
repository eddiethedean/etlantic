"""Project configuration tests."""

from __future__ import annotations

from pathlib import Path

from etlantic.profile import development_profile, write_profile
from etlantic.project import (
    load_project,
    resolve_project_profile,
    write_minimal_etlantic_toml,
)


def test_etlantic_toml_load_and_profile_resolution(tmp_path: Path, monkeypatch) -> None:
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    write_profile(
        development_profile(name="development", assets={"rows": "memory"}),
        profiles / "development.json",
    )
    write_minimal_etlantic_toml(tmp_path / "etlantic.toml", project="demo")
    monkeypatch.chdir(tmp_path)
    project = load_project()
    assert project is not None
    assert project.default_profile == "development"
    profile, source = resolve_project_profile(None)
    assert profile.name == "development"
    assert "development.json" in source or "etlantic.toml" in source
