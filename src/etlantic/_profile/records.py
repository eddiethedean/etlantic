"""Internal profile sub-records (not public API)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

PortableTransformPolicy = Literal["require", "prefer", "native"]
SecurityMode = Literal["development", "test", "production"]
ExecutionStrategy = Literal["explicit", "adaptive"]
AdaptiveFallback = Literal["error", "explicit"]


@dataclass(frozen=True, slots=True)
class EngineProfile:
    dataframe_engine: str | None = "local"
    sql_engine: str | None = None
    spark_engine: str | None = None
    orchestrator: str = "local"
    allow_trusted_sql: bool = False
    spark_udf_policy: str = "warn"
    spark_streaming: bool = False
    required_sql_capabilities: tuple[str, ...] = ()
    required_spark_capabilities: tuple[str, ...] = ()
    required_orchestrator_capabilities: tuple[str, ...] = ()
    portable_transform_policy: PortableTransformPolicy = "prefer"
    implementation_overrides: dict[str, str] = field(default_factory=dict)
    execution_strategy: ExecutionStrategy = "explicit"
    eligible_targets: tuple[str, ...] = ()
    adaptive_fallback: AdaptiveFallback = "error"


@dataclass(frozen=True, slots=True)
class SecurityProfile:
    security_domain: str = "default"
    security_mode: SecurityMode = "development"
    plugin_allowlist: dict[str, str | None] = field(default_factory=dict)
    require_plugin_probe: bool = False
    tenant: str = "default"
    environment: str = "default"
    safe_io: dict[str, Any] = field(default_factory=dict)
    outbound: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ExecutionProfile:
    concurrency: int | None = None
    timeout_seconds: float | None = None
    retry_max_attempts: int | None = None
    schedule: dict[str, Any] = field(default_factory=dict)
    execution: dict[str, Any] = field(default_factory=dict)
    validation_policy: str = "default"


@dataclass(frozen=True, slots=True)
class ReliabilityProfile:
    resources: dict[str, str] = field(default_factory=dict)
    secret_providers: dict[str, str] = field(default_factory=dict)
    bindings: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
