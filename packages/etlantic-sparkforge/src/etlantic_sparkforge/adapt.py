"""Compatibility re-export — use ``medallantic.adapt`` instead."""

from __future__ import annotations

from medallantic.adapt import (
    AdaptationResult,
    AdaptedRow,
    AdapterError,
    MedallionRow,
    adapt_pipeline,
    adapt_profile,
    adapt_validation_policy,
    enrich_plan,
    spec_to_document,
)

__all__ = [
    "AdaptationResult",
    "AdaptedRow",
    "AdapterError",
    "MedallionRow",
    "adapt_pipeline",
    "adapt_profile",
    "adapt_validation_policy",
    "enrich_plan",
    "spec_to_document",
]
