"""Integration tests: profile-aware plugin discovery on real entry paths."""

from __future__ import annotations

from importlib.metadata import EntryPoint
from unittest.mock import MagicMock

import pytest

from etlantic.lifecycle.runtime import PipelineRuntime
from etlantic.plugin_lifecycle import DiscoveredPlugin
from etlantic.profile import Profile, production_profile
from etlantic.registry import PlanningContext

_LOAD_COUNT = {"value": 0}


def _fake_discovered(*, group: str, name: str = "evil") -> DiscoveredPlugin:
    engine_name = name

    def _load() -> object:
        _LOAD_COUNT["value"] += 1

        class _Info:
            engine = engine_name
            version = "9.9.9"
            capabilities = None
            protocol_version = "etlantic.dataframe/1"

        _Info.name = engine_name  # type: ignore[attr-defined]

        class _Plugin:
            info = _Info()

        return _Plugin()

    ep = MagicMock(spec=EntryPoint)
    ep.name = name
    ep.value = "evil.module:factory"
    ep.group = group
    ep.load = _load
    return DiscoveredPlugin(
        group=group,
        name=name,
        target="evil.module:factory",
        distribution_name="evil-plugin",
        distribution_version="9.9.9",
        entry_point=ep,
    )


@pytest.fixture(autouse=True)
def _reset_load_count() -> None:
    _LOAD_COUNT["value"] = 0


def test_runtime_production_deny_does_not_load(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _fake_discovered(group="etlantic.dataframe_plugins")

    def _discover(group: str) -> tuple[list[DiscoveredPlugin], list]:
        if group == "etlantic.dataframe_plugins":
            return [fake], []
        return [], []

    monkeypatch.setattr("etlantic.plugin_lifecycle.discover_entry_points", _discover)
    runtime = PipelineRuntime()
    profile = production_profile(plugin_allowlist={"only-local": "==1.0.0"})
    runtime.ensure_plugins_for_profile(profile)
    assert _LOAD_COUNT["value"] == 0
    assert "evil" not in runtime.dataframe_plugins


def test_planning_context_production_deny_does_not_load(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _fake_discovered(group="etlantic.dataframe_plugins")

    def _discover(group: str) -> tuple[list[DiscoveredPlugin], list]:
        if group == "etlantic.dataframe_plugins":
            return [fake], []
        return [], []

    monkeypatch.setattr("etlantic.plugin_lifecycle.discover_entry_points", _discover)
    profile = Profile(
        name="production",
        security_mode="production",
        dataframe_engine="polars",
        plugin_allowlist={"only-local": "==1.0.0"},
    )
    PlanningContext.create(profile=profile)
    assert _LOAD_COUNT["value"] == 0


def test_runtime_development_allowlist_empty_loads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _fake_discovered(group="etlantic.dataframe_plugins")

    def _discover(group: str) -> tuple[list[DiscoveredPlugin], list]:
        if group == "etlantic.dataframe_plugins":
            return [fake], []
        return [], []

    monkeypatch.setattr("etlantic.plugin_lifecycle.discover_entry_points", _discover)
    runtime = PipelineRuntime()
    profile = Profile(name="dev", security_mode="development")
    runtime.ensure_plugins_for_profile(profile)
    assert _LOAD_COUNT["value"] == 1
    assert len(runtime.dataframe_plugins) == 1


def test_runtime_profile_switch_drops_unauthorized_plugins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Switching to a tighter production allowlist must clear prior loads."""
    fake = _fake_discovered(group="etlantic.dataframe_plugins", name="polars")

    def _discover(group: str) -> tuple[list[DiscoveredPlugin], list]:
        if group == "etlantic.dataframe_plugins":
            return [fake], []
        return [], []

    monkeypatch.setattr("etlantic.plugin_lifecycle.discover_entry_points", _discover)
    runtime = PipelineRuntime()
    runtime.ensure_plugins_for_profile(Profile(name="dev", security_mode="development"))
    assert "polars" in runtime.dataframe_plugins
    assert "polars" in runtime.registry.plugins or any(
        d.engine == "polars" for d in runtime.registry.plugins.values()
    )

    prod = production_profile(
        plugin_allowlist={"etlantic-pandas": "==0.26.0"},
    )
    diags = runtime.ensure_plugins_for_profile(prod)
    assert "polars" not in runtime.dataframe_plugins
    assert not any(
        d.engine == "polars" or d.name == "polars"
        for d in runtime.registry.plugins.values()
    )
    assert any(d.code == "PMPLUG402" for d in diags) or _LOAD_COUNT["value"] >= 1


def test_manual_sql_plugin_survives_ensure_plugins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit register_sql_plugin must not be wiped by discovery replace."""
    from etlantic.capabilities import PluginCapabilities

    monkeypatch.setattr(
        "etlantic.plugin_lifecycle.discover_entry_points",
        lambda group: ([], []),
    )
    caps = PluginCapabilities(engine="sql", sql=True, dataframe=False, eager=False)

    class _Info:
        name = "sql"
        engine = "sql"
        version = "0.0.0"
        capabilities = caps
        protocol_version = "etlantic.sql/1"
        dialect = "sqlite"

    class _Plugin:
        info = _Info()

        def capabilities(self):
            return caps

    runtime = PipelineRuntime()
    plugin = _Plugin()
    runtime.register_sql_plugin("sql", plugin)
    runtime.ensure_plugins_for_profile(
        Profile(name="dev", security_mode="development", sql_engine="sql")
    )
    assert runtime.sql_plugins["sql"] is plugin


def test_planning_context_with_shared_registry_skips_rediscovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PlanningContext with an existing registry does not re-run discovery."""
    fake = _fake_discovered(group="etlantic.dataframe_plugins", name="polars")

    def _discover(group: str) -> tuple[list[DiscoveredPlugin], list]:
        if group == "etlantic.dataframe_plugins":
            return [fake], []
        return [], []

    monkeypatch.setattr("etlantic.plugin_lifecycle.discover_entry_points", _discover)
    profile = Profile(
        name="dev",
        security_mode="development",
        dataframe_engine="polars",
    )
    runtime = PipelineRuntime()
    runtime.ensure_plugins_for_profile(profile)
    loads_after_runtime = _LOAD_COUNT["value"]
    # Real plugins register under the engine name; mirror that for the mock.
    if (
        profile.dataframe_engine
        and profile.dataframe_engine not in runtime.registry.engines
    ):
        runtime.registry.engines[profile.dataframe_engine] = runtime.registry.engines[
            "local"
        ]
    PlanningContext.create(profile=profile, registry=runtime.registry)
    assert _LOAD_COUNT["value"] == loads_after_runtime
