"""In-process Spark Connect SparkProvider fake."""

from __future__ import annotations

import os

from etlantic.capabilities import PluginCapabilities
from etlantic.spark.provider import (
    ResourceContext,
    SparkProviderInfo,
    SparkSessionHandle,
    SparkSessionRequest,
)

_PKG_VERSION = "0.48.0"


def live_configured() -> bool:
    """True when a live Spark Connect URL is opted in (never required in CI)."""
    return bool(str(os.environ.get("ETLANTIC_SPARK_CONNECT_URL") or "").strip())


class FakeSparkConnectProvider:
    """In-process Spark Connect stand-in. No Databricks/EMR SDK."""

    @property
    def info(self) -> SparkProviderInfo:
        return SparkProviderInfo(
            name="spark-connect",
            version=_PKG_VERSION,
            capabilities=self.capabilities(),
            metadata={"fake": True, "package": "etlantic-spark-connect"},
        )

    def capabilities(self) -> PluginCapabilities:
        return PluginCapabilities(
            engine="spark-connect",
            spark=True,
            dataframe=False,
            extras=frozenset({"spark-connect"}),
        )

    def acquire(
        self,
        request: SparkSessionRequest,
        context: ResourceContext,
    ) -> SparkSessionHandle:
        if live_configured():
            raise RuntimeError("live Spark Connect path is skipped in 0.47 (047-S-01)")
        _ = context
        return SparkSessionHandle(
            identity=f"fake-connect:{request.app_name}",
            app_name=request.app_name,
            master=request.master or "connect://fake",
            metadata={"fake": True},
        )

    def release(
        self,
        handle: SparkSessionHandle,
        context: ResourceContext,
    ) -> None:
        _ = handle, context


def create_provider() -> FakeSparkConnectProvider:
    return FakeSparkConnectProvider()
