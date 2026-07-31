"""Connector maturity labels (ADR-015 / 038-M)."""

from __future__ import annotations

from enum import StrEnum


class ConnectorMaturity(StrEnum):
    """Promotion ladder for connector packages."""

    EXPERIMENTAL = "experimental"
    PREVIEW = "preview"
    SUPPORTED = "supported"
    DEPRECATED = "deprecated"


__all__ = ["ConnectorMaturity"]
