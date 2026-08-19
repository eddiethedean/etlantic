"""Untrusted proposal schema, sandbox, and 0.42 approval handoff."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from etlantic.agents.catalog import (
    ALLOWED_PROPOSAL_ACTIONS,
    FORBIDDEN_ACTIONS,
    action_is_forbidden,
)
from etlantic.agents.diagnostics import prop_diagnostic
from etlantic.authoring.lifecycle import validate_pipeline_like
from etlantic.authoring.preview import plan_preview
from etlantic.control_plane.approval_models import ApprovalRequest
from etlantic.control_plane.approval_protocols import ApprovalStore
from etlantic.control_plane.models import ControlPlaneContext
from etlantic.diagnostics import Diagnostic, ValidationReport

PROPOSAL_SCHEMA = "etlantic.proposal/1"


def canonical_fingerprint(payload: Mapping[str, Any]) -> str:
    blob = json.dumps(dict(payload), sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


@dataclass
class Proposal:
    """Ordinary reviewable files/plans. Untrusted until sandbox + approval."""

    schema: str = PROPOSAL_SCHEMA
    task_id: str = "scaffold_model"
    kind: str = "files"
    files: list[dict[str, str]] = field(default_factory=list)
    plan_fingerprint: str | None = None
    policy_fingerprint: str | None = None
    optimization_candidate: dict[str, Any] | None = None
    requested_actions: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "task_id": self.task_id,
            "kind": self.kind,
            "files": list(self.files),
            "plan_fingerprint": self.plan_fingerprint,
            "policy_fingerprint": self.policy_fingerprint,
            "optimization_candidate": self.optimization_candidate,
            "requested_actions": list(self.requested_actions),
            "fingerprint": self.fingerprint,
        }

    @property
    def fingerprint(self) -> str:
        return canonical_fingerprint(
            {
                "task_id": self.task_id,
                "kind": self.kind,
                "files": self.files,
                "plan_fingerprint": self.plan_fingerprint,
                "policy_fingerprint": self.policy_fingerprint,
                "requested_actions": list(self.requested_actions),
                "optimization_candidate": self.optimization_candidate,
            }
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Proposal:
        files_raw = payload.get("files") or []
        files: list[dict[str, str]] = []
        if isinstance(files_raw, list):
            for item in files_raw:
                if isinstance(item, Mapping) and item.get("path"):
                    files.append(
                        {
                            "path": str(item["path"]),
                            "content": str(item.get("content") or ""),
                        }
                    )
        actions = tuple(
            str(a) for a in (payload.get("requested_actions") or ()) if str(a)
        )
        candidate = payload.get("optimization_candidate")
        return cls(
            schema=str(payload.get("schema") or PROPOSAL_SCHEMA),
            task_id=str(payload.get("task_id") or "scaffold_model"),
            kind=str(payload.get("kind") or "files"),
            files=files,
            plan_fingerprint=(
                str(payload["plan_fingerprint"])
                if payload.get("plan_fingerprint")
                else None
            ),
            policy_fingerprint=(
                str(payload["policy_fingerprint"])
                if payload.get("policy_fingerprint")
                else None
            ),
            optimization_candidate=(
                dict(candidate) if isinstance(candidate, Mapping) else None
            ),
            requested_actions=actions,
        )


@dataclass
class ProposalValidation:
    ok: bool
    proposal: Proposal
    diagnostics: list[Diagnostic]
    required_hook: str = "pre_promote"
    approval_fingerprints: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "etlantic.proposal.validation/1",
            "ok": self.ok,
            "proposal": self.proposal.to_dict(),
            "diagnostics": [d.to_dict() for d in self.diagnostics],
            "required_hook": self.required_hook,
            "approval_fingerprints": dict(self.approval_fingerprints),
            "applied": False,
        }


def _scan_for_execution(text: str, diagnostics: list[Diagnostic]) -> None:
    lowered = text.lower()
    if any(
        token in lowered
        for token in ("pipeline.run", "etlantic run", "secret.resolve", "os.system")
    ):
        diagnostics.append(
            prop_diagnostic(
                "execution_denied",
                "Proposal requested execution, secrets, or host commands.",
            )
        )


def validate_proposal(
    proposal: Proposal | Mapping[str, Any],
    *,
    pipeline: Any | None = None,
    profile: str | Any | None = "development",
) -> ProposalValidation:
    """Deterministic no-network/no-secret sandbox. Never applies files."""
    raw = proposal if isinstance(proposal, Mapping) else None
    parsed = (
        proposal if isinstance(proposal, Proposal) else Proposal.from_dict(proposal)
    )
    diagnostics: list[Diagnostic] = []
    if parsed.schema != PROPOSAL_SCHEMA:
        diagnostics.append(
            prop_diagnostic(
                "invalid",
                f"Proposal schema must be {PROPOSAL_SCHEMA}.",
                path=("schema",),
            )
        )
    if raw is not None:
        for item in raw.get("files") or ():
            if not isinstance(item, Mapping):
                continue
            extra = set(item) - {"path", "content"}
            if extra:
                diagnostics.append(
                    prop_diagnostic(
                        "invalid",
                        "Proposal files must send full content; patches and unknown "
                        "file fields are rejected.",
                        path=("files", str(item.get("path") or "")),
                    )
                )
    for action in parsed.requested_actions:
        if (
            action_is_forbidden(action)
            or action in FORBIDDEN_ACTIONS
            or action not in ALLOWED_PROPOSAL_ACTIONS
        ):
            diagnostics.append(
                prop_diagnostic(
                    "untrusted",
                    f"Proposal requested forbidden action {action!r}.",
                    path=("requested_actions", action),
                )
            )
    for item in parsed.files:
        _scan_for_execution(item.get("content") or "", diagnostics)
        if _contains_injection(item.get("content") or ""):
            diagnostics.append(
                prop_diagnostic(
                    "untrusted",
                    "Untrusted proposal text attempted to grant tools.",
                    path=("files", item.get("path") or ""),
                )
            )

    if pipeline is not None:
        report: ValidationReport = validate_pipeline_like(pipeline, profile=profile)
        diagnostics.extend(list(report.diagnostics))
        try:
            from etlantic.authoring.definition import PipelineDefinition
            from etlantic.authoring.normalize import definition_from_pipeline
            from etlantic.authoring.types import is_pipeline_class

            defn = None
            if isinstance(pipeline, PipelineDefinition):
                defn = pipeline
            elif is_pipeline_class(pipeline):
                defn = definition_from_pipeline(pipeline)
            if defn is not None:
                planned, plan_report = plan_preview(defn, profile=profile)
                diagnostics.extend(list(plan_report.diagnostics))
                if planned is not None and parsed.plan_fingerprint is None:
                    parsed.plan_fingerprint = planned.fingerprint
        except Exception as exc:
            diagnostics.append(
                prop_diagnostic(
                    "sandbox",
                    f"Sandbox plan preview failed: {exc}",
                    severity="warning",
                )
            )

    if parsed.optimization_candidate is not None:
        diagnostics.append(
            prop_diagnostic(
                "impact",
                "Optimization candidate is advisory until a current human approval.",
                severity="info",
                path=("optimization_candidate",),
            )
        )

    plan_fp = parsed.plan_fingerprint or parsed.fingerprint
    policy_fp = parsed.policy_fingerprint or parsed.fingerprint
    ok = not any(d.severity.value == "error" for d in diagnostics)
    return ProposalValidation(
        ok=ok,
        proposal=parsed,
        diagnostics=diagnostics,
        required_hook="pre_promote",
        approval_fingerprints={
            "plan_fingerprint": plan_fp,
            "policy_fingerprint": policy_fp,
            "proposal_fingerprint": parsed.fingerprint,
        },
    )


def _contains_injection(text: str) -> bool:
    lowered = text.lower()
    return any(
        needle in lowered
        for needle in (
            "ignore previous instructions",
            "grant additional tools",
            "install plugins",
            "submit a run",
        )
    )


def request_proposal_approval(
    store: ApprovalStore,
    ctx: ControlPlaneContext,
    validation: ProposalValidation,
    *,
    hook: str | None = None,
    revision_id: str | None = None,
) -> ApprovalRequest:
    """Create a 0.42 approval covering the validated proposal fingerprints."""
    if not validation.ok:
        raise ValueError("Refusing approval handoff for an invalid proposal")
    fps = validation.approval_fingerprints
    return store.create(
        ctx,
        hook=hook or validation.required_hook,
        plan_fingerprint=fps["plan_fingerprint"],
        policy_fingerprint=fps["policy_fingerprint"],
        revision_id=revision_id,
    )
