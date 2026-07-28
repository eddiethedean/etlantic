"""Local runtime package."""

from __future__ import annotations

from typing import Any

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

__all__ = [
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
    "RetryPolicy",
    "RunIntent",
    "RunRequest",
    "RunSelection",
    "RunStatus",
    "StateStore",
    "StepStatus",
    "TimeoutPolicy",
    "arun_pipeline",
    "run_pipeline",
]


def __getattr__(name: str) -> Any:
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
        "FileStateStore",
        "IncrementalStrategy",
        "MemoryStateStore",
        "StateStore",
    }:
        from etlantic.runtime import incremental as _incremental

        return getattr(_incremental, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
