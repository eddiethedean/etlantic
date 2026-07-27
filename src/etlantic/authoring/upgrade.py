"""Pipeline definition wire-schema upgrades."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from etlantic.authoring.definition import PIPELINE_SCHEMA

_UPGRADERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {}


class UnsupportedPipelineSchemaError(ValueError):
    """Raised when a pipeline definition uses an unsupported wire schema."""


def upgrade_pipeline_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Upgrade a pipeline definition mapping to the current wire schema.

    Currently only :data:`PIPELINE_SCHEMA` (``etlantic.pipeline/1``) is accepted.
    """
    if not isinstance(data, dict):
        raise TypeError(
            f"PipelineDefinition document must be a mapping, got {type(data)!r}"
        )
    current = dict(data)
    schema = current.get("schema")
    seen: set[str] = set()
    while isinstance(schema, str) and schema in _UPGRADERS:
        if schema in seen:
            raise UnsupportedPipelineSchemaError(
                f"Pipeline schema upgrade cycle detected at {schema!r}."
            )
        seen.add(schema)
        current = dict(_UPGRADERS[schema](current))
        schema = current.get("schema")
    if schema == PIPELINE_SCHEMA:
        return current
    if schema is None or schema == "":
        raise UnsupportedPipelineSchemaError(
            f"PipelineDefinition document is missing required 'schema' "
            f"(expected {PIPELINE_SCHEMA!r})."
        )
    raise UnsupportedPipelineSchemaError(
        f"Unsupported PipelineDefinition schema {schema!r}; "
        f"expected {PIPELINE_SCHEMA!r}."
    )
