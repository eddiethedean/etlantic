"""Tests for asset descriptor parsing."""

from __future__ import annotations

from etlantic.bindings import (
    normalize_assets_map,
    parse_asset_descriptor,
)


def test_parse_uri_descriptor() -> None:
    parsed = parse_asset_descriptor("json://data/sample.json")
    assert parsed.provider == "json"
    assert parsed.location == "data/sample.json"


def test_parse_object_descriptor() -> None:
    parsed = parse_asset_descriptor({"provider": "csv", "location": "data/out.csv"})
    assert parsed.provider == "csv"
    assert parsed.location == "data/out.csv"


def test_normalize_assets_map() -> None:
    normalized = normalize_assets_map(
        {
            "rows": "json://data/rows.json",
            "out": {"provider": "json", "location": "data/out.json"},
        }
    )
    assert normalized["rows"] == "json://data/rows.json"
    assert normalized["out"] == "json://data/out.json"
