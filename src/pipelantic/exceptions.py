"""Public exception hierarchy for Pipelantic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pipelantic.diagnostics import ValidationReport


class PipelanticError(Exception):
    """Base class for public Pipelantic exceptions."""


class ModelDefinitionError(PipelanticError):
    """Raised when a class definition cannot form a usable model."""


class PipelineValidationError(PipelanticError):
    """Raised when validation fails and the caller requested an exception."""

    def __init__(self, message: str, *, report: ValidationReport) -> None:
        super().__init__(message)
        self.report = report


class InternalPipelanticError(PipelanticError):
    """Raised when an internal invariant is violated."""


class PipelineExecutionError(PipelanticError):
    """Raised when pipeline execution fails."""

    def __init__(
        self,
        message: str,
        *,
        run_id: str | None = None,
        report: Any = None,
        code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.run_id = run_id
        self.report = report
        self.code = code


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
        super().__init__(message, run_id=run_id, report=report, code=code)
        self.node_name = node_name
        self.stage = stage
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
