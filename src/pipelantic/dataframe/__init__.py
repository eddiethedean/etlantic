"""Versioned dataframe execution protocol (pipelantic.dataframe/1).

Core stays engine-free. Polars/Pandas plugins implement ``DataframePlugin``.
"""

from __future__ import annotations

from pipelantic.dataframe.arrow import (
    arrow_available,
    from_arrow_table,
    records_to_arrow_table,
    to_arrow_table,
)
from pipelantic.dataframe.discovery import (
    DATAFRAME_PLUGIN_ENTRY_POINT,
    discover_dataframe_plugins,
    register_discovered_plugins,
)
from pipelantic.dataframe.protocol import (
    DATAFRAME_ENGINES,
    DATAFRAME_PROTOCOL_VERSION,
    ArtifactOwnership,
    DataframeExecutionContext,
    DataframeMetrics,
    DataframeOutputBundle,
    DataframePhase,
    DataframePlugin,
    DataframePluginInfo,
    DataframeValidationOutcome,
    DataframeValidationPolicy,
    ValidationDecision,
)

__all__ = [
    "DATAFRAME_ENGINES",
    "DATAFRAME_PLUGIN_ENTRY_POINT",
    "DATAFRAME_PROTOCOL_VERSION",
    "ArtifactOwnership",
    "DataframeExecutionContext",
    "DataframeMetrics",
    "DataframeOutputBundle",
    "DataframePhase",
    "DataframePlugin",
    "DataframePluginInfo",
    "DataframeValidationOutcome",
    "DataframeValidationPolicy",
    "ValidationDecision",
    "arrow_available",
    "discover_dataframe_plugins",
    "from_arrow_table",
    "records_to_arrow_table",
    "register_discovered_plugins",
    "to_arrow_table",
]
