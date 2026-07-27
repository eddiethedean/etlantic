"""Experimental DataFusion plugin stub smoke tests."""

from __future__ import annotations

import pytest

pytest.importorskip("etlantic_datafusion")

from etlantic.dataframe.discovery import discover_dataframe_plugins
from etlantic_datafusion import create_plugin


@pytest.mark.datafusion
def test_datafusion_plugin_discovered() -> None:
    found = discover_dataframe_plugins()
    assert "datafusion" in found


@pytest.mark.datafusion
def test_materialize_stub_raises_not_implemented() -> None:
    plugin = create_plugin()
    with pytest.raises(NotImplementedError, match="experimental stub"):
        plugin.materialize()


@pytest.mark.datafusion
def test_datafusion_capabilities_ungraduated() -> None:
    plugin = create_plugin()
    caps = plugin.info.capabilities
    assert caps.dataframe is False
    assert caps.lazy is False
    assert caps.eager is False
    assert caps.arrow_import is False
    assert caps.arrow_export is False
    assert not caps.interchange_mechanisms
    assert "experimental" in caps.extras
