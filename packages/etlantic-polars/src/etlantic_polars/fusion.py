"""Native schema and query proof checks; raw explain text never leaves process."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from typing import Any

import polars as pl

from etlantic.transform.fusion import FusionDescriptor


def validate_fusion_schema(frame: pl.LazyFrame, contract: Mapping[str, Any]) -> None:
    """Check every required raw column before filtering can hide a bad value."""
    schema = frame.collect_schema()
    types = {"int64": pl.Int64, "boolean": pl.Boolean}
    if any(
        name not in schema or schema[name] != types[dtype]
        for name, dtype in contract["fields"].items()
    ):
        raise ValueError("Fused schema contract mismatch")


def inspect_fusion_query(
    query: pl.LazyFrame, descriptor: FusionDescriptor
) -> dict[str, Any]:
    """Inspect actual optimized native scan, retaining only sanitized facts."""
    text = query.explain(optimized=True)
    # Bound in-process provider text too, before retaining or parsing it.
    if len(text.encode()) > 4 * 1024 * 1024:
        raise ValueError("Native fusion explanation exceeds bounds")
    first, second = descriptor.members
    predicate = first.definition["actions"][0]["kind"]["parameters"]["predicate"]
    column = predicate["left"]["target"]
    fields = second.definition["actions"][0]["kind"]["parameters"]["fields"]
    needed = len(set(fields) | {column})
    # Explain renders identifiers verbatim. Remove the exact predicate token
    # before parsing layout so embedded newlines cannot invent operators.
    layout = text.replace(f'col("{column}")', 'col("__etlantic_predicate__")')
    projection = re.search(
        r"^\s*PROJECT\s+(\d+)/(\d+)\s+COLUMNS\s*$", layout, re.MULTILINE
    )
    # A standalone FILTER above the scan is not scan predicate pushdown.
    scan = re.search(r"^\s*Parquet SCAN\s+\[", layout, re.MULTILINE)
    raw_scan = re.search(r"^\s*Parquet SCAN\s+\[", text, re.MULTILINE)
    scan_text = text[raw_scan.end() :] if raw_scan else ""
    scalar = descriptor.parameters[predicate["right"]["target"]]
    # Check identity against raw text, not the masked layout: another real
    # column could have the same name as a normalization placeholder.
    native_column = r'col\("' + re.escape(column) + r'"\)'
    native_scalar = re.escape(str(scalar))
    selection = re.search(
        r"^\s*SELECTION:[ \t]*(?:"
        # Polars 1.42 and earlier layout.
        + r"\[\("
        + native_column
        + r"\)\s*==\s*\("
        + native_scalar
        + r"\)\]"
        # Polars 1.44 layout (the dependency permits both).
        + r"|"
        + native_column
        + r"[ \t]*==[ \t]*"
        + native_scalar
        + r")[ \t]*$",
        scan_text,
        re.MULTILINE,
    )
    return {
        "schema": "etlantic.native_fusion_proof/1",
        "scan_predicate": bool(
            scan
            and scan_text
            and selection
            and not re.search(r"^\s*FILTER(?:\s|$)", layout, re.MULTILINE)
        ),
        "scan_projection": bool(
            projection and int(projection[1]) == needed and int(projection[2]) > needed
        ),
        "query_digest": "sha256:" + hashlib.sha256(text.encode()).hexdigest(),
        "main_collections": 0,
    }
