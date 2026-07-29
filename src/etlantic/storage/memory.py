"""Process-scoped in-memory storage binding."""

from __future__ import annotations

from typing import Any

from etlantic.storage.protocol import as_records


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
        mode = str((context or {}).get("write_mode") or "overwrite").lower()
        if mode in {"merge", "upsert"}:
            from etlantic.exceptions import PipelineExecutionError

            raise PipelineExecutionError(
                f"Memory binding {binding!r} does not support write_mode={mode!r}; "
                "failing closed.",
                code="PMEXEC456",
            )
        existing = self._store.get(key)
        if mode in {"skip_if_exists", "skip"} and existing:
            return {
                "binding": binding,
                "location": key,
                "records": len(existing),
                "skipped": True,
            }
        if mode == "append" and existing:
            self._store[key] = list(existing) + list(records)
        else:
            self._store[key] = list(records)
        return {
            "binding": binding,
            "location": key,
            "records": len(self._store[key]),
            "skipped": False,
        }

    def seed(self, binding: str, data: Any, *, location: str | None = None) -> None:
        """Seed data for tests and callable pipelines."""
        self._store[self._key(binding, location)] = list(
            as_records(data, None) if not isinstance(data, list) else data
        )

    def get(self, binding: str, *, location: str | None = None) -> list[Any]:
        return list(self._store.get(self._key(binding, location), []))
