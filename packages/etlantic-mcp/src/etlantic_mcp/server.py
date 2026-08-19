"""In-process FakeMcpServer — read-only method catalog, no MCP SDK."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from etlantic.agents.catalog import FORBIDDEN_ACTIONS
from etlantic.agents.context import assemble_context_bundle
from etlantic.agents.diagnostics import mcp_diagnostic
from etlantic.agents.mcp_trust import mcp_server_allowed
from etlantic.agents.proposal import validate_proposal
from etlantic.profile import Profile
from etlantic.runtime.logging import redact_value

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


def _is_leak_key(key: str) -> bool:
    lowered = str(key).lower()
    return any(
        token in lowered
        for token in (
            "password",
            "secret",
            "token",
            "credential",
            "payload",
            "api_key",
        )
    )


def _has_tool_expansion(value: Any) -> bool:
    if isinstance(value, Mapping):
        if value.get("grant_tools") or value.get("tools"):
            return True
        return any(_has_tool_expansion(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_tool_expansion(item) for item in value)
    return False


def _redact_arguments(value: Any) -> Any:
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if _is_leak_key(str(key)):
                out[str(key)] = "[redacted]"
                continue
            out[str(key)] = _redact_arguments(item)
        return out
    if isinstance(value, list):
        return [_redact_arguments(item) for item in value]
    if isinstance(value, str):
        return str(redact_value(value))
    return value


@dataclass
class FakeMcpServer:
    """In-memory MCP stand-in. No stdio transport or vendor SDK."""

    package: str = "etlantic-mcp"
    version: str = _PKG_VERSION
    profile: Profile | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)
    allowlist_diagnostic: dict[str, Any] | None = None

    def list_methods(self) -> tuple[str, ...]:
        return tuple(sorted(READ_ONLY_METHODS))

    def call(self, method: str, **arguments: Any) -> dict[str, Any]:
        self.calls.append({"method": method, "arguments": dict(arguments)})
        if live_configured():
            raise RuntimeError("live MCP client path is skipped in 0.48 (048-M-01)")
        if self.allowlist_diagnostic is not None:
            return {"ok": False, "diagnostic": dict(self.allowlist_diagnostic)}
        if _has_tool_expansion(arguments):
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
        safe_args = _redact_arguments(arguments)
        if method == "proposal.validate":
            raw = arguments.get("proposal") if "proposal" in arguments else arguments
            result = validate_proposal(raw if isinstance(raw, Mapping) else {})
            payload = result.to_dict()
            payload["method"] = method
            payload["read_only"] = True
            return payload
        if method == "context.bundle":
            pipeline = arguments.get("pipeline")
            if pipeline is None:
                return {
                    "ok": True,
                    "method": method,
                    "read_only": True,
                    "bundle": None,
                    "arguments": safe_args,
                }
            bundle = assemble_context_bundle(
                pipeline,
                profile=arguments.get("profile") or self.profile or "development",
            )
            payload = bundle.to_dict()
            payload["method"] = method
            payload["read_only"] = True
            return payload
        return {
            "ok": True,
            "method": method,
            "read_only": True,
            "arguments": safe_args,
        }


def create_server(profile: Profile | None = None) -> FakeMcpServer:
    """Entry point. Production profiles fail closed without an allowlist pin."""
    diagnostic = None
    if profile is not None:
        allowed, diag = mcp_server_allowed(
            profile,
            "etlantic-mcp",
            version=_PKG_VERSION,
            selected=True,
        )
        if not allowed and diag is not None:
            diagnostic = diag.to_dict()
    return FakeMcpServer(profile=profile, allowlist_diagnostic=diagnostic)
