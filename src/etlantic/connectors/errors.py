"""Connector error hierarchy."""

from __future__ import annotations

from typing import Any

from etlantic.exceptions import ETLanticError


class ConnectorError(ETLanticError):
    """Base class for connector failures."""

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        provider: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.provider = provider
        self.details = dict(details or {})


class ConnectorConfigError(ConnectorError):
    """Invalid or unsupported connector configuration."""


class ConnectorCapabilityError(ConnectorError):
    """Required capability is missing or unsupported."""


class ConnectorPlanError(ConnectorError):
    """Static planning failed without live I/O."""


class ConnectorReadError(ConnectorError):
    """Source listing or read failed."""


class ConnectorWriteError(ConnectorError):
    """Sink staging, prepare, commit, or abort failed."""


class ConnectorCheckpointError(ConnectorError):
    """Landing checkpoint load, lease, or advance failed."""


class ConnectorCompatibilityError(ConnectorError):
    """Compatibility adapter or record mismatch."""


__all__ = [
    "ConnectorCapabilityError",
    "ConnectorCheckpointError",
    "ConnectorCompatibilityError",
    "ConnectorConfigError",
    "ConnectorError",
    "ConnectorPlanError",
    "ConnectorReadError",
    "ConnectorWriteError",
]
