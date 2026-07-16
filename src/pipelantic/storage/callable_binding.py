"""Callable-backed storage binding."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from pipelantic.exceptions import PipelineExecutionError
from pipelantic.runtime.invoke import maybe_await
from pipelantic.storage.protocol import as_records

Reader = Callable[..., Any] | Callable[..., Awaitable[Any]]
Writer = Callable[..., Any] | Callable[..., Awaitable[Any]]


class CallableStorage:
    """User-registered Python readers/writers keyed by binding name."""

    name = "callable"

    def __init__(self) -> None:
        self._readers: dict[str, Reader] = {}
        self._writers: dict[str, Writer] = {}

    def register_reader(self, binding: str, reader: Reader) -> None:
        self._readers[binding] = reader

    def register_writer(self, binding: str, writer: Writer) -> None:
        self._writers[binding] = writer

    async def read(
        self,
        *,
        binding: str,
        location: str | None,
        contract_type: type[Any] | None,
        context: dict[str, Any],
    ) -> Any:
        reader = self._readers.get(binding)
        if reader is None:
            raise PipelineExecutionError(
                f"No callable reader registered for binding {binding!r}",
                code="PMEXEC410",
            )
        raw = await maybe_await(reader, location=location, context=context)
        return as_records(raw, contract_type)

    async def write(
        self,
        *,
        binding: str,
        location: str | None,
        data: Any,
        contract_type: type[Any] | None,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        writer = self._writers.get(binding)
        if writer is None:
            raise PipelineExecutionError(
                f"No callable writer registered for binding {binding!r}",
                code="PMEXEC411",
            )
        records = as_records(data, contract_type)
        result = await maybe_await(writer, records, location=location, context=context)
        if isinstance(result, dict):
            return result
        return {"binding": binding, "records": len(records)}
