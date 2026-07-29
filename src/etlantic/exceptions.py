"""Public exception hierarchy for ETLantic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from etlantic.diagnostics import ValidationReport


class ETLanticError(Exception):
    """Base class for public ETLantic exceptions."""


class ModelDefinitionError(ETLanticError):
    """Raised when a class definition cannot form a usable model."""


class PipelineValidationError(ETLanticError):
    """Raised when validation fails and the caller requested an exception."""

    def __init__(self, message: str, *, report: ValidationReport) -> None:
        super().__init__(message)
        self.report = report


class InternalETLanticError(ETLanticError):
    """Raised when an internal invariant is violated."""


class PipelineExecutionError(ETLanticError):
    """Raised when pipeline execution fails."""

    def __init__(
        self,
        message: str,
        *,
        run_id: str | None = None,
        report: Any = None,
        code: str | None = None,
        stage: str | None = None,
    ) -> None:
        super().__init__(message)
        self.run_id = run_id
        self.report = report
        self.code = code
        self.stage = stage


class NodeExecutionError(PipelineExecutionError):
    """Raised when a single node fails during execution."""

    def __init__(
        self,
        message: str,
        *,
        node_name: str,
        stage: str | None = None,
        run_id: str | None = None,
        report: Any = None,
        code: str | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(
            message, run_id=run_id, report=report, code=code, stage=stage
        )
        self.node_name = node_name
        self.cause = cause


class DataValidationError(PipelineExecutionError):
    """Raised when runtime data fails a contract boundary."""

    def __init__(
        self,
        message: str,
        *,
        node_name: str | None = None,
        boundary: str | None = None,
        run_id: str | None = None,
        report: Any = None,
        code: str | None = None,
    ) -> None:
        super().__init__(message, run_id=run_id, report=report, code=code)
        self.node_name = node_name
        self.boundary = boundary


class PipelineTimeoutError(PipelineExecutionError):
    """Raised when a run or step exceeds its timeout."""


class PipelineCancelledError(PipelineExecutionError):
    """Raised when a run is cancelled."""
