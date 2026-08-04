"""Experimental Iceberg connector package for ETLantic."""

from __future__ import annotations

__version__ = "0.43.0"

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
