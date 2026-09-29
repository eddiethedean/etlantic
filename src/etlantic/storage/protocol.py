# pyright: reportUnknownArgumentType=false, reportUnknownVariableType=false
"""Minimal storage binding protocol for local runtime I/O."""

from __future__ import annotations

import inspect
import math
import sys
import time
from collections.abc import Iterable, Mapping
from itertools import islice
from typing import Any, Protocol, cast, runtime_checkable

DEFAULT_MATERIALIZATION_ROWS = 10_000
DEFAULT_MATERIALIZATION_BYTES = 64 * 1024 * 1024
DEFAULT_MATERIALIZATION_TIMEOUT_SECONDS = 30.0
_MAX_ESTIMATED_ITEMS_PER_ROW = 10_000
_MAX_ESTIMATED_DEPTH = 8
_KNOWN_BOUNDED_PROVIDER_MODULES = frozenset(
    {"datafusion", "duckdb", "_duckdb", "pandas", "polars", "pyarrow"}
)


class _BoundedViewError(ValueError):
    """Internal validation failure for an unproven provider view."""


class _MaterializationLimitError(ValueError):
    """Materialized records exceeded a configured resource limit."""


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
    if type(max_rows) is not int:
        raise ValueError("max_rows must be an integer")
    if max_rows < 0:
        raise ValueError("max_rows must be non-negative")
    return max_rows


def _require_materialization_budget(
    max_bytes: int | None, timeout_seconds: float | None
) -> None:
    if max_bytes is not None and (type(max_bytes) is not int or max_bytes < 1):
        raise ValueError("max_bytes must be a positive integer when provided")
    if timeout_seconds is not None and (
        type(timeout_seconds) not in (int, float) or timeout_seconds <= 0
    ):
        raise ValueError("timeout_seconds must be positive and finite when provided")
    if timeout_seconds is not None:
        try:
            finite_timeout = math.isfinite(timeout_seconds)
        except (OverflowError, TypeError):
            finite_timeout = False
        if not finite_timeout:
            raise ValueError(
                "timeout_seconds must be positive and finite when provided"
            )


def _check_deadline(deadline: float | None) -> None:
    if deadline is not None and time.monotonic() >= deadline:
        raise _MaterializationLimitError(
            "record materialization exceeded timeout_seconds"
        )


def _estimate_record_size(
    value: Any, *, max_bytes: int | None, deadline: float | None
) -> int:
    """Estimate decoded row size with early byte, depth, item, and time bounds."""
    total = 0
    items_seen = 0
    active: set[int] = set()

    def add(size: int) -> None:
        nonlocal total
        _check_deadline(deadline)
        if max_bytes is not None and size > max_bytes - total:
            raise _MaterializationLimitError(
                "record materialization exceeded max_bytes"
            )
        total += size

    def visit(item: Any, depth: int) -> None:
        nonlocal items_seen
        _check_deadline(deadline)
        items_seen += 1
        if items_seen > _MAX_ESTIMATED_ITEMS_PER_ROW:
            raise _MaterializationLimitError(
                "record materialization exceeded the per-row item limit"
            )
        if item is None or isinstance(item, (bool, int, float, complex)):
            add(sys.getsizeof(item))
            return
        if isinstance(item, str):
            add(
                max(
                    sys.getsizeof(item),
                    len(item) if item.isascii() else len(item) * 4,
                )
            )
            return
        if isinstance(item, (bytes, bytearray, memoryview)):
            byte_length = item.nbytes if isinstance(item, memoryview) else len(item)
            add(max(sys.getsizeof(item), byte_length))
            return
        if depth >= _MAX_ESTIMATED_DEPTH:
            raise _MaterializationLimitError(
                "record materialization exceeded the per-row nesting limit"
            )

        identity = id(item)
        if identity in active:
            add(sys.getsizeof(item))
            return
        active.add(identity)
        try:
            if isinstance(item, Mapping):
                add(sys.getsizeof(item))
                try:
                    entries = iter(item.items())
                    for key, nested in islice(
                        entries, _MAX_ESTIMATED_ITEMS_PER_ROW + 1
                    ):
                        _check_deadline(deadline)
                        visit(key, depth + 1)
                        visit(nested, depth + 1)
                except _MaterializationLimitError:
                    raise
                except Exception:
                    raise _MaterializationLimitError(
                        "record materialization could not inspect a mapping safely"
                    ) from None
                if items_seen > _MAX_ESTIMATED_ITEMS_PER_ROW:
                    raise _MaterializationLimitError(
                        "record materialization exceeded the per-row item limit"
                    )
                return
            if isinstance(item, (list, tuple, set, frozenset)):
                add(sys.getsizeof(item))
                try:
                    children = iter(item)
                    for nested in islice(children, _MAX_ESTIMATED_ITEMS_PER_ROW + 1):
                        visit(nested, depth + 1)
                except _MaterializationLimitError:
                    raise
                except Exception:
                    raise _MaterializationLimitError(
                        "record materialization could not inspect a collection safely"
                    ) from None
                if items_seen > _MAX_ESTIMATED_ITEMS_PER_ROW:
                    raise _MaterializationLimitError(
                        "record materialization exceeded the per-row item limit"
                    )
                return
            try:
                attributes = vars(item)
            except (TypeError, AttributeError):
                attributes = None
            add(sys.getsizeof(item))
            if isinstance(attributes, Mapping):
                visit(attributes, depth + 1)
        finally:
            active.remove(identity)

    visit(value, 0)
    return total


def _bounded_records(
    rows: Iterable[Any],
    *,
    max_rows: int,
    max_bytes: int | None,
    deadline: float | None,
) -> list[Any]:
    output: list[Any] = []
    bytes_observed = 0
    try:
        iterator = iter(rows)
        for item in islice(iterator, max_rows + 1):
            _check_deadline(deadline)
            if len(output) >= max_rows:
                raise _MaterializationLimitError(
                    f"record materialization exceeded max_rows={max_rows}"
                )
            item_bytes = _estimate_record_size(
                item,
                max_bytes=(
                    max_bytes - bytes_observed if max_bytes is not None else None
                ),
                deadline=deadline,
            )
            bytes_observed += item_bytes
            output.append(item)
    except (_MaterializationLimitError, _BoundedViewError):
        raise
    except Exception:
        raise ValueError(
            "record materialization failed; refusing provider object"
        ) from None
    return output


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
        raise _BoundedViewError("provider head returned more than the bounded row view")
    if row_count is None and not _has_bounded_provider_contract(bounded):
        raise _BoundedViewError("provider head did not prove a bounded view")
    return bounded


def _provider_size_estimate(value: Any) -> int | None:
    """Read a provider's declared materialized size without converting rows."""
    for attribute in ("estimated_size", "nbytes", "byte_size", "memory_usage"):
        try:
            estimate = getattr(value, attribute, None)
            if callable(estimate):
                estimate = (
                    estimate(index=True) if attribute == "memory_usage" else estimate()
                )
            if attribute == "memory_usage":
                sum_method = getattr(estimate, "sum", None)
                if callable(sum_method):
                    estimate = sum_method()
            item_method = getattr(estimate, "item", None)
            if callable(item_method):
                estimate = item_method()
            if (
                isinstance(estimate, (int, float))
                and not isinstance(estimate, bool)
                and math.isfinite(estimate)
            ):
                return max(0, int(estimate))
        except Exception:
            continue
    return None


def _provider_column_names(
    columns: Any, *, max_bytes: int | None, deadline: float | None
) -> tuple[str, ...]:
    """Validate labels under the same byte, item, and time bounds as rows."""
    try:
        iterator = iter(columns)
    except Exception:
        raise _BoundedViewError("provider column names are malformed") from None
    max_fields = (_MAX_ESTIMATED_ITEMS_PER_ROW - 1) // 2
    names: list[str] = []
    seen: set[str] = set()
    # A materialized output mapping includes its container, every key, and a
    # value slot per provider column. Reject an impossible row before asking
    # pandas or another adapter to construct a full tuple.
    estimated_bytes = sys.getsizeof({})
    if max_bytes is not None and estimated_bytes > max_bytes:
        raise _BoundedViewError("provider column names exceed max_bytes")
    try:
        for name in iterator:
            _check_deadline(deadline)
            if len(names) >= max_fields:
                raise _BoundedViewError(
                    "provider column count exceeds the per-row item limit"
                )
            if type(name) is not str or not name:
                raise _BoundedViewError(
                    "provider column names must be non-empty strings"
                )
            if name in seen:
                raise _BoundedViewError("provider column names must be unique")
            estimated_bytes += sys.getsizeof(name) + sys.getsizeof(None)
            if max_bytes is not None and estimated_bytes > max_bytes:
                raise _BoundedViewError("provider column names exceed max_bytes")
            names.append(name)
            seen.add(name)
    except (_BoundedViewError, _MaterializationLimitError):
        raise
    except Exception:
        raise _BoundedViewError("provider column names are malformed") from None
    return tuple(names)


def _provider_rows(
    bounded: Any,
    *,
    max_bytes: int | None,
    deadline: float | None,
) -> Iterable[Any]:
    """Return a row iterator, refusing eager converters without a size proof."""
    _check_deadline(deadline)
    if isinstance(bounded, Mapping):
        return (bounded,)

    iter_rows = getattr(bounded, "iter_rows", None)
    if callable(iter_rows):
        columns = getattr(bounded, "columns", None)
        column_names: tuple[str, ...] | None = None
        if columns is not None:
            column_names = _provider_column_names(
                columns, max_bytes=max_bytes, deadline=deadline
            )
        try:
            rows = iter_rows(named=True)
            return (rows,) if isinstance(rows, Mapping) else cast(Iterable[Any], rows)
        except TypeError:
            try:
                row_iterator = iter_rows()
            except Exception:
                raise ValueError(
                    "provider conversion failed; refusing to retain provider object"
                ) from None
            if isinstance(row_iterator, Mapping):
                return (row_iterator,)
            if column_names is not None:
                return (
                    dict(zip(column_names, row, strict=True))
                    if not isinstance(row, Mapping)
                    else row
                    for row in cast(Iterable[Any], row_iterator)
                )
            return cast(Iterable[Any], row_iterator)
        except Exception:
            raise ValueError(
                "provider conversion failed; refusing to retain provider object"
            ) from None

    module = type(bounded).__module__.split(".", 1)[0].casefold()
    if module == "pandas" and callable(getattr(bounded, "itertuples", None)):
        columns = _provider_column_names(
            bounded.columns, max_bytes=max_bytes, deadline=deadline
        )
        return (
            dict(zip(columns, row, strict=True))
            for row in bounded.itertuples(index=False, name=None)
        )
    if module == "pyarrow" and callable(getattr(bounded, "slice", None)):
        row_count = _bounded_length(bounded)
        if row_count is not None:

            def arrow_rows() -> Iterable[Any]:
                for index in range(row_count):
                    _check_deadline(deadline)
                    values = bounded.slice(index, 1).to_pylist()
                    if len(values) != 1:
                        raise _BoundedViewError(
                            "provider row conversion did not return one bounded row"
                        )
                    yield values[0]

            return arrow_rows()
    if module == "datafusion" and callable(getattr(bounded, "execute_stream", None)):

        def datafusion_rows() -> Iterable[Any]:
            for batch in bounded.execute_stream():
                _check_deadline(deadline)
                to_pyarrow = getattr(batch, "to_pyarrow", None)
                if not callable(to_pyarrow):
                    raise _BoundedViewError("provider batch conversion is unsupported")
                arrow_batch = cast(Any, to_pyarrow())
                row_count = _bounded_length(arrow_batch)
                slice_rows = cast(Any, getattr(arrow_batch, "slice", None))
                if row_count is None or not callable(slice_rows):
                    raise _BoundedViewError("provider batch conversion is unbounded")
                for index in range(row_count):
                    _check_deadline(deadline)
                    row_batch = slice_rows(index, 1)
                    to_pylist = cast(Any, getattr(row_batch, "to_pylist", None))
                    if not callable(to_pylist):
                        raise _BoundedViewError(
                            "provider row conversion is unsupported"
                        )
                    values = cast(Any, to_pylist())
                    if not isinstance(values, list) or len(values) != 1:
                        raise _BoundedViewError(
                            "provider row conversion did not return one bounded row"
                        )
                    yield values[0]

        return datafusion_rows()
    columns = getattr(bounded, "columns", None)
    fetchmany = cast(Any, getattr(bounded, "fetchmany", None))
    if callable(fetchmany) and columns is not None:
        names = _provider_column_names(columns, max_bytes=max_bytes, deadline=deadline)

        def fetched_rows() -> Iterable[Any]:
            while True:
                _check_deadline(deadline)
                batch = cast(Any, fetchmany(1))
                if not batch:
                    break
                if len(batch) != 1:
                    raise _BoundedViewError("provider ignored the bounded fetch size")
                row = batch[0]
                yield (
                    row
                    if isinstance(row, Mapping)
                    else dict(zip(names, row, strict=True))
                )

        return fetched_rows()
    if (
        getattr(bounded, "__etlantic_bounded_view__", False)
        or _bounded_length(bounded) is not None
    ):
        try:
            return iter(bounded)
        except TypeError:
            pass

    converter_name = (
        "to_dicts"
        if callable(getattr(bounded, "to_dicts", None))
        else "to_dict"
        if callable(getattr(bounded, "to_dict", None))
        else None
    )
    if converter_name is None:
        raise _BoundedViewError("provider bounded view has no row iterator")
    converter = getattr(bounded, converter_name)
    size_estimate = _provider_size_estimate(bounded)
    if (
        max_bytes is not None
        and size_estimate is None
        and not inspect.isgeneratorfunction(converter)
    ):
        raise _BoundedViewError(
            "provider conversion failed: byte size could not be proven before eager conversion"
        )
    if (
        max_bytes is not None
        and size_estimate is not None
        and size_estimate > max_bytes
    ):
        raise _MaterializationLimitError("record materialization exceeded max_bytes")
    _check_deadline(deadline)
    try:
        converted = (
            converter(orient="records") if converter_name == "to_dict" else converter()
        )
    except Exception:
        raise ValueError(
            "provider conversion failed; refusing to retain provider object"
        ) from None
    if isinstance(converted, Mapping):
        return (converted,)
    if isinstance(converted, Iterable) and not isinstance(
        converted, (str, bytes, bytearray)
    ):
        return converted
    return (converted,)


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
    max_bytes: int | None = DEFAULT_MATERIALIZATION_BYTES,
    timeout_seconds: float | None = DEFAULT_MATERIALIZATION_TIMEOUT_SECONDS,
) -> list[Any]:
    """Normalize data to a bounded list of contract instances or mappings.

    ``max_rows``, ``max_bytes``, and ``timeout_seconds`` bound inference and
    runtime materialization. Passing ``None`` for ``max_rows`` is rejected
    because provider and iterable conversion would otherwise eagerly consume
    an unbounded source. Passing ``None`` for ``max_bytes`` or
    ``timeout_seconds`` explicitly disables that bound. Providers must return
    a bounded ``head`` view, or mark that view with
    ``__etlantic_bounded_view__ = True``. Timeouts are checked cooperatively
    between provider calls and row conversions; synchronous provider calls
    cannot be interrupted.
    """
    max_rows = _require_materialization_limit(max_rows)
    _require_materialization_budget(max_bytes, timeout_seconds)
    deadline = (
        time.monotonic() + timeout_seconds if timeout_seconds is not None else None
    )
    if data is None:
        return []
    if isinstance(data, Mapping):
        rows: Iterable[Any] = (data,)
    elif isinstance(data, (list, tuple)):
        rows = data
    elif callable(getattr(data, "head", None)):
        _check_deadline(deadline)
        bounded = _bounded_view(data, max_rows)
        _check_deadline(deadline)
        estimate = _provider_size_estimate(bounded)
        _check_deadline(deadline)
        if max_bytes is not None and estimate is not None and estimate > max_bytes:
            raise _MaterializationLimitError(
                "record materialization exceeded max_bytes"
            )
        try:
            rows = _provider_rows(
                bounded,
                max_bytes=max_bytes,
                deadline=deadline,
            )
        except (_MaterializationLimitError, _BoundedViewError):
            raise
        except Exception:
            raise ValueError(
                "provider conversion failed; refusing to retain provider object"
            ) from None
    elif callable(getattr(data, "to_dicts", None)) or callable(
        getattr(data, "to_dict", None)
    ):
        raise _BoundedViewError(
            "provider conversion requires a bounded head view; refusing unbounded source"
        )
    elif isinstance(data, Iterable) and not isinstance(data, (str, bytes, bytearray)):
        rows = data
    else:
        rows = (data,)
    items = _bounded_records(
        rows,
        max_rows=max_rows,
        max_bytes=max_bytes,
        deadline=deadline,
    )
    if contract_type is None:
        return items
    validated: list[Any] = []
    for item in items:
        _check_deadline(deadline)
        if isinstance(item, contract_type):
            validated.append(item)
        elif isinstance(item, dict):
            validated.append(contract_type.model_validate(item))
        else:
            validated.append(contract_type.model_validate(item))
        _check_deadline(deadline)
    return validated


def records_to_dicts(
    data: Any,
    *,
    max_rows: int | None = DEFAULT_MATERIALIZATION_ROWS,
    max_bytes: int | None = DEFAULT_MATERIALIZATION_BYTES,
    timeout_seconds: float | None = DEFAULT_MATERIALIZATION_TIMEOUT_SECONDS,
) -> list[dict[str, Any]]:
    """Convert records to plain dicts for file writers."""
    _require_materialization_limit(max_rows)
    _require_materialization_budget(max_bytes, timeout_seconds)
    deadline = (
        time.monotonic() + timeout_seconds if timeout_seconds is not None else None
    )
    records = as_records(
        data,
        None,
        max_rows=max_rows,
        max_bytes=max_bytes,
        timeout_seconds=timeout_seconds,
    )
    out: list[dict[str, Any]] = []
    bytes_observed = 0
    for item in records:
        _check_deadline(deadline)
        if hasattr(item, "model_dump"):
            inferred_model = (
                getattr(type(item), "__etlantic_inferred_schema_model__", False) is True
            )
            row = item.model_dump(
                mode="json", by_alias=True, exclude_unset=inferred_model
            )
        elif isinstance(item, dict):
            row = dict(item)
        else:
            raise ValueError(
                "record conversion requires mappings or model instances; refusing provider object"
            )
        row_bytes = _estimate_record_size(
            row,
            max_bytes=(max_bytes - bytes_observed if max_bytes is not None else None),
            deadline=deadline,
        )
        bytes_observed += row_bytes
        out.append(row)
    return out
