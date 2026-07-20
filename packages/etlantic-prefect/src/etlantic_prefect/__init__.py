"""etlantic-prefect — Prefect ExecutionScheduler for ETLantic 0.16."""

from __future__ import annotations

from etlantic_prefect.plugin import PrefectScheduler, create_plugin

__version__ = "0.21.0"

__all__ = [
    "PrefectScheduler",
    "__version__",
    "create_plugin",
]
