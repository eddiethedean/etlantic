"""Compatibility re-export — use ``medallantic.ir`` instead."""

from __future__ import annotations

from medallantic.ir import (
    LayerKind,
    SparkForgePipelineSpec,
    SparkForgeStepSpec,
    StepKind,
)

__all__ = [
    "LayerKind",
    "SparkForgePipelineSpec",
    "SparkForgeStepSpec",
    "StepKind",
]
