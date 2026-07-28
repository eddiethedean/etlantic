"""Resolve Medallantic transform_ref callables into ETLantic Transformations."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any

from etlantic.transformation import Input, Output, Transformation


def resolve_transform_callable(transform_ref: str) -> Callable[..., Any]:
    """Import ``module:attr`` or ``module.attr`` and return the callable."""
    ref = transform_ref.strip()
    if not ref:
        raise ValueError("transform_ref must be a non-empty import path")
    if ":" in ref:
        module_name, attr = ref.split(":", 1)
    else:
        parts = ref.rsplit(".", 1)
        if len(parts) != 2:
            raise ValueError(
                f"transform_ref {transform_ref!r} must be 'module:attr' "
                "or 'module.attr'"
            )
        module_name, attr = parts
    module = importlib.import_module(module_name)
    target = module
    for part in attr.split("."):
        target = getattr(target, part)
    if not callable(target):
        raise TypeError(
            f"transform_ref {transform_ref!r} did not resolve to a callable"
        )
    return target


def _safe_ident(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in name)
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"S_{cleaned}"
    return cleaned


def make_callable_transformation(
    name: str,
    *,
    transform_ref: str,
    fn: Callable[..., Any] | None = None,
    row_type: type[Any],
) -> type[Transformation]:
    """Build a Transformation that executes ``transform_ref`` on local records."""
    callable_fn = fn or resolve_transform_callable(transform_ref)
    safe = _safe_ident(name)
    ns: dict[str, Any] = {
        "__annotations__": {
            "rows": Input[row_type],
            "result": Output[row_type],
        },
        "__module__": "medallantic.callables",
        "__doc__": f"Medallion callable transform {name} ({transform_ref}).",
        "__transform_ref__": transform_ref,
    }
    transform_cls = type(f"{safe}Transform", (Transformation,), ns)

    @transform_cls.implementation("local")
    def _local(rows: list[Any]) -> list[Any]:
        result = callable_fn(rows)
        if result is None:
            return list(rows)
        if isinstance(result, list):
            return result
        return list(result)

    @transform_cls.implementation("pyspark")
    def _pyspark(rows: Any) -> Any:
        if isinstance(rows, list):
            return _local(rows)
        return rows

    try:
        import polars as pl

        @transform_cls.implementation("polars")
        def _polars(rows: Any) -> Any:

            if isinstance(rows, pl.DataFrame):
                out = callable_fn(rows)
                if isinstance(out, pl.DataFrame):
                    return out
                return pl.DataFrame(list(out) if out is not None else rows.to_dicts())
            records = rows.to_dicts() if hasattr(rows, "to_dicts") else list(rows)
            out = callable_fn(records)
            return pl.DataFrame(out if out is not None else records)

    except ImportError:
        pass

    try:
        import pandas as pd

        @transform_cls.implementation("pandas")
        def _pandas(rows: Any) -> Any:

            if isinstance(rows, pd.DataFrame):
                out = callable_fn(rows)
                if isinstance(out, pd.DataFrame):
                    return out
                return pd.DataFrame(
                    list(out) if out is not None else rows.to_dict("records")
                )
            records = (
                rows.to_dict("records") if hasattr(rows, "to_dict") else list(rows)
            )
            out = callable_fn(records)
            return pd.DataFrame(out if out is not None else records)

    except ImportError:
        pass

    return transform_cls
