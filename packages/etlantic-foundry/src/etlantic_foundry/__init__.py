"""Palantir Foundry dataset connector package for ETLantic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .connectors import (
        FoundrySinkConnector as FoundrySinkConnector,
    )
    from .connectors import (
        FoundrySourceConnector as FoundrySourceConnector,
    )
    from .connectors import (
        FoundryStorageConnector as FoundryStorageConnector,
    )
    from .connectors import (
        create_sink as create_sink,
    )
    from .connectors import (
        create_source as create_source,
    )
    from .connectors import (
        create_storage as create_storage,
    )

__version__ = "0.55.0"


def __getattr__(name: str) -> Any:
    if name in {
        "FoundrySinkConnector",
        "FoundrySourceConnector",
        "FoundryStorageConnector",
        "create_sink",
        "create_source",
        "create_storage",
    }:
        from etlantic_foundry import connectors

        return getattr(connectors, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "FoundrySinkConnector",
    "FoundrySourceConnector",
    "FoundryStorageConnector",
    "__version__",
    "create_sink",
    "create_source",
    "create_storage",
]
