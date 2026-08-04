"""GitHub Actions annotation renderer for diagnostics."""

from __future__ import annotations

from collections.abc import Iterable

from etlantic.diagnostics import Diagnostic, Severity


def diagnostics_to_github_annotations(
    diagnostics: Iterable[Diagnostic],
) -> list[str]:
    """Return GitHub workflow command lines for annotations."""
    lines: list[str] = []
    for diagnostic in diagnostics:
        level = {
            Severity.ERROR: "error",
            Severity.WARNING: "warning",
            Severity.INFO: "notice",
            Severity.HINT: "notice",
        }.get(diagnostic.severity, "notice")
        source = diagnostic.source
        if source is not None and source.path:
            path = source.path
            loc_bits = [f"file={path}"]
            if source.line is not None:
                loc_bits.append(f"line={source.line}")
            if source.column is not None:
                loc_bits.append(f"col={source.column}")
            loc = ",".join(loc_bits)
        else:
            path = "/".join(str(p) for p in diagnostic.path if p) or "pipeline"
            loc = f"file={path}"
        lines.append(f"::{level} {loc},title={diagnostic.code}::{diagnostic.message}")
    return lines
