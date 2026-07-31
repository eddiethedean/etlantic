"""Negative typing fixture: removed root symbols are not curated.

This file is intended for a future pyright fail-suite. Specialist helpers
like ``Edge`` are owned by ``etlantic.model``, not the root facade. Root
import of demoted aliases was removed in 0.37.0.
"""

from __future__ import annotations

# pyright: reportMissingImports=false
# Prefer owning-module imports after 0.37 root alias removal.
from etlantic.model import Edge

_ = Edge
