"""Stable pipeline used for Extract/Load DPCS golden fixtures."""

from __future__ import annotations

from pydantic import Field

from etlantic import Data, Extract, Input, Load, Output, Pipeline, Transformation


class CustomerRow(Data):
    id: int
    name: str = Field(min_length=1)


class NormalizeCustomerRow(Transformation):
    rows: Input[CustomerRow]
    result: Output[CustomerRow]


class ExtractLoadGoldenPipeline(Pipeline):
    __published_id__ = "extract-load-golden"
    __published_version__ = "0.15.0"

    raw: Extract[CustomerRow] = Extract(asset="raw_customers")
    normalized = NormalizeCustomerRow.step(rows=raw)
    out: Load[CustomerRow] = Load(input=normalized.result, asset="curated_customers")
