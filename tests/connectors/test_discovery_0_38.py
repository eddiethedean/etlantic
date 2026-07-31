"""Connector discovery wiring regressions (0.38)."""

from __future__ import annotations

from etlantic.connectors.discovery import discover_connectors_for_profile
from etlantic.lifecycle.runtime import PipelineRuntime
from etlantic.profile import Profile


def test_discover_connectors_for_profile_no_typeerror() -> None:
    results = discover_connectors_for_profile(Profile(name="dev"))
    assert isinstance(results, dict)
    assert "etlantic.source_connectors" in results
    assert "etlantic.sink_connectors" in results
    assert "etlantic.storage_connectors" in results


def test_ensure_plugins_loads_connector_groups_without_crash() -> None:
    runtime = PipelineRuntime()
    diags = runtime.ensure_plugins_for_profile(
        Profile(name="dev", security_mode="development")
    )
    assert isinstance(diags, list)
    assert isinstance(runtime.source_connectors, dict)
    assert isinstance(runtime.sink_connectors, dict)
    assert isinstance(runtime.storage_connectors, dict)


def test_local_files_present_after_ensure_plugins() -> None:
    runtime = PipelineRuntime()
    assert "local-files" in runtime.source_connectors
    runtime.ensure_plugins_for_profile(Profile(name="dev", security_mode="development"))
    assert "local-files" in runtime.source_connectors
