# pyright: reportUnknownVariableType=false
"""Outbound network / webhook / remote-reference policy (0.20)."""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from etlantic.diagnostics import Diagnostic, Severity
from etlantic.exceptions import ETLanticError
from etlantic.runtime.events import SecurityEvent

# Common cloud metadata endpoints and unsafe defaults.
_BLOCKED_HOSTS = frozenset(
    {
        "metadata.google.internal",
        "metadata",
        "169.254.169.254",
    }
)


class OutboundDeniedError(ETLanticError):
    """Raised when an outbound target is rejected by policy."""

    def __init__(
        self,
        message: str,
        *,
        diagnostics: list[Diagnostic] | None = None,
        event: SecurityEvent | None = None,
    ) -> None:
        super().__init__(message)
        self.diagnostics = diagnostics or []
        self.event = event


@dataclass(frozen=True, slots=True)
class OutboundPolicy:
    """Default-deny outbound destination controls."""

    allowed_schemes: tuple[str, ...] = ("https",)
    allowed_hosts: tuple[str, ...] = ()
    allow_private: bool = False
    allow_loopback: bool = False
    allow_link_local: bool = False
    allow_redirects: bool = False
    timeout_seconds: float = 10.0
    max_response_bytes: int = 1_048_576
    forward_ambient_credentials: bool = False
    default_deny: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed_schemes": list(self.allowed_schemes),
            "allowed_hosts": list(self.allowed_hosts),
            "allow_private": self.allow_private,
            "allow_loopback": self.allow_loopback,
            "allow_link_local": self.allow_link_local,
            "allow_redirects": self.allow_redirects,
            "timeout_seconds": self.timeout_seconds,
            "max_response_bytes": self.max_response_bytes,
            "forward_ambient_credentials": self.forward_ambient_credentials,
            "default_deny": self.default_deny,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> OutboundPolicy:
        data = dict(data or {})
        return cls(
            allowed_schemes=tuple(
                str(s) for s in (data.get("allowed_schemes") or ("https",))
            ),
            allowed_hosts=tuple(str(h) for h in (data.get("allowed_hosts") or ())),
            allow_private=bool(data.get("allow_private", False)),
            allow_loopback=bool(data.get("allow_loopback", False)),
            allow_link_local=bool(data.get("allow_link_local", False)),
            allow_redirects=bool(data.get("allow_redirects", False)),
            timeout_seconds=float(data.get("timeout_seconds") or 10.0),
            max_response_bytes=int(data.get("max_response_bytes") or 1_048_576),
            forward_ambient_credentials=bool(
                data.get("forward_ambient_credentials", False)
            ),
            default_deny=bool(data.get("default_deny", True)),
        )

    @classmethod
    def deny_all(cls) -> OutboundPolicy:
        return cls(allowed_hosts=(), default_deny=True)

    @classmethod
    def development(cls, *hosts: str) -> OutboundPolicy:
        return cls(
            allowed_schemes=("https", "http"),
            allowed_hosts=tuple(hosts),
            allow_loopback=True,
            default_deny=True,
        )


@dataclass
class OutboundDecision:
    """Result of evaluating an outbound URL."""

    allowed: bool
    url: str
    reason: str
    host: str | None = None
    scheme: str | None = None
    resolved_addresses: tuple[str, ...] = ()
    diagnostics: list[Diagnostic] = field(default_factory=list)
    event: SecurityEvent | None = None


def _is_blocked_address(
    address: str,
    policy: OutboundPolicy,
) -> str | None:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return None
    if ip.is_loopback and not policy.allow_loopback:
        return "loopback address blocked"
    if ip.is_link_local and not policy.allow_link_local:
        return "link-local address blocked"
    if ip.is_private and not policy.allow_private:
        return "private address blocked"
    if ip.is_reserved or ip.is_multicast or ip.is_unspecified:
        return "non-global address blocked"
    # AWS/GCP/Azure metadata link-local classic.
    if str(ip) == "169.254.169.254":
        return "metadata-service address blocked"
    return None


def evaluate_outbound_url(
    url: str,
    policy: OutboundPolicy,
    *,
    run_id: str = "outbound",
    resolve_dns: bool = True,
) -> OutboundDecision:
    """Evaluate whether ``url`` is permitted by ``policy`` (default deny)."""
    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    host = (parsed.hostname or "").lower()

    def _deny(reason: str) -> OutboundDecision:
        diag = Diagnostic(
            code="PMSEC050",
            severity=Severity.ERROR,
            message=f"Outbound target denied: {reason} ({url!r})",
            phase="outbound",
            path=("outbound", host or url),
        )
        event = SecurityEvent(
            kind="outbound_denied",
            run_id=run_id,
            provider="network",
            outcome="denied",
            message=reason,
            subject=url,
            metadata={"scheme": scheme, "host": host},
        )
        return OutboundDecision(
            allowed=False,
            url=url,
            reason=reason,
            host=host or None,
            scheme=scheme or None,
            diagnostics=[diag],
            event=event,
        )

    if policy.forward_ambient_credentials:
        return _deny("ambient credential forwarding is prohibited")

    if not scheme or scheme not in {s.lower() for s in policy.allowed_schemes}:
        return _deny(f"scheme {scheme!r} not allowed")

    if not host:
        return _deny("missing host")

    if host in _BLOCKED_HOSTS:
        return _deny("metadata-service host blocked")

    if policy.default_deny and host not in {h.lower() for h in policy.allowed_hosts}:
        return _deny("host not in allowlist")

    resolved: list[str] = []
    if resolve_dns:
        try:
            infos = socket.getaddrinfo(
                host, parsed.port or None, type=socket.SOCK_STREAM
            )
            for info in infos:
                addr = info[4][0]
                resolved.append(str(addr))
                blocked = _is_blocked_address(str(addr), policy)
                if blocked:
                    return _deny(blocked)
        except socket.gaierror:
            return _deny("DNS resolution failed")
    else:
        # Literal IP in host
        blocked = _is_blocked_address(host, policy)
        if blocked:
            return _deny(blocked)

    event = SecurityEvent(
        kind="outbound_allowed",
        run_id=run_id,
        provider="network",
        outcome="allowed",
        message="Outbound target permitted",
        subject=url,
        metadata={
            "scheme": scheme,
            "host": host,
            "timeout_seconds": policy.timeout_seconds,
            "max_response_bytes": policy.max_response_bytes,
            "allow_redirects": policy.allow_redirects,
        },
    )
    return OutboundDecision(
        allowed=True,
        url=url,
        reason="allowed",
        host=host,
        scheme=scheme,
        resolved_addresses=tuple(resolved),
        event=event,
    )


def assert_outbound_allowed(
    url: str,
    policy: OutboundPolicy,
    *,
    run_id: str = "outbound",
) -> OutboundDecision:
    """Raise :class:`OutboundDeniedError` when the URL is rejected."""
    decision = evaluate_outbound_url(url, policy, run_id=run_id)
    if not decision.allowed:
        raise OutboundDeniedError(
            decision.reason,
            diagnostics=decision.diagnostics,
            event=decision.event,
        )
    return decision


def assert_response_within_bounds(
    size: int,
    policy: OutboundPolicy,
    *,
    url: str = "",
    run_id: str = "outbound",
) -> None:
    """Reject oversized outbound responses."""
    if size > policy.max_response_bytes:
        raise OutboundDeniedError(
            f"response exceeds max_response_bytes ({size} > {policy.max_response_bytes})",
            diagnostics=[
                Diagnostic(
                    code="PMSEC051",
                    severity=Severity.ERROR,
                    message="Outbound response oversized.",
                    phase="outbound",
                    path=("outbound", url or "response"),
                )
            ],
            event=SecurityEvent(
                kind="outbound_denied",
                run_id=run_id,
                provider="network",
                outcome="denied",
                message="oversized response",
                subject=url,
                metadata={"size": size, "max": policy.max_response_bytes},
            ),
        )
