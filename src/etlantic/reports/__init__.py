"""Run report package."""

from __future__ import annotations

from etlantic.reports.file_store import FileReportStore, compare_reports
from etlantic.reports.model import (
    REPORT_SCHEMA,
    ArtifactResult,
    BackendRunReference,
    PipelineRunReport,
    RunDiagnostic,
    RunRecommendation,
    RunSummary,
    SchemaObservationResult,
    StateTransitionResult,
    StepRunReport,
    ValidationResult,
)
from etlantic.reports.render import render_html, render_text
from etlantic.reports.store import ReportStore
from etlantic.reports.streaming import (
    STREAM_OPS_KEY,
    StreamOperationsSnapshot,
    attach_stream_operations,
)

__all__ = [
    "REPORT_SCHEMA",
    "STREAM_OPS_KEY",
    "ArtifactResult",
    "BackendRunReference",
    "FileReportStore",
    "PipelineRunReport",
    "ReportStore",
    "RunDiagnostic",
    "RunRecommendation",
    "RunSummary",
    "SchemaObservationResult",
    "StateTransitionResult",
    "StepRunReport",
    "StreamOperationsSnapshot",
    "ValidationResult",
    "attach_stream_operations",
    "compare_reports",
    "render_html",
    "render_text",
]
