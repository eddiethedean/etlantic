"""Minimal storage binding protocol for local runtime I/O."""

from __future__ import annotations

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


def as_records(data: Any, contract_type: type[Any] | None) -> list[Any]:
    """Normalize data to a list of contract instances or mappings."""
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
        items = list(data.to_dicts())
    elif hasattr(data, "to_dict") and callable(data.to_dict):
        try:
            items = list(data.to_dict(orient="records"))
        except TypeError:
            items = [data]
    else:
        items = [data]
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
