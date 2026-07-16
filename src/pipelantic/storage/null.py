"""Null / no-write storage binding."""

from __future__ import annotations

from typing import Any

from pipelantic.storage.protocol import as_records


class NullStorage:
    """Read empty datasets; discard writes (VALIDATE / no-write intents)."""

    name = "null"

    async def read(
        self,
        *,
        binding: str,
        location: str | None,
        contract_type: type[Any] | None,
        context: dict[str, Any],
    ) -> Any:
        return as_records([], contract_type)

    async def write(
        self,
        *,
        binding: str,
        location: str | None,
        data: Any,
        contract_type: type[Any] | None,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        records = as_records(data, contract_type)
        return {
            "binding": binding,
            "location": location,
            "records": len(records),
            "written": False,
        }
