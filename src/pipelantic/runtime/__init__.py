"""Local runtime package."""

from __future__ import annotations

from typing import Any

from pipelantic.runtime.request import (
    CancellationPolicy,
    InvalidationMode,
    MaterializationPolicy,
    RetryPolicy,
    RunIntent,
    RunRequest,
    RunSelection,
    TimeoutPolicy,
)
from pipelantic.runtime.state import FailureStage, RunStatus, StepStatus

__all__ = [
    "CancellationPolicy",
    "DebugSession",
    "FailureStage",
    "InvalidationMode",
    "LocalOrchestrator",
    "MaterializationPolicy",
    "RetryPolicy",
    "RunIntent",
    "RunRequest",
    "RunSelection",
    "RunStatus",
    "StepStatus",
    "TimeoutPolicy",
    "arun_pipeline",
    "run_pipeline",
]


def __getattr__(name: str) -> Any:
    if name in {"DebugSession", "arun_pipeline", "run_pipeline"}:
        from pipelantic.runtime import execute as _execute

        return getattr(_execute, name)
    if name == "LocalOrchestrator":
        from pipelantic.runtime.orchestrator import LocalOrchestrator

        return LocalOrchestrator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
