"""Plugin capability declarations and negotiation results."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

CAPABILITY_VOCABULARY_VERSION = "etlantic.capabilities/1"


class CapabilityDecision(StrEnum):
    """Outcome of comparing required vs available capabilities."""

    SUPPORTED = "supported"
    FALLBACK = "fallback"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class PluginCapabilities:
    """Declared capabilities of a plugin or engine.

    Dataframe-oriented flags (eager/lazy/arrow/...) are first-class for 0.5
    planning. SQL-oriented flags are first-class for 0.6. Unknown requirements
    may still be declared via ``extras``.
    """

    engine: str
    vocabulary_version: str = CAPABILITY_VOCABULARY_VERSION
    async_execution: bool = False
    streaming: bool = False
    transactions: bool = False
    checkpoints: bool = False
    sql: bool = False
    spark: bool = False
    dataframe: bool = True
    secret_provider: bool = False
    eager: bool = True
    lazy: bool = False
    arrow_import: bool = False
    arrow_export: bool = False
    zero_copy: bool = False
    schema_inspection: bool = False
    invalid_row_separation: bool = False
    cancellation: bool = False
    thread_safe: bool = False
    # SQL 0.6 vocabulary
    sql_merge: bool = False
    sql_cte: bool = False
    sql_returning: bool = False
    sql_transactional_ddl: bool = False
    sql_atomic_rename: bool = False
    sql_catalog_inspect: bool = False
    sql_trusted_fragments: bool = False
    # Spark 0.7 vocabulary
    spark_delta: bool = False
    spark_merge: bool = False
    spark_streaming: bool = False
    spark_native_exprs: bool = False
    spark_udf: bool = False
    spark_cache: bool = False
    spark_checkpoint: bool = False
    # Orchestration 0.8 vocabulary
    orchestration: bool = False
    orch_scheduling: bool = False
    orch_retries: bool = False
    orch_timeouts: bool = False
    orch_parallel: bool = False
    orch_sensors: bool = False
    orch_artifacts_only_xcom: bool = False
    interchange_mechanisms: frozenset[str] = field(default_factory=frozenset)
    extras: frozenset[str] = field(default_factory=frozenset)

    def supports(self, requirement: str) -> bool:
        """Return True when this capability set covers ``requirement``."""
        known = {
            "async": self.async_execution,
            "async_execution": self.async_execution,
            "streaming": self.streaming,
            "transactions": self.transactions,
            "checkpoints": self.checkpoints,
            "sql": self.sql,
            "spark": self.spark,
            "dataframe": self.dataframe,
            "secret_provider": self.secret_provider,
            "eager": self.eager,
            "lazy": self.lazy,
            "arrow_import": self.arrow_import,
            "arrow_export": self.arrow_export,
            "zero_copy": self.zero_copy,
            "schema_inspection": self.schema_inspection,
            "invalid_row_separation": self.invalid_row_separation,
            "cancellation": self.cancellation,
            "thread_safe": self.thread_safe,
            "sql_merge": self.sql_merge,
            "merge": self.sql_merge,
            "sql_cte": self.sql_cte,
            "cte": self.sql_cte,
            "sql_returning": self.sql_returning,
            "returning": self.sql_returning,
            "sql_transactional_ddl": self.sql_transactional_ddl,
            "transactional_ddl": self.sql_transactional_ddl,
            "sql_atomic_rename": self.sql_atomic_rename,
            "atomic_rename": self.sql_atomic_rename,
            "sql_catalog_inspect": self.sql_catalog_inspect,
            "catalog_inspect": self.sql_catalog_inspect,
            "sql_trusted_fragments": self.sql_trusted_fragments,
            "trusted_fragments": self.sql_trusted_fragments,
            "spark_delta": self.spark_delta,
            "delta": self.spark_delta,
            "spark_merge": self.spark_merge,
            "spark_streaming": self.spark_streaming,
            "spark_native_exprs": self.spark_native_exprs,
            "spark_udf": self.spark_udf,
            "spark_cache": self.spark_cache,
            "spark_checkpoint": self.spark_checkpoint,
            "orchestration": self.orchestration,
            "orch_scheduling": self.orch_scheduling,
            "scheduling": self.orch_scheduling,
            "orch_retries": self.orch_retries,
            "retries": self.orch_retries,
            "orch_timeouts": self.orch_timeouts,
            "timeouts": self.orch_timeouts,
            "orch_parallel": self.orch_parallel,
            "parallel": self.orch_parallel,
            "orch_sensors": self.orch_sensors,
            "sensors": self.orch_sensors,
            "orch_artifacts_only_xcom": self.orch_artifacts_only_xcom,
            "artifacts_only_xcom": self.orch_artifacts_only_xcom,
        }
        if requirement in known:
            return known[requirement]
        return requirement in self.interchange_mechanisms or requirement in self.extras

    def to_dict(self) -> dict[str, Any]:
        """Serialize capabilities."""
        return {
            "engine": self.engine,
            "vocabulary_version": self.vocabulary_version,
            "async_execution": self.async_execution,
            "streaming": self.streaming,
            "transactions": self.transactions,
            "checkpoints": self.checkpoints,
            "sql": self.sql,
            "spark": self.spark,
            "dataframe": self.dataframe,
            "secret_provider": self.secret_provider,
            "eager": self.eager,
            "lazy": self.lazy,
            "arrow_import": self.arrow_import,
            "arrow_export": self.arrow_export,
            "zero_copy": self.zero_copy,
            "schema_inspection": self.schema_inspection,
            "invalid_row_separation": self.invalid_row_separation,
            "cancellation": self.cancellation,
            "thread_safe": self.thread_safe,
            "sql_merge": self.sql_merge,
            "sql_cte": self.sql_cte,
            "sql_returning": self.sql_returning,
            "sql_transactional_ddl": self.sql_transactional_ddl,
            "sql_atomic_rename": self.sql_atomic_rename,
            "sql_catalog_inspect": self.sql_catalog_inspect,
            "sql_trusted_fragments": self.sql_trusted_fragments,
            "spark_delta": self.spark_delta,
            "spark_merge": self.spark_merge,
            "spark_streaming": self.spark_streaming,
            "spark_native_exprs": self.spark_native_exprs,
            "spark_udf": self.spark_udf,
            "spark_cache": self.spark_cache,
            "spark_checkpoint": self.spark_checkpoint,
            "orchestration": self.orchestration,
            "orch_scheduling": self.orch_scheduling,
            "orch_retries": self.orch_retries,
            "orch_timeouts": self.orch_timeouts,
            "orch_parallel": self.orch_parallel,
            "orch_sensors": self.orch_sensors,
            "orch_artifacts_only_xcom": self.orch_artifacts_only_xcom,
            "interchange_mechanisms": sorted(self.interchange_mechanisms),
            "extras": sorted(self.extras),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PluginCapabilities:
        """Deserialize capabilities."""
        extras = data.get("extras") or ()
        interchange_mechanisms = data.get("interchange_mechanisms") or ()
        return cls(
            engine=str(data["engine"]),
            vocabulary_version=str(
                data.get("vocabulary_version", CAPABILITY_VOCABULARY_VERSION)
            ),
            async_execution=bool(data.get("async_execution", False)),
            streaming=bool(data.get("streaming", False)),
            transactions=bool(data.get("transactions", False)),
            checkpoints=bool(data.get("checkpoints", False)),
            sql=bool(data.get("sql", False)),
            spark=bool(data.get("spark", False)),
            dataframe=bool(data.get("dataframe", True)),
            secret_provider=bool(data.get("secret_provider", False)),
            eager=bool(data.get("eager", True)),
            lazy=bool(data.get("lazy", False)),
            arrow_import=bool(data.get("arrow_import", False)),
            arrow_export=bool(data.get("arrow_export", False)),
            zero_copy=bool(data.get("zero_copy", False)),
            schema_inspection=bool(data.get("schema_inspection", False)),
            invalid_row_separation=bool(data.get("invalid_row_separation", False)),
            cancellation=bool(data.get("cancellation", False)),
            thread_safe=bool(data.get("thread_safe", False)),
            sql_merge=bool(data.get("sql_merge", False)),
            sql_cte=bool(data.get("sql_cte", False)),
            sql_returning=bool(data.get("sql_returning", False)),
            sql_transactional_ddl=bool(data.get("sql_transactional_ddl", False)),
            sql_atomic_rename=bool(data.get("sql_atomic_rename", False)),
            sql_catalog_inspect=bool(data.get("sql_catalog_inspect", False)),
            sql_trusted_fragments=bool(data.get("sql_trusted_fragments", False)),
            spark_delta=bool(data.get("spark_delta", False)),
            spark_merge=bool(data.get("spark_merge", False)),
            spark_streaming=bool(data.get("spark_streaming", False)),
            spark_native_exprs=bool(data.get("spark_native_exprs", False)),
            spark_udf=bool(data.get("spark_udf", False)),
            spark_cache=bool(data.get("spark_cache", False)),
            spark_checkpoint=bool(data.get("spark_checkpoint", False)),
            orchestration=bool(data.get("orchestration", False)),
            orch_scheduling=bool(data.get("orch_scheduling", False)),
            orch_retries=bool(data.get("orch_retries", False)),
            orch_timeouts=bool(data.get("orch_timeouts", False)),
            orch_parallel=bool(data.get("orch_parallel", False)),
            orch_sensors=bool(data.get("orch_sensors", False)),
            orch_artifacts_only_xcom=bool(data.get("orch_artifacts_only_xcom", False)),
            interchange_mechanisms=frozenset(str(x) for x in interchange_mechanisms),
            extras=frozenset(str(x) for x in extras),
        )


@dataclass(frozen=True, slots=True)
class CapabilityNegotiation:
    """Record of a capability check for one requirement."""

    requirement: str
    engine: str
    decision: CapabilityDecision
    fallback_engine: str | None = None
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize negotiation record."""
        return {
            "requirement": self.requirement,
            "engine": self.engine,
            "decision": self.decision.value,
            "fallback_engine": self.fallback_engine,
            "message": self.message,
        }


def negotiate_capabilities(
    *,
    requirements: list[str],
    available: PluginCapabilities,
    fallback: PluginCapabilities | None = None,
    allow_fallback: bool = False,
) -> list[CapabilityNegotiation]:
    """Negotiate required capabilities against an available engine.

    Unsupported requirements fail closed unless ``allow_fallback`` is True and
    a fallback engine covers the requirement.
    """
    results: list[CapabilityNegotiation] = []
    for requirement in requirements:
        if available.supports(requirement):
            results.append(
                CapabilityNegotiation(
                    requirement=requirement,
                    engine=available.engine,
                    decision=CapabilityDecision.SUPPORTED,
                )
            )
            continue
        if allow_fallback and fallback is not None and fallback.supports(requirement):
            results.append(
                CapabilityNegotiation(
                    requirement=requirement,
                    engine=available.engine,
                    decision=CapabilityDecision.FALLBACK,
                    fallback_engine=fallback.engine,
                    message=(
                        f"Requirement {requirement!r} unsupported by "
                        f"{available.engine}; using fallback {fallback.engine}."
                    ),
                )
            )
            continue
        results.append(
            CapabilityNegotiation(
                requirement=requirement,
                engine=available.engine,
                decision=CapabilityDecision.UNSUPPORTED,
                message=(
                    f"Requirement {requirement!r} unsupported by {available.engine}."
                ),
            )
        )
    return results


def capability_implications() -> dict[str, frozenset[str]]:
    """Return capability names that must also be claimed when a flag is set.

    Specialized SQL, Spark, and orchestration flags imply their family root.
    Dataframe-oriented execution and interchange flags imply ``dataframe``.
    """
    sql_family = frozenset({"sql"})
    spark_family = frozenset({"spark"})
    orch_family = frozenset({"orchestration"})
    dataframe_family = frozenset({"dataframe"})
    return {
        "sql_merge": sql_family,
        "sql_cte": sql_family,
        "sql_returning": sql_family,
        "sql_transactional_ddl": sql_family,
        "sql_atomic_rename": sql_family,
        "sql_catalog_inspect": sql_family,
        "sql_trusted_fragments": sql_family,
        "spark_delta": spark_family,
        "spark_merge": spark_family,
        "spark_streaming": spark_family,
        "spark_native_exprs": spark_family,
        "spark_udf": spark_family,
        "spark_cache": spark_family,
        "spark_checkpoint": spark_family,
        "orch_scheduling": orch_family,
        "orch_retries": orch_family,
        "orch_timeouts": orch_family,
        "orch_parallel": orch_family,
        "orch_sensors": orch_family,
        "orch_artifacts_only_xcom": orch_family,
        "lazy": dataframe_family,
        "arrow_import": dataframe_family,
        "arrow_export": dataframe_family,
        "zero_copy": dataframe_family,
        "invalid_row_separation": dataframe_family,
    }


def capability_conflicts() -> list[tuple[str, str]]:
    """Return pairs of capability names that must not both be claimed.

    Vocabulary ``/1`` has no hard mutual exclusions; ``eager`` and ``lazy`` may
    both be true for engines that support both execution modes.
    """
    return []


def validate_capability_claims(caps: PluginCapabilities) -> list[str]:
    """Return human-readable findings for inconsistent capability claims.

    Currently reports missing implied capabilities. Conflict pairs from
    :func:`capability_conflicts` are also checked when defined. Storage
    ``storage.delta.*`` extras imply ``spark_delta`` and ``spark``.
    """
    findings: list[str] = []
    for claim, required in capability_implications().items():
        if not bool(getattr(caps, claim, False)):
            continue
        for req in sorted(required):
            if not bool(getattr(caps, req, False)):
                findings.append(
                    f"Capability {claim!r} implies {req!r}, but {req!r} is not claimed."
                )
    for left, right in capability_conflicts():
        if bool(getattr(caps, left, False)) and bool(getattr(caps, right, False)):
            findings.append(
                f"Capabilities {left!r} and {right!r} conflict and cannot both be claimed."
            )
    # Storage extras are advertised via ``extras``, not boolean fields.
    from etlantic.storage.delta_capabilities import (
        STORAGE_DELTA_CAPABILITY_EXTRAS,
        STORAGE_DELTA_EXTRA_IMPLIES,
    )

    for extra in sorted(caps.extras & STORAGE_DELTA_CAPABILITY_EXTRAS):
        for req in sorted(STORAGE_DELTA_EXTRA_IMPLIES):
            if not caps.supports(req):
                findings.append(
                    f"Capability extra {extra!r} implies {req!r}, "
                    f"but {req!r} is not claimed."
                )
    return findings


def vocabulary_major_compatible(version: str) -> bool:
    """Return True when ``version`` shares major ``/1`` with this vocabulary."""
    prefix = "etlantic.capabilities/"
    if not version.startswith(prefix):
        return False
    major = version[len(prefix) :].split(".", 1)[0]
    current_major = CAPABILITY_VOCABULARY_VERSION[len(prefix) :].split(".", 1)[0]
    return major == current_major and major == "1"
