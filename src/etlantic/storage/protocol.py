# pyright: reportUnknownArgumentType=false, reportUnknownVariableType=false
"""Minimal storage binding protocol for local runtime I/O."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from itertools import islice
from typing import Any, Protocol, runtime_checkable

DEFAULT_MATERIALIZATION_ROWS = 10_000
_KNOWN_BOUNDED_PROVIDER_MODULES = frozenset(
    {"datafusion", "duckdb", "_duckdb", "pandas", "polars", "pyarrow"}
)


class _BoundedViewError(ValueError):
    """Internal validation failure for an unproven provider view."""


def _bounded_length(value: Any) -> int | None:
    try:
        return len(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _has_bounded_provider_contract(value: Any) -> bool:
    if bool(getattr(value, "__etlantic_bounded_view__", False)):
        return True
    module = type(value).__module__.split(".", 1)[0].casefold()
    return module in _KNOWN_BOUNDED_PROVIDER_MODULES


def _require_materialization_limit(max_rows: int | None) -> int:
    if max_rows is None:
        raise ValueError(
            "record materialization requires a finite max_rows bound; "
            "unbounded provider conversion is not supported"
        )
    if isinstance(max_rows, bool):
        raise ValueError("max_rows must be an integer")
    if max_rows < 0:
        raise ValueError("max_rows must be non-negative")
    return max_rows


def _bounded_view(data: Any, max_rows: int | None) -> Any:
    """Require an explicit bounded view before eager provider conversion."""
    if max_rows is None:
        raise _BoundedViewError(
            "provider conversion requires a finite max_rows bound; refusing "
            "unbounded materialization"
        )
    head = getattr(data, "head", None)
    if not callable(head):
        raise _BoundedViewError("provider conversion requires a bounded head view")
    try:
        bounded = head(max_rows + 1)
    except Exception:
        raise _BoundedViewError("provider bounded head view failed") from None
    if bounded is data:
        raise _BoundedViewError("provider head returned the unbounded source")
    row_count = _bounded_length(bounded)
    if row_count is not None and row_count > max_rows + 1:
        raise _BoundedViewError(
            "provider head returned more than the bounded row view"
        )
    if row_count is None and not _has_bounded_provider_contract(bounded):
        raise _BoundedViewError("provider head did not prove a bounded view")
    return bounded


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
    max_rows: int | None = DEFAULT_MATERIALIZATION_ROWS,
) -> list[Any]:
    """Normalize data to a bounded list of contract instances or mappings.

    ``max_rows`` is an inference and runtime safety boundary.  Passing
    ``None`` is intentionally rejected because provider and iterable
    conversion would otherwise require eagerly materializing an unbounded
    source.  Providers must return a bounded ``head`` view, or mark that view
    with ``__etlantic_bounded_view__ = True``.
    """
    max_rows = _require_materialization_limit(max_rows)
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
        try:
            converted = _bounded_view(data, max_rows).to_dicts()
            if isinstance(converted, Mapping):
                items = [converted]
            elif isinstance(converted, Iterable):
                items = list(islice(converted, max_rows + 1))
            else:
                items = [converted]
        except _BoundedViewError:
            raise
        except Exception:
            raise ValueError(
                "provider conversion failed; refusing to retain provider object"
            ) from None
    elif hasattr(data, "to_dict") and callable(data.to_dict):
        try:
            converted = _bounded_view(data, max_rows).to_dict(orient="records")
            if isinstance(converted, Mapping):
                items = [converted]
            elif isinstance(converted, Iterable):
                items = list(islice(converted, max_rows + 1))
            else:
                items = [converted]
        except _BoundedViewError:
            raise
        except Exception:
            raise ValueError(
                "provider conversion failed; refusing to retain provider object"
            ) from None
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


def records_to_dicts(
    data: Any, *, max_rows: int | None = DEFAULT_MATERIALIZATION_ROWS
) -> list[dict[str, Any]]:
    """Convert records to plain dicts for file writers."""
    records = as_records(data, None, max_rows=max_rows)
    out: list[dict[str, Any]] = []
    for item in records:
        if hasattr(item, "model_dump"):
            out.append(item.model_dump(mode="json"))
        elif isinstance(item, dict):
            out.append(dict(item))
        else:
            raise ValueError(
                "record conversion requires mappings or model instances; refusing provider object"
            )
    return out
