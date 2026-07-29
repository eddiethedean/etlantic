"""Local Spark session provider for ETLantic."""

from __future__ import annotations

import contextlib
import uuid
from typing import Any

from etlantic.capabilities import PluginCapabilities
from etlantic.spark.provider import (
    ResourceContext,
    SessionOwnership,
    SparkProviderInfo,
    SparkSessionHandle,
    SparkSessionRequest,
)

__version__ = "0.32.0"


class LocalSparkProvider:
    """In-process SparkSession provider for CI and local development."""

    def __init__(self) -> None:
        caps = PluginCapabilities(
            engine="pyspark",
            spark=True,
            dataframe=True,
            eager=False,
            lazy=True,
            streaming=True,
            checkpoints=True,
            spark_streaming=True,
            spark_delta=True,
            spark_cache=True,
            spark_checkpoint=True,
            cancellation=True,
            extras=frozenset(
                {
                    "local_spark",
                    "storage.delta.merge",
                    "storage.delta.optimize",
                    "storage.delta.vacuum",
                    "storage.delta.history",
                    "storage.delta.time_travel",
                    "storage.delta.schema_evolution",
                }
            ),
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
            resolved_config[str(key)] = self._resolve_config_value(
                ref, context=context, required=False
            )
        for key, ref in request.secret_refs.items():
            resolved_config[str(key)] = self._resolve_config_value(
                ref, context=context, required=True
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
                delta_enabled=bool(request.enable_delta),
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
        delta_enabled = False
        if request.enable_delta:
            try:
                builder = builder.config(
                    "spark.sql.extensions",
                    "io.delta.sql.DeltaSparkSessionExtension",
                ).config(
                    "spark.sql.catalog.spark_catalog",
                    "org.apache.spark.sql.delta.catalog.DeltaCatalog",
                )
                delta_enabled = True
            except Exception as exc:
                raise RuntimeError(
                    "Failed to apply Delta session configuration; failing closed."
                ) from exc

        session = builder.getOrCreate()
        handle = SparkSessionHandle(
            identity=f"spark-{uuid.uuid4().hex[:10]}",
            ownership=SessionOwnership.PROVIDER,
            app_name=request.app_name,
            master=request.master or "local[2]",
            delta_enabled=delta_enabled,
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

    @staticmethod
    def _resolve_config_value(
        ref: Any,
        *,
        context: ResourceContext,
        required: bool,
    ) -> str:
        if isinstance(ref, dict):
            key = str(ref.get("key") or "")
            if not key:
                if required:
                    raise RuntimeError("secret_refs entry missing 'key'")
                return ""
            if context.resolve_secret is None:
                if required:
                    raise RuntimeError(
                        f"secret_refs requires resolve_secret for key {key!r}"
                    )
                return key
            return str(context.resolve_secret(key))
        text = str(ref)
        if text.startswith("secret:"):
            key = text[7:]
            if context.resolve_secret is None:
                if required:
                    raise RuntimeError(
                        f"secret_refs requires resolve_secret for key {key!r}"
                    )
                return key
            return str(context.resolve_secret(key))
        if required and context.resolve_secret is not None:
            return str(context.resolve_secret(text))
        if required and context.resolve_secret is None:
            raise RuntimeError(f"secret_refs requires resolve_secret for key {text!r}")
        return text


def create_provider() -> LocalSparkProvider:
    """Entry-point factory for ``etlantic.spark_providers``."""
    return LocalSparkProvider()
