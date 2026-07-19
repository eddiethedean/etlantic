"""Profile and SecretRef tests."""

from __future__ import annotations

from pathlib import Path

from etlantic.profile import (
    development_profile,
    load_profile,
    production_profile,
    resolve_profile,
    write_profile,
)
from etlantic.secrets import SecretRef


def test_profile_templates() -> None:
    assert development_profile().name == "development"
    assert production_profile().security_domain == "production"
    assert resolve_profile("local").name in {"local", "development"}


def test_profile_round_trip(tmp_path: Path) -> None:
    profile = development_profile(
        name="demo",
        assets={"customers": "csv://customers"},
        secrets={
            "token": SecretRef(provider="env-secrets", name="api", key="token"),
        },
    )
    path = write_profile(profile, tmp_path / "demo.json")
    loaded = load_profile(path)
    assert loaded.name == "demo"
    assert loaded.bindings["customers"] == "csv://customers"
    assert loaded.secrets["token"].provider == "env-secrets"


def test_secret_ref_identity() -> None:
    ref = SecretRef(provider="vault", name="db", key="password", version="v1")
    assert "vault" in ref.identity()
    assert ref.to_dict()["key"] == "password"


def test_resolve_profile_loads_json_path(tmp_path: Path) -> None:
    path = write_profile(
        production_profile(
            name="ci-production",
            plugin_allowlist={"local": None},
        ),
        tmp_path / "ci-production.json",
    )
    loaded = resolve_profile(str(path))
    assert loaded.name == "ci-production"
    assert loaded.plugin_allowlist == {"local": None}


def test_resolve_profile_missing_json_raises(tmp_path: Path) -> None:
    missing = tmp_path / "missing-prod.json"
    try:
        resolve_profile(str(missing))
        raise AssertionError("expected FileNotFoundError")
    except FileNotFoundError:
        pass


def test_profile_rejects_plaintext_secrets() -> None:
    try:
        from etlantic.profile import Profile

        Profile.from_dict({"name": "x", "secrets": {"db": "password"}})
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_profile_capabilities_string_not_char_split() -> None:
    from etlantic.profile import Profile

    profile = Profile.from_dict({"name": "x", "required_sql_capabilities": "sql_merge"})
    assert profile.required_sql_capabilities == ("sql_merge",)


def test_with_updates_rejects_unknown_keys() -> None:
    try:
        production_profile(plugin_allow_list={"local": None})  # typo
        raise AssertionError("expected TypeError")
    except TypeError:
        pass
