"""In-memory governed erasure coordinator (CP4)."""

from __future__ import annotations

import hashlib
import threading
import uuid
from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass, field, replace

from etlantic.control_plane.erasure_models import (
    ErasureAction,
    ErasurePlan,
    ErasurePlanStep,
    ErasureReport,
    ErasureRequest,
    ErasureStepResult,
)
from etlantic.control_plane.erasure_protocols import ErasureProvider
from etlantic.control_plane.errors import ControlPlaneError
from etlantic.control_plane.models import ControlPlaneContext


def _scope(ctx: ControlPlaneContext) -> tuple[str, str]:
    return ctx.tenant.tenant_id, ctx.workspace.workspace_id


@dataclass
class MemoryErasureProvider:
    provider_id: str
    supported: set[str] = field(
        default_factory=lambda: {"delete", "anonymize", "lookup", "proof", "retry"}
    )
    fail_actions: set[str] = field(default_factory=set)

    def supports(self, action: ErasureAction) -> bool:
        return action in self.supported

    def execute(
        self,
        ctx: ControlPlaneContext,
        *,
        action: ErasureAction,
        subject_key_fingerprint: str,
        field_paths: Sequence[str],
    ) -> ErasureStepResult:
        if action not in self.supported:
            return ErasureStepResult(
                step_id=str(uuid.uuid4()),
                provider_id=self.provider_id,
                status="unsupported",
                reason=f"provider does not support {action}",
            )
        if action in self.fail_actions:
            return ErasureStepResult(
                step_id=str(uuid.uuid4()),
                provider_id=self.provider_id,
                status="failed",
                reason="injected failure",
            )
        proof = hashlib.sha256(
            f"{self.provider_id}:{action}:{subject_key_fingerprint}:{','.join(field_paths)}".encode()
        ).hexdigest()
        return ErasureStepResult(
            step_id=str(uuid.uuid4()),
            provider_id=self.provider_id,
            status="completed",
            proof_fingerprint=proof,
        )


class MemoryErasureStore:
    def __init__(self) -> None:
        self._requests: dict[tuple[str, str, str], ErasureRequest] = {}
        self._plans: dict[tuple[str, str, str], ErasurePlan] = {}
        self._plan_by_request: dict[tuple[str, str, str], str] = {}
        self._reports: dict[tuple[str, str, str], ErasureReport] = {}
        self._idempotency: dict[tuple[str, str, str], str] = {}
        self._lock = threading.RLock()

    def create_request(
        self,
        ctx: ControlPlaneContext,
        *,
        subject_key_fingerprint: str,
        field_paths: Sequence[str],
        legal_hold: bool = False,
        request_id: str | None = None,
    ) -> ErasureRequest:
        rid = request_id or str(uuid.uuid4())
        # Idempotency on subject fingerprint + fields.
        idem = (
            *_scope(ctx),
            f"{subject_key_fingerprint}:{','.join(sorted(field_paths))}",
        )
        with self._lock:
            prior = self._idempotency.get(idem)
            if prior is not None:
                return deepcopy(self._requests[(*_scope(ctx), prior)])
            status = "blocked" if legal_hold else "pending"
            req = ErasureRequest(
                request_id=rid,
                tenant_id=ctx.tenant.tenant_id,
                workspace_id=ctx.workspace.workspace_id,
                subject_key_fingerprint=subject_key_fingerprint,
                field_paths=tuple(field_paths),
                legal_hold=legal_hold,
                status=status,  # type: ignore[arg-type]
            )
            self._requests[(*_scope(ctx), rid)] = req
            self._idempotency[idem] = rid
            return deepcopy(req)

    def get_request(
        self, ctx: ControlPlaneContext, *, request_id: str
    ) -> ErasureRequest:
        with self._lock:
            req = self._requests.get((*_scope(ctx), request_id))
            if req is None:
                raise ControlPlaneError.not_found("erasure request not found")
            return deepcopy(req)

    def plan(
        self,
        ctx: ControlPlaneContext,
        *,
        request_id: str,
        providers: Sequence[ErasureProvider],
        actions: Sequence[ErasureAction] | None = None,
    ) -> ErasurePlan:
        with self._lock:
            req = self.get_request(ctx, request_id=request_id)
            if req.legal_hold or req.status == "blocked":
                raise ControlPlaneError.forbidden(
                    "erasure blocked by legal hold",
                    extensions={"request_id": request_id},
                )
            wanted: Sequence[ErasureAction] = actions or ("delete", "anonymize")
            steps: list[ErasurePlanStep] = []
            for provider in providers:
                for action in wanted:
                    supported = provider.supports(action)
                    steps.append(
                        ErasurePlanStep(
                            step_id=str(uuid.uuid4()),
                            provider_id=provider.provider_id,
                            action=action,
                            field_paths=req.field_paths,
                            supported=supported,
                            reason=None if supported else "unsupported",
                        )
                    )
            plan = ErasurePlan(
                plan_id=str(uuid.uuid4()),
                request_id=request_id,
                steps=tuple(steps),
            )
            self._plans[(*_scope(ctx), plan.plan_id)] = plan
            self._plan_by_request[(*_scope(ctx), request_id)] = plan.plan_id
            self._requests[(*_scope(ctx), request_id)] = replace(req, status="planned")
            return deepcopy(plan)

    def execute(
        self,
        ctx: ControlPlaneContext,
        *,
        plan_id: str,
        providers: Sequence[ErasureProvider],
    ) -> ErasureReport:
        with self._lock:
            plan = self._plans.get((*_scope(ctx), plan_id))
            if plan is None:
                raise ControlPlaneError.not_found("erasure plan not found")
            req = self.get_request(ctx, request_id=plan.request_id)
            if req.legal_hold:
                raise ControlPlaneError.forbidden("erasure blocked by legal hold")
            by_id = {p.provider_id: p for p in providers}
            results: list[ErasureStepResult] = []
            for step in plan.steps:
                provider = by_id.get(step.provider_id)
                if provider is None or not step.supported:
                    results.append(
                        ErasureStepResult(
                            step_id=step.step_id,
                            provider_id=step.provider_id,
                            status="unsupported",
                            reason="provider missing or unsupported",
                        )
                    )
                    continue
                result = provider.execute(
                    ctx,
                    action=step.action,
                    subject_key_fingerprint=req.subject_key_fingerprint,
                    field_paths=step.field_paths,
                )
                results.append(
                    replace(result, step_id=step.step_id)
                    if result.step_id != step.step_id
                    else result
                )
            statuses = {r.status for r in results}
            reconciled = (
                all(r.status in ("completed",) for r in results)
                and "unsupported" not in statuses
            )
            if "unsupported" in statuses or "failed" in statuses:
                # Cannot claim completion while required providers unresolved.
                if all(
                    r.status == "completed"
                    for r in results
                    if r.status != "unsupported"
                ):
                    status = "partial"
                elif all(r.status == "unsupported" for r in results):
                    status = "unsupported"
                else:
                    status = "partial"
                reconciled = False
            elif all(r.status == "completed" for r in results):
                status = "completed"
            else:
                status = "partial"
                reconciled = False
            # Hard rule: never report completed if any unsupported/unknown.
            if any(r.status in ("unsupported", "failed", "blocked") for r in results):
                if status == "completed":
                    status = "partial"
                reconciled = False
            report = ErasureReport(
                report_id=str(uuid.uuid4()),
                request_id=plan.request_id,
                plan_id=plan_id,
                status=status,  # type: ignore[arg-type]
                results=tuple(results),
                reconciled=reconciled,
            )
            self._reports[(*_scope(ctx), report.report_id)] = report
            self._requests[(*_scope(ctx), plan.request_id)] = replace(
                req,
                status=status,  # type: ignore[arg-type]
            )
            return deepcopy(report)

    def get_report(self, ctx: ControlPlaneContext, *, report_id: str) -> ErasureReport:
        with self._lock:
            report = self._reports.get((*_scope(ctx), report_id))
            if report is None:
                raise ControlPlaneError.not_found("erasure report not found")
            return deepcopy(report)


__all__ = ["MemoryErasureProvider", "MemoryErasureStore"]
