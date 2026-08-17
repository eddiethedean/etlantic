"""In-process remote-runtime protocol (`etlantic.remote-runtime/1`)."""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from etlantic.control_plane.redaction import redact_control_plane_payload
from etlantic.control_plane.schedule_diagnostics import fed_diagnostic, res_diagnostic

REMOTE_RUNTIME_SCHEMA = "etlantic.remote-runtime/1"

PlacementReason = Literal[
    "ok",
    "missing_capability",
    "trust",
    "policy",
    "quota",
    "residency",
]


@dataclass(frozen=True, slots=True)
class RemoteCapabilities:
    version: str = "0.47.0"
    map: bool = True
    branch: bool = True
    stream: bool = True
    identity: str = "fake-remote"
    trust_domain: str = "test"


@dataclass
class FakeRemoteSession:
    session_id: str
    capabilities: RemoteCapabilities
    submitted: list[dict[str, Any]] = field(default_factory=list)
    fence: int = 1
    cursor: int = 0
    disconnected: bool = False


class FakeRemoteHost:
    """In-process fake remote execution host (no network credentials)."""

    def __init__(
        self,
        *,
        capabilities: RemoteCapabilities | None = None,
        hmac_key: bytes = b"etlantic-fake-remote",
    ) -> None:
        self.capabilities = capabilities or RemoteCapabilities()
        self.hmac_key = hmac_key
        self.sessions: dict[str, FakeRemoteSession] = {}
        self.seen_nonces: set[str] = set()

    def negotiate(self, offer: Mapping[str, Any]) -> FakeRemoteSession:
        offer_caps = dict(offer.get("capabilities") or {})
        required = ("map", "branch", "stream")
        missing = [name for name in required if offer_caps.get(name) is False]
        if missing:
            raise ValueError(
                fed_diagnostic(
                    "missing_dyn_caps",
                    "Remote host must preserve map/branch/stream or reject.",
                    path=("capabilities",),
                ).code
            )
        if (
            str(offer.get("version") or "")
            and not str(offer["version"]).startswith("0.47")
            and offer.get("version") not in {None, self.capabilities.version}
        ):
            raise ValueError(
                fed_diagnostic(
                    "version_skew",
                    "Incompatible remote-runtime version.",
                ).code
            )
        session_id = hashlib.sha256(
            json.dumps(offer, sort_keys=True).encode()
        ).hexdigest()[:16]
        session = FakeRemoteSession(
            session_id=f"rs-{session_id}",
            capabilities=self.capabilities,
        )
        self.sessions[session.session_id] = session
        return session

    def evaluate_placement(self, request: Mapping[str, Any]) -> dict[str, Any]:
        required = set(request.get("required_capabilities") or ())
        have = {"map", "branch", "stream"} if self.capabilities.map else set()
        if not required.issubset(have | {"k8s", "spark-connect", "cpu"}):
            raise ValueError(
                res_diagnostic(
                    "placement_reject",
                    "Placement rejected: missing capability.",
                    path=("placement",),
                ).code
            )
        if request.get("trust_ok") is False:
            raise ValueError(
                res_diagnostic("placement_reject", "Placement rejected: trust.").code
            )
        if request.get("policy_ok") is False:
            raise ValueError(
                res_diagnostic("placement_reject", "Placement rejected: policy.").code
            )
        if request.get("quota_ok") is False:
            raise ValueError(
                res_diagnostic("placement_reject", "Placement rejected: quota.").code
            )
        if request.get("residency_ok") is False:
            raise ValueError(
                res_diagnostic(
                    "placement_reject", "Placement rejected: residency."
                ).code
            )
        return {"decision": "accept", "transferred": False}

    def sign_plan(self, plan: Mapping[str, Any], *, nonce: str) -> dict[str, Any]:
        if nonce in self.seen_nonces:
            raise ValueError(
                fed_diagnostic("incompatible", "Replay of signed plan nonce.").code
            )
        payload = redact_control_plane_payload(dict(plan))
        if not isinstance(payload, dict):
            payload = {}
        blob = json.dumps(payload, sort_keys=True).encode()
        digest = hmac.new(self.hmac_key, blob, hashlib.sha256).hexdigest()
        self.seen_nonces.add(nonce)
        return {
            "schema": REMOTE_RUNTIME_SCHEMA,
            "nonce": nonce,
            "sha256": hashlib.sha256(blob).hexdigest(),
            "hmac": digest,
            "artifact": {"content_address": hashlib.sha256(blob).hexdigest()},
        }

    def verify_plan(self, envelope: Mapping[str, Any], plan: Mapping[str, Any]) -> None:
        payload = redact_control_plane_payload(dict(plan))
        blob = json.dumps(payload, sort_keys=True).encode()
        digest = hmac.new(self.hmac_key, blob, hashlib.sha256).hexdigest()
        if envelope.get("hmac") != digest:
            raise ValueError(
                fed_diagnostic("incompatible", "Tampered signed-plan envelope.").code
            )
        if (
            envelope.get("artifact", {}).get("content_address")
            != hashlib.sha256(blob).hexdigest()
        ):
            raise ValueError(
                fed_diagnostic("payload_leak", "Partial or mismatched artifact.").code
            )

    def submit(
        self, session_id: str, envelope: Mapping[str, Any], plan: Mapping[str, Any]
    ) -> dict[str, Any]:
        session = self.sessions[session_id]
        if session.disconnected:
            raise ValueError(
                fed_diagnostic("stale_fence", "Session disconnected.").code
            )
        self.verify_plan(envelope, plan)
        text = json.dumps(plan, sort_keys=True).lower()
        if "payload" in text or "secret" in json.dumps(plan).lower():
            raise ValueError(
                fed_diagnostic(
                    "payload_leak",
                    "Remote submit rejected payload/secret tokens.",
                ).code
            )
        record = {"envelope": dict(envelope), "plan": dict(plan)}
        session.submitted.append(record)
        return {"accepted": True, "fence": session.fence}

    def heartbeat(self, session_id: str, fence: int) -> int:
        session = self.sessions[session_id]
        if fence != session.fence:
            raise ValueError(
                fed_diagnostic("stale_fence", "Stale remote fencing token.").code
            )
        session.fence += 1
        return session.fence

    def event_cursor(self, session_id: str) -> int:
        return self.sessions[session_id].cursor

    def recover(self, session_id: str) -> FakeRemoteSession:
        session = self.sessions[session_id]
        session.disconnected = False
        return session

    def disconnect(self, session_id: str) -> None:
        self.sessions[session_id].disconnected = True
