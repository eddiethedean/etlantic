"""Plan wire-schema upgrades.

Historical plan documents are migrated here before
:meth:`PipelinePlan.from_dict` validation. Only ``etlantic.plan/1`` is
accepted today; future versions will register upgrade steps in
``_UPGRADERS``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from etlantic.plan.adaptive_model import ADAPTIVE_PLAN_SCHEMA
from etlantic.plan.model import PLAN_SCHEMA

# schema id → upgrade step producing the next schema version
_UPGRADERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {}


class UnsupportedPlanSchemaError(ValueError):
    """Raised when a plan document uses an unsupported wire schema."""


def upgrade_plan_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Upgrade a plan mapping to the current wire schema.

    Currently only :data:`PLAN_SCHEMA` (``etlantic.plan/1``) is accepted.
    Missing or unknown schemas raise :class:`UnsupportedPlanSchemaError`.
    """
    if not isinstance(data, dict):
        raise TypeError(f"PipelinePlan document must be a mapping, got {type(data)!r}")
    current = dict(data)
    schema = current.get("schema")
    seen: set[str] = set()
    while isinstance(schema, str) and schema in _UPGRADERS:
        if schema in seen:
            raise UnsupportedPlanSchemaError(
                f"Plan schema upgrade cycle detected at {schema!r}."
            )
        seen.add(schema)
        current = dict(_UPGRADERS[schema](current))
        schema = current.get("schema")
    if schema in {PLAN_SCHEMA, ADAPTIVE_PLAN_SCHEMA}:
        return current
    if schema is None or schema == "":
        raise UnsupportedPlanSchemaError(
            f"PipelinePlan document is missing required 'schema' "
            f"(expected {PLAN_SCHEMA!r})."
        )
    raise UnsupportedPlanSchemaError(
        f"Unsupported PipelinePlan schema {schema!r}; expected {PLAN_SCHEMA!r} or "
        f"{ADAPTIVE_PLAN_SCHEMA!r}."
    )
