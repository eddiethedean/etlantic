"""Compatibility redirect — use ``medallantic`` instead."""

from __future__ import annotations

import warnings

from medallantic import *  # noqa: F403
from medallantic import __all__ as __all__

warnings.warn(
    "etlantic-sparkforge is deprecated; install and import medallantic instead. "
    "See packages/medallantic/docs/sparkforge-migration.md.",
    DeprecationWarning,
    stacklevel=2,
)

__version__ = "0.36.0"
