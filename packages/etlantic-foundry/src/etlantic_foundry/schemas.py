"""Public JSON Schemas for the connector's declared options."""

from __future__ import annotations

_BASE = {
    "base_url": {
        "type": "string",
        "format": "uri",
        "pattern": "^https://",
        "description": "HTTPS origin of the Foundry deployment.",
    },
    "dataset_rid": {
        "type": "string",
        "minLength": 1,
        "description": "Foundry Dataset resource identifier.",
    },
    "branch_name": {
        "type": "string",
        "minLength": 1,
        "description": "Branch used for file operations.",
    },
    "timeout_seconds": {
        "type": "integer",
        "minimum": 1,
        "maximum": 60,
        "default": 20,
    },
}

_FILE = {
    "format": {"type": "string", "enum": ["csv", "json", "jsonl"], "default": "csv"},
    "encoding": {
        "type": "string",
        "enum": ["utf-8", "utf-8-sig", "latin-1"],
        "default": "utf-8",
    },
    "delimiter": {"type": "string", "minLength": 1, "maxLength": 1, "default": ","},
}

_READ_BOUNDS = {
    "max_files": {"type": "integer", "minimum": 1, "maximum": 10_000, "default": 1_000},
    "max_file_bytes": {
        "type": "integer",
        "minimum": 1,
        "maximum": 128 * 1024 * 1024,
        "default": 32 * 1024 * 1024,
    },
    "max_total_bytes": {
        "type": "integer",
        "minimum": 1,
        "maximum": 256 * 1024 * 1024,
        "default": 128 * 1024 * 1024,
    },
    "max_rows": {
        "type": "integer",
        "minimum": 1,
        "maximum": 1_000_000,
        "default": 100_000,
    },
    "batch_size": {
        "type": "integer",
        "minimum": 1,
        "maximum": 10_000,
        "default": 1_000,
    },
}

_ROOT = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "x-etlantic-secret-context": {
        "required": True,
        "value_type": "SecretValue",
        "binding_field": "secret_ref",
        "purpose": "Foundry API bearer token",
    },
}

SOURCE_CONFIG_SCHEMA = {
    **_ROOT,
    "title": "Foundry source options",
    "properties": {
        **_BASE,
        "transaction_rid": {"type": "string", "minLength": 1},
        "mode": {"type": "string", "enum": ["snapshot"], "default": "snapshot"},
        "path_prefix": {"type": "string", "minLength": 1},
        **_FILE,
        **_READ_BOUNDS,
        "allow_empty": {"type": "boolean", "default": False},
    },
    "required": ["base_url", "dataset_rid", "branch_name", "transaction_rid"],
}

SINK_CONFIG_SCHEMA = {
    **_ROOT,
    "title": "Foundry sink options",
    "properties": {
        **_BASE,
        "mode": {
            "type": "string",
            "enum": ["append", "replace", "update", "snapshot", "overwrite"],
            "default": "append",
        },
        "file_path": {"type": ["string", "null"], "minLength": 1},
        "path_prefix": {
            "type": "string",
            "minLength": 1,
            "default": "etlantic/effects",
        },
        **_FILE,
        "max_rows": {
            "type": "integer",
            "minimum": 1,
            "maximum": 1_000_000,
            "default": 100_000,
        },
        "max_bytes": {
            "type": "integer",
            "minimum": 1,
            "maximum": 128 * 1024 * 1024,
            "default": 32 * 1024 * 1024,
        },
    },
    "required": ["base_url", "dataset_rid", "branch_name"],
    "allOf": [
        {
            "if": {
                "properties": {"mode": {"enum": ["replace", "update"]}},
                "required": ["mode"],
            },
            "then": {
                "required": ["file_path"],
                "properties": {"file_path": {"type": "string", "minLength": 1}},
            },
        }
    ],
}

STORAGE_CONFIG_SCHEMA = {
    **_ROOT,
    "title": "Foundry storage inspection options",
    "properties": {
        **_BASE,
        "path_prefix": {"type": "string", "minLength": 1},
        **_FILE,
        "max_file_bytes": {
            "type": "integer",
            "minimum": 1,
            "maximum": 128 * 1024 * 1024,
            "default": 32 * 1024 * 1024,
        },
    },
    "required": ["base_url", "dataset_rid", "branch_name"],
}

__all__ = [
    "SINK_CONFIG_SCHEMA",
    "SOURCE_CONFIG_SCHEMA",
    "STORAGE_CONFIG_SCHEMA",
]
