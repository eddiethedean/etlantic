"""Versioned orchestrator compilation protocol (``etlantic.orchestration/1``)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from etlantic.capabilities import PluginCapabilities
from etlantic.plan.artifacts import ArtifactRef
from etlantic.plan.model import PipelinePlan

ORCHESTRATION_PROTOCOL_VERSION = "etlantic.orchestration/1"
ORCHESTRATOR_ENGINES = frozenset({"airflow", "local"})


class OrchestrationPhase(StrEnum):
    """Phases of external orchestration."""

    COMPILE = "compile"
    SUBMIT = "submit"
    POLL = "poll"
    CANCEL = "cancel"
    CORRELATE = "correlate"


class TaskRetryPolicy(StrEnum):
    """How retries are applied on a compiled task."""

    DISABLED = "disabled"
    SAFE = "safe"
    FORCED_OFF = "forced_off"
    UNSAFE_REJECTED = "unsafe_rejected"


@dataclass(frozen=True, slots=True)
class CompilationDiagnostic:
    """Structured diagnostic from orchestration compilation."""

    code: str
    severity: str
    message: str
    subject_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "subject_id": self.subject_id,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class CompiledTask:
    """Backend-agnostic compiled task derived from a plan node."""

    task_id: str
    node_name: str
    node_kind: str
    dependencies: tuple[str, ...] = ()
    retries: int = 0
    retry_policy: TaskRetryPolicy = TaskRetryPolicy.DISABLED
    timeout_seconds: float | None = None
    write_intent: str | None = None
    repair: dict[str, Any] | None = None
    backfill: dict[str, Any] | None = None
    reconciliation: dict[str, Any] | None = None
    artifact_outputs: tuple[ArtifactRef, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "node_name": self.node_name,
            "node_kind": self.node_kind,
            "dependencies": list(self.dependencies),
            "retries": self.retries,
            "retry_policy": self.retry_policy.value,
            "timeout_seconds": self.timeout_seconds,
            "write_intent": self.write_intent,
            "repair": dict(self.repair) if self.repair else None,
            "backfill": dict(self.backfill) if self.backfill else None,
            "reconciliation": (
                dict(self.reconciliation) if self.reconciliation else None
            ),
            "artifact_outputs": [a.to_dict() for a in self.artifact_outputs],
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class ScheduleIntent:
    """Portable scheduling intent (orchestrator maps to backend constructs)."""

    type: str = "manual"  # manual | cron | event | dependency
    expression: str | None = None
    timezone: str | None = "UTC"
    catchup: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "expression": self.expression,
            "timezone": self.timezone,
            "catchup": self.catchup,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> ScheduleIntent:
        if not data:
            return cls(timezone=None)
        if "timezone" in data:
            raw_tz = data.get("timezone")
            timezone = str(raw_tz).strip() if raw_tz not in (None, "") else None
        else:
            # Missing key must stay unset so compilers can fail closed.
            timezone = None
        return cls(
            type=str(data.get("type") or "manual"),
            expression=data.get("expression"),
            timezone=timezone,
            catchup=bool(data.get("catchup", False)),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True, slots=True)
class ExecutionIntent:
    """Portable execution settings for orchestration backends."""

    retries: int = 0
    retry_delay_seconds: float = 0.0
    timeout_seconds: float | None = None
    max_active_runs: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "retries": self.retries,
            "retry_delay_seconds": self.retry_delay_seconds,
            "timeout_seconds": self.timeout_seconds,
            "max_active_runs": self.max_active_runs,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> ExecutionIntent:
        if not data:
            return cls()
        return cls(
            retries=int(data.get("retries") or 0),
            retry_delay_seconds=float(data.get("retry_delay_seconds") or 0.0),
            timeout_seconds=(
                float(data["timeout_seconds"])
                if data.get("timeout_seconds") is not None
                else None
            ),
            max_active_runs=(
                int(data["max_active_runs"])
                if data.get("max_active_runs") is not None
                else None
            ),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True, slots=True)
class CompilationContext:
    """Context supplied to orchestrator compilers."""

    target: str
    schedule: ScheduleIntent = field(default_factory=ScheduleIntent)
    execution: ExecutionIntent = field(default_factory=ExecutionIntent)
    required_capabilities: tuple[str, ...] = ()
    max_inline_bytes: int = 65536
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "schedule": self.schedule.to_dict(),
            "execution": self.execution.to_dict(),
            "required_capabilities": list(self.required_capabilities),
            "max_inline_bytes": self.max_inline_bytes,
            "metadata": dict(self.metadata),
        }


@dataclass
class CompiledOrchestrationArtifact:
    """Deterministic compiled orchestration artifact (secret-free)."""

    target: str
    dag_id: str
    protocol_version: str = ORCHESTRATION_PROTOCOL_VERSION
    plan_id: str = ""
    pipeline_id: str = ""
    fingerprint: str = ""
    tasks: tuple[CompiledTask, ...] = ()
    dependencies: dict[str, tuple[str, ...]] = field(default_factory=dict)
    schedule: ScheduleIntent = field(default_factory=ScheduleIntent)
    execution: ExecutionIntent = field(default_factory=ExecutionIntent)
    source: str = ""
    diagnostics: tuple[CompilationDiagnostic, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def task_ids(self) -> set[str]:
        return {t.task_id for t in self.tasks}

    def explain(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "dag_id": self.dag_id,
            "protocol_version": self.protocol_version,
            "plan_id": self.plan_id,
            "pipeline_id": self.pipeline_id,
            "fingerprint": self.fingerprint,
            "task_count": len(self.tasks),
            "task_ids": sorted(self.task_ids),
            "dependencies": {k: list(v) for k, v in self.dependencies.items()},
            "schedule": self.schedule.to_dict(),
            "execution": self.execution.to_dict(),
            "diagnostics": [d.to_dict() for d in self.diagnostics],
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        data = self.explain()
        data["tasks"] = [t.to_dict() for t in self.tasks]
        data["source"] = self.source
        return data

    def write(self, path: str | Path) -> Path:
        """Write the generated module source to ``path``."""
        resolved = Path(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        if not self.source:
            raise ValueError("Compiled artifact has no source to write")
        text = self.source if self.source.endswith("\n") else self.source + "\n"
        resolved.write_text(text, encoding="utf-8")
        return resolved


@dataclass(frozen=True, slots=True)
class OrchestratorPluginInfo:
    """Identity and capability declaration for an orchestrator plugin."""

    name: str
    engine: str
    version: str
    protocol_version: str = ORCHESTRATION_PROTOCOL_VERSION
    capabilities: PluginCapabilities | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "engine": self.engine,
            "version": self.version,
            "protocol_version": self.protocol_version,
            "capabilities": (
                self.capabilities.to_dict() if self.capabilities is not None else None
            ),
            "metadata": dict(self.metadata),
        }


@runtime_checkable
class OrchestratorPlugin(Protocol):
    """Protocol for external orchestration compilers.

    Implementations turn a resolved :class:`~etlantic.plan.model.PipelinePlan`
    into backend artifacts (for example Airflow DAG modules) without executing
    user transformation code during compilation.
    """

    @property
    def info(self) -> OrchestratorPluginInfo:
        """Plugin metadata including orchestrator id and capabilities."""
        ...

    def capabilities(self) -> PluginCapabilities:
        """Return scheduling/retry/parallelism flags for planning."""
        ...

    def compile(
        self,
        plan: PipelinePlan,
        *,
        context: CompilationContext,
    ) -> CompiledOrchestrationArtifact:
        """Compile a pipeline plan into a deterministic orchestration artifact."""
        ...

    def explain(
        self,
        artifact: CompiledOrchestrationArtifact,
    ) -> dict[str, Any]:
        """Return a JSON-serializable summary of a compiled artifact."""
        ...
