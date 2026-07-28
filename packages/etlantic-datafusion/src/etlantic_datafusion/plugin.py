"""Experimental DataFusion dataframe plugin stub."""

from __future__ import annotations

from typing import Any

from etlantic.capabilities import PluginCapabilities
from etlantic.dataframe.protocol import DataframePluginInfo

__version__ = "0.31.0"


class DataFusionPlugin:
    """Experimental dataframe plugin — kernel claims expand after conformance."""

    info = DataframePluginInfo(
        name="etlantic-datafusion",
        version=__version__,
        engine="datafusion",
        capabilities=PluginCapabilities(
            engine="datafusion",
            dataframe=False,
            eager=False,
            lazy=False,
            arrow_import=False,
            arrow_export=False,
            interchange_mechanisms=frozenset(),
            extras=frozenset({"experimental"}),
        ),
    )

    def materialize(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError(
            "etlantic-datafusion is an experimental stub as of 0.31.0; "
            "materialize is not implemented. See CAPABILITIES."
        )

    def execute_transformation(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError(
            "etlantic-datafusion execute_transformation is experimental/ungraduated "
            "as of 0.31.0"
        )

    def to_records(
        self, value: Any, *, contract_type: type[Any] | None = None
    ) -> list[Any]:
        raise NotImplementedError(
            "etlantic-datafusion to_records is ungraduated as of 0.31.0"
        )

    def from_records(
        self, rows: list[Any], *, contract_type: type[Any] | None = None
    ) -> Any:
        raise NotImplementedError(
            "etlantic-datafusion from_records is ungraduated as of 0.31.0"
        )
