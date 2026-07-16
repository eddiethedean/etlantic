"""Optional Arrow interchange helpers (PyArrow imported only when available)."""

from __future__ import annotations

from typing import Any


def arrow_available() -> bool:
    """Return True when ``pyarrow`` can be imported."""
    try:
        import pyarrow  # noqa: F401
    except ImportError:
        return False
    return True


def records_to_arrow_table(
    records: list[Any],
    *,
    contract_type: type[Any] | None = None,
) -> Any:
    """Build a ``pyarrow.Table`` from Python records.

    Raises ``ImportError`` when PyArrow is not installed.
    """
    import pyarrow as pa

    from pipelantic.storage.protocol import records_to_dicts

    rows = records_to_dicts(records)
    if not rows:
        if contract_type is not None and hasattr(contract_type, "model_fields"):
            names = list(contract_type.model_fields)
            return pa.table({name: [] for name in names})
        return pa.table({})
    return pa.Table.from_pylist(rows)


def to_arrow_table(value: Any) -> Any | None:
    """Best-effort conversion of a native frame to ``pyarrow.Table``.

    Returns ``None`` when the value cannot be converted without engine plugins.
    """
    if value is None:
        return None
    if not arrow_available():
        return None
    import pyarrow as pa

    if isinstance(value, pa.Table):
        return value
    # Duck-typed Polars
    if hasattr(value, "to_arrow") and callable(value.to_arrow):
        try:
            table = value.to_arrow()
            if isinstance(table, pa.Table):
                return table
        except Exception:
            return None
    # Duck-typed Pandas
    if hasattr(value, "to_numpy") and hasattr(value, "columns"):
        try:
            return pa.Table.from_pandas(value, preserve_index=False)
        except Exception:
            return None
    if isinstance(value, list):
        try:
            return records_to_arrow_table(value)
        except Exception:
            return None
    return None


def from_arrow_table(table: Any, *, engine: str) -> Any:
    """Convert an Arrow table into an engine-native frame.

    Core only provides the Arrow→records path and delegates engine construction
    to plugins when they call this helper after importing their own libraries.
    """
    import pyarrow as pa

    if not isinstance(table, pa.Table):
        raise TypeError(f"Expected pyarrow.Table, got {type(table)!r}")
    if engine == "polars":
        import polars as pl

        return pl.from_arrow(table)
    if engine == "pandas":
        return table.to_pandas(types_mapper=None)
    # Generic: return pylist for local/record engines
    return table.to_pylist()
