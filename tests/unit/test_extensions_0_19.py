"""Extension metadata budget helpers (0.19)."""

from __future__ import annotations

import warnings

import pytest

from etlantic.extensions import (
    MAX_METADATA_BYTES,
    MAX_METADATA_DEPTH,
    validate_extension_metadata,
)


def test_metadata_within_budget_ok() -> None:
    validate_extension_metadata({"etlantic.note": "ok"})


def test_builtin_runtime_report_metadata_keys_are_valid() -> None:
    validate_extension_metadata(
        {"dataframe": {}, "sql": {}, "spark": {}, "spark_schema": {}}
    )


def test_metadata_size_budget_rejected() -> None:
    # Payload must exceed MAX_METADATA_BYTES after JSON encoding.
    oversized = {"etlantic.blob": "x" * (MAX_METADATA_BYTES + 1)}
    with pytest.raises(ValueError, match="size budget"):
        validate_extension_metadata(oversized)


def test_metadata_depth_budget_rejected() -> None:
    nested: dict = {"leaf": 1}
    for _ in range(MAX_METADATA_DEPTH):
        nested = {"etlantic.wrap": nested}
    with pytest.raises(ValueError, match="nesting depth"):
        validate_extension_metadata(nested)


def test_bare_keys_warn_when_not_strict() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        validate_extension_metadata({"bare": 1}, strict=False)
    assert any(issubclass(w.category, UserWarning) for w in caught)


def test_bare_keys_rejected_when_strict() -> None:
    with pytest.raises(ValueError, match="extension namespaces"):
        validate_extension_metadata({"bare": 1}, strict=True)


def test_non_json_serializable_rejected() -> None:
    with pytest.raises(ValueError, match="JSON-serializable"):
        validate_extension_metadata({"etlantic.x": object()})
