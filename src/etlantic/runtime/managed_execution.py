"""Packaged adapter that executes an accepted envelope with ETLantic runtime."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from threading import Event
from typing import TYPE_CHECKING, Any, cast

from etlantic.control_plane.durable_models import (
    ResultPublicationRecord,
    execution_context_from_submission,
)
from etlantic.control_plane.execution_envelope import ExecutionEnvelope
from etlantic.control_plane.input_resources import (
    InputResourceReference,
    InputResourceStore,
)
from etlantic.control_plane.models import (
    ControlPlaneContext,
)
from etlantic.exceptions import (
    PipelineCancelledError,
    PipelineExecutionError,
    PipelineTimeoutError,
)
from etlantic.lifecycle.runtime import PipelineRuntime
from etlantic.plan.adaptive_model import AdaptivePipelinePlan, PlanDocument
from etlantic.plan.freeze import mutable_copy
from etlantic.plan.serialize import plan_from_json
from etlantic.profile import Profile, resolve_profile
from etlantic.reports.file_store import FileReportStore
from etlantic.reports.model import PipelineRunReport
from etlantic.reports.retention import ArtifactRetentionResult
from etlantic.runtime.artifacts import ArtifactStore
from etlantic.runtime.context import TrustedExecutionScope
from etlantic.runtime.execute import run_pipeline
from etlantic.runtime.faults import active_faults
from etlantic.runtime.managed_errors import ExecutionRejected, UnknownCommitError
from etlantic.runtime.request import RunRequest
from etlantic.runtime.state import RunStatus
from etlantic.secrets.provider import SecretAliasAuthorizer

if TYPE_CHECKING:
    from etlantic.control_plane.durable_models import SubmissionRecord


def _scope_fragment(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def _record_attempt(execution: dict[str, Any], *, attempt_id: str, role: str) -> None:
    history: list[dict[str, str]] = []
    prior_history: object = execution.get("attempt_history")
    if isinstance(prior_history, (list, tuple)):
        for raw_item in cast(list[object] | tuple[object, ...], prior_history):
            if not isinstance(raw_item, Mapping):
                continue
            item = cast(Mapping[str, object], raw_item)
            history_attempt = item.get("attempt_id")
            history_role = item.get("role")
            if isinstance(history_attempt, str) and isinstance(history_role, str):
                history.append({"attempt_id": history_attempt, "role": history_role})
    if not any(
        item["attempt_id"] == attempt_id and item["role"] == role for item in history
    ):
        history.append({"attempt_id": attempt_id, "role": role})
    execution["attempt_history"] = history


def managed_run_id(
    ctx: ControlPlaneContext,
    idempotency_key: str,
    *,
    operation: str = "run.submit",
) -> str:
    parts = [
        ctx.security_domain.domain_id,
        ctx.tenant.tenant_id,
        ctx.workspace.workspace_id,
    ]
    # Preserve established run.submit identities while isolating lifecycle
    # commands that reuse the same idempotency key in another operation scope.
    if operation != "run.submit":
        parts.append(operation)
    parts.append(idempotency_key)
    scope = "/".join(parts)
    return "run-" + _scope_fragment(scope)


def managed_artifact_workspace(
    ctx: ControlPlaneContext,
    run_id: str,
    *,
    artifact_root: str | Path | None = None,
) -> Path:
    """Return a run-specific artifact root under the trusted caller scope."""
    configured_root = artifact_root or os.environ.get("ETLANTIC_ARTIFACT_DIR")
    root = Path(configured_root or (Path.home() / ".etlantic" / "artifacts"))
    root = root.expanduser()
    scoped_root = (
        root
        / _scope_fragment(ctx.security_domain.domain_id)
        / _scope_fragment(ctx.tenant.tenant_id)
        / _scope_fragment(ctx.workspace.workspace_id)
    )
    return scoped_root / _scope_fragment(run_id)


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


def managed_incremental_state_store(
    ctx: ControlPlaneContext,
    pipeline_id: str,
    *,
    state_root: str | Path | None = None,
) -> Any:
    """Return durable incremental cursors scoped to one managed pipeline."""
    from etlantic.runtime.incremental import FileStateStore

    configured_root = state_root or os.environ.get("ETLANTIC_STATE_DIR")
    root = Path(configured_root or (Path.home() / ".etlantic" / "state")).expanduser()
    scoped_root = (
        root
        / _scope_fragment(ctx.security_domain.domain_id)
        / _scope_fragment(ctx.tenant.tenant_id)
        / _scope_fragment(ctx.workspace.workspace_id)
        / _scope_fragment(pipeline_id)
    )
    return FileStateStore(scoped_root / "incremental-cursors.json")


def _plan_has_input_resources(plan: PlanDocument) -> bool:
    if isinstance(plan, AdaptivePipelinePlan):
        return False
    return any(
        "input_resource" in descriptor.config for descriptor in plan.bindings.values()
    )


def accepted_execution_context(
    worker_ctx: ControlPlaneContext, submission: SubmissionRecord
) -> ControlPlaneContext:
    """Rebuild provider authority from the durable accepted submission."""
    if (submission.tenant_id, submission.workspace_id) != (
        worker_ctx.tenant.tenant_id,
        worker_ctx.workspace.workspace_id,
    ):
        raise ExecutionRejected(
            "Accepted tenant/workspace does not match the worker lease"
        )
    accepted_ctx = execution_context_from_submission(submission)
    if accepted_ctx is None:
        raise ExecutionRejected(
            "Accepted submission has no durable execution authority"
        )
    return accepted_ctx


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
        artifact_root: str | Path | None = None,
        report_store_factory: Callable[[ControlPlaneContext], Any] | None = None,
        event_publisher: (
            Callable[[ControlPlaneContext, str, str, Mapping[str, Any]], None] | None
        ) = None,
        runtime_factory: Any = PipelineRuntime,
        secret_alias_authorizer: SecretAliasAuthorizer | None = None,
        profile: str | Profile | None = None,
        input_resource_store: InputResourceStore | None = None,
        run_artifact_retention_seconds: int | None = None,
        artifact_cleanup_batch_size: int = 100,
    ) -> None:
        if run_artifact_retention_seconds is not None and (
            type(run_artifact_retention_seconds) is not int
            or run_artifact_retention_seconds < 1
        ):
            raise ValueError(
                "run_artifact_retention_seconds must be a positive integer or None"
            )
        if (
            type(artifact_cleanup_batch_size) is not int
            or not 1 <= artifact_cleanup_batch_size <= 1000
        ):
            raise ValueError("artifact_cleanup_batch_size must be between 1 and 1000")
        configured_root = report_root or os.environ.get("ETLANTIC_REPORT_DIR")
        self.report_root = Path(
            configured_root or (Path.home() / ".etlantic" / "reports")
        ).expanduser()
        self.artifact_root = artifact_root
        self.report_store_factory = report_store_factory
        self.event_publisher = event_publisher
        self.runtime_factory = runtime_factory
        self.secret_alias_authorizer = secret_alias_authorizer
        self.profile = resolve_profile(profile) if profile is not None else None
        self.input_resource_store = input_resource_store
        self.run_artifact_retention_seconds = run_artifact_retention_seconds
        self.artifact_cleanup_batch_size = artifact_cleanup_batch_size

    @property
    def run_artifact_retention_enabled(self) -> bool:
        """Whether this adapter has artifact retention configured."""
        return self.run_artifact_retention_seconds is not None

    def artifact_retention_scope_key(
        self, ctx: ControlPlaneContext
    ) -> tuple[str | tuple[bool, str], ...]:
        """Return the dimensions that select this adapter's retention stores."""
        if self.report_store_factory is not None:
            return (
                ctx.tenant.tenant_id,
                ctx.workspace.workspace_id,
                (ctx.principal.issuer is not None, ctx.principal.issuer or ""),
                ctx.principal.kind,
                ctx.principal.subject,
                ctx.environment.name,
                ctx.security_domain.domain_id,
                (ctx.resource_owner_id is not None, ctx.resource_owner_id or ""),
            )
        # The managed report store and artifact workspace share these bounds.
        return (
            ctx.tenant.tenant_id,
            ctx.workspace.workspace_id,
            ctx.security_domain.domain_id,
        )

    def cleanup_expired_run_artifacts(
        self,
        ctx: ControlPlaneContext,
        *,
        now: datetime | None = None,
        limit: int | None = None,
    ) -> ArtifactRetentionResult:
        """Run one bounded result-retention pass for this trusted scope."""
        from etlantic.runtime.artifact_retention import cleanup_expired_run_artifacts

        report_store = None
        if self.run_artifact_retention_seconds is not None:
            report_store = (
                self.report_store_factory(ctx)
                if self.report_store_factory is not None
                else managed_report_store(ctx, report_root=self.report_root)
            )
        return cleanup_expired_run_artifacts(
            ctx,
            report_store=report_store,
            artifact_root=self.artifact_root,
            retention_seconds=self.run_artifact_retention_seconds,
            limit=self.artifact_cleanup_batch_size if limit is None else limit,
            now=now,
        )

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
        result_publisher: Callable[[PipelineRunReport], ResultPublicationRecord]
        | None = None,
        result_reader: Callable[[], ResultPublicationRecord | None] | None = None,
    ) -> PipelineRunReport:
        if submission.submission_id != submission_id:
            raise ExecutionRejected("Submission identity does not match the lease")
        ctx = accepted_execution_context(ctx, submission)
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
            plan = plan_from_json(
                json.dumps(
                    mutable_copy(envelope.plan_document),
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                    allow_nan=False,
                ),
                verify=True,
            )
            request = RunRequest.from_dict(envelope.effective_request)
        except Exception as exc:
            raise ExecutionRejected(
                "Accepted plan or run controls are invalid"
            ) from exc

        has_input_resources = _plan_has_input_resources(plan)
        input_resource_store = self.input_resource_store
        input_lease_id = (envelope.evidence_refs or {}).get("input_resource_lease_id")
        leased_reader: Callable[..., bytes] | None = None
        if has_input_resources:
            if (
                input_resource_store is None
                or not isinstance(input_lease_id, str)
                or not input_lease_id.strip()
            ):
                raise ExecutionRejected(
                    "Accepted input resources have no durable worker lease"
                )
            candidate_reader = getattr(input_resource_store, "read_leased", None)
            if not callable(candidate_reader):
                raise ExecutionRejected(
                    "Input resource store does not support lease-authorized worker reads"
                )
            leased_reader = cast(Callable[..., bytes], candidate_reader)

        run_id = managed_run_id(
            ctx, submission.idempotency_key, operation=submission.operation
        )
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
        report_store = (
            self.report_store_factory(ctx)
            if self.report_store_factory is not None
            else managed_report_store(ctx, report_root=self.report_root)
        )
        reports = _ResultRecoveryReportStore(report_store, result_publisher)
        try:
            existing = reports.get(run_id)
        except Exception:
            existing = None
        recovered_publication = False
        if existing is None and result_reader is not None:
            existing = _read_result_publication(
                result_reader,
                run_id=run_id,
                plan_fingerprint=envelope.plan_fingerprint,
            )
            recovered_publication = existing is not None
        if existing is not None:
            if existing.plan_fingerprint != envelope.plan_fingerprint:
                raise ExecutionRejected("Stored result conflicts with accepted plan")
            metadata = dict(existing.metadata)
            execution: dict[str, Any] = {}
            prior_execution: object = metadata.get("etlantic.control_plane.execution")
            if isinstance(prior_execution, Mapping):
                execution.update(cast(Mapping[str, Any], prior_execution))
            _record_attempt(execution, attempt_id=attempt_id, role="result_reconciled")
            if recovered_publication:
                execution["result_publication_status"] = "pending"
            metadata["etlantic.control_plane.execution"] = execution
            existing = replace(existing, metadata=metadata)
            if not recovered_publication:
                reports.put(existing)
            elif result_publisher is not None:
                # Preserve the updated attempt lineage in the durable snapshot.
                result_publisher(existing)
            self._publish_report_event(ctx, event_base, existing)
            return existing
        if recovered_attempt:
            raise ExecutionRejected(
                "A prior worker attempt has no durable report; reconcile its effects before retry"
            )

        runtime = self.runtime_factory()
        plan_intents = getattr(plan, "intents", {}) or {}
        incremental_strategies = plan_intents.get("incremental_strategies")
        if isinstance(incremental_strategies, Mapping) and incremental_strategies:
            runtime.incremental_state_store = managed_incremental_state_store(
                ctx,
                plan.pipeline_id,
            )
        runtime.reports = reports
        previous_cancel_event = getattr(runtime, "external_cancel_event", None)
        previous_trusted_scope = getattr(runtime, "trusted_execution_scope", None)
        previous_secret_alias_authorizer = getattr(
            runtime, "secret_alias_authorizer", None
        )
        previous_input_resource_resolver = getattr(
            runtime, "input_resource_resolver", None
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
        if has_input_resources:
            assert leased_reader is not None
            assert isinstance(input_lease_id, str)

            def resolve_input_resource(
                reference: InputResourceReference | Mapping[str, object],
            ) -> bytes:
                immutable = (
                    reference
                    if isinstance(reference, InputResourceReference)
                    else InputResourceReference.from_dict(reference)
                )
                return leased_reader(ctx, immutable, lease_id=input_lease_id)

            runtime.input_resource_resolver = resolve_input_resource
        evidence_refs = envelope.evidence_refs or {}
        artifact_parent_run_id = evidence_refs.get("artifact_parent_run_id")
        artifact_run_id = (
            artifact_parent_run_id
            if isinstance(artifact_parent_run_id, str)
            and artifact_parent_run_id.strip()
            else run_id
        )
        publication_recovered = False
        try:
            try:
                execution_profile = self._execution_profile(envelope, plan)
                report = run_pipeline(
                    plan,
                    profile=execution_profile,
                    request=request,
                    runtime=runtime,
                    artifact_store=ArtifactStore(
                        workspace=managed_artifact_workspace(
                            ctx, artifact_run_id, artifact_root=self.artifact_root
                        ),
                        hash_identities=True,
                    ),
                    run_id=run_id,
                )
            except PipelineCancelledError as exc:
                if not isinstance(exc.report, PipelineRunReport):
                    raise UnknownCommitError(
                        "Managed cancellation ended without a durable run report"
                    ) from exc
                report = exc.report
            except PipelineTimeoutError as exc:
                if not isinstance(exc.report, PipelineRunReport):
                    raise UnknownCommitError(
                        "Managed timeout ended without a durable run report"
                    ) from exc
                report = exc.report
            except PipelineExecutionError as exc:
                candidate = exc.report
                if (
                    exc.code != "PMEXEC410"
                    or not isinstance(candidate, PipelineRunReport)
                    or candidate.status is not RunStatus.FAILED
                    or not any(
                        item.code == "PMEXEC410" for item in candidate.diagnostics
                    )
                ):
                    raise
                # PMEXEC410 is raised only after the runtime knows target
                # publication committed. Require the fallback report to be
                # readable before replacing its transient publication failure.
                try:
                    persisted = reports.get(run_id)
                except Exception:
                    persisted = None
                from_durable_publication = False
                if (
                    not isinstance(persisted, PipelineRunReport)
                    and result_reader is not None
                ):
                    persisted = _read_result_publication(
                        result_reader,
                        run_id=run_id,
                        plan_fingerprint=envelope.plan_fingerprint,
                    )
                    from_durable_publication = persisted is not None
                if (
                    not isinstance(persisted, PipelineRunReport)
                    or persisted.plan_fingerprint != envelope.plan_fingerprint
                ):
                    raise
                if from_durable_publication:
                    recovered_status = persisted.status
                else:
                    if persisted.status is not RunStatus.FAILED or not any(
                        item.code == "PMEXEC410" for item in persisted.diagnostics
                    ):
                        raise
                    report_failure = next(
                        item
                        for item in persisted.diagnostics
                        if item.code == "PMEXEC410"
                    )
                    original_status_value = report_failure.metadata.get(
                        "etlantic.report_failure.original_status"
                    )
                    if original_status_value is None:
                        # Preserve the established recovery behavior for legacy
                        # reports that predate status metadata.
                        recovered_status = RunStatus.SUCCEEDED
                    else:
                        try:
                            recovered_status = RunStatus(original_status_value)
                        except (TypeError, ValueError) as exc:
                            raise UnknownCommitError(
                                "Managed result recovery found an invalid prior run status"
                            ) from exc
                        if recovered_status in (RunStatus.PENDING, RunStatus.RUNNING):
                            raise UnknownCommitError(
                                "Managed result recovery found a nonterminal prior run status"
                            ) from None
                if from_durable_publication:
                    diagnostics = (
                        *persisted.diagnostics,
                        replace(
                            next(
                                item
                                for item in candidate.diagnostics
                                if item.code == "PMEXEC410"
                            ),
                            severity="warning",
                            message=(
                                "Output publication was observed; the run result was "
                                "recovered without rerunning ETL."
                            ),
                        ),
                    )
                else:
                    diagnostics = tuple(
                        replace(
                            item,
                            severity="warning",
                            message=(
                                "Output publication was observed; the run result was "
                                "recovered without rerunning ETL."
                            ),
                        )
                        if item.code == "PMEXEC410"
                        else item
                        for item in persisted.diagnostics
                    )
                recovered_metadata = dict(persisted.metadata)
                execution_metadata: dict[str, Any] = {}
                prior_execution: object = recovered_metadata.get(
                    "etlantic.control_plane.execution"
                )
                if isinstance(prior_execution, Mapping):
                    execution_metadata.update(cast(Mapping[str, Any], prior_execution))
                execution_metadata.update(
                    {
                        "submission_id": submission_id,
                        "attempt_id": attempt_id,
                        "plan_fingerprint": envelope.plan_fingerprint,
                        "canonical_intent_fingerprint": (
                            envelope.canonical_intent_fingerprint
                        ),
                        "no_write": request.no_write,
                        "effect_status": (
                            "none"
                            if request.no_write
                            else "committed"
                            if recovered_status is RunStatus.SUCCEEDED
                            else "unknown"
                        ),
                        "result_publication_status": (
                            "pending" if from_durable_publication else "recovered"
                        ),
                    }
                )
                _record_attempt(
                    execution_metadata, attempt_id=attempt_id, role="executed"
                )
                recovered_metadata["etlantic.control_plane.execution"] = (
                    execution_metadata
                )
                report = replace(
                    persisted,
                    status=recovered_status,
                    diagnostics=diagnostics,
                    metadata=recovered_metadata,
                )
                if not from_durable_publication:
                    with active_faults():
                        reports.put(report)
                publication_recovered = True
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
            runtime.input_resource_resolver = previous_input_resource_resolver

        metadata = dict(report.metadata)
        execution_metadata: dict[str, Any] = {}
        previous_execution: object = metadata.get("etlantic.control_plane.execution")
        if isinstance(previous_execution, Mapping):
            execution_metadata.update(cast(Mapping[str, Any], previous_execution))
        execution_metadata.update(
            {
                "submission_id": submission_id,
                "attempt_id": attempt_id,
                "plan_fingerprint": envelope.plan_fingerprint,
                "canonical_intent_fingerprint": envelope.canonical_intent_fingerprint,
                "no_write": request.no_write,
            }
        )
        _record_attempt(execution_metadata, attempt_id=attempt_id, role="executed")
        if publication_recovered:
            execution_metadata.update(
                {
                    "effect_status": (
                        "none"
                        if request.no_write
                        else "committed"
                        if report.status is RunStatus.SUCCEEDED
                        else "unknown"
                    ),
                    "result_publication_status": execution_metadata.get(
                        "result_publication_status", "recovered"
                    ),
                }
            )
        metadata["etlantic.control_plane.execution"] = execution_metadata
        published = replace(report, metadata=metadata)
        # Runtime persists during execution; write the enriched immutable
        # result last so result queries and recovery see the same lineage.
        if not publication_recovered:
            reports.put(published)
        elif result_publisher is not None:
            result_publisher(published)
        self._publish_report_event(ctx, event_base, published)
        return published

    def publish_result_publication(
        self, ctx: ControlPlaneContext, record: ResultPublicationRecord
    ) -> None:
        """Copy a previously fenced report into the queryable report store."""
        if (record.tenant_id, record.workspace_id) != (
            ctx.tenant.tenant_id,
            ctx.workspace.workspace_id,
        ):
            raise ExecutionRejected("Durable run result has an invalid owner scope")
        report = _decode_result_publication(record)
        metadata = dict(report.metadata)
        execution: dict[str, Any] = {}
        prior_execution: object = metadata.get("etlantic.control_plane.execution")
        if isinstance(prior_execution, Mapping):
            execution.update(cast(Mapping[str, Any], prior_execution))
        execution["result_publication_status"] = "published"
        metadata["etlantic.control_plane.execution"] = execution
        report = replace(report, metadata=metadata)
        report_store = (
            self.report_store_factory(ctx)
            if self.report_store_factory is not None
            else managed_report_store(ctx, report_root=self.report_root)
        )
        report_store.put(report)

    def _execution_profile(
        self, envelope: ExecutionEnvelope, plan: PlanDocument
    ) -> str | Profile:
        """Resolve worker runtime policy and reject drift from accepted settings."""
        snapshot = plan.profile_snapshot or {}
        from etlantic.streaming.control import is_control_kind

        graph = getattr(plan, "logical_graph", None)
        if graph is not None and any(
            is_control_kind(node.kind) for node in getattr(graph, "nodes", ())
        ):
            raise ExecutionRejected(
                "Managed worker executes frozen batch graphs; dynamic control nodes "
                "require a control.expansion child scheduler and durable child ledger"
            )
        if snapshot.get("spark_streaming") is True:
            raise ExecutionRejected(
                "Managed worker runs finite batches; continuous Spark streaming "
                "requires a streaming trigger runner and checkpoint owner"
            )
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


class _ResultRecoveryReportStore:
    """Mirror failed report writes into the fenced durable-work snapshot."""

    def __init__(
        self,
        store: Any,
        publisher: Callable[[PipelineRunReport], ResultPublicationRecord] | None,
    ) -> None:
        self._store = store
        self._publisher = publisher

    def get(self, run_id: str) -> PipelineRunReport | None:
        try:
            return self._store.get(run_id)
        except Exception:
            # Runtime report lookup is advisory on the first attempt. A
            # recovered attempt remains fenced by the adapter's explicit
            # recovered_attempt check before execution can start.
            return None

    def put(self, report: PipelineRunReport) -> None:
        try:
            self._store.put(report)
        except Exception:
            # PMEXEC410 is the runtime's fallback report for the failure to
            # publish the original result. Keep the already mirrored original
            # result as the recovery authority instead of replacing it with
            # this synthetic failure report.
            if self._publisher is not None and not any(
                item.code == "PMEXEC410" for item in report.diagnostics
            ):
                self._publisher(report)
            raise


def _decode_result_publication(
    record: ResultPublicationRecord,
) -> PipelineRunReport:
    if hashlib.sha256(record.report_json.encode("utf-8")).hexdigest() != (
        record.report_sha256
    ):
        raise UnknownCommitError("Durable run result fingerprint is invalid")
    try:
        raw = json.loads(record.report_json)
    except (TypeError, ValueError) as exc:
        raise UnknownCommitError("Durable run result is invalid JSON") from exc
    if not isinstance(raw, dict):
        raise UnknownCommitError("Durable run result has an invalid document")
    try:
        report = PipelineRunReport.from_dict(cast(dict[str, Any], raw))
    except Exception as exc:
        raise UnknownCommitError("Durable run result schema is invalid") from exc
    if report.run_id != record.run_id or report.status in (
        RunStatus.PENDING,
        RunStatus.RUNNING,
    ):
        raise UnknownCommitError("Durable run result identity or status is invalid")
    return report


def _read_result_publication(
    reader: Callable[[], ResultPublicationRecord | None],
    *,
    run_id: str,
    plan_fingerprint: str,
) -> PipelineRunReport | None:
    try:
        record = reader()
    except Exception as exc:
        raise UnknownCommitError(
            "Durable run result is temporarily unavailable"
        ) from exc
    if record is None:
        return None
    report = _decode_result_publication(record)
    if report.run_id != run_id or report.plan_fingerprint != plan_fingerprint:
        raise UnknownCommitError("Durable run result does not match the accepted plan")
    return report


__all__ = ["ManagedExecutionAdapter", "managed_report_store", "managed_run_id"]
