"""Quality expression wire-schema upgrades."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from etlantic.quality.model import QUALITY_SCHEMA

_UPGRADERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {}


class UnsupportedQualitySchemaError(ValueError):
    """Raised when a quality expression uses an unsupported wire schema."""


def upgrade_quality_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Upgrade a quality expression mapping to the current wire schema.

    Currently only :data:`QUALITY_SCHEMA` (``etlantic.quality/1``) is accepted.
    """
    if not isinstance(data, dict):
        raise TypeError(
            f"QualityExpression document must be a mapping, got {type(data)!r}"
        )
    current = dict(data)
    schema = current.get("schema")
    seen: set[str] = set()
    while isinstance(schema, str) and schema in _UPGRADERS:
        if schema in seen:
            raise UnsupportedQualitySchemaError(
                f"Quality schema upgrade cycle detected at {schema!r}."
            )
        seen.add(schema)
        current = dict(_UPGRADERS[schema](current))
        schema = current.get("schema")
    if schema == QUALITY_SCHEMA:
        return current
    if schema is None or schema == "":
        raise UnsupportedQualitySchemaError(
            f"QualityExpression document is missing required 'schema' "
            f"(expected {QUALITY_SCHEMA!r})."
        )
    raise UnsupportedQualitySchemaError(
        f"Unsupported QualityExpression schema {schema!r}; expected {QUALITY_SCHEMA!r}."
    )
