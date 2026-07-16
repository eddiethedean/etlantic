"""Safe, bounded path and file loading helpers."""

from __future__ import annotations

from pathlib import Path

from contractmodel.validation.limits import check_file_byte_limit

from pipelantic.diagnostics import (
    Diagnostic,
    Severity,
    SourceLocation,
    ValidationReport,
)
from pipelantic.exceptions import PipelanticError

# Default read budget for contract artifacts (10 MiB).
DEFAULT_MAX_BYTES = 10 * 1024 * 1024


class UnsafeLoadError(PipelanticError):
    """Raised when a path or file fails safe-loading checks."""

    def __init__(self, message: str, *, report: ValidationReport | None = None) -> None:
        super().__init__(message)
        self.report = report or ValidationReport()


def resolve_safe_path(
    path: str | Path,
    *,
    root: str | Path | None = None,
) -> Path:
    """Resolve ``path`` and optionally require it to stay under ``root``."""
    resolved = Path(path).expanduser().resolve()
    if root is not None:
        root_resolved = Path(root).expanduser().resolve()
        try:
            resolved.relative_to(root_resolved)
        except ValueError as exc:
            report = ValidationReport.from_diagnostics(
                [
                    Diagnostic(
                        code="PMSRC101",
                        severity=Severity.ERROR,
                        message=f"Path {path!s} escapes allowed root {root!s}.",
                        source=SourceLocation(path=str(path)),
                        help="Provide a path under the contract bundle root.",
                    )
                ]
            )
            raise UnsafeLoadError(str(report.errors[0].message), report=report) from exc
    return resolved


def ensure_file_within_budget(
    path: str | Path,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> Path:
    """Ensure ``path`` exists, is a file, and does not exceed ``max_bytes``."""
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_file():
        report = ValidationReport.from_diagnostics(
            [
                Diagnostic(
                    code="PMSRC102",
                    severity=Severity.ERROR,
                    message=f"Contract file not found: {resolved}",
                    source=SourceLocation(path=str(resolved)),
                )
            ]
        )
        raise UnsafeLoadError(str(report.errors[0].message), report=report)

    result = check_file_byte_limit(resolved, max_bytes=max_bytes)
    if result is not None and not result.success:
        details = "; ".join(err.message for err in result.errors) or "file too large"
        report = ValidationReport.from_diagnostics(
            [
                Diagnostic(
                    code="PMSRC103",
                    severity=Severity.ERROR,
                    message=f"Refusing to load oversized contract file: {details}",
                    source=SourceLocation(path=str(resolved)),
                    help=f"Maximum allowed size is {max_bytes} bytes.",
                    metadata={"max_bytes": max_bytes},
                )
            ]
        )
        raise UnsafeLoadError(str(report.errors[0].message), report=report)
    return resolved


def read_text_bounded(
    path: str | Path,
    *,
    root: str | Path | None = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
    encoding: str = "utf-8",
) -> tuple[Path, str]:
    """Safely read a text file after path and size checks."""
    resolved = resolve_safe_path(path, root=root)
    resolved = ensure_file_within_budget(resolved, max_bytes=max_bytes)
    return resolved, resolved.read_text(encoding=encoding)
