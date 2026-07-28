"""Compatibility re-export — use ``medallantic.reports`` instead."""

from __future__ import annotations

from medallantic.reports import (
    adapt_run_result,
    report_to_sparkforge_explain,
)

__all__ = [
    "adapt_run_result",
    "report_to_sparkforge_explain",
]
