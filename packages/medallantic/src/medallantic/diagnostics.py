"""Stable Medallantic construction and graph diagnostics (MDL1xx)."""

from __future__ import annotations

from etlantic.diagnostics import Diagnostic, Severity

# Construction / graph family (facade-owned — not core PM*).
MDL100_EMPTY = "MDL100"
MDL101_DUPLICATE_NAME = "MDL101"
MDL102_CYCLE = "MDL102"
MDL103_UNKNOWN_SOURCE = "MDL103"
MDL104_MISSING_SOURCE = "MDL104"
MDL105_BAD_WRITE_MODE = "MDL105"
MDL106_UNKNOWN_KIND = "MDL106"
MDL107_UNKNOWN_LAYER = "MDL107"
MDL110_RULES_INVALID = "MDL110"
# Historical alias — M2 replaced unenforced passthrough with parse-error use.
MDL110_RULES_UNENFORCED = MDL110_RULES_INVALID
MDL111_TRANSFORM_PASSTHROUGH = "MDL111"
MDL120_ACCEPT_RATE = "MDL120"

VALID_LAYERS = frozenset({"bronze", "silver", "gold"})


def mdl_diagnostic(
    code: str,
    message: str,
    *,
    severity: Severity = Severity.ERROR,
    path: tuple[str, ...] = (),
    phase: str = "medallion_authoring",
) -> Diagnostic:
    """Build a Medallantic ``MDL*`` diagnostic."""
    return Diagnostic(
        code=code,
        severity=severity,
        message=message,
        path=path,
        phase=phase,
    )
