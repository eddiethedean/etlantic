"""Resource-provider protocol (`etlantic.resource/1`)."""

from __future__ import annotations

from etlantic.resources.discovery import discover_resource_providers
from etlantic.resources.protocol import (
    RESOURCE_SCHEMA,
    ResourceHandle,
    ResourceProvider,
    ResourceProviderInfo,
    ResourceRequest,
)

__all__ = [
    "RESOURCE_SCHEMA",
    "ResourceHandle",
    "ResourceProvider",
    "ResourceProviderInfo",
    "ResourceRequest",
    "discover_resource_providers",
]
