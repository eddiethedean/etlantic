"""DataFusion portable baseline smoke tests."""

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
def test_materialize_requires_value_but_is_implemented() -> None:
    plugin = create_plugin()
    with pytest.raises(TypeError, match="requires a value"):
        plugin.materialize()


@pytest.mark.datafusion
def test_datafusion_capabilities_graduated() -> None:
    plugin = create_plugin()
    caps = plugin.info.capabilities
    assert caps.dataframe is True
    assert caps.lazy is True
    assert caps.eager is True
    assert caps.arrow_import is True
    assert caps.arrow_export is True
    assert caps.interchange_mechanisms
    assert "datafusion" in caps.extras
