"""Local Spark session provider for ETLantic."""

from __future__ import annotations

import contextlib
import uuid

from etlantic.capabilities import PluginCapabilities
from etlantic.spark.provider import (
    ResourceContext,
    SessionOwnership,
    SparkProviderInfo,
    SparkSessionHandle,
    SparkSessionRequest,
)

__version__ = "0.21.0"


class LocalSparkProvider:
    """In-process SparkSession provider for CI and local development."""

    def __init__(self) -> None:
        caps = PluginCapabilities(
            engine="pyspark",
            spark=True,
            dataframe=False,
            eager=False,
            lazy=True,
            streaming=True,
            checkpoints=True,
            spark_streaming=True,
            spark_delta=False,
            spark_cache=True,
            spark_checkpoint=True,
            cancellation=True,
            extras=frozenset({"local_spark"}),
        )
        self._info = SparkProviderInfo(
            name="local",
            version=__version__,
            capabilities=caps,
            metadata={"streaming_stability": "experimental"},
        )
        self._owned: set[str] = set()

    @property
    def info(self) -> SparkProviderInfo:
        return self._info

    def capabilities(self) -> PluginCapabilities:
        assert self._info.capabilities is not None
        return self._info.capabilities

    def acquire(
        self,
        request: SparkSessionRequest,
        context: ResourceContext,
    ) -> SparkSessionHandle:
        # Resolve secret refs at acquire time only — never store values on the handle.
        resolved_config: dict[str, str] = {}
        for key, ref in request.config_refs.items():
            if context.resolve_secret is not None and ref.startswith("secret:"):
                resolved_config[key] = str(context.resolve_secret(ref[7:]))
            else:
                resolved_config[key] = ref
        for _key, ref in request.secret_refs.items():
            # Secret values used only for builder config; not retained on handle.
            if context.resolve_secret is not None:
                _ = context.resolve_secret(
                    ref if not isinstance(ref, dict) else ref.get("key", "")
                )

        if request.ownership is SessionOwnership.EXTERNAL:
            # Expect an externally managed session passed via metadata.
            external = (request.metadata or {}).get("session")
            if external is None:
                raise RuntimeError(
                    "EXTERNAL ownership requires metadata['session'] at acquire."
                )
            return SparkSessionHandle(
                identity=f"spark-ext-{uuid.uuid4().hex[:10]}",
                ownership=SessionOwnership.EXTERNAL,
                app_name=request.app_name,
                master=request.master,
                delta_enabled=request.enable_delta,
                metadata={"run_id": context.run_id},
                _session=external,
            )

        from etlantic_pyspark.sparkless_shim import install

        install()
        from pyspark.sql import SparkSession

        builder = (
            SparkSession.builder.appName(request.app_name)
            .master(request.master or "local[2]")
            .config("spark.ui.enabled", "false")
            .config("spark.sql.shuffle.partitions", "2")
            .config("spark.driver.host", "127.0.0.1")
        )
        for key, value in resolved_config.items():
            builder = builder.config(key, value)
        if request.checkpoint_root:
            builder = builder.config(
                "spark.sql.streaming.checkpointLocation", request.checkpoint_root
            )
        if request.enable_delta:
            with contextlib.suppress(Exception):
                builder = builder.config(
                    "spark.sql.extensions",
                    "io.delta.sql.DeltaSparkSessionExtension",
                ).config(
                    "spark.sql.catalog.spark_catalog",
                    "org.apache.spark.sql.delta.catalog.DeltaCatalog",
                )

        session = builder.getOrCreate()
        handle = SparkSessionHandle(
            identity=f"spark-{uuid.uuid4().hex[:10]}",
            ownership=SessionOwnership.PROVIDER,
            app_name=request.app_name,
            master=request.master or "local[2]",
            delta_enabled=request.enable_delta,
            metadata={
                "run_id": context.run_id,
                "plan_id": context.plan_id,
                # Explicitly omit secrets from serializable metadata.
            },
            _session=session,
        )
        self._owned.add(handle.identity)
        return handle

    def release(
        self,
        handle: SparkSessionHandle,
        context: ResourceContext,
    ) -> None:
        _ = context
        if handle.ownership is SessionOwnership.EXTERNAL:
            return
        if handle.identity not in self._owned:
            return
        session = handle.session
        self._owned.discard(handle.identity)
        if session is not None:
            with contextlib.suppress(Exception):
                session.stop()


def create_provider() -> LocalSparkProvider:
    """Entry-point factory for ``etlantic.spark_providers``."""
    return LocalSparkProvider()
