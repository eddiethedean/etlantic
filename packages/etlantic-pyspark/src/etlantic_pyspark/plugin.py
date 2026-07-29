"""PySpark execution plugin for ETLantic."""

from __future__ import annotations

import contextlib
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
    SparkWrite,
    SparkWriteMode,
)
from etlantic.spark.provider import SparkSessionHandle
from etlantic.spark.schema import (
    map_contract_schema,
    observation_from_spark_schema,
)
from etlantic.storage.protocol import as_records, records_to_dicts

__version__ = "0.34.0"


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


def _delta_spark_available() -> bool:
    """True when delta-spark (or delta) can be imported for Delta ops."""
    try:
        import importlib.util

        return importlib.util.find_spec("delta") is not None
    except Exception:
        return False


class PySparkPlugin:
    """Reference PySpark region compiler and executor."""

    def __init__(self) -> None:
        delta_ok = _delta_spark_available()
        extras = {
            "pyspark",
            "write.append",
            "write.overwrite",
            "write.merge",
            "write.upsert",
            "write.partition_replace",
        }
        if delta_ok:
            extras.update(
                {
                    "delta_compatible",
                    "storage.delta.merge",
                    "storage.delta.optimize",
                    "storage.delta.vacuum",
                    "storage.delta.history",
                    "storage.delta.time_travel",
                    "storage.delta.schema_evolution",
                }
            )
        caps = PluginCapabilities(
            engine="pyspark",
            async_execution=False,
            dataframe=True,
            spark=True,
            eager=False,
            lazy=True,
            streaming=True,
            checkpoints=True,
            schema_inspection=True,
            invalid_row_separation=False,
            cancellation=True,
            spark_delta=delta_ok,
            spark_merge=True,
            spark_streaming=True,
            spark_native_exprs=True,
            spark_udf=True,
            spark_cache=True,
            spark_checkpoint=True,
            extras=frozenset(extras),
        )
        self._info = SparkPluginInfo(
            name="etlantic-pyspark",
            engine="pyspark",
            version=__version__,
            protocol_version=SPARK_PROTOCOL_VERSION,
            capabilities=caps,
            streaming_stability=STREAMING_STABILITY,
            metadata={
                "delta_optimize": True,
                "delta_vacuum": True,
                "delta_history": True,
                "delta_time_travel": True,
                "delta_schema_evolution": True,
                "requires_delta_spark": True,
            },
        )
        self._session: Any = None
        self._frames: dict[str, Any] = {}
        self._delta_enabled = False
        self._active_job_group: str | None = None

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
        from etlantic.spark.protocol import logical_identities_for_region

        strategies: list[ExpressionStrategy] = [ExpressionStrategy.NATIVE_DF]
        actions: list[SparkAction] = []
        cache_points: list[str] = []
        checkpoint_points: list[str] = []
        materialization_points: list[str] = []
        for name in region.node_names:
            meta = dict(region.metadata.get(name) or {})
            if meta.get("cache") or meta.get("spark_cache"):
                actions.append(
                    SparkAction(
                        kind=SparkActionKind.CACHE,
                        node_name=name,
                        reason="declared_cache",
                    )
                )
                cache_points.append(name)
            if meta.get("checkpoint") or meta.get("spark_checkpoint"):
                actions.append(
                    SparkAction(
                        kind=SparkActionKind.CHECKPOINT,
                        node_name=name,
                        reason="declared_checkpoint",
                    )
                )
                checkpoint_points.append(name)
        if region.node_names:
            actions.append(
                SparkAction(
                    kind=SparkActionKind.MATERIALIZE,
                    node_name=region.node_names[-1],
                    reason="region_sink_or_boundary",
                )
            )
            materialization_points.append(region.node_names[-1])
            if region.streaming:
                actions.append(
                    SparkAction(
                        kind=SparkActionKind.STREAMING_START,
                        node_name=region.node_names[-1],
                        reason="streaming_region",
                    )
                )
        logical_ids = logical_identities_for_region(
            region.node_names, region_id=region.identity
        )
        return CompiledSparkPlan(
            region_id=region.identity,
            node_names=region.node_names,
            actions=tuple(actions),
            expression_strategies=tuple(strategies),
            cache_points=tuple(cache_points),
            checkpoint_points=tuple(checkpoint_points),
            materialization_points=tuple(materialization_points),
            streaming=region.streaming,
            logical_identities=logical_ids,
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
        frames = dict(inputs or {})
        if context.job_group and self._session is not None:
            self._active_job_group = context.job_group
            _set_job_group(
                self._session, context.job_group, f"etlantic:{compiled.region_id}"
            )
        logical_ids = [
            compiled.logical_identities.get(n, n) for n in compiled.node_names
        ]
        last_handle: SparkDataFrameHandle | None = None
        for name in compiled.node_names:
            frame = frames.get(name)
            if frame is None:
                continue
            if name in compiled.cache_points and hasattr(frame, "cache"):
                with contextlib.suppress(Exception):
                    frame.cache()
            if name in compiled.checkpoint_points and hasattr(frame, "checkpoint"):
                with contextlib.suppress(Exception):
                    frame.checkpoint()
            remembered = self._remember(
                frame,
                context=SparkExecutionContext(
                    run_id=context.run_id,
                    pipeline_id=context.pipeline_id,
                    plan_id=context.plan_id,
                    step_name=name,
                    region_id=compiled.region_id,
                    engine=context.engine,
                    attempt=context.attempt,
                    job_group=context.job_group,
                    streaming=context.streaming,
                    session_handle_id=context.session_handle_id,
                    allow_udfs=context.allow_udfs,
                    metadata={
                        **dict(context.metadata),
                        "logical_step_id": compiled.logical_identities.get(name, name),
                    },
                ),
            )
            if isinstance(remembered, SparkDataFrameHandle):
                last_handle = remembered
                frames[name] = remembered
        metrics = SparkMetrics(
            fused_steps=len(compiled.node_names),
            stages=max(1, len(compiled.node_names)),
            actions=[a.kind.value for a in compiled.actions],
            expression_strategies=[s.value for s in compiled.expression_strategies],
            phases=["compile", "execute"],
            job_group=context.job_group,
            logical_step_ids=logical_ids,
            extras={"region_id": compiled.region_id},
        )
        if context.job_group and self._active_job_group == context.job_group:
            self._active_job_group = None
        return SparkExecutionResult(
            handle=last_handle,
            metrics=metrics,
            metadata={"compiled": compiled.to_dict()},
        )

    def cancel(
        self,
        *,
        context: SparkExecutionContext,
        job_group: str | None = None,
    ) -> SparkExecutionResult:
        group = job_group or context.job_group or self._active_job_group
        cancelled = False
        cancel_error: str | None = None
        if group and self._session is not None:
            spark_context = getattr(self._session, "sparkContext", None)
            cancel = getattr(spark_context, "cancelJobGroup", None)
            if callable(cancel):
                try:
                    cancel(group)
                    cancelled = True
                except Exception as exc:
                    cancelled = False
                    cancel_error = str(exc)
            else:
                cancel_error = "cancelJobGroup not available on sparkContext"
        elif group:
            cancel_error = "no active Spark session for cancel"
        if group and group == self._active_job_group:
            self._active_job_group = None
        metadata: dict[str, Any] = {"job_group": group, "cancelled": cancelled}
        if cancel_error:
            metadata["cancel_error"] = cancel_error
        return SparkExecutionResult(
            metrics=SparkMetrics(
                actions=[SparkActionKind.CANCEL.value],
                phases=["cleanup"],
                job_group=group,
                cancelled=cancelled,
            ),
            metadata=metadata,
        )

    def execute_storage_op(
        self,
        *,
        operation: str,
        target: DatasetRef,
        context: SparkExecutionContext,
        options: Mapping[str, Any] | None = None,
    ) -> SparkExecutionResult:
        op = str(operation).strip().lower()
        opts = dict(options or {})
        path = target.path or target.table or target.name
        if context.job_group and self._session is not None:
            _set_job_group(self._session, context.job_group, f"etlantic-storage:{op}")
        handlers = {
            "optimize": self._delta_optimize,
            "vacuum": self._delta_vacuum,
            "history": self._delta_history,
            "time_travel": self._delta_time_travel,
            "schema_evolution": self._delta_schema_evolution,
            "merge": self._delta_storage_merge,
        }
        handler = handlers.get(op)
        if handler is None:
            return SparkExecutionResult(
                metrics=SparkMetrics(actions=["no_op"], phases=["execute"]),
                diagnostics=[
                    {
                        "code": "PMDELTA300",
                        "severity": "error",
                        "message": f"Unknown Delta storage operation {operation!r}.",
                    }
                ],
            )
        return handler(path, target, context, opts)

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
            if fmt != "delta" or not self._delta_enabled:
                return SparkExecutionResult(
                    write=write,
                    metrics=SparkMetrics(rows_affected=0, actions=["no_write"]),
                    diagnostics=[
                        {
                            "code": "PMSPARK331",
                            "severity": "error",
                            "message": (
                                "MERGE/UPSERT requires Delta format and an "
                                "enabled Delta session; failing closed."
                            ),
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

    def _require_delta(self) -> list[dict[str, Any]]:
        try:
            import delta.tables  # noqa: F401
        except ImportError:
            return [
                {
                    "code": "PMSPARK332",
                    "severity": "error",
                    "message": (
                        "delta-spark not installed; Delta storage operation "
                        "failing closed."
                    ),
                }
            ]
        if self._session is None:
            return [
                {
                    "code": "PMSPARK330",
                    "severity": "error",
                    "message": "No SparkSession bound for Delta storage operation.",
                }
            ]
        return []

    def _delta_storage_merge(
        self,
        path: str,
        target: DatasetRef,
        context: SparkExecutionContext,
        opts: dict[str, Any],
    ) -> SparkExecutionResult:
        _ = target, context
        missing = self._require_delta()
        if missing:
            return SparkExecutionResult(
                metrics=SparkMetrics(actions=["no_write"]),
                diagnostics=missing,
            )
        source = opts.get("source")
        merge_keys = tuple(str(k) for k in (opts.get("merge_keys") or ()))
        if source is None:
            return SparkExecutionResult(
                metrics=SparkMetrics(actions=["no_write"]),
                diagnostics=[
                    {
                        "code": "PMDELTA307",
                        "severity": "error",
                        "message": "Delta merge storage op requires options['source'].",
                    }
                ],
            )
        df = self._to_dataframe(self._session, source)
        diagnostics = self._delta_merge(df, path, merge_keys)
        if any(str(d.get("severity")) == "error" for d in diagnostics):
            return SparkExecutionResult(
                metrics=SparkMetrics(
                    rows_affected=0,
                    actions=["no_write"],
                    phases=["publish"],
                    logical_step_ids=[context.step_name],
                ),
                diagnostics=diagnostics,
            )
        return SparkExecutionResult(
            metrics=SparkMetrics(
                actions=[SparkWriteMode.MERGE.value],
                phases=["publish"],
                logical_step_ids=[context.step_name],
            ),
            diagnostics=diagnostics,
        )

    def _delta_optimize(
        self,
        path: str,
        target: DatasetRef,
        context: SparkExecutionContext,
        opts: dict[str, Any],
    ) -> SparkExecutionResult:
        _ = target
        missing = self._require_delta()
        if missing:
            return SparkExecutionResult(
                metrics=SparkMetrics(actions=["no_op"]), diagnostics=missing
            )
        try:
            from delta.tables import DeltaTable

            table = DeltaTable.forPath(self._session, path)
            zorder = opts.get("zorder_by") or opts.get("zorder")
            if zorder:
                cols = list(zorder) if isinstance(zorder, (list, tuple)) else [zorder]
                table.optimize().executeZOrderBy(*cols)
            else:
                table.optimize().executeCompaction()
        except Exception as exc:
            return SparkExecutionResult(
                metrics=SparkMetrics(actions=["no_op"]),
                diagnostics=[
                    {
                        "code": "PMDELTA310",
                        "severity": "error",
                        "message": f"Delta optimize failed: {exc}",
                    }
                ],
            )
        return SparkExecutionResult(
            metrics=SparkMetrics(
                actions=[SparkActionKind.DELTA_OPTIMIZE.value],
                phases=["execute"],
                logical_step_ids=[context.step_name],
                extras={"path": path},
            )
        )

    def _delta_vacuum(
        self,
        path: str,
        target: DatasetRef,
        context: SparkExecutionContext,
        opts: dict[str, Any],
    ) -> SparkExecutionResult:
        _ = target
        missing = self._require_delta()
        if missing:
            return SparkExecutionResult(
                metrics=SparkMetrics(actions=["no_op"]), diagnostics=missing
            )
        try:
            from delta.tables import DeltaTable

            table = DeltaTable.forPath(self._session, path)
            retention = opts.get("retention_hours")
            if retention is None:
                table.vacuum()
            else:
                table.vacuum(float(retention))
        except Exception as exc:
            return SparkExecutionResult(
                metrics=SparkMetrics(actions=["no_op"]),
                diagnostics=[
                    {
                        "code": "PMDELTA311",
                        "severity": "error",
                        "message": f"Delta vacuum failed: {exc}",
                    }
                ],
            )
        return SparkExecutionResult(
            metrics=SparkMetrics(
                actions=[SparkActionKind.DELTA_VACUUM.value],
                phases=["execute"],
                logical_step_ids=[context.step_name],
                extras={"path": path},
            )
        )

    def _delta_history(
        self,
        path: str,
        target: DatasetRef,
        context: SparkExecutionContext,
        opts: dict[str, Any],
    ) -> SparkExecutionResult:
        _ = target
        missing = self._require_delta()
        if missing:
            return SparkExecutionResult(
                metrics=SparkMetrics(actions=["no_op"]), diagnostics=missing
            )
        try:
            from delta.tables import DeltaTable

            table = DeltaTable.forPath(self._session, path)
            limit = opts.get("limit")
            history = (
                table.history(int(limit)) if limit is not None else table.history()
            )
            rows = history.count()
            handle = self._remember(history, context=context)
        except Exception as exc:
            return SparkExecutionResult(
                metrics=SparkMetrics(actions=["no_op"]),
                diagnostics=[
                    {
                        "code": "PMDELTA312",
                        "severity": "error",
                        "message": f"Delta history failed: {exc}",
                    }
                ],
            )
        return SparkExecutionResult(
            handle=handle if isinstance(handle, SparkDataFrameHandle) else None,
            metrics=SparkMetrics(
                rows_out=rows,
                actions=[SparkActionKind.DELTA_HISTORY.value],
                phases=["execute"],
                logical_step_ids=[context.step_name],
                extras={"path": path},
            ),
        )

    def _delta_time_travel(
        self,
        path: str,
        target: DatasetRef,
        context: SparkExecutionContext,
        opts: dict[str, Any],
    ) -> SparkExecutionResult:
        missing = self._require_delta()
        if missing:
            return SparkExecutionResult(
                metrics=SparkMetrics(actions=["no_op"]), diagnostics=missing
            )
        session = self._session
        reader = session.read.format("delta")
        version = opts.get("version_as_of", opts.get("version"))
        timestamp = opts.get("timestamp_as_of", opts.get("timestamp"))
        try:
            if version is not None:
                reader = reader.option("versionAsOf", str(version))
            elif timestamp is not None:
                reader = reader.option("timestampAsOf", str(timestamp))
            else:
                return SparkExecutionResult(
                    metrics=SparkMetrics(actions=["no_op"]),
                    diagnostics=[
                        {
                            "code": "PMDELTA313",
                            "severity": "error",
                            "message": (
                                "time_travel requires version_as_of or timestamp_as_of."
                            ),
                        }
                    ],
                )
            loc = path or target.table
            df = reader.load(loc) if not target.table else reader.table(target.table)
            handle = self._remember(df, context=context)
        except Exception as exc:
            return SparkExecutionResult(
                metrics=SparkMetrics(actions=["no_op"]),
                diagnostics=[
                    {
                        "code": "PMDELTA313",
                        "severity": "error",
                        "message": f"Delta time travel failed: {exc}",
                    }
                ],
            )
        return SparkExecutionResult(
            handle=handle if isinstance(handle, SparkDataFrameHandle) else None,
            metrics=SparkMetrics(
                actions=["time_travel"],
                phases=["execute"],
                logical_step_ids=[context.step_name],
                extras={"path": path, "version": version, "timestamp": timestamp},
            ),
        )

    def _delta_schema_evolution(
        self,
        path: str,
        target: DatasetRef,
        context: SparkExecutionContext,
        opts: dict[str, Any],
    ) -> SparkExecutionResult:
        _ = target
        missing = self._require_delta()
        if missing:
            return SparkExecutionResult(
                metrics=SparkMetrics(actions=["no_op"]), diagnostics=missing
            )
        source = opts.get("source")
        if source is None:
            return SparkExecutionResult(
                metrics=SparkMetrics(actions=["no_op"]),
                diagnostics=[
                    {
                        "code": "PMDELTA314",
                        "severity": "error",
                        "message": (
                            "schema_evolution requires options['source'] DataFrame."
                        ),
                    }
                ],
            )
        try:
            df = self._to_dataframe(self._session, source)
            (
                df.write.format("delta")
                .mode("append")
                .option("mergeSchema", "true")
                .save(path)
            )
        except Exception as exc:
            return SparkExecutionResult(
                metrics=SparkMetrics(actions=["no_op"]),
                diagnostics=[
                    {
                        "code": "PMDELTA314",
                        "severity": "error",
                        "message": f"Delta schema evolution failed: {exc}",
                    }
                ],
            )
        return SparkExecutionResult(
            metrics=SparkMetrics(
                actions=[SparkActionKind.SCHEMA_EVOLVE.value],
                phases=["publish"],
                logical_step_ids=[context.step_name],
                extras={"path": path},
            )
        )

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
                metadata={
                    "logical_step_id": str(
                        context.metadata.get("logical_step_id") or context.step_name
                    )
                },
            )
        return result
