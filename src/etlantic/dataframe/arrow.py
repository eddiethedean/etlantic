# pyright: reportMissingTypeStubs=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnusedImport=false
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

    from etlantic.storage.protocol import records_to_dicts

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
    Gate A interchange boundaries must use :func:`to_arrow_table_strict`
    instead so a planned Arrow conversion cannot silently fall back.
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


def to_arrow_table_strict(value: Any) -> Any:
    """Convert a native frame to ``pyarrow.Table`` or raise.

    PyArrow is imported lazily. Missing PyArrow raises ``ImportError`` and
    unsupported values or invalid engine exports raise ``TypeError``.
    """
    import pyarrow as pa

    if isinstance(value, pa.Table):
        return value
    if value is None:
        raise TypeError("Cannot convert None to pyarrow.Table")
    if hasattr(value, "to_arrow") and callable(value.to_arrow):
        try:
            table = value.to_arrow()
        except ImportError:
            raise
        except Exception as exc:
            raise TypeError(f"{type(value)!r}.to_arrow() failed: {exc}") from exc
        if isinstance(table, pa.Table):
            return table
        raise TypeError(
            f"{type(value)!r}.to_arrow() returned {type(table)!r}, not pyarrow.Table"
        )
    if hasattr(value, "to_numpy") and hasattr(value, "columns"):
        try:
            return pa.Table.from_pandas(value, preserve_index=False)
        except ImportError:
            raise
        except Exception as exc:
            raise TypeError(
                f"Cannot convert {type(value)!r} via pandas: {exc}"
            ) from exc
    if isinstance(value, list):
        try:
            return records_to_arrow_table(value)
        except ImportError:
            raise
        except Exception as exc:
            raise TypeError(f"Cannot convert records to pyarrow.Table: {exc}") from exc
    raise TypeError(f"Cannot convert {type(value)!r} to pyarrow.Table")


def from_arrow_table(table: Any, *, engine: str) -> Any:
    """Convert an Arrow table into records (core) or raise for engine frames.

    Core keeps Arrow↔records only. Engine-native construction belongs in
    dataframe plugins (``pl.from_arrow`` / ``Table.to_pandas``). Pass
    ``engine="records"`` (or any non-plugin name) to get a pylist.
    """
    import pyarrow as pa

    if not isinstance(table, pa.Table):
        raise TypeError(f"Expected pyarrow.Table, got {type(table)!r}")
    if engine in {"polars", "pandas"}:
        raise ValueError(
            f"from_arrow_table no longer constructs {engine!r} frames in core; "
            f"use the {engine} dataframe plugin (e.g. pl.from_arrow / "
            f"table.to_pandas) instead."
        )
    return table.to_pylist()
