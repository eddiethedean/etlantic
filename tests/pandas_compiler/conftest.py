# pyright: reportMissingTypeStubs=false, reportUnusedImport=false
"""Skip Pandas compiler suite when pandas/numpy are not fully installed."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def _pandas_ready() -> bool:
    """True only for a real pandas install (not an empty namespace leftover)."""
    spec = importlib.util.find_spec("pandas")
    if spec is None or spec.origin is None:
        return False
    try:
        import numpy  # noqa: F401
        import pandas as pd
    except ImportError:
        return False
    return bool(getattr(pd, "__version__", None))


def pytest_ignore_collect(collection_path: Path, config: pytest.Config) -> bool:
    if collection_path.suffix != ".py" or not collection_path.name.startswith("test_"):
        return False
    return not _pandas_ready()
