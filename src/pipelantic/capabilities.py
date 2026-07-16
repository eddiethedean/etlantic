"""Plugin capability declarations and negotiation results."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class CapabilityDecision(StrEnum):
    """Outcome of comparing required vs available capabilities."""

    SUPPORTED = "supported"
    FALLBACK = "fallback"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class PluginCapabilities:
    """Declared capabilities of a plugin or engine.

    Dataframe-oriented flags (eager/lazy/arrow/...) are first-class for 0.5
    planning. Unknown requirements may still be declared via ``extras``.
    """

    engine: str
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
        }
        if requirement in known:
            return known[requirement]
        return requirement in self.extras

    def to_dict(self) -> dict[str, Any]:
        """Serialize capabilities."""
        return {
            "engine": self.engine,
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
            "extras": sorted(self.extras),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PluginCapabilities:
        """Deserialize capabilities."""
        extras = data.get("extras") or ()
        return cls(
            engine=str(data["engine"]),
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
