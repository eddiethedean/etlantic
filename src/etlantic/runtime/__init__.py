# pyright: reportUnsupportedDunderAll=false
"""Local runtime package."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from etlantic.runtime.context import TrustedExecutionScope
from etlantic.runtime.request import (
    CancellationPolicy,
    InvalidationMode,
    MaterializationPolicy,
    RetryPolicy,
    RunIntent,
    RunRequest,
    RunSelection,
    TimeoutPolicy,
)
from etlantic.runtime.state import FailureStage, RunStatus, StepStatus

if TYPE_CHECKING:
    from etlantic.runtime.action_execution_host import (
        ActionExecutionHost,
        ActionHandler,
    )

__all__ = [
    "ActionExecutionHost",
    "ActionHandler",
    "CancellationPolicy",
    "DebugSession",
    "FailureStage",
    "FileStateStore",
    "IncrementalStrategy",
    "InvalidationMode",
    "LocalOrchestrator",
    "LocalScheduler",
    "MaterializationPolicy",
    "MemoryStateStore",
    "PhysicalArtifactHandle",
    "PhysicalExecutorInfo",
    "PhysicalLogicalOutcome",
    "PhysicalScheduler",
    "PhysicalUnitContext",
    "PhysicalUnitExecutor",
    "PhysicalUnitFailure",
    "PhysicalUnitResult",
    "PhysicalUnitSupport",
    "RetryPolicy",
    "RunIntent",
    "RunRequest",
    "RunSelection",
    "RunStatus",
    "StateStore",
    "StepStatus",
    "TimeoutPolicy",
    "TrustedExecutionScope",
    "arun_pipeline",
    "run_pipeline",
]


def __getattr__(name: str) -> Any:
    if name in {"ActionExecutionHost", "ActionHandler"}:
        from etlantic.runtime import action_execution_host

        return getattr(action_execution_host, name)
    if name in {"DebugSession", "arun_pipeline", "run_pipeline"}:
        from etlantic.runtime import execute as _execute

        return getattr(_execute, name)
    if name == "LocalOrchestrator":
        from etlantic.runtime.orchestrator import LocalOrchestrator

        return LocalOrchestrator
    if name == "LocalScheduler":
        from etlantic.runtime.scheduler import LocalScheduler

        return LocalScheduler
    if name in {
        "PhysicalArtifactHandle",
        "PhysicalExecutorInfo",
        "PhysicalLogicalOutcome",
        "PhysicalUnitContext",
        "PhysicalUnitExecutor",
        "PhysicalUnitFailure",
        "PhysicalUnitResult",
        "PhysicalUnitSupport",
    }:
        from etlantic.runtime import physical_protocol

        return getattr(physical_protocol, name)
    if name == "PhysicalScheduler":
        from etlantic.runtime.physical_scheduler import PhysicalScheduler

        return PhysicalScheduler
    if name in {
        "FileStateStore",
        "IncrementalStrategy",
        "MemoryStateStore",
        "StateStore",
    }:
        from etlantic.runtime import incremental as _incremental

        return getattr(_incremental, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
