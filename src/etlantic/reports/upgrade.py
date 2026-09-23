# pyright: reportUnnecessaryIsInstance=false
"""Run-report wire-schema upgrades.

Historical run-report documents are migrated here before
:meth:`PipelineRunReport.from_dict` validation. Only
``etlantic.run_report/1`` is accepted today; future versions will register
upgrade steps in ``_UPGRADERS``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from etlantic.reports.model import REPORT_SCHEMA

# schema id → upgrade step producing the next schema version
_UPGRADERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {}


class UnsupportedReportSchemaError(ValueError):
    """Raised when a run-report document uses an unsupported wire schema."""


def upgrade_report_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Upgrade a run-report mapping to the current wire schema.

    Currently only :data:`REPORT_SCHEMA` (``etlantic.run_report/1``) is
    accepted. Missing or unknown schemas raise
    :class:`UnsupportedReportSchemaError`.
    """
    if not isinstance(data, dict):
        raise TypeError(
            f"PipelineRunReport document must be a mapping, got {type(data)!r}"
        )
    current = dict(data)
    schema = current.get("schema")
    seen: set[str] = set()
    while isinstance(schema, str) and schema in _UPGRADERS:
        if schema in seen:
            raise UnsupportedReportSchemaError(
                f"Run-report schema upgrade cycle detected at {schema!r}."
            )
        seen.add(schema)
        current = dict(_UPGRADERS[schema](current))
        schema = current.get("schema")
    if schema == REPORT_SCHEMA:
        return current
    if schema is None or schema == "":
        raise UnsupportedReportSchemaError(
            f"PipelineRunReport document is missing required 'schema' "
            f"(expected {REPORT_SCHEMA!r})."
        )
    raise UnsupportedReportSchemaError(
        f"Unsupported PipelineRunReport schema {schema!r}; expected {REPORT_SCHEMA!r}."
    )
