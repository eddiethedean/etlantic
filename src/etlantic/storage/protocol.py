"""Minimal storage binding protocol for local runtime I/O."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from itertools import islice
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class StorageBinding(Protocol):
    """Read/write datasets for Extract and Load nodes."""

    name: str

    async def read(
        self,
        *,
        binding: str,
        location: str | None,
        contract_type: type[Any] | None,
        context: dict[str, Any],
    ) -> Any: ...

    async def write(
        self,
        *,
        binding: str,
        location: str | None,
        data: Any,
        contract_type: type[Any] | None,
        context: dict[str, Any],
    ) -> dict[str, Any]: ...


def as_records(
    data: Any,
    contract_type: type[Any] | None,
    *,
    max_rows: int = 10_000,
) -> list[Any]:
    """Normalize data to a list of contract instances or mappings."""
    if max_rows < 0:
        raise ValueError("max_rows must be non-negative")
    if data is None:
        return []
    if isinstance(data, list):
        items = data
    elif isinstance(data, tuple):
        items = list(data)
    elif hasattr(data, "to_dicts") and callable(data.to_dicts):
        # Portable SQL/DuckDB relation frames expose a bounded record view at
        # a declared materialization boundary.  Normalize that view before
        # validating a public Data contract rather than treating the frame
        # object itself as one record.
        converted = data.to_dicts()
        items = list(islice(converted, max_rows + 1)) if isinstance(converted, Iterable) else [converted]
    elif hasattr(data, "to_dict") and callable(data.to_dict):
        try:
            converted = data.to_dict(orient="records")
            items = (
                list(islice(converted, max_rows + 1))
                if isinstance(converted, Iterable)
                and not isinstance(converted, Mapping)
                else [converted]
            )
        except TypeError:
            items = [data]
    elif isinstance(data, Mapping):
        items = [data]
    elif isinstance(data, Iterable) and not isinstance(data, (str, bytes, bytearray)):
        # Generic iterables of dictionaries are the portable records boundary.
        # Materialize exactly once so generators remain usable by inference and
        # by subsequent contract validation.
        items = list(islice(data, max_rows + 1))
    else:
        items = [data]
    if len(items) > max_rows:
        raise ValueError(f"record materialization exceeded max_rows={max_rows}")
    if contract_type is None:
        return items
    validated: list[Any] = []
    for item in items:
        if isinstance(item, contract_type):
            validated.append(item)
        elif isinstance(item, dict):
            validated.append(contract_type.model_validate(item))
        else:
            validated.append(contract_type.model_validate(item))
    return validated


def records_to_dicts(data: Any) -> list[dict[str, Any]]:
    """Convert records to plain dicts for file writers."""
    records = as_records(data, None)
    out: list[dict[str, Any]] = []
    for item in records:
        if hasattr(item, "model_dump"):
            out.append(item.model_dump(mode="json"))
        elif isinstance(item, dict):
            out.append(dict(item))
        else:
            out.append({"value": item})
    return out
