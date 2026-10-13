"""Compatibility redirect — use ``medallantic`` instead."""

from __future__ import annotations

import warnings

from medallantic import *  # noqa: F403
from medallantic import __all__ as __all__

warnings.warn(
    "etlantic-sparkforge is deprecated; install and import medallantic instead. "
    "The final compatibility release is ETLantic 0.62.0; routine releases stop "
    "in 0.63.0. See packages/medallantic/docs/sparkforge-migration.md.",
    FutureWarning,
    stacklevel=2,
)

__version__ = "0.59.0"
