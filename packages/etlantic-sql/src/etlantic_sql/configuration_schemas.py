"""Public schemas for live PostgreSQL connector options."""

from __future__ import annotations

_ROOT = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "x-etlantic-secret-context": {
        "value_type": "SecretValue",
        "binding_field": "secret_ref",
        "secret": "PostgreSQL connection URL",
        "alternative": "ETLANTIC_SQL_URL in the worker environment",
    },
}

_COMMON = {
    "schema": {"type": "string", "minLength": 1, "default": "public"},
    "table": {"type": "string", "minLength": 1},
    "timeout_seconds": {
        "type": "integer",
        "minimum": 1,
        "maximum": 300,
        "default": 30,
    },
}

SOURCE_CONFIG_SCHEMA = {
    **_ROOT,
    "title": "PostgreSQL source options",
    "properties": {
        **_COMMON,
        "mode": {"type": "string", "enum": ["snapshot"], "default": "snapshot"},
        "row_limit": {
            "type": "integer",
            "minimum": 1,
            "maximum": 100_000,
            "default": 10_000,
        },
        "batch_size": {
            "type": "integer",
            "minimum": 1,
            "maximum": 10_000,
            "default": 1_000,
        },
        "max_bytes": {
            "type": "integer",
            "minimum": 1,
            "maximum": 256 * 1024 * 1024,
            "default": 64 * 1024 * 1024,
        },
    },
}

SINK_CONFIG_SCHEMA = {
    **_ROOT,
    "title": "PostgreSQL sink options",
    "properties": {
        **_COMMON,
        "mode": {
            "type": "string",
            "enum": ["append", "overwrite", "replace", "upsert", "merge"],
            "default": "append",
        },
        "key_columns": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "uniqueItems": True,
        },
        "effect_table": {
            "type": "string",
            "minLength": 1,
            "default": "etlantic_connector_effects",
        },
    },
    "allOf": [
        {
            "if": {
                "properties": {"mode": {"enum": ["upsert", "merge"]}},
                "required": ["mode"],
            },
            "then": {
                "required": ["key_columns"],
                "properties": {"key_columns": {"minItems": 1}},
            },
        }
    ],
}

STORAGE_CONFIG_SCHEMA = {
    **_ROOT,
    "title": "PostgreSQL schema inspection options",
    "properties": _COMMON,
}

__all__ = ["SINK_CONFIG_SCHEMA", "SOURCE_CONFIG_SCHEMA", "STORAGE_CONFIG_SCHEMA"]
