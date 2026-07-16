"""Execution state vocabulary for local runtime."""

from __future__ import annotations

from enum import StrEnum


class RunStatus(StrEnum):
    """Normalized pipeline run status."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    PARTIAL = "partial"


class StepStatus(StrEnum):
    """Normalized step / node execution status."""

    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RETRYING = "retrying"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    ABANDONED = "abandoned"


class FailureStage(StrEnum):
    """Where a node failure occurred."""

    READ = "read"
    INPUT_VALIDATION = "input_validation"
    TRANSFORM = "transform"
    OUTPUT_VALIDATION = "output_validation"
    WRITE = "write"
    RESOURCE = "resource"
    ORCHESTRATOR = "orchestrator"
    FRESHNESS = "freshness"
    SCHEMA_DRIFT = "schema_drift"
