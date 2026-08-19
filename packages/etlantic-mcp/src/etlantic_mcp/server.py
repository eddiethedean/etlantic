"""In-process FakeMcpServer — read-only method catalog, no MCP SDK."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from etlantic.agents.catalog import FORBIDDEN_ACTIONS
from etlantic.agents.diagnostics import mcp_diagnostic

_PKG_VERSION = "0.48.0"

READ_ONLY_METHODS = frozenset(
    {
        "inspect",
        "validate",
        "plan",
        "docs",
        "report.query",
        "context.bundle",
        "proposal.validate",
    }
)


def live_configured() -> bool:
    """True when a live MCP client is opted in (never required in CI)."""
    return bool(str(os.environ.get("ETLANTIC_MCP_LIVE") or "").strip())


@dataclass
class FakeMcpServer:
    """In-memory MCP stand-in. No stdio transport or vendor SDK."""

    package: str = "etlantic-mcp"
    version: str = _PKG_VERSION
    calls: list[dict[str, Any]] = field(default_factory=list)

    def list_methods(self) -> tuple[str, ...]:
        return tuple(sorted(READ_ONLY_METHODS))

    def call(self, method: str, **arguments: Any) -> dict[str, Any]:
        self.calls.append({"method": method, "arguments": dict(arguments)})
        if live_configured():
            raise RuntimeError("live MCP client path is skipped in 0.48 (048-M-01)")
        extra_tools = arguments.get("grant_tools") or arguments.get("tools")
        if extra_tools:
            diag = mcp_diagnostic(
                "tool_expansion",
                "MCP tools cannot grant additional tools.",
                path=("mcp", "tools"),
            )
            return {"ok": False, "diagnostic": diag.to_dict()}
        if method in FORBIDDEN_ACTIONS or method not in READ_ONLY_METHODS:
            key = "secret_denied" if "secret" in method else "method_denied"
            if "network" in method:
                key = "network_denied"
            diag = mcp_diagnostic(
                key,
                f"MCP method {method!r} is not a read-only inspection tool.",
                path=("mcp", "method", method),
            )
            return {"ok": False, "diagnostic": diag.to_dict()}
        return {
            "ok": True,
            "method": method,
            "read_only": True,
            "arguments": {k: v for k, v in arguments.items() if k != "secret"},
        }


def create_server() -> FakeMcpServer:
    return FakeMcpServer()
