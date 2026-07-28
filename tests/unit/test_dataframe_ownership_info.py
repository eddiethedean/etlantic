"""Regression: resolve dataframe plugin.info as property or callable."""

from __future__ import annotations

from etlantic.capabilities import PluginCapabilities
from etlantic.dataframe.protocol import (
    ArtifactOwnership,
    DataframePluginInfo,
)
from etlantic.runtime.dataframe_exec import (
    ownership_for_engine,
    resolve_plugin_info,
)


class _PropertyInfoPlugin:
    @property
    def info(self) -> DataframePluginInfo:
        return DataframePluginInfo(
            name="prop",
            engine="prop",
            version="0.27.0",
            protocol_version="etlantic.dataframe/1",
            capabilities=PluginCapabilities(
                engine="prop", dataframe=True, thread_safe=False
            ),
        )


class _CallableInfoPlugin:
    def info(self) -> DataframePluginInfo:
        return DataframePluginInfo(
            name="call",
            engine="call",
            version="0.27.0",
            protocol_version="etlantic.dataframe/1",
            capabilities=PluginCapabilities(
                engine="call", dataframe=True, thread_safe=True
            ),
        )


def test_resolve_plugin_info_property_and_callable() -> None:
    prop = resolve_plugin_info(_PropertyInfoPlugin())
    call = resolve_plugin_info(_CallableInfoPlugin())
    assert prop.capabilities.thread_safe is False
    assert call.capabilities.thread_safe is True
    assert (
        ownership_for_engine("prop", capabilities=prop.capabilities)
        is ArtifactOwnership.COPIED
    )
    assert (
        ownership_for_engine("call", capabilities=call.capabilities)
        is ArtifactOwnership.SHARED
    )
    assert ownership_for_engine("unknown") is ArtifactOwnership.COPIED
