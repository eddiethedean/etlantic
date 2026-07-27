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
    with pytest.raises(NotImplementedError, match="experimental"):
        plugin.materialize()
