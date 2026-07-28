"""Quality-gate Transformation factory with accepted/rejected ports."""

from __future__ import annotations

from typing import Any

from etlantic.ports import Input, Output
from etlantic.quality.evaluate import split_by_quality
from etlantic.quality.model import QualityExpression, QualityRuleset
from etlantic.quality.serialize import quality_fingerprint, quality_to_dict
from etlantic.transformation import Transformation

QUALITY_METADATA_KEY = "etlantic.quality"


def make_quality_gate(
    contract_type: type[Any],
    ruleset: QualityRuleset,
    *,
    name: str = "QualityGate",
    expression_id: str | None = None,
) -> type[Transformation]:
    """Build a Transformation class that splits rows by a quality ruleset.

    The class exposes ``result`` (accepted) and ``rejected`` (invalid role)
    outputs and stores a fingerprinted ``etlantic.quality/1`` expression on
    ``__quality_expression__`` for planning.
    """
    expr = QualityExpression(
        expression_id=expression_id or name,
        ruleset=ruleset,
    )
    fp = quality_fingerprint(expr)
    expr = QualityExpression(
        schema=expr.schema,
        expression_id=expr.expression_id,
        ruleset=expr.ruleset,
        fingerprint=fp,
        metadata=dict(expr.metadata),
    )
    expr_dict = quality_to_dict(expr)

    rows_marker = Input(contract_type)
    result_marker = Output(contract_type)
    rejected_marker = Output(contract_type).as_invalid()

    namespace: dict[str, Any] = {
        "__annotations__": {
            "rows": rows_marker,
            "result": result_marker,
            "rejected": rejected_marker,
        },
        "rows": rows_marker,
        "result": result_marker,
        "rejected": rejected_marker,
        "__quality_expression__": expr_dict,
        "__quality_ruleset__": ruleset,
        "__module__": __name__,
        "__doc__": f"Quality gate {name} over {getattr(contract_type, '__name__', contract_type)}.",
    }
    gate_cls = type(name, (Transformation,), namespace)

    @gate_cls.implementation("local")
    def _local(rows):  # type: ignore[no-untyped-def]
        records = list(rows) if not isinstance(rows, list) else rows
        valid, invalid, _diags = split_by_quality(records, ruleset)
        return {"result": valid, "rejected": invalid}

    @gate_cls.implementation("polars")
    def _polars(rows):  # type: ignore[no-untyped-def]
        return _split_frame_like(rows, ruleset, engine="polars")

    @gate_cls.implementation("pandas")
    def _pandas(rows):  # type: ignore[no-untyped-def]
        return _split_frame_like(rows, ruleset, engine="pandas")

    return gate_cls


def _split_frame_like(
    rows: Any, ruleset: QualityRuleset, *, engine: str
) -> dict[str, Any]:
    """Split a dataframe-like object using the portable evaluator."""
    if engine == "polars":
        import polars as pl

        if isinstance(rows, pl.DataFrame):
            records = rows.to_dicts()
            valid, invalid, _ = split_by_quality(records, ruleset)
            empty = rows.clear()
            return {
                "result": pl.DataFrame(valid) if valid else empty,
                "rejected": pl.DataFrame(invalid) if invalid else empty,
            }
        if hasattr(rows, "collect"):
            frame = rows.collect()
            return _split_frame_like(frame, ruleset, engine="polars")
    if engine == "pandas":
        import pandas as pd

        if isinstance(rows, pd.DataFrame):
            records = rows.to_dict(orient="records")
            valid, invalid, _ = split_by_quality(records, ruleset)
            empty = rows.iloc[0:0].copy()
            return {
                "result": pd.DataFrame(valid) if valid else empty,
                "rejected": pd.DataFrame(invalid) if invalid else empty,
            }
    records = list(rows) if not isinstance(rows, list) else rows
    valid, invalid, _ = split_by_quality(records, ruleset)
    return {"result": valid, "rejected": invalid}


def quality_expression_from_transform(
    transform: type[Transformation] | Any,
) -> dict[str, Any] | None:
    """Return the embedded quality expression dict, if any."""
    raw = getattr(transform, "__quality_expression__", None)
    if isinstance(raw, dict):
        return dict(raw)
    return None
