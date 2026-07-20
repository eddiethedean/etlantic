"""ETLantic 0.19 profile freeze tests."""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from etlantic.plugin_trust import is_production_profile
from etlantic.profile import (
    Profile,
    development_profile,
    production_profile,
    resolve_profile,
    write_profile,
)
from etlantic.profile import (
    test_profile as built_in_test_profile,
)


def test_templates_set_security_mode() -> None:
    assert development_profile().security_mode == "development"
    assert built_in_test_profile().security_mode == "test"
    assert production_profile().security_mode == "production"


def test_is_production_uses_security_mode_only() -> None:
    assert is_production_profile(production_profile()) is True
    named = Profile(name="production", security_mode="development")
    assert is_production_profile(named) is False
    domain = Profile(
        name="dev",
        security_domain="production",
        security_mode="development",
    )
    assert is_production_profile(domain) is False
    assert is_production_profile(None, security_mode="production") is True


def test_resolve_unknown_name_fails_closed() -> None:
    with pytest.raises(ValueError, match="PMCFG100"):
        resolve_profile("definitely-not-a-real-profile")


def test_resolve_adhoc_opt_in() -> None:
    profile = resolve_profile("scratch-env", allow_adhoc_profile=True)
    assert profile.name == "scratch-env"
    assert profile.security_mode == "development"


def test_legacy_bindings_warns(tmp_path: Path) -> None:
    path = tmp_path / "legacy.json"
    path.write_text(
        '{"name":"legacy","security_mode":"development","bindings":{"customers":"csv://x"}}',
        encoding="utf-8",
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        loaded = Profile.from_dict(
            __import__("json").loads(path.read_text(encoding="utf-8")),
            accept_legacy_bindings=True,
        )
    assert any("PMCFG110" in str(w.message) for w in caught)
    assert loaded.assets["customers"] == "csv://x"


def test_legacy_bindings_fail_closed() -> None:
    with pytest.raises(ValueError, match="PMCFG111"):
        Profile.from_dict(
            {"name": "legacy", "security_mode": "development", "bindings": {"a": "b"}},
        )
    with pytest.raises(ValueError, match="PMCFG111"):
        Profile.from_dict(
            {"name": "legacy", "security_mode": "development", "bindings": {"a": "b"}},
            accept_legacy_bindings=False,
        )


def test_write_profile_emits_assets_not_bindings(tmp_path: Path) -> None:
    path = write_profile(
        development_profile(name="demo", assets={"a": "csv://a"}),
        tmp_path / "demo.json",
    )
    text = path.read_text(encoding="utf-8")
    assert '"assets"' in text
    assert '"bindings"' not in text
    assert '"security_mode"' in text
