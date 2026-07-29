"""Versioned Spark execution protocol (etlantic.spark/1).

Core stays PySpark-free. The reference plugin lives in ``etlantic-pyspark``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from etlantic.capabilities import PluginCapabilities
from etlantic.protocol_meta import (
    CompileArtifactMeta,
    ExecutionContextMeta,
    coerce_compile_meta,
    coerce_context_meta,
)

SPARK_PROTOCOL_VERSION = "etlantic.spark/1"
# Known first-party engine names for defaults/aliases; not a privilege allowlist.
# Third-party engines register via discovery.
SPARK_ENGINES = frozenset({"pyspark", "spark"})
STREAMING_STABILITY = "experimental"  # 0.7 exit: streaming APIs are experimental


class SparkPhase(StrEnum):
    """Reportable phases of Spark region / step execution."""

    RESOLVE = "resolve"
    COMPILE = "compile"
    EXECUTE = "execute"
    VALIDATE = "validate"
    CHECKPOINT = "checkpoint"
    PUBLISH = "publish"
    STREAM = "stream"
    CLEANUP = "cleanup"


class SparkActionKind(StrEnum):
    """Explicit Spark actions (no hidden collect/show/toPandas)."""

    WRITE = "write"
    VALIDATION_COUNT = "validation_count"
    QUALITY_GATE = "quality_gate"
    CHECKPOINT = "checkpoint"
    MATERIALIZE = "materialize"
    CACHE = "cache"
    UNCACHE = "uncache"
    STREAMING_START = "streaming_start"
    STREAMING_STOP = "streaming_stop"
    CANCEL = "cancel"
    DELTA_OPTIMIZE = "delta_optimize"
    DELTA_VACUUM = "delta_vacuum"
    DELTA_HISTORY = "delta_history"
    SCHEMA_EVOLVE = "schema_evolve"


class ExpressionStrategy(StrEnum):
    """How a compiled step realizes expressions."""

    NATIVE_DF = "native_df"
    SPARK_SQL = "spark_sql"
    SCALAR_PYTHON_UDF = "scalar_python_udf"
    PANDAS_UDF = "pandas_udf"
    ITERATOR_PANDAS_UDF = "iterator_pandas_udf"
    JVM_EXTENSION = "jvm_extension"


class SchemaCompatibility(StrEnum):
    """Contract ↔ Spark schema mapping outcome (never guess)."""

    EXACT = "exact"
    COMPATIBLE = "compatible"
    LOSSY = "lossy"
    UNKNOWN = "unknown"
    UNSUPPORTED = "unsupported"


class SparkWriteMode(StrEnum):
    """Delta-compatible portable write modes."""

    APPEND = "append"
    OVERWRITE = "overwrite"
    OVERWRITE_PARTITION = "overwrite_partition"
    MERGE = "merge"
    UPSERT = "upsert"
    REPLACE = "replace"
    NO_WRITE = "no_write"


class SparkUdfPolicy(StrEnum):
    """Profile policy for UDF usage during planning/compile."""

    ALLOW = "allow"
    WARN = "warn"
    NATIVE_REQUIRED = "native_required"
    DENY = "deny"


@dataclass(frozen=True, slots=True)
class DatasetRef:
    """Logical Spark dataset identity without credentials or live sessions."""

    name: str
    format: str | None = None  # parquet, delta, json, csv, memory, …
    path: str | None = None
    table: str | None = None
    options: Mapping[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "format": self.format,
            "path": self.path,
            "table": self.table,
            "options": dict(self.options),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DatasetRef:
        return cls(
            name=str(data["name"]),
            format=data.get("format"),
            path=data.get("path"),
            table=data.get("table"),
            options=dict(data.get("options") or {}),
        )


@dataclass(frozen=True, slots=True)
class SparkDataFrameHandle:
    """Portable handle wrapping a native Spark DataFrame identity.

    The live frame lives only inside the plugin/runtime; plans and reports
    never embed sessions or credentials.
    """

    identity: str
    contract_id: str | None = None
    region_id: str | None = None
    step_name: str | None = None
    streaming: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity,
            "contract_id": self.contract_id,
            "region_id": self.region_id,
            "step_name": self.step_name,
            "streaming": self.streaming,
            "metadata": dict(self.metadata),
        }

    @property
    def logical_step_id(self) -> str:
        """Stable logical-step identity for fused / distributed artifacts."""
        meta_step = self.metadata.get("logical_step_id") or self.metadata.get(
            "step_name"
        )
        if meta_step:
            return str(meta_step)
        if self.step_name:
            return str(self.step_name)
        return self.identity


@dataclass(frozen=True, slots=True)
class SparkAction:
    """An explicit action boundary recorded in compiled plans."""

    kind: SparkActionKind
    node_name: str
    reason: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "node_name": self.node_name,
            "reason": self.reason,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class SparkWrite:
    """Portable write intent realized by the Spark/Delta plugin."""

    source: SparkDataFrameHandle | DatasetRef | Any
    target: DatasetRef
    mode: SparkWriteMode = SparkWriteMode.APPEND
    merge_keys: tuple[str, ...] = ()
    partition_by: tuple[str, ...] = ()
    idempotency_key: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        source: Any
        if hasattr(self.source, "to_dict"):
            source = self.source.to_dict()
        else:
            source = {"kind": "opaque"}
        return {
            "source": source,
            "target": self.target.to_dict(),
            "mode": self.mode.value,
            "merge_keys": list(self.merge_keys),
            "partition_by": list(self.partition_by),
            "idempotency_key": self.idempotency_key,
            "metadata": dict(self.metadata),
        }


@dataclass
class SparkMetrics:
    """Normalized Spark execution metrics (no secret values)."""

    rows_in: int | None = None
    rows_out: int | None = None
    rows_affected: int | None = None
    fused_steps: int = 0
    stages: int = 0
    tasks: int = 0
    actions: list[str] = field(default_factory=list)
    expression_strategies: list[str] = field(default_factory=list)
    phases: list[str] = field(default_factory=list)
    job_group: str | None = None
    cancelled: bool = False
    cache_hits: int = 0
    logical_step_ids: list[str] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rows_in": self.rows_in,
            "rows_out": self.rows_out,
            "rows_affected": self.rows_affected,
            "fused_steps": self.fused_steps,
            "stages": self.stages,
            "tasks": self.tasks,
            "actions": list(self.actions),
            "expression_strategies": list(self.expression_strategies),
            "phases": list(self.phases),
            "job_group": self.job_group,
            "cancelled": self.cancelled,
            "cache_hits": self.cache_hits,
            "logical_step_ids": list(self.logical_step_ids),
            "extras": dict(self.extras),
        }


@dataclass
class SparkExecutionResult:
    """Result of executing a compiled Spark plan or step."""

    handle: SparkDataFrameHandle | None = None
    write: SparkWrite | None = None
    metrics: SparkMetrics = field(default_factory=SparkMetrics)
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
    schema_observation: dict[str, Any] | None = None
    streaming_query_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "handle": self.handle.to_dict() if self.handle else None,
            "write": self.write.to_dict() if self.write else None,
            "metrics": self.metrics.to_dict(),
            "diagnostics": list(self.diagnostics),
            "schema_observation": self.schema_observation,
            "streaming_query_id": self.streaming_query_id,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class SparkPlanRegion:
    """Planner-facing description of a Spark execution region."""

    identity: str
    node_names: tuple[str, ...]
    security_domain: str = "default"
    streaming: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity,
            "node_names": list(self.node_names),
            "security_domain": self.security_domain,
            "streaming": self.streaming,
            "metadata": dict(self.metadata),
        }


@dataclass
class CompiledSparkPlan:
    """Compiled Spark region — secret-free and inspectable."""

    region_id: str
    node_names: tuple[str, ...]
    actions: tuple[SparkAction, ...] = ()
    expression_strategies: tuple[ExpressionStrategy, ...] = ()
    checkpoint_points: tuple[str, ...] = ()
    cache_points: tuple[str, ...] = ()
    materialization_points: tuple[str, ...] = ()
    streaming: bool = False
    logical_identities: Mapping[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def artifact_meta(self) -> CompileArtifactMeta:
        """Typed interoperability view of ``metadata`` (ExtensionMetadata-compatible)."""
        return coerce_compile_meta(self.metadata)

    def to_dict(self) -> dict[str, Any]:
        return {
            "region_id": self.region_id,
            "node_names": list(self.node_names),
            "actions": [a.to_dict() for a in self.actions],
            "expression_strategies": [s.value for s in self.expression_strategies],
            "checkpoint_points": list(self.checkpoint_points),
            "cache_points": list(self.cache_points),
            "materialization_points": list(self.materialization_points),
            "streaming": self.streaming,
            "logical_identities": dict(self.logical_identities),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class SparkCompilationContext:
    """Inputs for region compilation (no live session)."""

    run_id: str
    pipeline_id: str
    plan_id: str
    region_id: str
    security_domain: str = "default"
    udf_policy: SparkUdfPolicy = SparkUdfPolicy.WARN
    streaming: bool = False
    required_capabilities: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def context_meta(self) -> ExecutionContextMeta:
        """Typed interoperability view of ``metadata`` (ExtensionMetadata-compatible)."""
        return coerce_context_meta(self.metadata)


@dataclass(frozen=True, slots=True)
class SparkExecutionContext:
    """Runtime context for Spark execution."""

    run_id: str
    pipeline_id: str
    plan_id: str
    step_name: str
    region_id: str | None = None
    engine: str = "pyspark"
    attempt: int = 1
    job_group: str | None = None
    streaming: bool = False
    session_handle_id: str | None = None
    allow_udfs: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def context_meta(self) -> ExecutionContextMeta:
        """Typed interoperability view of ``metadata`` (ExtensionMetadata-compatible)."""
        return coerce_context_meta(self.metadata)


@dataclass(frozen=True, slots=True)
class SparkPluginInfo:
    """Discoverable plugin metadata."""

    name: str
    engine: str
    version: str
    protocol_version: str = SPARK_PROTOCOL_VERSION
    capabilities: PluginCapabilities | None = None
    streaming_stability: str = STREAMING_STABILITY
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "engine": self.engine,
            "version": self.version,
            "protocol_version": self.protocol_version,
            "capabilities": (
                self.capabilities.to_dict() if self.capabilities is not None else None
            ),
            "streaming_stability": self.streaming_stability,
            "metadata": dict(self.metadata),
        }


@runtime_checkable
class SparkPlugin(Protocol):
    """PySpark / Spark execution plugin protocol.

    Implementations compile portable Spark plan regions, execute transformations
    and writes against a live ``SparkSession``, and expose schema inspection and
    record export for hybrid boundaries.
    """

    @property
    def info(self) -> SparkPluginInfo:
        """Plugin metadata including engine id and declared capabilities."""
        ...

    def capabilities(self) -> PluginCapabilities:
        """Return Spark-specific capability flags for planning."""
        ...

    def dataset_from_binding(
        self,
        *,
        binding: str,
        location: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> DatasetRef:
        """Resolve a profile asset/binding to a logical dataset reference."""
        ...

    def compile(
        self,
        region: SparkPlanRegion,
        *,
        context: SparkCompilationContext,
    ) -> CompiledSparkPlan:
        """Lower a portable Spark plan region to engine-specific actions."""
        ...

    def execute(
        self,
        compiled: CompiledSparkPlan,
        *,
        context: SparkExecutionContext,
        inputs: Mapping[str, Any] | None = None,
    ) -> SparkExecutionResult:
        """Execute a compiled plan region and return metrics plus outputs."""
        ...

    def execute_step(
        self,
        *,
        callable_: Any,
        inputs: Mapping[str, Any],
        params: Mapping[str, Any],
        context: SparkExecutionContext,
    ) -> Any:
        """Invoke a native Spark transformation implementation."""
        ...

    def execute_write(
        self,
        write: SparkWrite,
        *,
        context: SparkExecutionContext,
    ) -> SparkExecutionResult:
        """Execute a write/publication intent against Spark storage."""
        ...

    def inspect_schema(
        self,
        value: Any,
        *,
        contract_type: type[Any] | None = None,
    ) -> dict[str, Any]:
        """Return a NormalizedSchema-compatible mapping for a DataFrame handle."""
        ...

    def to_records(
        self,
        value: Any,
        *,
        contract_type: type[Any] | None = None,
    ) -> list[Any]:
        """Materialize rows as Python records for storage or publication."""
        ...

    def split_valid_invalid(
        self,
        value: Any,
        *,
        contract_type: type[Any],
        context: SparkExecutionContext,
    ) -> tuple[Any, Any]:
        """Split a DataFrame into valid and invalid partitions by contract."""
        ...

    def cancel(
        self,
        *,
        context: SparkExecutionContext,
        job_group: str | None = None,
    ) -> SparkExecutionResult:
        """Cancel work for ``job_group`` (or ``context.job_group``) if supported."""
        ...

    def execute_storage_op(
        self,
        *,
        operation: str,
        target: DatasetRef,
        context: SparkExecutionContext,
        options: Mapping[str, Any] | None = None,
    ) -> SparkExecutionResult:
        """Run a capability-gated Delta/storage maintenance or inspect op."""
        ...


def logical_identities_for_region(
    node_names: tuple[str, ...] | list[str],
    *,
    region_id: str,
) -> dict[str, str]:
    """Map physical node slots to logical step identities for fusion provenance."""
    return {str(name): f"{region_id}:{name}" for name in node_names}
