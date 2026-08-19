"""Experimental read-only MCP server for ETLantic (fake by default)."""

from __future__ import annotations

__version__ = "0.48.0"

from etlantic_mcp.server import FakeMcpServer, create_server, live_configured

__all__ = [
    "FakeMcpServer",
    "__version__",
    "create_server",
    "live_configured",
]
