"""Packaged adapter that executes an accepted envelope with ETLantic runtime."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Mapping
from dataclasses import replace
from pathlib import Path
from threading import Event
from typing import TYPE_CHECKING, Any

from etlantic.control_plane.execution_envelope import ExecutionEnvelope
from etlantic.control_plane.models import ControlPlaneContext
from etlantic.exceptions import PipelineCancelledError
from etlantic.lifecycle.runtime import PipelineRuntime
from etlantic.plan.freeze import mutable_copy
from etlantic.plan.model import PipelinePlan
from etlantic.profile import Profile, resolve_profile
from etlantic.reports.file_store import FileReportStore
from etlantic.reports.model import PipelineRunReport
from etlantic.runtime.context import TrustedExecutionScope
from etlantic.runtime.execute import run_pipeline
from etlantic.runtime.managed_errors import ExecutionRejected, UnknownCommitError
from etlantic.runtime.request import RunRequest
from etlantic.runtime.state import RunStatus
from etlantic.secrets.provider import SecretAliasAuthorizer

if TYPE_CHECKING:
    from etlantic.control_plane.durable_models import SubmissionRecord


def _scope_fragment(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def managed_run_id(ctx: ControlPlaneContext, idempotency_key: str) -> str:
    scope = "/".join(
        (
            ctx.security_domain.domain_id,
            ctx.tenant.tenant_id,
            ctx.workspace.workspace_id,
            idempotency_key,
        )
    )
    return "run-" + _scope_fragment(scope)


def managed_report_store(
    ctx: ControlPlaneContext, *, report_root: str | Path | None = None
) -> FileReportStore:
    """Build the file result provider scoped by trusted tenant/workspace data."""
    configured_root = report_root or os.environ.get("ETLANTIC_REPORT_DIR")
    root = Path(configured_root or (Path.home() / ".etlantic" / "reports")).expanduser()
    scoped_root = (
        root
        / _scope_fragment(ctx.security_domain.domain_id)
        / _scope_fragment(ctx.tenant.tenant_id)
        / _scope_fragment(ctx.workspace.workspace_id)
    )
    return FileReportStore(scoped_root)


class ManagedExecutionAdapter:
    """Run verified submissions through the packaged local ETL runtime.

    Result files are scoped by trusted control-plane context. The accepted
    envelope is the only executable input; callers cannot provide a runner or
    replace the plan after admission.
    """

    def __init__(
        self,
        *,
        report_root: str | Path | None = None,
        report_store_factory: Callable[[ControlPlaneContext], Any] | None = None,
        event_publisher: (
            Callable[[ControlPlaneContext, str, str, Mapping[str, Any]], None] | None
        ) = None,
        runtime_factory: Any = PipelineRuntime,
        secret_alias_authorizer: SecretAliasAuthorizer | None = None,
        profile: str | Profile | None = None,
    ) -> None:
        configured_root = report_root or os.environ.get("ETLANTIC_REPORT_DIR")
        self.report_root = Path(
            configured_root or (Path.home() / ".etlantic" / "reports")
        ).expanduser()
        self.report_store_factory = report_store_factory
        self.event_publisher = event_publisher
        self.runtime_factory = runtime_factory
        self.secret_alias_authorizer = secret_alias_authorizer
        self.profile = resolve_profile(profile) if profile is not None else None

    def __call__(
        self,
        ctx: ControlPlaneContext,
        *,
        submission: SubmissionRecord,
        submission_id: str,
        attempt_id: str,
        fencing_token: int,
        recovered_attempt: bool = False,
        cancel_event: Event | None = None,
    ) -> PipelineRunReport:
        if submission.submission_id != submission_id:
            raise ExecutionRejected("Submission identity does not match the lease")
        if not submission.input_snapshot:
            raise ExecutionRejected(
                "Accepted submission has no verified execution envelope"
            )
        try:
            envelope = ExecutionEnvelope.from_json(submission.input_snapshot)
        except Exception as exc:
            raise ExecutionRejected("Accepted execution envelope is invalid") from exc
        if envelope.plan_fingerprint != submission.plan_fingerprint:
            raise ExecutionRejected(
                "Accepted plan fingerprint does not match submission"
            )
        if submission.revision_id is not None and (
            envelope.revision_id != submission.revision_id
        ):
            raise ExecutionRejected("Accepted revision does not match submission")

        try:
            plan = PipelinePlan.from_dict(
                mutable_copy(envelope.plan_document), verify=True
            )
            request = RunRequest.from_dict(envelope.effective_request)
        except Exception as exc:
            raise ExecutionRejected(
                "Accepted plan or run controls are invalid"
            ) from exc

        run_id = managed_run_id(ctx, submission.idempotency_key)
        event_base = {
            "run_id": run_id,
            "submission_id": submission_id,
            "attempt_id": attempt_id,
            "plan_fingerprint": envelope.plan_fingerprint,
        }
        self._publish_event(
            ctx,
            event_key=f"{submission_id}:{attempt_id}:started",
            kind="run.started",
            payload=event_base,
        )
        reports = (
            self.report_store_factory(ctx)
            if self.report_store_factory is not None
            else managed_report_store(ctx, report_root=self.report_root)
        )
        existing = reports.get(run_id)
        if existing is not None:
            if existing.plan_fingerprint != envelope.plan_fingerprint:
                raise ExecutionRejected("Stored result conflicts with accepted plan")
            self._publish_report_event(ctx, event_base, existing)
            return existing
        if recovered_attempt:
            raise ExecutionRejected(
                "A prior worker attempt has no durable report; reconcile its effects before retry"
            )

        runtime = self.runtime_factory()
        runtime.reports = reports
        previous_cancel_event = getattr(runtime, "external_cancel_event", None)
        previous_trusted_scope = getattr(runtime, "trusted_execution_scope", None)
        previous_secret_alias_authorizer = getattr(
            runtime, "secret_alias_authorizer", None
        )
        trusted_scope = TrustedExecutionScope(
            principal_id=ctx.principal.subject,
            principal_kind=ctx.principal.kind,
            principal_issuer=ctx.principal.issuer,
            tenant_id=ctx.tenant.tenant_id,
            workspace_id=ctx.workspace.workspace_id,
            environment=ctx.environment.name,
            security_domain_id=ctx.security_domain.domain_id,
            resource_owner_id=ctx.resource_owner_id,
        )
        runtime.trusted_execution_scope = trusted_scope
        runtime.secret_alias_authorizer = (
            self.secret_alias_authorizer
            if self.secret_alias_authorizer is not None
            else previous_secret_alias_authorizer
        )
        runtime.external_cancel_event = cancel_event
        try:
            try:
                execution_profile = self._execution_profile(envelope, plan)
                report = run_pipeline(
                    plan,
                    profile=execution_profile,
                    request=request,
                    runtime=runtime,
                    run_id=run_id,
                )
            except PipelineCancelledError as exc:
                if not isinstance(exc.report, PipelineRunReport):
                    raise UnknownCommitError(
                        "Managed cancellation ended without a durable run report"
                    ) from exc
                report = exc.report
        except ExecutionRejected:
            self._publish_event(
                ctx,
                event_key=f"{submission_id}:{attempt_id}:failed",
                kind="run.failed",
                payload={**event_base, "status": "failed"},
            )
            raise
        except Exception as exc:
            # A runtime exception can occur after a provider has committed. The
            # worker records an unknown effect and requires reconciliation.
            self._publish_event(
                ctx,
                event_key=f"{submission_id}:{attempt_id}:unknown",
                kind="run.reconciliation_required",
                payload={**event_base, "status": "unknown"},
            )
            raise UnknownCommitError(
                "Managed execution ended without a classified runtime report"
            ) from exc
        finally:
            runtime.external_cancel_event = previous_cancel_event
            runtime.trusted_execution_scope = previous_trusted_scope
            runtime.secret_alias_authorizer = previous_secret_alias_authorizer

        metadata = dict(report.metadata)
        metadata["etlantic.control_plane.execution"] = {
            "submission_id": submission_id,
            "attempt_id": attempt_id,
            "plan_fingerprint": envelope.plan_fingerprint,
            "canonical_intent_fingerprint": envelope.canonical_intent_fingerprint,
            "no_write": request.no_write,
        }
        published = replace(report, metadata=metadata)
        # Runtime persists during execution; write the enriched immutable
        # result last so result queries and recovery see the same lineage.
        reports.put(published)
        self._publish_report_event(ctx, event_base, published)
        return published

    def _execution_profile(
        self, envelope: ExecutionEnvelope, plan: PipelinePlan
    ) -> str | Profile:
        """Resolve worker runtime policy and reject drift from accepted settings."""
        if self.profile is None:
            return envelope.profile_name
        if self.profile.name != envelope.profile_name:
            raise ExecutionRejected(
                "Configured worker profile does not match the accepted profile"
            )
        accepted_snapshot = mutable_copy(plan.profile_snapshot)
        if not accepted_snapshot:
            raise ExecutionRejected("Accepted plan has no verified profile snapshot")
        try:
            configured_snapshot = self.profile.to_plan_snapshot()
            accepted_secrets = dict(accepted_snapshot.get("secrets") or {})
            configured_secrets = dict(configured_snapshot.get("secrets") or {})
            configured_snapshot["secrets"] = {
                key: configured_secrets[key]
                for key in accepted_secrets
                if key in configured_secrets
            }
            configured = json.dumps(
                configured_snapshot,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
            accepted = json.dumps(
                accepted_snapshot,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
        except Exception as exc:
            raise ExecutionRejected("Configured worker profile is invalid") from exc
        if configured != accepted:
            raise ExecutionRejected(
                "Configured worker profile differs from the accepted plan"
            )
        return self.profile

    def _publish_event(
        self,
        ctx: ControlPlaneContext,
        *,
        event_key: str,
        kind: str,
        payload: Mapping[str, Any],
    ) -> None:
        if self.event_publisher is not None:
            self.event_publisher(ctx, event_key, kind, payload)

    def _publish_report_event(
        self,
        ctx: ControlPlaneContext,
        event_base: Mapping[str, Any],
        report: PipelineRunReport,
    ) -> None:
        if report.status is RunStatus.SUCCEEDED:
            status, kind = "completed", "run.completed"
        elif report.status is RunStatus.CANCELLED:
            status, kind = "cancelled", "run.cancelled"
        else:
            status, kind = "unknown", "run.reconciliation_required"
        self._publish_event(
            ctx,
            event_key=f"{event_base['submission_id']!s}:{event_base['attempt_id']!s}:{status}",
            kind=kind,
            payload={**event_base, "status": status},
        )


__all__ = ["ManagedExecutionAdapter", "managed_report_store", "managed_run_id"]
