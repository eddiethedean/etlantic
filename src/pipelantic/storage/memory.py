"""Process-scoped in-memory storage binding."""

from __future__ import annotations

from typing import Any

from pipelantic.storage.protocol import as_records


class MemoryStorage:
    """Named in-process datasets keyed by binding or location."""

    name = "memory"

    def __init__(self) -> None:
        self._store: dict[str, list[Any]] = {}

    def _key(self, binding: str, location: str | None) -> str:
        return location or binding

    async def read(
        self,
        *,
        binding: str,
        location: str | None,
        contract_type: type[Any] | None,
        context: dict[str, Any],
    ) -> Any:
        key = self._key(binding, location)
        data = self._store.get(key, [])
        return as_records(data, contract_type)

    async def write(
        self,
        *,
        binding: str,
        location: str | None,
        data: Any,
        contract_type: type[Any] | None,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        key = self._key(binding, location)
        records = as_records(data, contract_type)
        self._store[key] = list(records)
        return {"binding": binding, "location": key, "records": len(records)}

    def seed(self, binding: str, data: Any, *, location: str | None = None) -> None:
        """Seed data for tests and callable pipelines."""
        self._store[self._key(binding, location)] = list(
            as_records(data, None) if not isinstance(data, list) else data
        )

    def get(self, binding: str, *, location: str | None = None) -> list[Any]:
        return list(self._store.get(self._key(binding, location), []))
