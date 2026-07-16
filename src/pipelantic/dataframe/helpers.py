"""Shared helpers for dataframe plugin implementations."""

from __future__ import annotations

from typing import Any

from pipelantic.schema_drift import NormalizedSchema, normalize_schema_from_fields
from pipelantic.storage.protocol import as_records, records_to_dicts


def logical_type_from_annotation(annotation: Any) -> str:
    """Map a Python type annotation to a stable logical type name."""
    origin = getattr(annotation, "__origin__", None)
    if origin is not None:
        args = getattr(annotation, "__args__", ())
        non_none = [a for a in args if a is not type(None)]
        if non_none:
            return logical_type_from_annotation(non_none[0])
    name = getattr(annotation, "__name__", None) or str(annotation)
    mapping = {
        "str": "string",
        "int": "integer",
        "float": "number",
        "bool": "boolean",
        "datetime": "timestamp",
        "date": "date",
        "Decimal": "decimal",
        "dict": "object",
        "list": "array",
    }
    return mapping.get(name, name.lower() if isinstance(name, str) else "unknown")


def schema_from_contract(
    contract_type: type[Any] | None, *, identity: str
) -> NormalizedSchema | None:
    """Build a NormalizedSchema from a ContractModel / Data class."""
    if contract_type is None or not hasattr(contract_type, "model_fields"):
        return None
    fields: list[dict[str, Any]] = []
    for name, field_info in contract_type.model_fields.items():
        ann = field_info.annotation
        required = field_info.is_required()
        nullable = not required
        fields.append(
            {
                "name": name,
                "logical_type": logical_type_from_annotation(ann),
                "required": required,
                "nullable": nullable,
            }
        )
    return normalize_schema_from_fields(fields, identity=identity)


def schema_dict(schema: NormalizedSchema | None) -> dict[str, Any] | None:
    if schema is None:
        return None
    return {
        "identity": schema.identity,
        "fields": [
            {
                "name": f.name,
                "logical_type": f.logical_type,
                "required": f.required,
                "nullable": f.nullable,
                "metadata": dict(f.metadata),
            }
            for f in schema.fields
        ],
        "fingerprint": schema.fingerprint(),
        "metadata": dict(schema.metadata),
    }


def normalized_from_field_dicts(
    fields: list[dict[str, Any]],
    *,
    identity: str,
) -> NormalizedSchema:
    return normalize_schema_from_fields(fields, identity=identity)


def records_from_mappings(
    rows: list[dict[str, Any]],
    *,
    contract_type: type[Any] | None,
) -> list[Any]:
    return as_records(rows, contract_type)


def mappings_from_any(value: Any) -> list[dict[str, Any]]:
    return records_to_dicts(value)


def split_valid_invalid_records(
    records: list[Any],
    *,
    contract_type: type[Any] | None,
) -> tuple[list[Any], list[Any], list[dict[str, Any]]]:
    """Validate records one-by-one; return (valid, invalid, diagnostics)."""
    if contract_type is None:
        return list(records), [], []
    valid: list[Any] = []
    invalid: list[Any] = []
    diagnostics: list[dict[str, Any]] = []
    for index, item in enumerate(records):
        try:
            if isinstance(item, contract_type):
                valid.append(item)
            elif isinstance(item, dict):
                valid.append(contract_type.model_validate(item))
            else:
                valid.append(contract_type.model_validate(item))
        except Exception as exc:
            invalid.append(item)
            diagnostics.append(
                {
                    "code": "PMDF410",
                    "message": str(exc),
                    "row_index": index,
                    "severity": "error",
                }
            )
    return valid, invalid, diagnostics
