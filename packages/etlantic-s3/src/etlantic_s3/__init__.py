"""Experimental S3-compatible connector package for ETLantic."""

from __future__ import annotations

from etlantic_s3.connectors import (
    PACKAGE_VERSION as __version__,
)
from etlantic_s3.connectors import (
    S3SinkConnector,
    S3SourceConnector,
    S3StorageConnector,
    create_sink,
    create_source,
    create_storage,
)
from etlantic_s3.fake import InMemoryS3Fake, boto3_available

__all__ = [
    "InMemoryS3Fake",
    "S3SinkConnector",
    "S3SourceConnector",
    "S3StorageConnector",
    "__version__",
    "boto3_available",
    "create_sink",
    "create_source",
    "create_storage",
]
