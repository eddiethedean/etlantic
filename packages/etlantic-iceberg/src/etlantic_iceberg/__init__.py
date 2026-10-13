"""Experimental Iceberg connector package for ETLantic."""

from __future__ import annotations

from etlantic_iceberg.connectors import (
    PACKAGE_VERSION as __version__,
)
from etlantic_iceberg.connectors import (
    IcebergSinkConnector,
    IcebergSourceConnector,
    IcebergStorageConnector,
    create_sink,
    create_source,
    create_storage,
)
from etlantic_iceberg.fake import FakeIcebergCatalog, pyiceberg_available

__all__ = [
    "FakeIcebergCatalog",
    "IcebergSinkConnector",
    "IcebergSourceConnector",
    "IcebergStorageConnector",
    "__version__",
    "create_sink",
    "create_source",
    "create_storage",
    "pyiceberg_available",
]
