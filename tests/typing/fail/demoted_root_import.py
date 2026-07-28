"""Negative typing fixture: demoted root symbols should not be treated as curated.

This file is intended for a future pyright fail-suite. It documents that
specialist helpers like ``Edge`` are owned by ``etlantic.model``, not the root
facade. Until CI enforces ``tests/typing/fail``, keep this as a documentation
anchor only.
"""

from __future__ import annotations

# pyright: reportMissingImports=false
# Intentionally incorrect for a fail fixture: prefer etl.model.Edge / from etlantic.model import Edge
from etlantic import Edge  # type: ignore[attr-defined]

_ = Edge
