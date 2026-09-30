"""Authorized, transport-neutral commands for managed ETL submissions."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from etlantic.authoring.edits import EditCommand, apply_edit
from etlantic.authoring.lifecycle import plan_pipeline_like, validate_pipeline_like
from etlantic.authoring.normalize import logical_graph_from_definition
from etlantic.authoring.serialize import (
    pipeline_fingerprint,
    pipeline_from_dict,
    pipeline_to_dict,
)
from etlantic.control_plane.authz import require_authorized, require_authorized_run
from etlantic.control_plane.durable_models import SubmissionRecord
from etlantic.control_plane.durable_protocols import DurableWorkStore
from etlantic.control_plane.errors import ControlPlaneError
from etlantic.control_plane.execution_envelope import ExecutionEnvelope
from etlantic.control_plane.models import (
    AcceptReceipt,
    ControlPlaneContext,
)
from etlantic.control_plane.policy_gates import gate_pre_submit
from etlantic.control_plane.protocols import (
    Authorizer,
    DefinitionRepository,
    EventStore,
    SubmissionStore,
)
from etlantic.plan.freeze import mutable_copy
from etlantic.plan.model import PipelinePlan
from etlantic.plan.serialize import verify_plan_fingerprint
from etlantic.profile import resolve_profile
from etlantic.registry import PlanningContext
from etlantic.reports.model import PipelineRunReport
from etlantic.runtime.managed_execution import (
    managed_report_store,
    managed_run_id,
)
from etlantic.runtime.request import RunIntent, RunRequest


def _mapping(value: object) -> Mapping[str, Any]:
    """Narrow untyped report payloads at the service boundary."""
    if isinstance(value, Mapping):
        return cast(Mapping[str, Any], value)
    return {}


@dataclass(slots=True)
class ManagedApplicationService:
    """Shared authorized service used by headless and HTTP callers.

    The service owns canonical validation, planning, idempotency recovery and
    durable acceptance. Transports provide only authenticated context and
    serialize its results.
    """

    authorizer: Authorizer
    definitions: DefinitionRepository
    submissions: SubmissionStore
    durable_work: DurableWorkStore
    events: EventStore | None = None
    profile: Any = "development"
    report_root: str | Path | None = None
    policy: Any = None
    approvals: Any = None
    quotas: Any = None
    audit: Any = None
    attestations: Any = None
    require_attestations: bool = False
    planning_context_factory: (
        Callable[[ControlPlaneContext, Any], PlanningContext] | None
    ) = None

    def register_definition(
        self,
        ctx: ControlPlaneContext,
        definition_id: str,
        document: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Validate and store one immutable canonical definition."""
        require_authorized(
            self.authorizer,
            ctx,
            "definition.write",
            f"definition:{definition_id}",
            resource_in_caller_scope=True,
        )
        definition = self._decode_definition(document)
        canonical = pipeline_to_dict(definition)
        self.definitions.put(ctx, definition_id, canonical)
        return {
            "definition_id": definition_id,
            "fingerprint": definition.fingerprint or pipeline_fingerprint(definition),
            "document": canonical,
        }

    def get_definition(
        self, ctx: ControlPlaneContext, definition_id: str
    ) -> dict[str, Any]:
        """Return a verified canonical definition after object authorization."""
        document = self._get_document(ctx, definition_id, action="definition.read")
        definition = self._decode_definition(document)
        return {
            "definition_id": definition_id,
            "fingerprint": definition.fingerprint or pipeline_fingerprint(definition),
            "document": pipeline_to_dict(definition),
        }

    def get_connector_catalog(self, ctx: ControlPlaneContext) -> dict[str, Any]:
        """Return installed connector schemas allowed by the active profile."""
        require_authorized(
            self.authorizer,
            ctx,
            "connector.catalog",
            "connector:*",
            resource_in_caller_scope=True,
        )
        try:
            from etlantic.connectors.catalog import connector_catalog_for_profile

            profile = resolve_profile(self.profile, allow_adhoc_profile=False)
            return connector_catalog_for_profile(profile)
        except Exception as exc:
            raise ControlPlaneError(
                "Connector catalog could not be resolved",
                code="PMCP503",
                status=503,
                title="Service Unavailable",
                type="etlantic.control_plane/unavailable",
            ) from exc

    def edit_definition(
        self,
        ctx: ControlPlaneContext,
        definition_id: str,
        command: Mapping[str, Any],
        *,
        expected_fingerprint: str,
    ) -> dict[str, Any]:
        """Apply a fingerprint-guarded edit and persist its new definition."""
        document = self._get_document(ctx, definition_id, action="definition.edit")
        definition = self._decode_definition(document)
        unknown = set(command) - {"op", "path", "payload"}
        if unknown:
            raise ControlPlaneError(
                "Unknown edit command field(s): " + ", ".join(sorted(unknown)),
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        path = command.get("path", ())
        payload = command.get("payload", {})
        if (
            not isinstance(command.get("op"), str)
            or not isinstance(path, (list, tuple))
            or not isinstance(payload, Mapping)
            or len(expected_fingerprint) != 64
        ):
            raise ControlPlaneError(
                "Edit command has an invalid shape or fingerprint",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        try:
            edit = EditCommand.from_dict(dict(command))
        except (KeyError, TypeError, ValueError) as exc:
            raise ControlPlaneError(
                "Edit command is invalid",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            ) from exc
        try:
            result = apply_edit(
                definition,
                edit,
                expected_token=expected_fingerprint,
            )
        except ValueError as exc:
            if str(exc).startswith("Optimistic concurrency failure:"):
                raise ControlPlaneError.conflict(
                    "Definition changed since the edit was prepared"
                ) from exc
            raise ControlPlaneError(
                "Definition edit command was rejected",
                code="PMCP422",
                status=422,
                title="Unprocessable Entity",
                type="etlantic.control_plane/validation_error",
            ) from exc
        canonical = pipeline_to_dict(result.definition)
        self.definitions.put(ctx, definition_id, canonical)
        return {
            "definition_id": definition_id,
            "fingerprint": result.fingerprint,
            "document": canonical,
        }

    def validate_definition(
        self, ctx: ControlPlaneContext, definition_id: str
    ) -> dict[str, Any]:
        """Run pure static validation without resolving credentials or doing I/O."""
        document = self._get_document(ctx, definition_id, action="definition.validate")
        definition = self._decode_definition(document)
        profile = resolve_profile(self.profile, allow_adhoc_profile=False)
        planning_context = self._planning_context(ctx, profile)
        report = validate_pipeline_like(
            definition, context=planning_context, profile=profile
        )
        return {
            "ok": not report.has_errors,
            "definition_id": definition_id,
            "fingerprint": definition.fingerprint or pipeline_fingerprint(definition),
            "diagnostics": [item.to_dict() for item in report.diagnostics],
        }

    def plan_definition(
        self,
        ctx: ControlPlaneContext,
        definition_id: str,
        *,
        request: RunRequest | Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build a deterministic verified plan without executing providers."""
        document = self._get_document(ctx, definition_id, action="definition.plan")
        definition = self._decode_definition(document)
        profile = resolve_profile(self.profile, allow_adhoc_profile=False)
        typed_request = self._coerce_request(request)
        graph = logical_graph_from_definition(definition)
        planning_context = self._planning_context(ctx, profile)
        plan = plan_pipeline_like(
            definition,
            context=planning_context,
            profile=profile,
            selection=typed_request.selection.to_plan_selection(graph),
            request=typed_request,
        )
        if not isinstance(plan, PipelinePlan):
            raise ControlPlaneError(
                "This managed service does not qualify adaptive plan schema /2",
                code="PMADP500",
                status=501,
                title="Not Implemented",
                type="etlantic.control_plane/not_implemented",
            )
        verify_plan_fingerprint(plan)
        return {
            "ok": True,
            "definition_id": definition_id,
            "fingerprint": plan.fingerprint,
            "plan": plan.to_dict(),
        }

    def submit_run(
        self,
        ctx: ControlPlaneContext,
        definition_id: str,
        *,
        idempotency_key: str,
        request: RunRequest | Mapping[str, Any] | None = None,
        revision_selector: str = "current",
    ) -> AcceptReceipt:
        """Prepare, bind and durably accept one managed execution."""
        if not idempotency_key.strip():
            raise ControlPlaneError(
                "Idempotency-Key is required for managed submission",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        revision_selector = _require_revision_selector(revision_selector)
        # Authorization is always evaluated before either idempotency or
        # definition lookup. A prior receipt does not grant continued access.
        require_authorized(
            self.authorizer,
            ctx,
            "run.submit",
            f"definition:{definition_id}",
            resource_in_caller_scope=False,
        )
        typed_request = self._coerce_request(request)
        profile = resolve_profile(self.profile, allow_adhoc_profile=False)
        intent_fingerprint = ExecutionEnvelope.intent_fingerprint(
            definition_id=definition_id,
            revision_selector=revision_selector,
            profile_name=profile.name,
            request=typed_request,
        )

        prior_receipt = self.submissions.lookup_idempotency(
            ctx, idempotency_key, operation="run.submit"
        )
        prior_payload = self.submissions.lookup_idempotency_payload(
            ctx, idempotency_key, operation="run.submit"
        )
        prior_durable = self.durable_work.get_submission_by_idempotency(
            ctx, idempotency_key=idempotency_key, operation="run.submit"
        )

        if prior_receipt is not None:
            envelope = self._envelope_from_payload(prior_payload)
            self._require_same_intent(envelope, intent_fingerprint)
            if envelope.definition_id != definition_id:
                raise ControlPlaneError.conflict(
                    "Idempotency key reuse with a different definition"
                )
            if prior_durable is None:
                self._accept_durable(
                    ctx,
                    idempotency_key=idempotency_key,
                    envelope=envelope,
                    submission_id=prior_receipt.submission_id,
                )
            elif prior_durable.submission_id != prior_receipt.submission_id:
                raise ControlPlaneError.conflict(
                    "Control-plane and execution submissions are inconsistent"
                )
            elif prior_durable.input_snapshot:
                durable_envelope = self._parse_envelope(prior_durable.input_snapshot)
                if (
                    durable_envelope.canonical_intent_fingerprint
                    != envelope.canonical_intent_fingerprint
                    or durable_envelope.plan_fingerprint != envelope.plan_fingerprint
                ):
                    raise ControlPlaneError.conflict(
                        "Control-plane and execution snapshots are inconsistent"
                    )
            else:
                raise ControlPlaneError.conflict(
                    "Legacy accepted work has no verified execution envelope"
                )
            return prior_receipt

        if prior_durable is not None:
            if not prior_durable.input_snapshot:
                raise ControlPlaneError.conflict(
                    "Legacy accepted work has no verified execution envelope"
                )
            envelope = self._parse_envelope(prior_durable.input_snapshot)
            self._require_same_intent(envelope, intent_fingerprint)
            if envelope.definition_id != definition_id:
                raise ControlPlaneError.conflict(
                    "Idempotency key reuse with a different definition"
                )
            payload = self._acceptance_payload(envelope)
            receipt_result = self.submissions.accept(
                ctx,
                idempotency_key=idempotency_key,
                payload=payload,
                resource_type="run",
                resource_id=managed_run_id(ctx, idempotency_key),
                submission_id=prior_durable.submission_id,
                operation="run.submit",
            )
            return receipt_result.receipt

        document = self._get_document(
            ctx, definition_id, action="run.submit", authorize=False
        )
        definition = self._decode_definition(document)
        planning_context = self._planning_context(ctx, profile)
        validation = validate_pipeline_like(
            definition, context=planning_context, profile=profile
        )
        if validation.has_errors:
            raise ControlPlaneError(
                "Pipeline definition failed static validation",
                code="PMCP422",
                status=422,
                title="Unprocessable Entity",
                type="etlantic.control_plane/validation_error",
                extensions={
                    "diagnostics": [item.to_dict() for item in validation.diagnostics]
                },
            )
        graph = logical_graph_from_definition(definition)
        plan = plan_pipeline_like(
            definition,
            context=planning_context,
            profile=profile,
            selection=typed_request.selection.to_plan_selection(graph),
            request=typed_request,
        )
        if not isinstance(plan, PipelinePlan):
            raise ControlPlaneError(
                "This managed service does not qualify adaptive plan schema /2",
                code="PMADP500",
                status=501,
                title="Not Implemented",
                type="etlantic.control_plane/not_implemented",
            )
        verify_plan_fingerprint(plan)
        plugin_fingerprint = (
            hashlib.sha256(
                json.dumps(
                    dict(plan.plugin_versions),
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            if plan.plugin_versions
            else None
        )
        policy_fingerprint = None
        if any(
            item is not None
            for item in (
                self.policy,
                self.approvals,
                self.quotas,
                self.audit,
                self.attestations,
            )
        ):
            decision, _quota = gate_pre_submit(
                ctx,
                policy=self.policy,
                approvals=self.approvals,
                quotas=self.quotas,
                audit=self.audit,
                attestations=self.attestations,
                plan_fingerprint=plan.fingerprint,
                revision_id=None,
                plugin_fingerprints=(
                    [plugin_fingerprint] if plugin_fingerprint is not None else None
                ),
                require_policy=self.policy is not None,
                require_attestations=self.require_attestations,
            )
            policy_fingerprint = (
                decision.policy_fingerprint if decision is not None else None
            )
        envelope = ExecutionEnvelope.create(
            definition_id=definition_id,
            revision_selector=revision_selector,
            revision_id=None,
            definition=definition,
            plan=plan,
            profile_name=profile.name,
            request=typed_request,
            plugin_fingerprint=plugin_fingerprint,
            policy_fingerprint=policy_fingerprint,
            resource_versions=self._resource_versions(plan),
        )
        payload = self._acceptance_payload(envelope)
        receipt_result = self.submissions.accept(
            ctx,
            idempotency_key=idempotency_key,
            payload=payload,
            resource_type="run",
            resource_id=managed_run_id(ctx, idempotency_key),
            operation="run.submit",
        )
        try:
            self._accept_durable(
                ctx,
                idempotency_key=idempotency_key,
                envelope=envelope,
                submission_id=receipt_result.receipt.submission_id,
            )
        except Exception as exc:
            if receipt_result.created:
                try:
                    _record, changed = self._cancel_cp1(
                        ctx, receipt_result.receipt.resource_id
                    )
                    _ = changed
                except Exception:
                    pass
            if isinstance(exc, ControlPlaneError):
                raise
            raise ControlPlaneError(
                "Durable execution acceptance failed; no receipt was returned",
                code="PMCP503",
                status=503,
                title="Service Unavailable",
                type="etlantic.control_plane/unavailable",
                extensions={
                    "submission_id": receipt_result.receipt.submission_id,
                    "compensated": receipt_result.created,
                },
            ) from exc

        if self.events is not None and receipt_result.created:
            with suppress(Exception):
                self.events.append(
                    ctx,
                    kind="run.accepted",
                    payload={
                        "run_id": receipt_result.receipt.resource_id,
                        "submission_id": receipt_result.receipt.submission_id,
                        "acceptance_id": receipt_result.receipt.acceptance_id,
                        "definition_id": definition_id,
                    },
                )
            # Acceptance is already durable. Event delivery is best-effort;
            # the accepted receipt remains the authoritative record.
        return receipt_result.receipt

    def get_run_status(self, ctx: ControlPlaneContext, run_id: str) -> dict[str, Any]:
        """Return the authorized CP1 projection with authoritative worker state."""
        record = self._authorized_run_record(ctx, "run.read", run_id)
        submission_id = str(record.get("submission_id") or "")
        if not submission_id:
            raise ControlPlaneError(
                "Run record is missing its submission identity",
                code="PMCP500",
                status=500,
                title="Internal Server Error",
            )
        try:
            durable = self.durable_work.get_submission(ctx, submission_id)
        except ControlPlaneError as exc:
            if exc.status != 404:
                raise
        else:
            record["status"] = durable.status
        return record

    def get_run_actions(self, ctx: ControlPlaneContext, run_id: str) -> dict[str, Any]:
        """Return state-aware commands supported by this managed service."""
        record = self._authorized_run_record(ctx, "run.actions", run_id)
        status = str(record.get("status") or "unknown")
        submission_id = str(record.get("submission_id") or "")
        durable_record: SubmissionRecord | None = None
        if submission_id:
            try:
                durable_record = self.durable_work.get_submission(ctx, submission_id)
                status = durable_record.status
            except ControlPlaneError as exc:
                if exc.status != 404:
                    raise
        decision = self.authorizer.authorize(ctx, "run.cancel", f"run:{run_id}")
        state_allows_cancel = status in {"accepted", "dispatched"}
        provider_supports_cancel = callable(
            getattr(self.submissions, "cancel_run", None)
        )
        if not decision.allowed:
            reason = "not_authorized"
        elif not provider_supports_cancel:
            reason = "provider_unsupported"
        elif status == "cancel_requested":
            reason = "already_requested"
        elif not state_allows_cancel:
            reason = "terminal_state"
        else:
            reason = None
        retry_decision = self.authorizer.authorize(ctx, "run.retry", f"run:{run_id}")
        retry_reason: str | None
        if not retry_decision.allowed:
            retry_reason = "not_authorized"
        elif status != "failed":
            retry_reason = "non_retryable_state"
        elif not submission_id or durable_record is None:
            retry_reason = "durable_state_unavailable"
        elif not durable_record.input_snapshot:
            retry_reason = "unverified_execution_envelope"
        else:
            retry_reason = self._retry_block_reason(ctx, submission_id)
        rerun_decision = self.authorizer.authorize(
            ctx, "run.rerun", f"run:{run_id}"
        )
        if not rerun_decision.allowed:
            rerun_reason: str | None = "not_authorized"
        elif status not in {"completed", "failed", "cancelled"}:
            rerun_reason = "non_rerunnable_state"
        elif not submission_id or durable_record is None:
            rerun_reason = "durable_state_unavailable"
        elif not durable_record.input_snapshot:
            rerun_reason = "unverified_execution_envelope"
        else:
            rerun_reason = self._rerun_block_reason(ctx, submission_id)
        replay_decision = self.authorizer.authorize(
            ctx, "run.replay", f"run:{run_id}"
        )
        if not replay_decision.allowed:
            replay_reason: str | None = "not_authorized"
        elif status not in {"completed", "failed", "cancelled"}:
            replay_reason = "non_replayable_state"
        elif not submission_id or durable_record is None:
            replay_reason = "durable_state_unavailable"
        elif not durable_record.input_snapshot:
            replay_reason = "unverified_execution_envelope"
        else:
            replay_reason = self._rerun_block_reason(ctx, submission_id)
        return {
            "run_id": run_id,
            "status": status,
            "actions": [
                {"name": "cancel", "allowed": reason is None, "reason": reason},
                {
                    "name": "retry",
                    "allowed": retry_reason is None,
                    "reason": retry_reason,
                },
                {
                    "name": "rerun",
                    "allowed": rerun_reason is None,
                    "reason": rerun_reason,
                },
                {
                    "name": "replay",
                    "allowed": replay_reason is None,
                    "reason": replay_reason,
                },
            ],
        }

    def retry_run(
        self,
        ctx: ControlPlaneContext,
        run_id: str,
        *,
        idempotency_key: str,
    ) -> AcceptReceipt:
        """Accept a new retry from the prior run's immutable execution envelope.

        Retries are limited to failed runs with no recorded effect or an
        authoritative no-effect receipt. Unknown and committed effects require
        provider reconciliation and cannot be replayed here.
        """
        if not idempotency_key.strip():
            raise ControlPlaneError(
                "Idempotency-Key is required for managed retry",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        record = self._authorized_run_record(ctx, "run.retry", run_id)
        parent_submission_id = str(record.get("submission_id") or "")
        if not parent_submission_id:
            raise ControlPlaneError.conflict(
                "Run record has no durable submission identity"
            )
        parent = self.durable_work.get_submission(ctx, parent_submission_id)
        if parent.status != "failed":
            raise ControlPlaneError.conflict(
                "Only failed runs can be retried from their accepted snapshot"
            )
        if not parent.input_snapshot:
            raise ControlPlaneError.conflict(
                "Legacy accepted work has no verified execution envelope"
            )
        parent_envelope = self._parse_envelope(parent.input_snapshot)
        envelope_data = parent_envelope.to_dict()
        evidence_refs = dict(envelope_data.get("evidence_refs") or {})
        evidence_refs.update(
            {
                "command": "retry",
                "parent_run_id": run_id,
                "parent_submission_id": parent_submission_id,
            }
        )
        envelope_data["evidence_refs"] = evidence_refs
        envelope = ExecutionEnvelope.from_dict(envelope_data)
        prior_receipt = self.submissions.lookup_idempotency(
            ctx, idempotency_key, operation="run.retry"
        )
        prior_durable = self.durable_work.get_submission_by_idempotency(
            ctx, idempotency_key=idempotency_key, operation="run.retry"
        )
        if prior_receipt is None and prior_durable is None:
            retry_reason = self._retry_block_reason(ctx, parent_submission_id)
            if retry_reason is not None:
                raise ControlPlaneError.conflict(
                    "Retry is blocked until the prior execution effect is reconciled",
                    extensions={"reason": retry_reason},
                )
        return self._accept_child_run(
            ctx,
            idempotency_key=idempotency_key,
            operation="run.retry",
            envelope=envelope,
            parent_run_id=run_id,
            parent_submission_id=parent_submission_id,
        )

    def rerun_run(
        self,
        ctx: ControlPlaneContext,
        run_id: str,
        *,
        idempotency_key: str,
    ) -> AcceptReceipt:
        """Accept an explicit fresh execution of a terminal run's snapshot.

        Unlike retry, rerun may intentionally repeat an already committed
        effect. An unresolved effect still blocks admission because the prior
        operation may be active or partially committed.
        """
        if not idempotency_key.strip():
            raise ControlPlaneError(
                "Idempotency-Key is required for managed rerun",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        record = self._authorized_run_record(ctx, "run.rerun", run_id)
        parent_submission_id = str(record.get("submission_id") or "")
        if not parent_submission_id:
            raise ControlPlaneError.conflict(
                "Run record has no durable submission identity"
            )
        parent = self.durable_work.get_submission(ctx, parent_submission_id)
        if parent.status not in {"completed", "failed", "cancelled"}:
            raise ControlPlaneError.conflict(
                "Only terminal runs can be rerun from their accepted snapshot"
            )
        if not parent.input_snapshot:
            raise ControlPlaneError.conflict(
                "Legacy accepted work has no verified execution envelope"
            )
        parent_envelope = self._parse_envelope(parent.input_snapshot)
        envelope_data = parent_envelope.to_dict()
        evidence_refs = dict(envelope_data.get("evidence_refs") or {})
        evidence_refs.update(
            {
                "command": "rerun",
                "parent_run_id": run_id,
                "parent_submission_id": parent_submission_id,
            }
        )
        envelope = ExecutionEnvelope.from_dict(
            {**envelope_data, "evidence_refs": evidence_refs}
        )
        prior_receipt = self.submissions.lookup_idempotency(
            ctx, idempotency_key, operation="run.rerun"
        )
        prior_durable = self.durable_work.get_submission_by_idempotency(
            ctx, idempotency_key=idempotency_key, operation="run.rerun"
        )
        if prior_receipt is None and prior_durable is None:
            rerun_reason = self._rerun_block_reason(ctx, parent_submission_id)
            if rerun_reason is not None:
                raise ControlPlaneError.conflict(
                    "Rerun is blocked until the prior execution effect is reconciled",
                    extensions={"reason": rerun_reason},
                )
        return self._accept_child_run(
            ctx,
            idempotency_key=idempotency_key,
            operation="run.rerun",
            envelope=envelope,
            parent_run_id=run_id,
            parent_submission_id=parent_submission_id,
        )

    def replay_run(
        self,
        ctx: ControlPlaneContext,
        run_id: str,
        *,
        idempotency_key: str,
    ) -> AcceptReceipt:
        """Replay a terminal run's complete verified snapshot from the start.

        This command preserves the original plan and controls, marks the run
        intent as ``replay``, and records the parent identity. It does not
        imply checkpoint resume; that requires a separately qualified command.
        """
        if not idempotency_key.strip():
            raise ControlPlaneError(
                "Idempotency-Key is required for managed replay",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        record = self._authorized_run_record(ctx, "run.replay", run_id)
        parent_submission_id = str(record.get("submission_id") or "")
        if not parent_submission_id:
            raise ControlPlaneError.conflict(
                "Run record has no durable submission identity"
            )
        parent = self.durable_work.get_submission(ctx, parent_submission_id)
        if parent.status not in {"completed", "failed", "cancelled"}:
            raise ControlPlaneError.conflict(
                "Only terminal runs can be replayed from their accepted snapshot"
            )
        if not parent.input_snapshot:
            raise ControlPlaneError.conflict(
                "Legacy accepted work has no verified execution envelope"
            )
        parent_envelope = self._parse_envelope(parent.input_snapshot)
        request = RunRequest.from_dict(dict(parent_envelope.run_request))
        replay_request = RunRequest(
            selection=request.selection,
            intent=RunIntent.REPLAY,
            materialization=request.materialization,
            retry=request.retry,
            timeout=request.timeout,
            cancellation=request.cancellation,
            parameter_overrides=request.parameter_overrides,
            asset_overrides=request.asset_overrides,
            implementation_overrides=request.implementation_overrides,
            invalidation=request.invalidation,
            no_write=request.no_write,
            metadata=request.metadata,
            extensions=request.extensions,
            explicit_settings=request.explicit_settings,
        )
        envelope = parent_envelope.with_request(replay_request)
        envelope_data = envelope.to_dict()
        evidence_refs = dict(envelope_data.get("evidence_refs") or {})
        evidence_refs.update(
            {
                "command": "replay",
                "parent_run_id": run_id,
                "parent_submission_id": parent_submission_id,
            }
        )
        envelope = ExecutionEnvelope.from_dict(
            {**envelope_data, "evidence_refs": evidence_refs}
        )
        prior_receipt = self.submissions.lookup_idempotency(
            ctx, idempotency_key, operation="run.replay"
        )
        prior_durable = self.durable_work.get_submission_by_idempotency(
            ctx, idempotency_key=idempotency_key, operation="run.replay"
        )
        if prior_receipt is None and prior_durable is None:
            replay_reason = self._rerun_block_reason(ctx, parent_submission_id)
            if replay_reason is not None:
                raise ControlPlaneError.conflict(
                    "Replay is blocked until the prior execution effect is reconciled",
                    extensions={"reason": replay_reason},
                )
            self.durable_work.replay(ctx, parent_submission_id)
        return self._accept_child_run(
            ctx,
            idempotency_key=idempotency_key,
            operation="run.replay",
            envelope=envelope,
            parent_run_id=run_id,
            parent_submission_id=parent_submission_id,
        )

    def _rerun_block_reason(
        self, ctx: ControlPlaneContext, submission_id: str
    ) -> str | None:
        try:
            effect = self.durable_work.get_effect(ctx, f"{submission_id}:execution")
        except ControlPlaneError as exc:
            if exc.status == 404:
                return None
            raise
        if effect.status in {"none", "not_committed", "failed", "committed"}:
            return None
        return "effect_requires_reconciliation"

    def _retry_block_reason(
        self, ctx: ControlPlaneContext, submission_id: str
    ) -> str | None:
        try:
            effect = self.durable_work.get_effect(ctx, f"{submission_id}:execution")
        except ControlPlaneError as exc:
            if exc.status == 404:
                # A failed attempt rejected before execution has no effect row.
                return None
            raise
        if effect.status in {"none", "not_committed", "failed"}:
            return None
        return "effect_requires_reconciliation"

    def _accept_child_run(
        self,
        ctx: ControlPlaneContext,
        *,
        idempotency_key: str,
        operation: str,
        envelope: ExecutionEnvelope,
        parent_run_id: str,
        parent_submission_id: str,
    ) -> AcceptReceipt:
        """Idempotently accept a lifecycle command and its verified envelope."""
        payload = self._acceptance_payload(envelope)
        payload.update(
            {
                "command": operation.removeprefix("run."),
                "parent_run_id": parent_run_id,
                "parent_submission_id": parent_submission_id,
            }
        )
        prior_receipt = self.submissions.lookup_idempotency(
            ctx, idempotency_key, operation=operation
        )
        prior_payload = self.submissions.lookup_idempotency_payload(
            ctx, idempotency_key, operation=operation
        )
        prior_durable = self.durable_work.get_submission_by_idempotency(
            ctx, idempotency_key=idempotency_key, operation=operation
        )
        expected_envelope = envelope.to_json()
        if prior_receipt is not None:
            prior_envelope = self._envelope_from_payload(prior_payload)
            if prior_envelope.to_json() != expected_envelope:
                raise ControlPlaneError.conflict(
                    "Idempotency key reuse with a different retry parent or intent"
                )
            if prior_durable is None:
                self._accept_child_durable(
                    ctx,
                    idempotency_key=idempotency_key,
                    operation=operation,
                    envelope=envelope,
                    submission_id=prior_receipt.submission_id,
                )
            elif (
                prior_durable.submission_id != prior_receipt.submission_id
                or prior_durable.input_snapshot != expected_envelope
            ):
                raise ControlPlaneError.conflict(
                    "Control-plane and execution retry snapshots are inconsistent"
                )
            return prior_receipt
        if prior_durable is not None:
            if prior_durable.input_snapshot != expected_envelope:
                raise ControlPlaneError.conflict(
                    "Idempotency key reuse with a different retry parent or intent"
                )
            receipt_result = self.submissions.accept(
                ctx,
                idempotency_key=idempotency_key,
                payload=payload,
                resource_type="run",
                resource_id=managed_run_id(ctx, idempotency_key),
                submission_id=prior_durable.submission_id,
                operation=operation,
            )
            return receipt_result.receipt

        receipt_result = self.submissions.accept(
            ctx,
            idempotency_key=idempotency_key,
            payload=payload,
            resource_type="run",
            resource_id=managed_run_id(ctx, idempotency_key),
            operation=operation,
        )
        try:
            self._accept_child_durable(
                ctx,
                idempotency_key=idempotency_key,
                operation=operation,
                envelope=envelope,
                submission_id=receipt_result.receipt.submission_id,
            )
        except Exception as exc:
            if receipt_result.created:
                with suppress(Exception):
                    self._cancel_cp1(ctx, receipt_result.receipt.resource_id)
            if isinstance(exc, ControlPlaneError):
                raise
            raise ControlPlaneError(
                "Durable retry acceptance failed; no receipt was returned",
                code="PMCP503",
                status=503,
                title="Service Unavailable",
                type="etlantic.control_plane/unavailable",
                extensions={
                    "submission_id": receipt_result.receipt.submission_id,
                    "compensated": receipt_result.created,
                },
            ) from exc
        if receipt_result.created and self.events is not None:
            with suppress(Exception):
                self.events.append(
                    ctx,
                    kind="run.retry.accepted",
                    payload={
                        "run_id": receipt_result.receipt.resource_id,
                        "submission_id": receipt_result.receipt.submission_id,
                        "parent_run_id": parent_run_id,
                        "parent_submission_id": parent_submission_id,
                    },
                )
        return receipt_result.receipt

    def _accept_child_durable(
        self,
        ctx: ControlPlaneContext,
        *,
        idempotency_key: str,
        operation: str,
        envelope: ExecutionEnvelope,
        submission_id: str,
    ) -> SubmissionRecord:
        row, _created = self.durable_work.accept(
            ctx,
            idempotency_key=idempotency_key,
            operation=operation,
            plan_fingerprint=envelope.plan_fingerprint,
            revision_id=envelope.revision_id,
            plugin_fingerprint=envelope.plugin_fingerprint,
            policy_fingerprint=envelope.policy_fingerprint,
            input_snapshot=envelope.to_json(),
            submission_id=submission_id,
        )
        return row

    def cancel_run(self, ctx: ControlPlaneContext, run_id: str) -> dict[str, Any]:
        """Request cancellation through the same authorized service as HTTP."""
        record = self._authorized_run_record(ctx, "run.cancel", run_id)
        submission_id = record.get("submission_id")
        if not isinstance(submission_id, str) or not submission_id:
            raise ControlPlaneError.conflict(
                "Run record has no durable submission identity"
            )
        cancel = getattr(self.submissions, "cancel_run", None)
        if not callable(cancel):
            raise ControlPlaneError(
                "Submission provider does not support run cancellation",
                code="PMCP501",
                status=501,
                title="Not Implemented",
            )
        cancel_run = cast(
            Callable[
                [ControlPlaneContext, str],
                tuple[dict[str, Any], bool] | dict[str, Any],
            ],
            cancel,
        )
        durable_status: str | None = None
        try:
            durable = self.durable_work.cancel_submission(ctx, submission_id)
            durable_status = durable.status
        except ControlPlaneError as exc:
            if exc.status == 404:
                # Legacy CP1-only records retain their observation-level cancel.
                pass
            elif exc.status == 409:
                durable = self.durable_work.get_submission(ctx, submission_id)
                durable_status = durable.status
                if durable.status not in {"cancelled", "completed", "failed"}:
                    raise
                response = dict(record)
                response["status"] = durable.status
                return response
            else:
                raise
        try:
            result = cancel_run(ctx, run_id)
        except KeyError as exc:
            raise ControlPlaneError.not_found(f"Run {run_id!r} not found") from exc
        if isinstance(result, tuple):
            updated, changed = result
        else:
            updated, changed = result, True
        response = dict(updated)
        if durable_status is not None:
            response["status"] = durable_status
        if changed and self.events is not None:
            with suppress(Exception):
                self.events.append(
                    ctx,
                    kind="run.cancel_requested",
                    payload={"run_id": run_id, "submission_id": submission_id},
                )
        return response

    def get_run_report(self, ctx: ControlPlaneContext, run_id: str) -> dict[str, Any]:
        """Return the persisted runtime report or an explicit pending response."""
        _record, result = self._runtime_report(ctx, "run.report", run_id)
        return result.to_dict()

    def _runtime_report(
        self, ctx: ControlPlaneContext, action: str, run_id: str
    ) -> tuple[dict[str, Any], PipelineRunReport]:
        record = self._authorized_run_record(ctx, action, run_id)
        idempotency_key = str(record.get("idempotency_key") or "")
        if not idempotency_key:
            raise ControlPlaneError.not_found("Run report not found")
        result = managed_report_store(ctx, report_root=self.report_root).get(
            managed_run_id(ctx, idempotency_key)
        )
        if result is None:
            raise ControlPlaneError(
                "Run report has not been published",
                code="PMCP425",
                status=425,
                title="Too Early",
                type="etlantic.control_plane/result_pending",
                extensions={"run_id": run_id, "status": record.get("status")},
            )
        submission_id = str(record.get("submission_id") or "")
        durable = self.durable_work.get_submission(ctx, submission_id)
        if result.plan_fingerprint != durable.plan_fingerprint:
            raise ControlPlaneError(
                "Stored run report does not match the accepted plan",
                code="PMCP500",
                status=500,
                title="Internal Server Error",
            )
        return record, result

    def get_run_lineage(self, ctx: ControlPlaneContext, run_id: str) -> dict[str, Any]:
        """Project actual runtime lineage, artifacts and execution identity."""
        record, report_model = self._runtime_report(ctx, "run.lineage", run_id)
        report: dict[str, Any] = report_model.to_dict()
        nodes: list[dict[str, Any]] = [{"id": report["run_id"], "kind": "run"}]
        edges: list[dict[str, Any]] = list(report.get("lineage") or [])
        artifacts: list[dict[str, Any]] = report.get("artifacts") or []
        for artifact in artifacts:
            identity = str(artifact.get("identity") or "")
            if not identity:
                continue
            nodes.append(
                {
                    "id": identity,
                    "kind": "artifact",
                    "logical_output": artifact.get("logical_output"),
                    "status": artifact.get("status"),
                }
            )
            edges.append(
                {
                    "from": report["run_id"],
                    "to": identity,
                    "kind": "produced",
                }
            )
        metadata = _mapping(report.get("metadata"))
        execution = _mapping(metadata.get("etlantic.control_plane.execution"))
        submission_id_raw: object = execution.get("submission_id") or record.get(
            "submission_id"
        )
        submission_id = (
            submission_id_raw if isinstance(submission_id_raw, str) else None
        )
        if isinstance(submission_id, str) and submission_id:
            durable = self.durable_work.get_submission(ctx, submission_id)
            if durable.input_snapshot:
                envelope = self._parse_envelope(durable.input_snapshot)
                evidence_refs = envelope.evidence_refs or {}
                parent_run_id = evidence_refs.get("parent_run_id")
                command = evidence_refs.get("command")
                if parent_run_id:
                    nodes.insert(0, {"id": parent_run_id, "kind": "run"})
                    edges.append(
                        {
                            "from": parent_run_id,
                            "to": report["run_id"],
                            "kind": str(command or "child_run"),
                        }
                    )
        return {
            "schema": "etlantic.run_lineage/1",
            "run_id": report["run_id"],
            "submission_id": submission_id,
            "attempt_id": execution.get("attempt_id"),
            "nodes": nodes,
            "edges": edges,
        }

    def list_run_artifacts(
        self, ctx: ControlPlaneContext, run_id: str
    ) -> list[dict[str, Any]]:
        """List artifacts that the caller is separately authorized to observe."""
        _record, report_model = self._runtime_report(ctx, "run.artifacts", run_id)
        report: dict[str, Any] = report_model.to_dict()
        items: list[dict[str, Any]] = []
        artifacts: list[dict[str, Any]] = report.get("artifacts") or []
        for artifact in artifacts:
            identity = str(artifact.get("identity") or "")
            if not identity:
                continue
            try:
                require_authorized(
                    self.authorizer,
                    ctx,
                    "run.artifacts",
                    f"artifact:{identity}",
                    resource_in_caller_scope=False,
                )
            except ControlPlaneError:
                continue
            items.append(
                {
                    "artifact_id": identity,
                    "kind": artifact.get("strategy", "output"),
                    "media_type": _mapping(artifact.get("metadata")).get("media_type"),
                }
            )
        return items

    def _get_document(
        self,
        ctx: ControlPlaneContext,
        definition_id: str,
        *,
        action: str,
        authorize: bool = True,
    ) -> Mapping[str, Any]:
        if authorize:
            require_authorized(
                self.authorizer,
                ctx,
                action,
                f"definition:{definition_id}",
                resource_in_caller_scope=False,
            )
        try:
            return self.definitions.get(ctx, definition_id)
        except KeyError as exc:
            raise ControlPlaneError.not_found(
                f"Definition {definition_id!r} not found"
            ) from exc

    @staticmethod
    def _decode_definition(document: Mapping[str, Any]):
        try:
            return pipeline_from_dict(dict(document), verify=True)
        except Exception as exc:
            raise ControlPlaneError(
                "Definition is not a verified canonical pipeline",
                code="PMCP422",
                status=422,
                title="Unprocessable Entity",
                type="etlantic.control_plane/validation_error",
            ) from exc

    @staticmethod
    def _coerce_request(
        request: RunRequest | Mapping[str, Any] | None,
    ) -> RunRequest:
        if request is None:
            return RunRequest()
        if isinstance(request, RunRequest):
            return request
        try:
            return RunRequest.from_dict(request)
        except (TypeError, ValueError) as exc:
            raise ControlPlaneError(
                "Run request is invalid",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            ) from exc

    def _planning_context(
        self, ctx: ControlPlaneContext, profile: Any
    ) -> PlanningContext | None:
        if self.planning_context_factory is None:
            return None
        try:
            context = self.planning_context_factory(ctx, profile)
        except Exception as exc:
            raise ControlPlaneError(
                "Planning resources could not be resolved",
                code="PMCP503",
                status=503,
                title="Service Unavailable",
                type="etlantic.control_plane/unavailable",
            ) from exc
        return context

    @staticmethod
    def _acceptance_payload(envelope: ExecutionEnvelope) -> dict[str, Any]:
        return {
            "definition_id": envelope.definition_id,
            "revision_selector": envelope.revision_selector,
            "profile_name": envelope.profile_name,
            "request": mutable_copy(envelope.run_request),
            "plan_fingerprint": envelope.plan_fingerprint,
            # Kept as a JSON string so CP1 redaction preserves extension keys
            # and the exact digest-verified accepted bytes.
            "execution_envelope": envelope.to_json(),
        }

    @staticmethod
    def _envelope_from_payload(
        payload: Mapping[str, Any] | None,
    ) -> ExecutionEnvelope:
        if payload is None or not isinstance(payload.get("execution_envelope"), str):
            raise ControlPlaneError.conflict(
                "Prior acceptance has no verified execution envelope"
            )
        return ManagedApplicationService._parse_envelope(
            str(payload["execution_envelope"])
        )

    @staticmethod
    def _parse_envelope(value: str) -> ExecutionEnvelope:
        try:
            return ExecutionEnvelope.from_json(value)
        except Exception as exc:
            raise ControlPlaneError.conflict(
                "Stored execution envelope failed integrity verification"
            ) from exc

    @staticmethod
    def _require_same_intent(
        envelope: ExecutionEnvelope, intent_fingerprint: str
    ) -> None:
        if envelope.canonical_intent_fingerprint != intent_fingerprint:
            raise ControlPlaneError.conflict(
                "Idempotency key reuse with different canonical intent"
            )

    def _accept_durable(
        self,
        ctx: ControlPlaneContext,
        *,
        idempotency_key: str,
        envelope: ExecutionEnvelope,
        submission_id: str,
    ) -> SubmissionRecord:
        row, _created = self.durable_work.accept(
            ctx,
            idempotency_key=idempotency_key,
            operation="run.submit",
            plan_fingerprint=envelope.plan_fingerprint,
            revision_id=envelope.revision_id,
            plugin_fingerprint=envelope.plugin_fingerprint,
            policy_fingerprint=envelope.policy_fingerprint,
            input_snapshot=envelope.to_json(),
            submission_id=submission_id,
        )
        return row

    @staticmethod
    def _resource_versions(plan: PipelinePlan) -> dict[str, str]:
        versions: dict[str, str] = {}
        for identity, resource in plan.resource_refs.items():
            version = resource.get("version") or resource.get("fingerprint")
            if isinstance(version, str) and version:
                versions[str(identity)] = version
        return versions

    def _cancel_cp1(
        self, ctx: ControlPlaneContext, run_id: str | None
    ) -> tuple[dict[str, Any], bool]:
        if not run_id:
            raise ControlPlaneError(
                "Acceptance cannot be compensated without a run identity",
                code="PMCP500",
                status=500,
                title="Internal Server Error",
            )
        cancel = getattr(self.submissions, "cancel_run", None)
        if not callable(cancel):
            raise ControlPlaneError(
                "Submission provider cannot compensate incomplete acceptance",
                code="PMCP501",
                status=501,
                title="Not Implemented",
            )
        cancel_run = cast(
            Callable[
                [ControlPlaneContext, str], tuple[dict[str, Any], bool] | dict[str, Any]
            ],
            cancel,
        )
        result = cancel_run(ctx, run_id)
        if isinstance(result, tuple):
            return result
        return result, True

    def _authorized_run_record(
        self, ctx: ControlPlaneContext, action: str, run_id: str
    ) -> dict[str, Any]:
        get_run_value = getattr(self.submissions, "get_run", None)
        if not callable(get_run_value):
            raise ControlPlaneError(
                "Submission provider does not support run observation",
                code="PMCP501",
                status=501,
                title="Not Implemented",
            )
        get_run = cast(
            Callable[[ControlPlaneContext, str], dict[str, Any]], get_run_value
        )

        def probe() -> bool:
            try:
                get_run(ctx, run_id)
                return True
            except KeyError:
                return False
            except ControlPlaneError as exc:
                if exc.status == 404:
                    return False
                raise

        require_authorized_run(self.authorizer, ctx, action, run_id, probe_exists=probe)
        try:
            return get_run(ctx, run_id)
        except KeyError as exc:
            raise ControlPlaneError.not_found(f"Run {run_id!r} not found") from exc


__all__ = ["ManagedApplicationService"]


def _require_revision_selector(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ControlPlaneError(
            "revision_selector must be a non-empty string",
            code="PMCP400",
            status=400,
            title="Bad Request",
            type="etlantic.control_plane/bad_request",
        )
    return value
