"""PySpark execution plugin for ETLantic."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import Any

from etlantic.capabilities import PluginCapabilities
from etlantic.spark.protocol import (
    SPARK_PROTOCOL_VERSION,
    STREAMING_STABILITY,
    CompiledSparkPlan,
    DatasetRef,
    ExpressionStrategy,
    SchemaCompatibility,
    SparkAction,
    SparkActionKind,
    SparkCompilationContext,
    SparkDataFrameHandle,
    SparkExecutionContext,
    SparkExecutionResult,
    SparkMetrics,
    SparkPlanRegion,
    SparkPluginInfo,
    SparkUdfPolicy,
    SparkWrite,
    SparkWriteMode,
)
from etlantic.spark.provider import SparkSessionHandle
from etlantic.spark.schema import (
    map_contract_schema,
    observation_from_spark_schema,
)
from etlantic.storage.protocol import as_records, records_to_dicts

__version__ = "0.21.0"


def _set_job_group(session: Any, group: str, description: str) -> None:
    """Best-effort job group tagging (no-op on sparkless / limited contexts)."""
    spark_context = getattr(session, "sparkContext", None)
    setter = getattr(spark_context, "setJobGroup", None)
    if callable(setter):
        setter(group, description)


def _row_as_dict(row: Any) -> dict[str, Any]:
    """Row → dict helper compatible with PySpark and sparkless."""
    as_dict = getattr(row, "asDict", None)
    if callable(as_dict):
        try:
            return as_dict(recursive=True)
        except TypeError:
            return as_dict()
    if isinstance(row, Mapping):
        return dict(row)
    return dict(row)  # type: ignore[arg-type]


def create_plugin() -> PySparkPlugin:
    """Entry-point factory for ``etlantic.spark_plugins``."""
    return PySparkPlugin()


class PySparkPlugin:
    """Reference PySpark region compiler and executor."""

    def __init__(self) -> None:
        caps = PluginCapabilities(
            engine="pyspark",
            async_execution=False,
            dataframe=False,
            spark=True,
            eager=False,
            lazy=True,
            streaming=True,
            checkpoints=True,
            schema_inspection=True,
            invalid_row_separation=True,
            cancellation=True,
            spark_delta=True,
            spark_merge=True,
            spark_streaming=True,
            spark_native_exprs=True,
            spark_udf=True,
            spark_cache=True,
            spark_checkpoint=True,
            extras=frozenset({"pyspark", "delta_compatible"}),
        )
        self._info = SparkPluginInfo(
            name="etlantic-pyspark",
            engine="pyspark",
            version=__version__,
            protocol_version=SPARK_PROTOCOL_VERSION,
            capabilities=caps,
            streaming_stability=STREAMING_STABILITY,
            metadata={"delta_optimize": False, "delta_vacuum": False},
        )
        self._session: Any = None
        self._frames: dict[str, Any] = {}
        self._delta_enabled = False

    @property
    def info(self) -> SparkPluginInfo:
        return self._info

    def capabilities(self) -> PluginCapabilities:
        assert self._info.capabilities is not None
        return self._info.capabilities

    def bind_session(self, handle: SparkSessionHandle) -> None:
        self._session = handle.session
        self._delta_enabled = bool(handle.delta_enabled)

    def dataset_from_binding(
        self,
        *,
        binding: str,
        location: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> DatasetRef:
        meta = dict(metadata or {})
        fmt = meta.get("format")
        if location and location.endswith(".delta"):
            fmt = fmt or "delta"
        elif location and location.endswith(".parquet"):
            fmt = fmt or "parquet"
        return DatasetRef(
            name=binding,
            format=str(fmt) if fmt else None,
            path=location,
            table=meta.get("table"),
            options={str(k): str(v) for k, v in (meta.get("options") or {}).items()},
        )

    def compile(
        self,
        region: SparkPlanRegion,
        *,
        context: SparkCompilationContext,
    ) -> CompiledSparkPlan:
        strategies: list[ExpressionStrategy] = [ExpressionStrategy.NATIVE_DF]
        if context.udf_policy is SparkUdfPolicy.ALLOW:
            # Implementations may still declare UDFs; compile records preference.
            pass
        actions = [
            SparkAction(
                kind=SparkActionKind.MATERIALIZE,
                node_name=region.node_names[-1],
                reason="region_sink_or_boundary",
            )
        ]
        if region.streaming:
            actions.append(
                SparkAction(
                    kind=SparkActionKind.STREAMING_START,
                    node_name=region.node_names[-1],
                    reason="streaming_region",
                )
            )
        return CompiledSparkPlan(
            region_id=region.identity,
            node_names=region.node_names,
            actions=tuple(actions),
            expression_strategies=tuple(strategies),
            streaming=region.streaming,
            logical_identities={n: n for n in region.node_names},
            metadata={
                "udf_policy": context.udf_policy.value,
                "strategy": "lazy_fusion",
                "streaming_stability": STREAMING_STABILITY,
            },
        )

    def execute(
        self,
        compiled: CompiledSparkPlan,
        *,
        context: SparkExecutionContext,
        inputs: Mapping[str, Any] | None = None,
    ) -> SparkExecutionResult:
        _ = inputs
        if context.job_group and self._session is not None:
            _set_job_group(
                self._session, context.job_group, f"etlantic:{compiled.region_id}"
            )
        metrics = SparkMetrics(
            fused_steps=len(compiled.node_names),
            stages=1,
            actions=[a.kind.value for a in compiled.actions],
            expression_strategies=[s.value for s in compiled.expression_strategies],
            phases=["compile", "execute"],
            extras={"region_id": compiled.region_id},
        )
        return SparkExecutionResult(
            metrics=metrics,
            metadata={"compiled": compiled.to_dict()},
        )

    def execute_step(
        self,
        *,
        callable_: Any,
        inputs: Mapping[str, Any],
        params: Mapping[str, Any],
        context: SparkExecutionContext,
    ) -> Any:
        session = params.get("_spark_session") or self._session
        if session is None:
            raise RuntimeError("No SparkSession bound; acquire a session first.")
        if context.job_group:
            _set_job_group(session, context.job_group, f"etlantic:{context.step_name}")

        prepared: dict[str, Any] = {}
        for name, value in inputs.items():
            prepared[name] = self._to_dataframe(session, value)
        call_params = {k: v for k, v in params.items() if k != "_spark_session"}
        result = callable_(**prepared, **call_params)
        return self._remember(result, context=context)

    def execute_write(
        self,
        write: SparkWrite,
        *,
        context: SparkExecutionContext,
    ) -> SparkExecutionResult:
        session = self._session
        if session is None:
            raise RuntimeError("No SparkSession bound for write.")
        if context.job_group:
            _set_job_group(
                session, context.job_group, f"etlantic-write:{context.step_name}"
            )

        df = self._to_dataframe(session, write.source)
        target = write.target
        path = target.path or target.name
        fmt = (target.format or "parquet").lower()
        mode = write.mode
        diagnostics: list[dict[str, Any]] = []
        rows = None
        try:
            rows = df.count()
        except Exception:
            rows = None

        if mode is SparkWriteMode.NO_WRITE:
            return SparkExecutionResult(
                write=write,
                metrics=SparkMetrics(rows_affected=0, actions=["no_write"]),
            )

        if mode in {SparkWriteMode.MERGE, SparkWriteMode.UPSERT}:
            if fmt != "delta" and not self._delta_enabled:
                return SparkExecutionResult(
                    write=write,
                    metrics=SparkMetrics(rows_affected=0, actions=["no_write"]),
                    diagnostics=[
                        {
                            "code": "PMSPARK331",
                            "severity": "error",
                            "message": "MERGE/UPSERT requires Delta; failing closed.",
                        }
                    ],
                )
            diagnostics.extend(self._delta_merge(df, path, write.merge_keys))
            if any(str(d.get("severity")) == "error" for d in diagnostics):
                return SparkExecutionResult(
                    write=write,
                    metrics=SparkMetrics(rows_affected=0, actions=["no_write"]),
                    diagnostics=diagnostics,
                )
        elif mode is SparkWriteMode.OVERWRITE_PARTITION:
            writer = df.write.mode("overwrite")
            if write.partition_by:
                writer = writer.partitionBy(*write.partition_by)
            if fmt == "delta":
                writer.format("delta").save(path)
            else:
                writer.format(fmt).save(path)
        elif mode in {SparkWriteMode.OVERWRITE, SparkWriteMode.REPLACE}:
            writer = df.write.mode("overwrite")
            if write.partition_by:
                writer = writer.partitionBy(*write.partition_by)
            writer.format(fmt).save(path)
        else:  # APPEND
            writer = df.write.mode("append")
            if write.partition_by:
                writer = writer.partitionBy(*write.partition_by)
            writer.format(fmt).save(path)

        schema_obs = observation_from_spark_schema(
            df.schema,
            source="spark",
            partition_columns=list(write.partition_by),
        )
        return SparkExecutionResult(
            write=write,
            metrics=SparkMetrics(
                rows_affected=rows,
                rows_out=rows,
                actions=[mode.value],
                phases=["publish"],
                extras={"format": fmt, "path": path},
            ),
            diagnostics=diagnostics,
            schema_observation=schema_obs,
        )

    def inspect_schema(
        self,
        value: Any,
        *,
        contract_type: type[Any] | None = None,
    ) -> dict[str, Any]:
        df = value
        if isinstance(value, SparkDataFrameHandle):
            df = self._frames.get(value.identity)
        if df is None:
            return {"source": "spark", "fields": [], "diagnostics": []}
        obs = observation_from_spark_schema(df.schema, source="spark")
        if contract_type is not None:
            mapping = map_contract_schema(
                contract_type, observed=obs.get("types") or {}
            )
            obs["contract_mapping"] = mapping.to_dict()
            obs["diagnostics"] = (
                list(obs.get("diagnostics") or []) + mapping.diagnostics
            )
            if mapping.overall in {
                SchemaCompatibility.LOSSY,
                SchemaCompatibility.UNKNOWN,
                SchemaCompatibility.UNSUPPORTED,
            }:
                obs["overall_compatibility"] = mapping.overall.value
        return obs

    def to_records(
        self,
        value: Any,
        *,
        contract_type: type[Any] | None = None,
    ) -> list[Any]:
        df = value
        if isinstance(value, SparkDataFrameHandle):
            df = self._frames.get(value.identity)
        if df is None:
            if isinstance(value, list):
                return as_records(value, contract_type)
            return []
        rows = [_row_as_dict(row) for row in df.collect()]
        return as_records(rows, contract_type)

    def split_valid_invalid(
        self,
        value: Any,
        *,
        contract_type: type[Any],
        context: SparkExecutionContext,
    ) -> tuple[Any, Any]:
        _ = context
        records = self.to_records(value, contract_type=None)
        valid: list[Any] = []
        invalid: list[Any] = []
        for row in records:
            try:
                if hasattr(contract_type, "model_validate"):
                    valid.append(contract_type.model_validate(row))
                else:
                    valid.append(row)
            except Exception:
                invalid.append(row)
        session = self._session
        if session is None:
            return valid, invalid
        valid_df = self._to_dataframe(session, valid)
        invalid_df = self._to_dataframe(session, invalid)
        return valid_df, invalid_df

    def _delta_merge(
        self, df: Any, path: str, merge_keys: tuple[str, ...]
    ) -> list[dict[str, Any]]:
        if not merge_keys:
            return [
                {
                    "code": "PMDELTA307",
                    "severity": "error",
                    "message": "Delta merge requires stable merge_keys; failing closed.",
                }
            ]
        try:
            from delta.tables import DeltaTable
        except ImportError:
            return [
                {
                    "code": "PMSPARK332",
                    "severity": "error",
                    "message": (
                        "delta-spark not installed; MERGE/UPSERT failing closed "
                        "(no parquet overwrite fallback)."
                    ),
                }
            ]
        session = self._session
        if not DeltaTable.isDeltaTable(session, path):
            df.write.format("delta").mode("overwrite").save(path)
            return []
        delta_table = DeltaTable.forPath(session, path)
        condition = " AND ".join(f"t.{k} = s.{k}" for k in merge_keys)
        (
            delta_table.alias("t")
            .merge(df.alias("s"), condition)
            .whenMatchedUpdateAll()
            .whenNotMatchedInsertAll()
            .execute()
        )
        return []

    def _to_dataframe(self, session: Any, value: Any) -> Any:
        if isinstance(value, SparkDataFrameHandle):
            frame = self._frames.get(value.identity)
            if frame is not None:
                return frame
        if isinstance(value, DatasetRef):
            if value.path:
                reader = session.read
                fmt = value.format or "parquet"
                return reader.format(fmt).load(value.path)
            if value.table:
                return session.table(value.table)
        # Duck-type Spark DataFrame
        if hasattr(value, "schema") and hasattr(value, "write"):
            return value
        if isinstance(value, list):
            rows = records_to_dicts(value)
            if not rows:
                from pyspark.sql.types import StructType

                return session.createDataFrame([], schema=StructType([]))
            return session.createDataFrame(rows)
        if isinstance(value, SparkWrite):
            return self._to_dataframe(session, value.source)
        raise TypeError(f"Cannot convert {type(value)!r} to Spark DataFrame")

    def _remember(self, result: Any, *, context: SparkExecutionContext) -> Any:
        if hasattr(result, "schema") and hasattr(result, "write"):
            identity = f"df-{uuid.uuid4().hex[:12]}"
            self._frames[identity] = result
            return SparkDataFrameHandle(
                identity=identity,
                region_id=context.region_id,
                step_name=context.step_name,
                streaming=context.streaming,
            )
        return result
