# pyright: reportUnknownVariableType=false
"""Typed runtime contexts passed through middleware stacks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class RunContext:
    """Context for one pipeline run."""

    run_id: str
    pipeline_id: str
    plan_id: str
    profile: str
    intent: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StepContext:
    """Context for one step invocation within a run."""

    run: RunContext
    step_name: str
    node_kind: str
    attempt: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AttemptContext:
    """Context for a single attempt of a step."""

    step: StepContext
    attempt: int
    metadata: dict[str, Any] = field(default_factory=dict)
