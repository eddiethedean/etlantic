"""Structured diagnostics and validation reports."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from etlantic.exceptions import PipelineValidationError


class Severity(StrEnum):
    """Diagnostic severity levels."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    HINT = "hint"


@dataclass(frozen=True, slots=True)
class SourceLocation:
    """Optional origin of a diagnostic (file, Python object, or contract path)."""

    path: str | None = None
    line: int | None = None
    column: int | None = None
    object_ref: str | None = None
    symbol: str | None = None


@dataclass(frozen=True, slots=True)
class DiagnosticAction:
    """Machine-readable action a future IDE can expose as a quick fix."""

    kind: str
    title: str
    edit_suggestion: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize action for tooling."""
        return {
            "kind": self.kind,
            "title": self.title,
            "edit_suggestion": self.edit_suggestion,
            "arguments": dict(self.arguments),
        }


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """A structured finding from loading, inspection, or validation."""

    code: str
    severity: Severity
    message: str
    path: tuple[str, ...] = ()
    help: str | None = None
    related: tuple[tuple[str, ...], ...] = ()
    source: SourceLocation | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    phase: str | None = None
    actions: tuple[DiagnosticAction, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON/service payloads (secret-free)."""
        payload: dict[str, Any] = {
            "code": self.code,
            "severity": self.severity.value,
            "message": self.message,
            "path": list(self.path),
            "phase": self.phase,
        }
        if self.help:
            payload["help"] = self.help
        if self.related:
            payload["related"] = [list(item) for item in self.related]
        if self.source is not None:
            payload["source"] = {
                "path": self.source.path,
                "line": self.source.line,
                "column": self.source.column,
                "object_ref": self.source.object_ref,
                "symbol": self.source.symbol,
            }
        if self.actions:
            payload["actions"] = [action.to_dict() for action in self.actions]
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """Immutable collection of diagnostics from a validation pass.

    Produced by :meth:`~etlantic.pipeline.Pipeline.validate` and related loaders.
    Use :meth:`raise_for_errors` to fail closed in application or CI code.
    Serialize to JSON or SARIF via CLI ``etlantic validate --format``.
    """

    diagnostics: tuple[Diagnostic, ...] = ()
    phases: tuple[str, ...] = ()

    @property
    def valid(self) -> bool:
        """Return True when no error-severity diagnostics are present."""
        return not any(d.severity is Severity.ERROR for d in self.diagnostics)

    @property
    def has_errors(self) -> bool:
        """Return True when at least one error-severity diagnostic is present."""
        return not self.valid

    @property
    def errors(self) -> tuple[Diagnostic, ...]:
        """Return error-severity diagnostics."""
        return tuple(d for d in self.diagnostics if d.severity is Severity.ERROR)

    @property
    def warnings(self) -> tuple[Diagnostic, ...]:
        """Return warning-severity diagnostics."""
        return tuple(d for d in self.diagnostics if d.severity is Severity.WARNING)

    def filter(
        self,
        *,
        severity: Severity | None = None,
        code: str | None = None,
        phase: str | None = None,
    ) -> ValidationReport:
        """Return a report containing only matching diagnostics."""
        items = self.diagnostics
        if severity is not None:
            items = tuple(d for d in items if d.severity is severity)
        if code is not None:
            items = tuple(d for d in items if d.code == code)
        if phase is not None:
            items = tuple(d for d in items if d.phase == phase)
        return ValidationReport(diagnostics=items, phases=self.phases)

    def raise_for_errors(self) -> None:
        """Raise :class:`PipelineValidationError` if the report is invalid."""
        if self.valid:
            return
        count = len(self.errors)
        message = f"Pipeline validation failed with {count} error(s)."
        raise PipelineValidationError(message, report=self)

    def merge(self, other: ValidationReport) -> ValidationReport:
        """Combine two reports, preserving order and uniqueness by identity."""
        phases = tuple(dict.fromkeys([*self.phases, *other.phases]))
        return ValidationReport(
            diagnostics=self.diagnostics + other.diagnostics,
            phases=phases,
        )

    @classmethod
    def from_diagnostics(
        cls,
        diagnostics: Iterable[Diagnostic],
        *,
        phases: Sequence[str] = (),
    ) -> ValidationReport:
        """Build a report from an iterable of diagnostics."""
        return cls(diagnostics=tuple(diagnostics), phases=tuple(phases))

    def codes(self) -> Sequence[str]:
        """Return diagnostic codes in report order."""
        return tuple(d.code for d in self.diagnostics)
