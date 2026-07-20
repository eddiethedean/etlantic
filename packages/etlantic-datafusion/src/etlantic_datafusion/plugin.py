"""Experimental DataFusion dataframe plugin stub."""

from __future__ import annotations

from typing import Any

from etlantic.capabilities import PluginCapabilities
from etlantic.dataframe.protocol import DataframePluginInfo
from etlantic.interchange.tabular import InterchangeMechanism

__version__ = "0.21.0"


class DataFusionPlugin:
    """Experimental dataframe plugin — kernel claims expand after conformance."""

    info = DataframePluginInfo(
        name="etlantic-datafusion",
        version=__version__,
        engine="datafusion",
        capabilities=PluginCapabilities(
            engine="datafusion",
            dataframe=True,
            eager=False,
            lazy=True,
            arrow_import=True,
            arrow_export=True,
            interchange_mechanisms=frozenset(
                {
                    InterchangeMechanism.ARROW_C_DATA.value,
                    InterchangeMechanism.RECORDS_FALLBACK.value,
                }
            ),
            extras=frozenset({"experimental"}),
        ),
    )

    def materialize(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError(
            "etlantic-datafusion is experimental; kernel materialize is not "
            "experimental as of 0.20.0. See CAPABILITIES and INTEROPERABILITY plan."
        )

    def execute_transformation(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError(
            "etlantic-datafusion execute_transformation is experimental/ungraduated"
        )

    def to_records(
        self, value: Any, *, contract_type: type[Any] | None = None
    ) -> list[Any]:
        raise NotImplementedError("etlantic-datafusion to_records is ungraduated")

    def from_records(
        self, rows: list[Any], *, contract_type: type[Any] | None = None
    ) -> Any:
        raise NotImplementedError("etlantic-datafusion from_records is ungraduated")
