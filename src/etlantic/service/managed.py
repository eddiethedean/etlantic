"""Authorized, transport-neutral commands for managed ETL submissions."""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
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
from etlantic.control_plane.action_jobs import (
    ConnectorActionKind,
    ConnectorProvisionCleanupRequest,
    connector_action_resources,
    parse_connector_action_request,
    verify_provision_parent,
)
from etlantic.control_plane.authz import require_authorized, require_authorized_run
from etlantic.control_plane.durable_models import ActionJobRecord, SubmissionRecord
from etlantic.control_plane.durable_protocols import DurableWorkStore
from etlantic.control_plane.errors import ControlPlaneError
from etlantic.control_plane.execution_envelope import ExecutionEnvelope
from etlantic.control_plane.input_resources import (
    InputResourceReference,
    InputResourceStore,
)
from etlantic.control_plane.models import (
    AcceptReceipt,
    AcceptResult,
    ControlPlaneContext,
)
from etlantic.control_plane.policy_gates import gate_pre_submit
from etlantic.control_plane.protocols import (
    Authorizer,
    DefinitionRepository,
    DefinitionResolution,
    EventStore,
    SubmissionStore,
)
from etlantic.control_plane.redaction import redact_control_plane_payload
from etlantic.control_plane.schedule_models import ScheduleRecord, firing_key
from etlantic.io_policy import SafeIoPolicy, read_text_safe
from etlantic.lifecycle.runtime import PipelineRuntime
from etlantic.plan.adaptive_model import AdaptivePipelinePlan, PlanDocument
from etlantic.plan.freeze import mutable_copy
from etlantic.plan.model import PipelinePlan
from etlantic.plan.serialize import plan_from_json, verify_plan_fingerprint
from etlantic.profile import Profile, resolve_profile
from etlantic.registry import PlanningContext
from etlantic.reports.model import PipelineRunReport
from etlantic.reports.retention import RUN_ARTIFACT_RETENTION_STATE_KEY
from etlantic.runtime.artifacts import artifact_storage_path
from etlantic.runtime.logging import redact_message
from etlantic.runtime.managed_execution import (
    legacy_managed_run_id,
    managed_artifact_workspace,
    managed_report_store,
    managed_run_id,
)
from etlantic.runtime.request import RunIntent, RunRequest
from etlantic.secrets.ref import SecretRef


def _mapping(value: object) -> Mapping[str, Any]:
    """Narrow untyped report payloads at the service boundary."""
    if isinstance(value, Mapping):
        return cast(Mapping[str, Any], value)
    return {}


def _connector_action_cursor_scope(ctx: ControlPlaneContext) -> str:
    """Fingerprint the complete owner context used by action receipt pages."""
    scope = [
        ctx.security_domain.domain_id,
        ctx.tenant.tenant_id,
        ctx.workspace.workspace_id,
        ctx.environment.name,
        ctx.resource_owner_id or ctx.principal.subject,
    ]
    return hashlib.sha256(
        json.dumps(scope, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


CONNECTOR_ACTION_TYPES = frozenset(
    {
        "connector.test",
        "connector.catalog",
        "connector.schema.inspect",
        "connector.preflight",
        "connector.preview",
        "connector.provision",
        "connector.provision.cleanup",
    }
)
MAX_ACTION_PAGE_SIZE = 100


@dataclass(frozen=True, slots=True)
class _PreparationControl:
    operation_id: str
    worker_id: str
    fencing_token: int
    is_cancelled: Callable[[], bool]
    durable_work: DurableWorkStore
    context: ControlPlaneContext

    def check(self) -> None:
        if self.is_cancelled():
            raise ControlPlaneError.conflict(
                "Run preparation was cancelled",
                code="PMCP409",
                extensions={"reason": "cancelled"},
            )

    def begin_acceptance(self) -> None:
        self.check()
        self.durable_work.mark_action_job_accepting(
            self.context,
            self.operation_id,
            worker_id=self.worker_id,
            fencing_token=self.fencing_token,
        )


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
    report_store_factory: Callable[[ControlPlaneContext], Any] | None = None
    policy: Any = None
    approvals: Any = None
    quotas: Any = None
    audit: Any = None
    attestations: Any = None
    require_attestations: bool = False
    planning_context_factory: (
        Callable[[ControlPlaneContext, Any], PlanningContext] | None
    ) = None
    input_resources: InputResourceStore | None = None
    input_resource_retention_seconds: int = 90 * 24 * 60 * 60
    run_artifact_retention_seconds: int | None = None
    action_job_max_deadline_seconds: int = 300
    artifact_root: str | Path | None = None
    schedule_parameter_resolver: (
        Callable[
            [ControlPlaneContext, Mapping[str, str]],
            Mapping[str, Mapping[str, Any]],
        ]
        | None
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
        revision_id = self._store_definition(ctx, definition_id, canonical)
        result = {
            "definition_id": definition_id,
            "fingerprint": definition.fingerprint or pipeline_fingerprint(definition),
            "document": canonical,
        }
        if revision_id is not None:
            result["revision_id"] = revision_id
        return result

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

    def submit_connector_action(
        self,
        ctx: ControlPlaneContext,
        action: str,
        request: Mapping[str, Any],
        *,
        idempotency_key: str,
        deadline_seconds: int = 30,
    ) -> dict[str, Any]:
        """Accept one explicitly authorized connector action for worker execution."""
        if action not in CONNECTOR_ACTION_TYPES:
            raise ControlPlaneError(
                "Unsupported connector action",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        if not idempotency_key.strip():
            raise ControlPlaneError(
                "Idempotency-Key is required for connector actions",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        if (
            type(deadline_seconds) is not int
            or deadline_seconds < 1
            or deadline_seconds > self.action_job_max_deadline_seconds
        ):
            raise ControlPlaneError(
                "Connector action deadline is outside the configured bounds",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        typed_action = cast(ConnectorActionKind, action)
        typed_request = parse_connector_action_request(typed_action, dict(request))
        for resource in connector_action_resources(typed_action, typed_request):
            require_authorized(
                self.authorizer,
                ctx,
                action,
                resource,
                resource_in_caller_scope=True,
            )
        if isinstance(typed_request, ConnectorProvisionCleanupRequest):
            parent = self.durable_work.get_action_job(
                ctx, typed_request.provision_action_id
            )
            verify_provision_parent(ctx, typed_request, parent)
        deadline_at = (
            (datetime.now(UTC) + timedelta(seconds=deadline_seconds))
            .isoformat()
            .replace("+00:00", "Z")
        )
        return self.durable_work.accept_action_job(
            ctx,
            action=action,
            idempotency_key=idempotency_key,
            request=typed_request.to_dict(),
            deadline_at=deadline_at,
        ).to_dict()

    def get_connector_action(
        self, ctx: ControlPlaneContext, action_id: str
    ) -> dict[str, Any]:
        """Read an authorized owner-scoped action receipt."""
        require_authorized(
            self.authorizer,
            ctx,
            "connector.action.read",
            f"connector-action:{action_id}",
            resource_in_caller_scope=False,
        )
        return self.durable_work.get_action_job(ctx, action_id).to_dict()

    def list_connector_actions(
        self,
        ctx: ControlPlaneContext,
        *,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """List receipts through stable owner-scoped cursor pagination."""
        require_authorized(
            self.authorizer,
            ctx,
            "connector.action.list",
            "connector-action:*",
            resource_in_caller_scope=True,
        )
        if type(limit) is not int or not 1 <= limit <= MAX_ACTION_PAGE_SIZE:
            raise ControlPlaneError(
                f"Action page limit must be between 1 and {MAX_ACTION_PAGE_SIZE}",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        after: tuple[str, str] | None = None
        cursor_scope = _connector_action_cursor_scope(ctx)
        if cursor is not None:
            try:
                if len(cursor) > 2048:
                    raise ValueError("cursor too long")
                decoded = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
                decoded_payload = json.loads(decoded)
                if not isinstance(decoded_payload, list):
                    raise ValueError("cursor payload is invalid")
                payload = cast(list[Any], decoded_payload)
                if len(payload) == 2 and all(isinstance(item, str) for item in payload):
                    # Continue accepting previously issued cursors; the query
                    # still applies the current full receipt scope.
                    after = (payload[0], payload[1])
                elif (
                    len(payload) == 4
                    and payload[0] == "etlantic.connector_action_cursor/1"
                    and payload[1] == cursor_scope
                    and isinstance(payload[2], str)
                    and isinstance(payload[3], str)
                ):
                    after = (payload[2], payload[3])
                else:
                    raise ValueError("invalid cursor payload")
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                raise ControlPlaneError(
                    "Invalid connector action cursor",
                    code="PMCP400",
                    status=400,
                    title="Bad Request",
                    type="etlantic.control_plane/bad_request",
                ) from exc
        records = self.durable_work.list_action_jobs(ctx, after=after, limit=limit + 1)
        has_more = len(records) > limit
        page = records[:limit]
        next_cursor = None
        if has_more and page:
            last = page[-1]
            encoded = json.dumps(
                [
                    "etlantic.connector_action_cursor/1",
                    cursor_scope,
                    last.created_at,
                    last.action_id,
                ],
                separators=(",", ":"),
            ).encode("utf-8")
            next_cursor = base64.urlsafe_b64encode(encoded).decode("ascii").rstrip("=")
        return {
            "schema": "etlantic.control_plane.action_job_page/1",
            "items": [record.to_dict() for record in page],
            "next_cursor": next_cursor,
            "has_more": has_more,
        }

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
        revision_id = self._store_definition(ctx, definition_id, canonical)
        response = {
            "definition_id": definition_id,
            "fingerprint": result.fingerprint,
            "document": canonical,
        }
        if revision_id is not None:
            response["revision_id"] = revision_id
        return response

    def validate_definition(
        self,
        ctx: ControlPlaneContext,
        definition_id: str,
        *,
        revision_selector: str = "current",
    ) -> dict[str, Any]:
        """Run pure static validation without resolving credentials or doing I/O."""
        revision_selector = _require_revision_selector(revision_selector)
        require_authorized(
            self.authorizer,
            ctx,
            "definition.validate",
            f"definition:{definition_id}",
            resource_in_caller_scope=False,
        )
        resolution = self._resolve_definition_revision(
            ctx, definition_id, revision_selector
        )
        document = resolution.document
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
            "revision_id": resolution.revision_id,
            "diagnostics": [item.to_dict() for item in report.diagnostics],
            "metadata": {"revision_id": resolution.revision_id},
        }

    def plan_definition(
        self,
        ctx: ControlPlaneContext,
        definition_id: str,
        *,
        request: RunRequest | Mapping[str, Any] | None = None,
        revision_selector: str = "current",
    ) -> dict[str, Any]:
        """Build a deterministic verified plan without executing providers."""
        revision_selector = _require_revision_selector(revision_selector)
        require_authorized(
            self.authorizer,
            ctx,
            "definition.plan",
            f"definition:{definition_id}",
            resource_in_caller_scope=False,
        )
        resolution = self._resolve_definition_revision(
            ctx, definition_id, revision_selector
        )
        document = resolution.document
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
        verify_plan_fingerprint(plan)
        if isinstance(plan, AdaptivePipelinePlan):
            self._admit_adaptive_plan(plan, typed_request, profile=profile)
        self._authorize_plan_resources(ctx, plan, action="definition.plan")
        self._authorize_input_resources(ctx, plan)
        return {
            "ok": True,
            "definition_id": definition_id,
            "fingerprint": plan.fingerprint,
            "revision_id": resolution.revision_id,
            "plan": plan.to_dict(),
        }

    def pin_schedule_definition_revision(
        self,
        ctx: ControlPlaneContext,
        definition_id: str,
        *,
        revision_selector: str = "current",
    ) -> tuple[str, str]:
        """Resolve the immutable definition/profile selected by a schedule."""
        revision_selector = _require_revision_selector(revision_selector)
        require_authorized(
            self.authorizer,
            ctx,
            "run.submit",
            f"definition:{definition_id}",
            resource_in_caller_scope=False,
        )
        profile = resolve_profile(self.profile, allow_adhoc_profile=False)
        resolution = self._resolve_definition_revision(
            ctx, definition_id, revision_selector
        )
        self._decode_definition(resolution.document)
        return resolution.revision_id, profile.name

    def validate_schedule_references(
        self,
        parameter_refs: Mapping[str, Any],
        secret_refs: Mapping[str, Any],
    ) -> dict[str, dict[str, Any]]:
        """Validate public schedule refs without resolving secret values."""
        profile = resolve_profile(self.profile, allow_adhoc_profile=False)
        if parameter_refs and self.schedule_parameter_resolver is None:
            raise ControlPlaneError(
                "Managed schedule parameter references require a configured resolver",
                code="PMCP501",
                status=501,
                title="Not Implemented",
                type="etlantic.control_plane/not_implemented",
            )
        for target, reference in cast(Mapping[object, Any], parameter_refs).items():
            if (
                not isinstance(target, str)
                or not target.strip()
                or not isinstance(reference, str)
                or not reference.strip()
            ):
                raise ControlPlaneError(
                    "Schedule parameter references must map non-empty targets to references",
                    code="PMCP400",
                    status=400,
                    title="Bad Request",
                    type="etlantic.control_plane/bad_request",
                )
        normalized_secrets: dict[str, dict[str, Any]] = {}
        for alias, raw_ref in cast(Mapping[object, Any], secret_refs).items():
            if (
                not isinstance(alias, str)
                or not alias.strip()
                or not isinstance(raw_ref, Mapping)
            ):
                raise ControlPlaneError(
                    "Schedule secret references must be named SecretRef objects",
                    code="PMCP400",
                    status=400,
                    title="Bad Request",
                    type="etlantic.control_plane/bad_request",
                )
            try:
                ref_payload = {
                    str(key): value
                    for key, value in cast(Mapping[object, Any], raw_ref).items()
                }
                ref = SecretRef.from_dict(ref_payload)
            except (KeyError, TypeError, ValueError) as exc:
                raise ControlPlaneError(
                    "Schedule secret reference is invalid",
                    code="PMCP400",
                    status=400,
                    title="Bad Request",
                    type="etlantic.control_plane/bad_request",
                ) from exc
            if ref.version == "current":
                raise ControlPlaneError(
                    "Managed schedule secret references must pin an immutable version",
                    code="PMCP400",
                    status=400,
                    title="Bad Request",
                    type="etlantic.control_plane/bad_request",
                )
            if ref.provider not in set(profile.secret_providers.values()) and (
                ref.provider not in profile.secret_providers
            ):
                raise ControlPlaneError(
                    "Managed schedule secret provider is outside the active profile",
                    code="PMCP403",
                    status=403,
                    title="Forbidden",
                    type="etlantic.control_plane/forbidden",
                )
            normalized_secrets[alias] = ref.to_dict()
        return normalized_secrets

    def submit_scheduled_run(
        self,
        ctx: ControlPlaneContext,
        schedule: ScheduleRecord,
        nominal_fire_time: str,
    ) -> tuple[str, str]:
        """Submit one occurrence through the standard managed admission path.

        The stable occurrence key and firing snapshot make a process restart
        reuse the revision, workload identity, parameter policy and pinned
        SecretRef set selected for this occurrence.
        """
        prepared = schedule
        if prepared.occurrence_inputs is None:
            prepared = self.prepare_scheduled_occurrence(
                ctx, schedule, nominal_fire_time
            )
        if prepared.definition_revision_id is None:
            raise ControlPlaneError.conflict(
                "Managed schedule occurrence has no selected definition revision"
            )
        occurrence_inputs = cast(Mapping[str, Any], prepared.occurrence_inputs)
        profile = cast(Profile, occurrence_inputs["profile"])
        if prepared.profile_name != profile.name:
            raise ControlPlaneError.conflict(
                "Managed schedule profile differs from the active managed profile"
            )
        occurrence = firing_key(
            prepared.schedule_id, prepared.revision_id, nominal_fire_time
        )
        idempotency_key = (
            "schedule-" + hashlib.sha256(occurrence.encode("utf-8")).hexdigest()
        )
        receipt = self.submit_run(
            ctx,
            prepared.definition_id,
            idempotency_key=idempotency_key,
            request=RunRequest(
                parameter_overrides=cast(
                    Mapping[str, Mapping[str, Any]],
                    occurrence_inputs["parameter_overrides"],
                )
            ),
            revision_selector=prepared.definition_revision_id,
            _profile_override=profile,
        )
        submission = self.durable_work.get_submission(ctx, receipt.submission_id)
        if not submission.input_snapshot:
            raise ControlPlaneError.conflict(
                "Managed schedule submission has no verified execution snapshot"
            )
        return submission.submission_id, submission.plan_fingerprint

    def prepare_scheduled_occurrence(
        self,
        ctx: ControlPlaneContext,
        schedule: ScheduleRecord,
        nominal_fire_time: str,
        existing_firing: Any = None,
    ) -> ScheduleRecord:
        """Bind occurrence-time selection, identity and input policy once.

        The returned ``occurrence_snapshot`` contains only identifiers and
        fingerprints suitable for durable schedule metadata. Resolved
        parameter values and the profile carrying SecretRef objects live only
        on the runtime-only ``occurrence_inputs`` field and are accepted into
        the execution envelope after the firing is durably claimed.
        """
        require_authorized(
            self.authorizer,
            ctx,
            "run.submit",
            f"definition:{schedule.definition_id}",
            resource_in_caller_scope=False,
        )
        if (
            schedule.workload_identity is not None
            and ctx.principal != schedule.workload_identity
        ):
            raise ControlPlaneError.not_found("schedule workload identity not found")
        prior_metadata: Mapping[str, Any] = (
            cast(Mapping[str, Any], existing_firing.metadata)
            if existing_firing is not None
            else {}
        )
        prior_principal = prior_metadata.get("trigger_principal")
        if prior_principal is not None and prior_principal != ctx.principal.to_dict():
            raise ControlPlaneError.conflict(
                "Schedule occurrence belongs to a different workload identity"
            )

        prior_revision = prior_metadata.get("selected_definition_revision_id")
        if isinstance(prior_revision, str) and prior_revision:
            selector = prior_revision
        elif schedule.revision_policy == "latest-approved":
            selector = "latest-approved"
        else:
            selector = schedule.definition_revision_id or ""
        if not selector:
            raise ControlPlaneError.conflict(
                "Pinned managed schedule has no definition revision"
            )
        resolution = self._resolve_definition_revision(
            ctx, schedule.definition_id, selector
        )
        self._decode_definition(resolution.document)

        parameter_overrides: dict[str, dict[str, Any]] = {}
        if schedule.parameter_refs:
            resolver = self.schedule_parameter_resolver
            if resolver is None:
                raise ControlPlaneError(
                    "Managed schedule parameter references require a configured resolver",
                    code="PMCP501",
                    status=501,
                    title="Not Implemented",
                    type="etlantic.control_plane/not_implemented",
                )
            resolved: Any = resolver(ctx, schedule.parameter_refs)
            if not isinstance(resolved, Mapping):
                raise ControlPlaneError.conflict(
                    "Schedule parameter resolver returned an invalid snapshot"
                )
            raw_parameters: dict[str, dict[str, Any]] = {}
            resolved_values = cast(Mapping[object, Any], resolved)
            for node, values in resolved_values.items():
                if not isinstance(node, str) or not isinstance(values, Mapping):
                    raise ControlPlaneError.conflict(
                        "Schedule parameter resolver returned an invalid snapshot"
                    )
                values_mapping = cast(Mapping[object, Any], values)
                normalized_values = {
                    key: value
                    for key, value in values_mapping.items()
                    if isinstance(key, str)
                }
                if len(normalized_values) != len(values_mapping):
                    raise ControlPlaneError.conflict(
                        "Schedule parameter resolver returned an invalid snapshot"
                    )
                raw_parameters[node] = normalized_values
            if redact_control_plane_payload(raw_parameters) != raw_parameters:
                raise ControlPlaneError(
                    "Resolved scheduled parameters contain secret-like values",
                    code="PMCP400",
                    status=400,
                    title="Bad Request",
                    type="etlantic.control_plane/bad_request",
                )
            try:
                parameter_bytes = json.dumps(
                    raw_parameters,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                    allow_nan=False,
                ).encode("utf-8")
            except (TypeError, ValueError) as exc:
                raise ControlPlaneError(
                    "Resolved scheduled parameters are not JSON-safe",
                    code="PMCP400",
                    status=400,
                    title="Bad Request",
                    type="etlantic.control_plane/bad_request",
                ) from exc
            parameter_overrides = raw_parameters
            parameter_fingerprint = hashlib.sha256(parameter_bytes).hexdigest()
        else:
            parameter_fingerprint = hashlib.sha256(b"{}").hexdigest()

        profile = resolve_profile(self.profile, allow_adhoc_profile=False)
        if schedule.profile_name != profile.name:
            raise ControlPlaneError.conflict(
                "Managed schedule profile differs from the active managed profile"
            )
        resolved_secret_refs: dict[str, SecretRef] = {}
        for alias, raw_ref in schedule.secret_refs.items():
            if not isinstance(raw_ref, Mapping):
                raise ControlPlaneError.conflict(
                    "Managed schedules require structured SecretRef values"
                )
            ref = SecretRef.from_dict(dict(raw_ref))
            if ref.version == "current":
                raise ControlPlaneError.conflict(
                    "Managed schedule secret references must pin an immutable version"
                )
            if ref.provider not in set(profile.secret_providers.values()) and (
                ref.provider not in profile.secret_providers
            ):
                raise ControlPlaneError.conflict(
                    "Managed schedule secret provider is outside the active profile"
                )
            resolved_secret_refs[alias] = ref
        profile_document = profile.to_dict()
        profile_document["secrets"] = {
            **{alias: ref.to_dict() for alias, ref in profile.secrets.items()},
            **{alias: ref.to_dict() for alias, ref in resolved_secret_refs.items()},
        }
        effective_profile = Profile.from_dict(profile_document)
        secret_payload = {
            alias: ref.to_dict() for alias, ref in sorted(resolved_secret_refs.items())
        }
        secret_fingerprint = hashlib.sha256(
            json.dumps(
                secret_payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()
        selection_policy = {
            "revision_policy": schedule.revision_policy,
            "selected_revision_id": resolution.revision_id,
            "parameter_refs": dict(schedule.parameter_refs),
            "parameter_fingerprint": parameter_fingerprint,
            "secret_fingerprint": secret_fingerprint,
            "trigger_principal": ctx.principal.to_dict(),
            "schedule_policy_fingerprint": schedule.policy_fingerprint,
        }
        policy_fingerprint = hashlib.sha256(
            json.dumps(
                selection_policy,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()
        snapshot = {
            "selected_definition_revision_id": resolution.revision_id,
            "trigger_principal": ctx.principal.to_dict(),
            "parameter_fingerprint": parameter_fingerprint,
            "reference_fingerprint": secret_fingerprint,
            "policy_fingerprint": policy_fingerprint,
        }
        if existing_firing is not None:
            for key, value in snapshot.items():
                expected = prior_metadata.get(key)
                if expected is not None and expected != value:
                    raise ControlPlaneError.conflict(
                        "Schedule occurrence policy changed after its durable claim",
                        extensions={"field": key},
                    )
        return replace(
            schedule,
            definition_revision_id=resolution.revision_id,
            policy_fingerprint=policy_fingerprint,
            occurrence_snapshot=snapshot,
            occurrence_inputs={
                "parameter_overrides": parameter_overrides,
                "profile": effective_profile,
            },
        )

    def start_run_preparation(
        self,
        ctx: ControlPlaneContext,
        definition_id: str,
        *,
        idempotency_key: str,
        request: RunRequest | Mapping[str, Any] | None = None,
        revision_selector: str = "current",
        deadline_seconds: int = 300,
    ) -> dict[str, Any]:
        """Persist an owner-scoped preparation operation for managed workers."""
        if not idempotency_key.strip():
            raise ControlPlaneError(
                "Idempotency-Key is required for run preparation",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        if (
            type(deadline_seconds) is not int
            or deadline_seconds < 1
            or deadline_seconds > self.action_job_max_deadline_seconds
        ):
            raise ControlPlaneError(
                "Preparation deadline is outside the configured bounds",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        revision_selector = _require_revision_selector(revision_selector)
        require_authorized(
            self.authorizer,
            ctx,
            "run.submit",
            f"definition:{definition_id}",
            resource_in_caller_scope=False,
        )
        typed_request = self._coerce_request(request)
        request_document = typed_request.to_dict()
        safe_request = redact_control_plane_payload(request_document)
        if safe_request != request_document:
            raise ControlPlaneError(
                "Run preparation cannot persist secret-like request values",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        profile = resolve_profile(self.profile, allow_adhoc_profile=False)
        intent = {
            "definition_id": definition_id,
            "revision_selector": revision_selector,
            "profile_name": profile.name,
            "run_request": request_document,
        }
        prior = self.durable_work.get_action_job_by_idempotency(
            ctx, action="run.prepare", idempotency_key=idempotency_key
        )
        if prior is not None:
            try:
                accepted_intent = json.loads(prior.request_json)
            except (TypeError, ValueError) as exc:
                raise ControlPlaneError.conflict(
                    "Preparation operation has an invalid stored intent"
                ) from exc
            if not isinstance(accepted_intent, Mapping):
                raise ControlPlaneError.conflict(
                    "Preparation idempotency key reuse has different inputs"
                )
            stored_intent = cast(Mapping[str, Any], accepted_intent)
            if any(stored_intent.get(key) != value for key, value in intent.items()):
                raise ControlPlaneError.conflict(
                    "Preparation idempotency key reuse has different inputs"
                )
            return self._preparation_operation_payload(prior)

        resolution = self._resolve_definition_revision(
            ctx, definition_id, revision_selector
        )
        operation_request = {
            **intent,
            "definition_revision_id": resolution.revision_id,
        }
        deadline_at = (
            (datetime.now(UTC) + timedelta(seconds=deadline_seconds))
            .isoformat()
            .replace("+00:00", "Z")
        )
        record = self.durable_work.accept_action_job(
            ctx,
            action="run.prepare",
            idempotency_key=idempotency_key,
            request=operation_request,
            deadline_at=deadline_at,
        )
        return self._preparation_operation_payload(record)

    def get_run_preparation(
        self, ctx: ControlPlaneContext, operation_id: str
    ) -> dict[str, Any]:
        require_authorized(
            self.authorizer,
            ctx,
            "run.read",
            f"preparation:{operation_id}",
            resource_in_caller_scope=False,
        )
        record = self.durable_work.get_action_job(ctx, operation_id)
        if record.action != "run.prepare":
            raise ControlPlaneError.not_found("Preparation operation not found")
        return self._preparation_operation_payload(record)

    def cancel_run_preparation(
        self, ctx: ControlPlaneContext, operation_id: str
    ) -> dict[str, Any]:
        require_authorized(
            self.authorizer,
            ctx,
            "run.cancel",
            f"preparation:{operation_id}",
            resource_in_caller_scope=False,
        )
        record = self.durable_work.cancel_action_job(ctx, operation_id)
        return self._preparation_operation_payload(record)

    def execute_run_preparation(
        self,
        ctx: ControlPlaneContext,
        operation_id: str,
        *,
        worker_id: str,
        fencing_token: int,
        request: Mapping[str, Any],
        is_cancelled: Callable[[], bool],
    ) -> dict[str, Any]:
        """Resume a durable operation under the worker's current fence."""
        record = self.durable_work.get_action_job(ctx, operation_id)
        if (
            record.action != "run.prepare"
            or record.worker_id != worker_id
            or (record.fencing_token != fencing_token)
        ):
            raise ControlPlaneError.conflict("Preparation worker fence is stale")
        try:
            intent = json.loads(record.request_json)
        except (TypeError, ValueError) as exc:
            raise ControlPlaneError.conflict(
                "Preparation operation has an invalid stored intent"
            ) from exc
        if not isinstance(intent, Mapping):
            raise ControlPlaneError.conflict(
                "Preparation operation has an invalid stored intent"
            )
        stored_intent = cast(Mapping[str, Any], intent)
        if any(
            request.get(key) != stored_intent.get(key)
            for key in (
                "definition_id",
                "definition_revision_id",
                "profile_name",
                "run_request",
            )
        ):
            raise ControlPlaneError.conflict(
                "Preparation worker input differs from its durable intent"
            )
        profile = resolve_profile(self.profile, allow_adhoc_profile=False)
        if profile.name != stored_intent.get("profile_name"):
            raise ControlPlaneError.conflict(
                "Preparation profile changed after operation acceptance"
            )
        control = _PreparationControl(
            operation_id=operation_id,
            worker_id=worker_id,
            fencing_token=fencing_token,
            is_cancelled=is_cancelled,
            durable_work=self.durable_work,
            context=ctx,
        )
        receipt = self.submit_run(
            ctx,
            str(stored_intent["definition_id"]),
            idempotency_key=f"preparation-{operation_id}",
            request=cast(Mapping[str, Any], stored_intent["run_request"]),
            revision_selector=str(stored_intent["definition_revision_id"]),
            _preparation_control=control,
        )
        return receipt.to_dict()

    @staticmethod
    def _preparation_operation_payload(record: ActionJobRecord) -> dict[str, Any]:
        if record.action != "run.prepare":
            raise ControlPlaneError.not_found("Preparation operation not found")
        return {
            **record.to_dict(),
            "schema": "etlantic.control_plane.preparation_operation/1",
            "operation_id": record.action_id,
        }

    def submit_run(
        self,
        ctx: ControlPlaneContext,
        definition_id: str,
        *,
        idempotency_key: str,
        request: RunRequest | Mapping[str, Any] | None = None,
        revision_selector: str = "current",
        _preparation_control: _PreparationControl | None = None,
        _profile_override: Profile | None = None,
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
        profile = _profile_override or resolve_profile(
            self.profile, allow_adhoc_profile=False
        )
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
                    run_id=prior_receipt.resource_id
                    or legacy_managed_run_id(ctx, idempotency_key),
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
                resource_id=prior_durable.run_id
                or legacy_managed_run_id(ctx, idempotency_key),
                submission_id=prior_durable.submission_id,
                operation="run.submit",
            )
            return receipt_result.receipt

        if _preparation_control is not None:
            _preparation_control.check()
        resolution = self._resolve_definition_revision(
            ctx, definition_id, revision_selector
        )
        if _preparation_control is not None:
            _preparation_control.check()
        document = resolution.document
        revision_id = resolution.revision_id
        definition = self._decode_definition(document)
        planning_context = self._planning_context(ctx, profile)
        validation = validate_pipeline_like(
            definition, context=planning_context, profile=profile
        )
        if _preparation_control is not None:
            _preparation_control.check()
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
        if _preparation_control is not None:
            _preparation_control.check()
        verify_plan_fingerprint(plan)
        if isinstance(plan, AdaptivePipelinePlan):
            self._admit_adaptive_plan(plan, typed_request, profile=profile)
        self._authorize_plan_resources(ctx, plan, action="run.submit")
        if _preparation_control is not None:
            _preparation_control.check()
        input_lease_id = self._protect_input_resources(
            ctx,
            plan,
            operation="run.submit",
            idempotency_key=idempotency_key,
        )
        if isinstance(plan, PipelinePlan):
            plugin_versions = dict(plan.plugin_versions)
        else:
            from etlantic.runtime.adaptive_support import support_row_for

            support_row = support_row_for(plan)
            plugin_versions = (
                dict(support_row.version_requirements)
                if support_row is not None
                else {}
            )
        plugin_fingerprint = (
            hashlib.sha256(
                json.dumps(
                    plugin_versions,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            if plugin_versions
            else None
        )
        resource_versions = self._resource_versions(plan)
        effective_fingerprint = ExecutionEnvelope.create(
            definition_id=definition_id,
            revision_selector=revision_selector,
            revision_id=revision_id,
            definition=definition,
            plan=plan,
            profile_name=profile.name,
            request=typed_request,
            plugin_fingerprint=plugin_fingerprint,
            resource_versions=resource_versions,
        ).effective_fingerprint
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
                effective_fingerprint=effective_fingerprint,
                revision_id=revision_id,
                quota_idempotency_key=self._quota_idempotency_key(ctx, idempotency_key),
                plugin_fingerprints=(
                    [plugin_fingerprint] if plugin_fingerprint is not None else None
                ),
                require_policy=self.policy is not None,
                require_attestations=self.require_attestations,
            )
            policy_fingerprint = (
                decision.policy_fingerprint if decision is not None else None
            )
        if _preparation_control is not None:
            try:
                _preparation_control.check()
            except Exception:
                self._release_input_lease(ctx, input_lease_id)
                raise
        envelope = ExecutionEnvelope.create(
            definition_id=definition_id,
            revision_selector=revision_selector,
            revision_id=revision_id,
            definition=definition,
            plan=plan,
            profile_name=profile.name,
            request=typed_request,
            plugin_fingerprint=plugin_fingerprint,
            policy_fingerprint=policy_fingerprint,
            resource_versions=resource_versions,
            evidence_refs=(
                {"input_resource_lease_id": input_lease_id}
                if input_lease_id is not None
                else None
            ),
        )
        payload = self._acceptance_payload(envelope)
        if _preparation_control is not None:
            try:
                _preparation_control.begin_acceptance()
            except Exception:
                self._release_input_lease(ctx, input_lease_id)
                raise
        try:
            receipt_result = self.submissions.accept(
                ctx,
                idempotency_key=idempotency_key,
                payload=payload,
                resource_type="run",
                resource_id=managed_run_id(ctx, idempotency_key),
                operation="run.submit",
            )
        except Exception as exc:
            # CP1 acceptance is itself durable. Recover its acknowledgement
            # loss by the same scoped idempotency key before rejecting the
            # command or trying to create another receipt.
            prior_receipt: AcceptReceipt | None = None
            prior_payload: Mapping[str, Any] | None = None
            candidate_receipt: AcceptReceipt | None = None
            candidate_payload: Mapping[str, Any] | None = None
            try:
                candidate_receipt = self.submissions.lookup_idempotency(
                    ctx, idempotency_key, operation="run.submit"
                )
                candidate_payload = self.submissions.lookup_idempotency_payload(
                    ctx, idempotency_key, operation="run.submit"
                )
            except Exception:
                # Keep both unset when either read fails; a partial lookup
                # cannot prove that the accepted snapshot matches.
                candidate_receipt = None
                candidate_payload = None
            if candidate_receipt is not None:
                prior_receipt = candidate_receipt
                prior_payload = candidate_payload
            if prior_receipt is not None:
                prior_envelope = self._envelope_from_payload(prior_payload)
                if prior_envelope.to_json() != envelope.to_json():
                    raise ControlPlaneError.conflict(
                        "Idempotency key reuse with a different accepted snapshot"
                    ) from exc
                receipt_result = AcceptResult(receipt=prior_receipt, created=False)
            else:
                if isinstance(exc, ControlPlaneError) and exc.status < 500:
                    raise
                raise ControlPlaneError(
                    "CP1 acceptance acknowledgement is uncertain; retry the same "
                    "idempotency key to reconcile",
                    code="PMCP503",
                    status=503,
                    title="Service Unavailable",
                    type="etlantic.control_plane/unavailable",
                    extensions={
                        "idempotency_key": idempotency_key,
                        "acceptance_uncertain": True,
                    },
                ) from exc
        try:
            self._accept_durable(
                ctx,
                idempotency_key=idempotency_key,
                envelope=envelope,
                submission_id=receipt_result.receipt.submission_id,
                run_id=receipt_result.receipt.resource_id
                or managed_run_id(ctx, idempotency_key),
            )
        except Exception as exc:
            # Durable acceptance and its outbox are committed atomically by
            # the execution store, but the acknowledgement can be lost after
            # that commit. Reconcile by the stable command identity before
            # compensating the separately durable CP1 receipt.
            durable_receipt: SubmissionRecord | None = None
            with suppress(Exception):
                durable_receipt = self.durable_work.get_submission_by_idempotency(
                    ctx,
                    idempotency_key=idempotency_key,
                    operation="run.submit",
                )
            # A failed reconciliation read leaves the commit outcome unknown.
            # Preserve the discoverable CP1 receipt so a caller can retry the
            # same idempotency key and reconcile later.
            if durable_receipt is not None:
                if (
                    durable_receipt.submission_id
                    != receipt_result.receipt.submission_id
                    or durable_receipt.input_snapshot != envelope.to_json()
                ):
                    raise ControlPlaneError.conflict(
                        "Durable acceptance conflicts with the CP1 receipt"
                    ) from exc
                # A matching durable row proves that acceptance committed;
                # continue to return the original CP1 receipt.
            else:
                compensated = False
                # Only an explicit client-side control-plane rejection proves
                # that no durable command was accepted. Transient/server
                # errors may have happened after commit and must not cancel a
                # runnable outbox record.
                definite_rejection = (
                    isinstance(exc, ControlPlaneError) and exc.status < 500
                )
                if receipt_result.created and definite_rejection:
                    try:
                        record, changed = self._cancel_cp1(
                            ctx, receipt_result.receipt.resource_id
                        )
                        compensated = changed or record.get("status") == "cancelled"
                        if compensated:
                            self._release_input_lease(ctx, input_lease_id)
                    except Exception:
                        pass
                if isinstance(exc, ControlPlaneError) and definite_rejection:
                    raise
                raise ControlPlaneError(
                    "Durable execution acceptance acknowledgement is uncertain; "
                    "retry the same idempotency key to reconcile",
                    code="PMCP503",
                    status=503,
                    title="Service Unavailable",
                    type="etlantic.control_plane/unavailable",
                    extensions={
                        "submission_id": receipt_result.receipt.submission_id,
                        "acceptance_uncertain": True,
                        "compensated": compensated,
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
        adaptive_plan = False
        if submission_id:
            try:
                durable_record = self.durable_work.get_submission(ctx, submission_id)
                status = durable_record.status
                if durable_record.input_snapshot:
                    adaptive_plan = (
                        self._parse_envelope(
                            durable_record.input_snapshot
                        ).plan_document.get("schema")
                        == "etlantic.plan/2"
                    )
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
        rerun_decision = self.authorizer.authorize(ctx, "run.rerun", f"run:{run_id}")
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
        replay_decision = self.authorizer.authorize(ctx, "run.replay", f"run:{run_id}")
        if not replay_decision.allowed:
            replay_reason: str | None = "not_authorized"
        elif status not in {"completed", "failed", "cancelled"}:
            replay_reason = "non_replayable_state"
        elif not submission_id or durable_record is None:
            replay_reason = "durable_state_unavailable"
        elif not durable_record.input_snapshot:
            replay_reason = "unverified_execution_envelope"
        elif adaptive_plan:
            replay_reason = "adaptive_policy_unsupported"
        else:
            replay_reason = self._rerun_block_reason(ctx, submission_id)
        resume_decision = self.authorizer.authorize(ctx, "run.resume", f"run:{run_id}")
        if not resume_decision.allowed:
            resume_reason: str | None = "not_authorized"
        elif status not in {"failed", "cancelled"}:
            resume_reason = "non_resumable_state"
        elif not submission_id or durable_record is None:
            resume_reason = "durable_state_unavailable"
        elif not durable_record.input_snapshot:
            resume_reason = "unverified_execution_envelope"
        elif adaptive_plan:
            resume_reason = "adaptive_policy_unsupported"
        else:
            resume_reason = self._retry_block_reason(ctx, submission_id)
        repair_decision = self.authorizer.authorize(ctx, "run.repair", f"run:{run_id}")
        if not repair_decision.allowed:
            repair_reason: str | None = "not_authorized"
        elif status not in {"completed", "failed", "cancelled"}:
            repair_reason = "non_repairable_state"
        elif not submission_id or durable_record is None:
            repair_reason = "durable_state_unavailable"
        elif not durable_record.input_snapshot:
            repair_reason = "unverified_execution_envelope"
        elif adaptive_plan:
            repair_reason = "adaptive_policy_unsupported"
        else:
            repair_reason = self._partition_action_block_reason(
                durable_record.input_snapshot, operation="repair"
            )
            if repair_reason is None:
                repair_reason = self._rerun_block_reason(ctx, submission_id)
        backfill_decision = self.authorizer.authorize(
            ctx, "run.backfill", f"run:{run_id}"
        )
        if not backfill_decision.allowed:
            backfill_reason: str | None = "not_authorized"
        elif status not in {"completed", "failed", "cancelled"}:
            backfill_reason = "non_backfillable_state"
        elif not submission_id or durable_record is None:
            backfill_reason = "durable_state_unavailable"
        elif not durable_record.input_snapshot:
            backfill_reason = "unverified_execution_envelope"
        elif adaptive_plan:
            backfill_reason = "adaptive_policy_unsupported"
        else:
            backfill_reason = self._partition_action_block_reason(
                durable_record.input_snapshot, operation="backfill"
            )
            if backfill_reason is None:
                backfill_reason = self._rerun_block_reason(ctx, submission_id)
        return {
            "schema": "etlantic.control_plane.run_actions/1",
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
                {
                    "name": "repair",
                    "allowed": repair_reason is None,
                    "reason": repair_reason,
                },
                {
                    "name": "backfill",
                    "allowed": backfill_reason is None,
                    "reason": backfill_reason,
                },
                {
                    "name": "resume",
                    "allowed": resume_reason is None,
                    "reason": resume_reason,
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
        if parent_envelope.plan_document.get("schema") == "etlantic.plan/2":
            raise ControlPlaneError.conflict(
                "Adaptive execution does not support replay intent",
                extensions={"reason": "adaptive_policy_unsupported"},
            )
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

    def resume_run(
        self,
        ctx: ControlPlaneContext,
        run_id: str,
        *,
        idempotency_key: str,
        checkpoint_id: str,
    ) -> AcceptReceipt:
        """Resume a terminal managed run from a verified durable checkpoint.

        The new submission retains a distinct run identity and attempt history.
        Named runtime artifacts use the parent run's scoped artifact workspace,
        allowing qualified checkpoint/reuse operators to find their persisted
        values without sharing report or submission identities.
        """
        if not idempotency_key.strip():
            raise ControlPlaneError(
                "Idempotency-Key is required for managed resume",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        if not checkpoint_id.strip():
            raise ControlPlaneError(
                "checkpoint_id is required for managed resume",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        record = self._authorized_run_record(ctx, "run.resume", run_id)
        parent_submission_id = str(record.get("submission_id") or "")
        if not parent_submission_id:
            raise ControlPlaneError.conflict(
                "Run record has no durable submission identity"
            )
        parent = self.durable_work.get_submission(ctx, parent_submission_id)
        if parent.status not in {"failed", "cancelled"}:
            raise ControlPlaneError.conflict(
                "Only failed or cancelled runs can resume from a checkpoint"
            )
        if not parent.input_snapshot:
            raise ControlPlaneError.conflict(
                "Legacy accepted work has no verified execution envelope"
            )
        prior_receipt = self.submissions.lookup_idempotency(
            ctx, idempotency_key, operation="run.resume"
        )
        prior_durable = self.durable_work.get_submission_by_idempotency(
            ctx, idempotency_key=idempotency_key, operation="run.resume"
        )
        if prior_receipt is None and prior_durable is None:
            resume_block = self._retry_block_reason(ctx, parent_submission_id)
            if resume_block is not None:
                raise ControlPlaneError.conflict(
                    "Resume is blocked until the prior execution effect is reconciled",
                    extensions={"reason": resume_block},
                )
        # This validates checkpoint scope and schema lineage before admitting
        # the child. The plan record itself is advisory; execution is the
        # durable child submission created below.
        self.durable_work.plan_resume(
            ctx, parent_submission_id, checkpoint_id=checkpoint_id
        )
        envelope = self._parse_envelope(parent.input_snapshot)
        if envelope.plan_document.get("schema") == "etlantic.plan/2":
            raise ControlPlaneError.conflict(
                "Adaptive execution does not support resume intent",
                extensions={"reason": "adaptive_policy_unsupported"},
            )
        request = RunRequest.from_dict(dict(envelope.run_request))
        resume_request = RunRequest(
            selection=request.selection,
            intent=RunIntent.RESUME,
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
        resumed = envelope.with_request(resume_request)
        envelope_data = resumed.to_dict()
        evidence_refs = dict(envelope_data.get("evidence_refs") or {})
        evidence_refs.update(
            {
                "command": "resume",
                "parent_run_id": run_id,
                "parent_submission_id": parent_submission_id,
                "checkpoint_id": checkpoint_id,
                "artifact_parent_run_id": run_id,
            }
        )
        resumed = ExecutionEnvelope.from_dict(
            {**envelope_data, "evidence_refs": evidence_refs}
        )
        return self._accept_child_run(
            ctx,
            idempotency_key=idempotency_key,
            operation="run.resume",
            envelope=resumed,
            parent_run_id=run_id,
            parent_submission_id=parent_submission_id,
        )

    def repair_run(
        self,
        ctx: ControlPlaneContext,
        run_id: str,
        *,
        idempotency_key: str,
        invalidated_partition_ids: Mapping[str, Sequence[str]],
        checkpoint_id: str | None = None,
        reusable_artifact_ids: Sequence[str] = (),
    ) -> AcceptReceipt:
        """Accept a bounded partition repair from a verified parent run.

        Every source and sink in the accepted selection must declare the
        corresponding partition read/write capability. The worker then calls
        the provider's explicit partition methods; ordinary whole-resource
        reads and writes are never used as a fallback.
        """
        return self._partition_child_run(
            ctx,
            run_id,
            idempotency_key=idempotency_key,
            operation="run.repair",
            partition_ids_by_node=invalidated_partition_ids,
            checkpoint_id=checkpoint_id,
            reusable_artifact_ids=reusable_artifact_ids,
        )

    def backfill_run(
        self,
        ctx: ControlPlaneContext,
        run_id: str,
        *,
        idempotency_key: str,
        partition_ids: Mapping[str, Sequence[str]],
        checkpoint_id: str | None = None,
    ) -> AcceptReceipt:
        """Accept a bounded partition backfill from a verified parent run."""
        return self._partition_child_run(
            ctx,
            run_id,
            idempotency_key=idempotency_key,
            operation="run.backfill",
            partition_ids_by_node=partition_ids,
            checkpoint_id=checkpoint_id,
        )

    def _partition_child_run(
        self,
        ctx: ControlPlaneContext,
        run_id: str,
        *,
        idempotency_key: str,
        operation: str,
        partition_ids_by_node: Mapping[str, Sequence[str]],
        checkpoint_id: str | None = None,
        reusable_artifact_ids: Sequence[str] = (),
    ) -> AcceptReceipt:
        if operation not in {"run.repair", "run.backfill"}:
            raise ValueError("unsupported partition lifecycle operation")
        if (
            not isinstance(cast(Any, idempotency_key), str)
            or not idempotency_key.strip()
        ):
            raise ControlPlaneError(
                "Idempotency-Key is required for managed partition commands",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        action = operation.removeprefix("run.")
        if checkpoint_id is not None and (
            not isinstance(cast(Any, checkpoint_id), str)
            or not checkpoint_id.strip()
            or len(checkpoint_id) > 4096
        ):
            raise ControlPlaneError(
                "checkpoint_id must be a non-blank string of at most 4096 characters",
                code="PMCP422",
                status=422,
                title="Unprocessable Entity",
                type="etlantic.control_plane/validation_error",
            )
        if not isinstance(cast(Any, reusable_artifact_ids), (list, tuple)):
            raise ControlPlaneError(
                "reusable_artifact_ids must be an array",
                code="PMCP422",
                status=422,
                title="Unprocessable Entity",
                type="etlantic.control_plane/validation_error",
            )
        reusable_ids = tuple(reusable_artifact_ids)
        if (
            len(reusable_ids) > 1000
            or any(
                not isinstance(cast(Any, identity), str)
                or not identity.strip()
                or len(identity) > 4096
                for identity in reusable_ids
            )
            or len(set(reusable_ids)) != len(reusable_ids)
        ):
            raise ControlPlaneError(
                "reusable_artifact_ids must contain at most 1000 unique, non-blank ids",
                code="PMCP422",
                status=422,
                title="Unprocessable Entity",
                type="etlantic.control_plane/validation_error",
            )
        record = self._authorized_run_record(ctx, operation, run_id)
        parent_submission_id = str(record.get("submission_id") or "")
        if not parent_submission_id:
            raise ControlPlaneError.conflict(
                "Run record has no durable submission identity"
            )
        parent = self.durable_work.get_submission(ctx, parent_submission_id)
        if parent.status not in {"completed", "failed", "cancelled"}:
            raise ControlPlaneError.conflict(
                f"Only terminal runs can be used for {action}"
            )
        if not parent.input_snapshot:
            raise ControlPlaneError.conflict(
                "Legacy accepted work has no verified execution envelope"
            )
        parent_envelope = self._parse_envelope(parent.input_snapshot)
        if parent_envelope.plan_document.get("schema") == "etlantic.plan/2":
            raise ControlPlaneError.conflict(
                f"Adaptive execution does not support {action}",
                extensions={"reason": "adaptive_policy_unsupported"},
            )
        if RunRequest.from_dict(dict(parent_envelope.run_request)).no_write:
            raise ControlPlaneError.conflict(
                "A no-write run cannot be repaired or backfilled",
                extensions={"reason": "no_write_parent"},
            )
        plan = _decode_plan_document(parent_envelope.plan_document)
        if not isinstance(plan, PipelinePlan):
            raise ControlPlaneError.conflict(
                "Partition command requires a standard plan"
            )
        block_reason = self._partition_action_block_reason(
            parent.input_snapshot, operation=action
        )
        if block_reason is not None:
            raise ControlPlaneError.conflict(
                f"Run cannot execute {action} with its accepted provider capabilities",
                extensions={"reason": block_reason},
            )
        selected = set(
            plan.selected_nodes or tuple(node.name for node in plan.logical_graph.nodes)
        )
        required_nodes: set[str] = set()
        for node in plan.logical_graph.nodes:
            if node.name not in selected:
                continue
            if node.kind.value in {"source", "sink"}:
                required_nodes.add(node.name)
        normalized = _validate_partition_ids_by_node(
            partition_ids_by_node,
            required_nodes=required_nodes,
            operation=action,
        )
        flattened_ids = tuple(
            partition_id
            for node_name in sorted(normalized)
            for partition_id in normalized[node_name]
        )
        if action == "backfill":
            repair_plan = self.durable_work.plan_backfill(
                ctx,
                parent_submission_id,
                partition_ids=flattened_ids,
                checkpoint_id=checkpoint_id,
            )
        else:
            repair_plan = self.durable_work.plan_repair(
                ctx,
                parent_submission_id,
                checkpoint_id=checkpoint_id,
                invalidated_partition_ids=flattened_ids,
                reusable_artifact_ids=reusable_ids,
            )
        if repair_plan.source_plan_fingerprint != parent_envelope.plan_fingerprint:
            raise ControlPlaneError.conflict(
                "Partition plan no longer matches the accepted source plan"
            )
        effect_reason = self._rerun_block_reason(ctx, parent_submission_id)
        if effect_reason is not None:
            raise ControlPlaneError.conflict(
                "Partition command is blocked until the prior execution effect is reconciled",
                extensions={"reason": effect_reason},
            )
        request = RunRequest.from_dict(dict(parent_envelope.run_request))
        metadata = dict(request.metadata)
        metadata["etlantic.control_plane.partition_operation"] = {
            "command": action,
            "parent_run_id": run_id,
            "partition_ids_by_node": {
                key: list(values) for key, values in normalized.items()
            },
            "checkpoint_id": checkpoint_id,
            "reusable_artifact_ids": list(reusable_ids),
        }
        child_request = _request_with_intent(
            request,
            intent=RunIntent.REPAIR if action == "repair" else RunIntent.BACKFILL,
            metadata=metadata,
        )
        child_envelope = parent_envelope.with_request(child_request)
        evidence_refs = dict(child_envelope.evidence_refs or {})
        evidence_refs.update(
            {
                "command": action,
                "parent_run_id": run_id,
                "parent_submission_id": parent_submission_id,
            }
        )
        if checkpoint_id:
            evidence_refs["checkpoint_id"] = checkpoint_id
            evidence_refs["artifact_parent_run_id"] = run_id
        child_envelope = ExecutionEnvelope.from_dict(
            {**child_envelope.to_dict(), "evidence_refs": evidence_refs}
        )
        return self._accept_child_run(
            ctx,
            idempotency_key=idempotency_key,
            operation=operation,
            envelope=child_envelope,
            parent_run_id=run_id,
            parent_submission_id=parent_submission_id,
        )

    def _partition_action_block_reason(
        self, input_snapshot: str, *, operation: str
    ) -> str | None:
        """Require explicit partition methods for each selected source and sink."""
        try:
            envelope = self._parse_envelope(input_snapshot)
            plan = _decode_plan_document(envelope.plan_document)
        except ControlPlaneError:
            return "unverified_execution_envelope"
        try:
            if RunRequest.from_dict(dict(envelope.run_request)).no_write:
                return "no_write_parent"
        except (TypeError, ValueError):
            return "unverified_execution_envelope"
        if not isinstance(plan, PipelinePlan):
            return "provider_unsupported"
        selected = set(
            plan.selected_nodes or tuple(node.name for node in plan.logical_graph.nodes)
        )
        source_count = 0
        sink_count = 0
        for node in plan.logical_graph.nodes:
            if node.name not in selected or node.kind.value not in {"source", "sink"}:
                continue
            requirement = (
                "source.partitioned"
                if node.kind.value == "source"
                else "write.partition_replace"
            )
            if node.kind.value == "sink":
                descriptor_requirements = {
                    "write.partition_replace",
                    "idempotency",
                }
            else:
                descriptor_requirements = {requirement}
            if node.kind.value == "source":
                source_count += 1
            else:
                sink_count += 1
            descriptor = plan.bindings.get(node.name) or plan.bindings.get(
                node.binding or node.name
            )
            if descriptor is None or not descriptor_requirements.issubset(
                set(descriptor.required_capabilities)
            ):
                return "provider_unsupported"
            if str(descriptor.provider or "").lower() == "postgresql":
                config = descriptor.config or {}
                partition_column = config.get("partition_column")
                if (
                    not isinstance(partition_column, str)
                    or not partition_column.strip()
                ):
                    return "provider_unsupported"
        if not source_count or not sink_count:
            return "provider_unsupported"
        return None

    def _rerun_block_reason(
        self, ctx: ControlPlaneContext, submission_id: str
    ) -> str | None:
        try:
            effect = self.durable_work.get_effect(ctx, f"{submission_id}:execution")
        except ControlPlaneError as exc:
            if exc.status == 404:
                return None
            raise
        if effect.submission_id != submission_id or not effect.authoritative:
            return "effect_requires_reconciliation"
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
        if effect.submission_id != submission_id or not effect.authoritative:
            return "effect_requires_reconciliation"
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
        parent_attempt_id: str | None = None
        list_attempts = getattr(self.durable_work, "list_attempts", None)
        if callable(list_attempts):
            parent_attempts = cast(
                Sequence[Any], list_attempts(ctx, parent_submission_id)
            )
            if parent_attempts:
                parent_attempt_id = parent_attempts[-1].attempt_id
        if parent_attempt_id:
            evidence_refs = dict(envelope.evidence_refs or {})
            evidence_refs["parent_attempt_id"] = parent_attempt_id
            envelope = ExecutionEnvelope.from_dict(
                {**envelope.to_dict(), "evidence_refs": evidence_refs}
            )
        envelope = _with_input_resource_lease(
            ctx,
            envelope,
            operation=operation,
            idempotency_key=idempotency_key,
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
                legacy_envelope = _with_input_resource_lease(
                    ctx,
                    envelope,
                    operation=operation,
                    idempotency_key=idempotency_key,
                    legacy_scope=True,
                )
                if prior_envelope.to_json() != legacy_envelope.to_json():
                    raise ControlPlaneError.conflict(
                        "Idempotency key reuse with a different lifecycle parent or intent"
                    )
                envelope = legacy_envelope
                expected_envelope = envelope.to_json()
        elif (
            prior_durable is not None
            and prior_durable.input_snapshot != expected_envelope
        ):
            legacy_envelope = _with_input_resource_lease(
                ctx,
                envelope,
                operation=operation,
                idempotency_key=idempotency_key,
                legacy_scope=True,
            )
            if prior_durable.input_snapshot != legacy_envelope.to_json():
                raise ControlPlaneError.conflict(
                    "Idempotency key reuse with a different lifecycle parent or intent"
                )
            envelope = legacy_envelope
            expected_envelope = envelope.to_json()
        payload = self._acceptance_payload(envelope)
        payload.update(
            {
                "command": operation.removeprefix("run."),
                "parent_run_id": parent_run_id,
                "parent_submission_id": parent_submission_id,
            }
        )
        if prior_receipt is not None:
            if prior_durable is None:
                self._accept_child_durable(
                    ctx,
                    idempotency_key=idempotency_key,
                    operation=operation,
                    envelope=envelope,
                    submission_id=prior_receipt.submission_id,
                    run_id=prior_receipt.resource_id
                    or legacy_managed_run_id(ctx, idempotency_key, operation=operation),
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
                    "Idempotency key reuse with a different lifecycle parent or intent"
                )
            receipt_result = self.submissions.accept(
                ctx,
                idempotency_key=idempotency_key,
                payload=payload,
                resource_type="run",
                resource_id=prior_durable.run_id
                or legacy_managed_run_id(ctx, idempotency_key, operation=operation),
                submission_id=prior_durable.submission_id,
                operation=operation,
            )
            return receipt_result.receipt

        input_plan = _decode_plan_document(envelope.plan_document)
        input_lease_id = self._protect_input_resources(
            ctx,
            input_plan,
            operation=operation,
            idempotency_key=idempotency_key,
        )
        envelope_lease_id = (envelope.evidence_refs or {}).get(
            "input_resource_lease_id"
        )
        if input_lease_id != envelope_lease_id:
            raise ControlPlaneError.conflict(
                "Accepted input resource lease does not match its execution envelope"
            )
        receipt_result = self.submissions.accept(
            ctx,
            idempotency_key=idempotency_key,
            payload=payload,
            resource_type="run",
            resource_id=managed_run_id(ctx, idempotency_key, operation=operation),
            operation=operation,
        )
        self._accept_child_durable(
            ctx,
            idempotency_key=idempotency_key,
            operation=operation,
            envelope=envelope,
            submission_id=receipt_result.receipt.submission_id,
            run_id=receipt_result.receipt.resource_id
            or managed_run_id(ctx, idempotency_key, operation=operation),
        )
        if receipt_result.created and self.events is not None:
            with suppress(Exception):
                self.events.append(
                    ctx,
                    kind=f"{operation}.accepted",
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
        run_id: str,
    ) -> SubmissionRecord:
        try:
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
                run_id=run_id,
            )
            return row
        except Exception as exc:
            # Acceptance and its outbox may have committed before the provider
            # lost the acknowledgement. Reconcile the scoped command identity
            # before returning the original receipt.
            recovered: SubmissionRecord | None = None
            reconciliation_available = False
            with suppress(Exception):
                recovered = self.durable_work.get_submission_by_idempotency(
                    ctx, idempotency_key=idempotency_key, operation=operation
                )
                reconciliation_available = True
            if recovered is not None:
                if (
                    recovered.submission_id != submission_id
                    or recovered.operation != operation
                    or recovered.input_snapshot != envelope.to_json()
                    or (recovered.run_id is not None and recovered.run_id != run_id)
                ):
                    raise ControlPlaneError.conflict(
                        "Durable lifecycle acceptance conflicts with the CP1 receipt"
                    ) from exc
                return recovered

            # Even a successful absence lookup cannot fence another caller
            # from accepting this shared command immediately afterwards. Keep
            # its CP1 receipt and input leases available for same-key recovery;
            # configured input retention bounds their eventual cleanup.
            provider_rejected = (
                reconciliation_available
                and isinstance(exc, ControlPlaneError)
                and exc.status < 500
            )
            if provider_rejected:
                raise
            raise ControlPlaneError(
                "Durable lifecycle acceptance acknowledgement is uncertain; retry "
                "the same idempotency key to reconcile",
                code="PMCP503",
                status=503,
                title="Service Unavailable",
                type="etlantic.control_plane/unavailable",
                extensions={
                    "submission_id": submission_id,
                    "acceptance_uncertain": True,
                    "compensated": False,
                },
            ) from exc

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

    def list_run_events(
        self,
        ctx: ControlPlaneContext,
        run_id: str,
        *,
        cursor: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Return one bounded, resumable page of events for an authorized run.

        The cursor advances through the caller's scoped event log. Events for
        other runs are filtered after the authorized run lookup, so a page can
        be empty while still carrying a cursor when other runs are active in
        the same workspace.
        """
        self._authorized_run_record(ctx, "run.events", run_id)
        if self.events is None:
            raise ControlPlaneError(
                "Event history is unavailable",
                code="PMCP501",
                status=501,
                title="Not Implemented",
            )
        if limit < 1 or limit > 200:
            raise ControlPlaneError(
                "Event page limit must be between 1 and 200",
                code="PMCP400",
                status=400,
                title="Bad Request",
                type="etlantic.control_plane/bad_request",
            )
        page = self.events.list_after_cursor(ctx, cursor, limit=limit)
        items = [
            event.to_dict()
            for event in page
            if str((event.payload or {}).get("run_id") or "") == run_id
        ]
        next_cursor: str | None = None
        if len(page) == limit and page:
            last_cursor = page[-1].cursor
            if self.events.list_after_cursor(ctx, last_cursor, limit=1):
                next_cursor = last_cursor
        return {
            "schema": "etlantic.control_plane.run_event_page/1",
            "run_id": run_id,
            "items": items,
            "next_cursor": next_cursor,
            "has_more": next_cursor is not None,
        }

    def _runtime_report(
        self,
        ctx: ControlPlaneContext,
        action: str,
        run_id: str,
        *,
        record: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], PipelineRunReport]:
        if record is None:
            record = self._authorized_run_record(ctx, action, run_id)
        idempotency_key = str(record.get("idempotency_key") or "")
        if not idempotency_key:
            raise ControlPlaneError.not_found("Run report not found")
        report_store = (
            self.report_store_factory(ctx)
            if self.report_store_factory is not None
            else managed_report_store(ctx, report_root=self.report_root)
        )
        submission_id = str(record.get("submission_id") or "")
        durable = self.durable_work.get_submission(ctx, submission_id)
        run_id = (
            durable.run_id
            or str(record.get("resource_id") or "")
            or legacy_managed_run_id(ctx, idempotency_key, operation=durable.operation)
        )
        report_store_error: Exception | None = None
        try:
            result = report_store.get(run_id)
        except Exception as exc:
            report_store_error = exc
            result = None
        if result is None:
            try:
                publication = self.durable_work.get_latest_result_publication(
                    ctx, submission_id
                )
            except Exception as exc:
                if report_store_error is not None:
                    raise ControlPlaneError(
                        "Run result stores are temporarily unavailable",
                        code="PMCP503",
                        status=503,
                        title="Service Unavailable",
                        type="etlantic.control_plane/unavailable",
                    ) from exc
                publication = None
            if publication is not None:
                try:
                    if (
                        publication.submission_id != submission_id
                        or publication.run_id != run_id
                        or (publication.tenant_id, publication.workspace_id)
                        != (ctx.tenant.tenant_id, ctx.workspace.workspace_id)
                        or hashlib.sha256(
                            publication.report_json.encode("utf-8")
                        ).hexdigest()
                        != publication.report_sha256
                    ):
                        raise ValueError("durable result identity is invalid")
                    raw_report = json.loads(publication.report_json)
                    if not isinstance(raw_report, dict):
                        raise ValueError("durable result document is invalid")
                    result = PipelineRunReport.from_dict(
                        cast(dict[str, Any], raw_report)
                    )
                except Exception as exc:
                    raise ControlPlaneError(
                        "Durable run result failed integrity validation",
                        code="PMCP500",
                        status=500,
                        title="Internal Server Error",
                    ) from exc
                if result.run_id != publication.run_id:
                    raise ControlPlaneError(
                        "Durable run result identity is invalid",
                        code="PMCP500",
                        status=500,
                        title="Internal Server Error",
                    )
                metadata = dict(result.metadata)
                execution = dict(
                    _mapping(metadata.get("etlantic.control_plane.execution"))
                )
                execution["result_publication_status"] = (
                    "published" if publication.published_at is not None else "pending"
                )
                metadata["etlantic.control_plane.execution"] = execution
                result = replace(result, metadata=metadata)
        if result is None and report_store_error is not None:
            raise ControlPlaneError(
                "Run result is temporarily unavailable",
                code="PMCP503",
                status=503,
                title="Service Unavailable",
                type="etlantic.control_plane/unavailable",
            ) from report_store_error
        if result is None:
            raise ControlPlaneError(
                "Run report has not been published",
                code="PMCP425",
                status=425,
                title="Too Early",
                type="etlantic.control_plane/result_pending",
                extensions={"run_id": run_id, "status": record.get("status")},
            )
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
        metadata = _mapping(report.get("metadata"))
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
        partition_lineage = _mapping(metadata.get("etlantic.partition_lineage"))
        raw_sources: object = partition_lineage.get("sources")
        raw_outputs: object = partition_lineage.get("outputs")
        sources: dict[str, dict[str, Any]] = {}
        for raw_items in (raw_sources, raw_outputs):
            if not isinstance(raw_items, (list, tuple)):
                continue
            for raw_item in cast(list[object] | tuple[object, ...], raw_items):
                if not isinstance(raw_item, Mapping):
                    continue
                item = cast(Mapping[str, Any], raw_item)
                node_id = item.get("node_id")
                if isinstance(node_id, str) and node_id:
                    sources[node_id] = dict(item)
        partition_nodes: dict[str, dict[str, Any]] = {}
        for edge in edges:
            partition_id = edge.get("to")
            source_id = edge.get("from")
            edge_kind = edge.get("kind")
            if (
                edge_kind not in {"observed_partition", "produced_partition"}
                or not isinstance(partition_id, str)
                or not isinstance(source_id, str)
            ):
                continue
            partition_node: dict[str, Any] = {
                "id": partition_id,
                "kind": "partition",
                "status": (
                    "produced" if edge_kind == "produced_partition" else "observed"
                ),
            }
            partition_node[
                "output_node_id"
                if edge_kind == "produced_partition"
                else "source_node_id"
            ] = source_id
            ordinal = partition_id.rsplit(":", maxsplit=1)[-1]
            if ordinal.isdigit():
                partition_node["ordinal"] = int(ordinal)
            source = sources.get(source_id)
            if source is not None:
                keys: object = source.get("partition_keys")
                if isinstance(keys, (list, tuple)):
                    key_items = cast(list[object] | tuple[object, ...], keys)
                    if all(isinstance(key, str) for key in key_items):
                        partition_node["partition_keys"] = [
                            str(key) for key in key_items
                        ]
            partition_nodes[partition_id] = partition_node
        nodes.extend(partition_nodes[key] for key in sorted(partition_nodes))
        execution = _mapping(metadata.get("etlantic.control_plane.execution"))
        submission_id_raw: object = execution.get("submission_id") or record.get(
            "submission_id"
        )
        submission_id = (
            submission_id_raw if isinstance(submission_id_raw, str) else None
        )
        raw_attempt_id: object = execution.get("attempt_id")
        attempt_id = raw_attempt_id if isinstance(raw_attempt_id, str) else None
        attempt_history: list[dict[str, str]] = []
        raw_attempt_history: object = execution.get("attempt_history")
        if isinstance(raw_attempt_history, (list, tuple)):
            for raw_item in cast(
                list[object] | tuple[object, ...], raw_attempt_history
            ):
                if not isinstance(raw_item, Mapping):
                    continue
                item = cast(Mapping[str, object], raw_item)
                history_attempt = item.get("attempt_id")
                history_role = item.get("role")
                if isinstance(history_attempt, str) and isinstance(history_role, str):
                    attempt_history.append(
                        {"attempt_id": history_attempt, "role": history_role}
                    )
        if attempt_id and not any(
            item["attempt_id"] == attempt_id and item["role"] == "executed"
            for item in attempt_history
        ):
            attempt_history.append({"attempt_id": attempt_id, "role": "executed"})
        run_id_value = str(report["run_id"])
        attempt_nodes: dict[str, str] = {}
        for item in attempt_history:
            current_attempt = item["attempt_id"]
            node_id = f"attempt:{current_attempt}"
            if node_id not in attempt_nodes.values():
                nodes.append(
                    {
                        "id": node_id,
                        "kind": "attempt",
                        "attempt_id": current_attempt,
                        "role": item["role"],
                    }
                )
                edges.append(
                    {"from": run_id_value, "to": node_id, "kind": "has_attempt"}
                )
            attempt_nodes[current_attempt] = node_id
        execution_attempts = [
            attempt_nodes[item["attempt_id"]]
            for item in attempt_history
            if item["role"] == "executed" and item["attempt_id"] in attempt_nodes
        ]
        steps: list[object] = report.get("steps") or []
        for step in steps:
            if not isinstance(step, Mapping):
                continue
            step_data = cast(Mapping[str, Any], step)
            step_id = step_data.get("step_id")
            if not isinstance(step_id, str) or not step_id:
                continue
            node_id = f"node:{report['pipeline_id']}:{step_id}"
            nodes.append(
                {
                    "id": node_id,
                    "kind": "node",
                    "step_id": step_id,
                    "name": step_data.get("step_name"),
                    "status": step_data.get("status"),
                }
            )
            for execution_attempt in execution_attempts:
                edges.append(
                    {
                        "from": execution_attempt,
                        "to": node_id,
                        "kind": "executed_node",
                    }
                )
        if isinstance(submission_id, str) and submission_id:
            durable = self.durable_work.get_submission(ctx, submission_id)
            if durable.input_snapshot:
                envelope = self._parse_envelope(durable.input_snapshot)
                evidence_refs = envelope.evidence_refs or {}
                parent_run_id = evidence_refs.get("parent_run_id")
                parent_attempt_id = evidence_refs.get("parent_attempt_id")
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
                if parent_attempt_id:
                    parent_attempt_node = f"attempt:{parent_attempt_id}"
                    if not any(node.get("id") == parent_attempt_node for node in nodes):
                        nodes.append(
                            {
                                "id": parent_attempt_node,
                                "kind": "attempt",
                                "attempt_id": parent_attempt_id,
                            }
                        )
                    edges.append(
                        {
                            "from": parent_attempt_node,
                            "to": report["run_id"],
                            "kind": "parent_attempt",
                        }
                    )
        return {
            "schema": "etlantic.run_lineage/1",
            "run_id": report["run_id"],
            "submission_id": submission_id,
            "attempt_id": attempt_id,
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
        retention_state = _mapping(report.get("metadata")).get(
            RUN_ARTIFACT_RETENTION_STATE_KEY
        )
        if not isinstance(retention_state, str):
            retention_state = (
                "pending"
                if self.run_artifact_retention_seconds is not None
                else "disabled"
            )
        workspace = managed_artifact_workspace(
            ctx, run_id, artifact_root=self.artifact_root
        )
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
            strategy = artifact.get("strategy", "output")
            path = artifact_storage_path(workspace, identity)
            content_available = (
                strategy == "durable" and path.is_file() and not path.is_symlink()
            )
            items.append(
                {
                    "artifact_id": identity,
                    "kind": strategy,
                    "status": artifact.get("status", "available"),
                    "retention_state": retention_state,
                    "content_available": content_available,
                    "media_type": (
                        "application/json"
                        if content_available
                        else _mapping(artifact.get("metadata")).get("media_type")
                    ),
                }
            )
        return items

    def get_run_artifact_content(
        self, ctx: ControlPlaneContext, run_id: str, artifact_id: str
    ) -> tuple[bytes, str]:
        """Return one authorized, durable artifact as bounded JSON bytes."""
        record = self._authorized_run_record(ctx, "run.artifact.content", run_id)
        if not artifact_id:
            raise ControlPlaneError.not_found("Run artifact not found")
        require_authorized(
            self.authorizer,
            ctx,
            "run.artifact.content",
            f"artifact:{artifact_id}",
            resource_in_caller_scope=False,
        )
        _record, report_model = self._runtime_report(
            ctx,
            "run.artifact.content",
            run_id,
            record=record,
        )
        artifact = next(
            (
                item
                for item in report_model.to_dict().get("artifacts", [])
                if item.get("identity") == artifact_id
                and item.get("strategy") == "durable"
            ),
            None,
        )
        if artifact is None:
            raise ControlPlaneError.not_found("Run artifact not found")

        workspace = managed_artifact_workspace(
            ctx, run_id, artifact_root=self.artifact_root
        )
        path = artifact_storage_path(workspace, artifact_id)
        if path.is_symlink() or not path.is_file():
            raise ControlPlaneError.not_found("Run artifact content not found")
        policy = SafeIoPolicy.for_root(
            workspace,
            security_domain=ctx.security_domain.domain_id,
            tenant=ctx.tenant.tenant_id,
        )
        try:
            _resolved, content, _events = read_text_safe(path, policy, run_id=run_id)
        except Exception as exc:
            raise ControlPlaneError(
                "Run artifact content is unavailable under the configured I/O policy",
                code="PMCP424",
                status=424,
                title="Failed Dependency",
            ) from exc
        return content.encode("utf-8"), "application/json"

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

    def _store_definition(
        self,
        ctx: ControlPlaneContext,
        definition_id: str,
        document: Mapping[str, Any],
    ) -> str | None:
        """Store one definition and return its exact revision when available."""
        append_revision = getattr(self.definitions, "put_revision", None)
        if not callable(append_revision):
            self.definitions.put(ctx, definition_id, document)
            return None
        revision_id = append_revision(ctx, definition_id, document)
        if type(revision_id) is not str or not revision_id.strip():
            raise ControlPlaneError(
                "Definition repository returned an invalid revision id",
                code="PMCP500",
                status=500,
                title="Internal Server Error",
            )
        return revision_id

    def _resolve_definition_revision(
        self,
        ctx: ControlPlaneContext,
        definition_id: str,
        selector: str,
    ) -> DefinitionResolution:
        resolver = getattr(self.definitions, "resolve_revision", None)
        if callable(resolver):
            try:
                result = resolver(ctx, definition_id, selector)
            except ControlPlaneError:
                raise
            except Exception as exc:
                raise ControlPlaneError(
                    "Definition revision could not be resolved",
                    code="PMCP503",
                    status=503,
                    title="Service Unavailable",
                    type="etlantic.control_plane/unavailable",
                ) from exc
            if not isinstance(result, DefinitionResolution):
                raise ControlPlaneError(
                    "Definition repository returned an invalid revision resolution",
                    code="PMCP500",
                    status=500,
                    title="Internal Server Error",
                )
            return result
        document = self._get_document(
            ctx, definition_id, action="run.submit", authorize=False
        )
        definition = self._decode_definition(document)
        revision_id = definition.fingerprint or pipeline_fingerprint(definition)
        if selector not in {"current", revision_id}:
            raise ControlPlaneError.not_found(
                "Definition revision was not found",
                extensions={"definition_id": definition_id},
            )
        return DefinitionResolution(revision_id=revision_id, document=document)

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
    def _admit_adaptive_plan(
        plan: AdaptivePipelinePlan, request: RunRequest, *, profile: Profile
    ) -> None:
        """Run the authoritative, side-effect-free /2 admission before accept."""
        from etlantic.exceptions import PipelineExecutionError
        from etlantic.runtime.adaptive_admission import admit_adaptive_plan

        runtime = PipelineRuntime()
        runtime.ensure_plugins_for_profile(profile)
        try:
            admit_adaptive_plan(plan, request=request, runtime=runtime)
        except PipelineExecutionError as exc:
            code = exc.code or "PMADP500"
            status_code = 501 if code in {"PMADP500", "PMADP501"} else 422
            raise ControlPlaneError(
                str(exc),
                code=code,
                status=status_code,
                title=(
                    "Not Implemented" if status_code == 501 else "Unprocessable Entity"
                ),
                type=(
                    "etlantic.control_plane/not_implemented"
                    if status_code == 501
                    else "etlantic.control_plane/validation_error"
                ),
            ) from exc

    def _authorize_plan_resources(
        self,
        ctx: ControlPlaneContext,
        plan: PlanDocument,
        *,
        action: str,
    ) -> None:
        """Authorize every resolved logical resource before disclosure or use."""
        if isinstance(plan, AdaptivePipelinePlan):
            # The first managed /2 tuple is intentionally restricted to
            # process-local memory bindings. Reject any future row that adds
            # external resources until the managed authorization and lease
            # projections understand their identity.
            if any(
                target.location != "local" or target.resource is not None
                for target in plan.inventory.targets
            ):
                raise ControlPlaneError(
                    "Managed adaptive execution does not support external resources",
                    code="PMADP500",
                    status=501,
                    title="Not Implemented",
                    type="etlantic.control_plane/not_implemented",
                )
            runtime_record = plan.metadata.get("etlantic.runtime")
            bindings = (
                cast(Mapping[str, Any], runtime_record).get("bindings")
                if isinstance(runtime_record, Mapping)
                else None
            )
            expected_nodes = {
                node.name
                for node in plan.logical_graph.nodes
                if node.kind.value in {"source", "sink"}
            }
            if not isinstance(bindings, Mapping) or set(
                cast(Mapping[str, Any], bindings)
            ) not in (set(), expected_nodes):
                raise ControlPlaneError(
                    "Managed adaptive plan lacks complete binding identities",
                    code="PMADP500",
                    status=501,
                    title="Not Implemented",
                    type="etlantic.control_plane/not_implemented",
                )
            if not bindings:
                # The supported local-static memory tuple uses implicit,
                # process-local source/sink bindings. Any configured binding
                # must be captured for every endpoint and pass the checks
                # below; a partial snapshot is never treated as implicit.
                return
            for descriptor in cast(Mapping[str, object], bindings).values():
                if (
                    not isinstance(descriptor, Mapping)
                    or cast(Mapping[str, Any], descriptor).get("provider") != "memory"
                    or cast(Mapping[str, Any], descriptor).get("secret_ref") is not None
                    or cast(Mapping[str, Any], descriptor).get("location") is not None
                    or cast(Mapping[str, Any], descriptor).get("root_ref") is not None
                    or cast(Mapping[str, Any], descriptor).get("config")
                ):
                    raise ControlPlaneError(
                        "Managed adaptive execution currently supports local memory bindings only",
                        code="PMADP500",
                        status=501,
                        title="Not Implemented",
                        type="etlantic.control_plane/not_implemented",
                    )
            return
        resources = {
            str(reference.get("binding") or identity)
            for identity, reference in plan.resource_refs.items()
        }
        for identity in sorted(resources):
            require_authorized(
                self.authorizer,
                ctx,
                action,
                f"resource:{identity}",
                resource_in_caller_scope=False,
            )

    def _authorize_input_resources(
        self, ctx: ControlPlaneContext, plan: PlanDocument
    ) -> tuple[InputResourceReference, ...]:
        references = _input_resource_references(plan)
        if not references:
            return ()
        if self.input_resources is None:
            raise ControlPlaneError(
                "Immutable input resources are unavailable on this backend",
                code="PMRES503",
                status=503,
                title="Service Unavailable",
                type="etlantic.control_plane/unavailable",
            )
        for reference in references:
            require_authorized(
                self.authorizer,
                ctx,
                "input.read",
                f"input-resource:{reference.resource_id}",
                resource_in_caller_scope=False,
            )
            self.input_resources.verify_reference(ctx, reference)
        return references

    def _protect_input_resources(
        self,
        ctx: ControlPlaneContext,
        plan: PlanDocument,
        *,
        operation: str,
        idempotency_key: str,
    ) -> str | None:
        references = self._authorize_input_resources(ctx, plan)
        if not references:
            return None
        if (
            type(self.input_resource_retention_seconds) is not int
            or self.input_resource_retention_seconds < 1
        ):
            raise ControlPlaneError(
                "Input resource retention policy is invalid",
                code="PMRES500",
                status=500,
                title="Internal Server Error",
            )
        lease_id = _input_resource_lease_id(ctx, operation, idempotency_key)
        retain_until = datetime.now(UTC) + timedelta(
            seconds=self.input_resource_retention_seconds
        )
        if self.input_resources is None:
            raise ControlPlaneError(
                "Immutable input resources are unavailable on this backend",
                code="PMRES503",
                status=503,
                title="Service Unavailable",
                type="etlantic.control_plane/unavailable",
            )
        for reference in references:
            self.input_resources.acquire_lease(
                ctx,
                reference,
                lease_id=lease_id,
                retain_until=retain_until,
            )
        return lease_id

    def _release_input_lease(
        self, ctx: ControlPlaneContext, lease_id: str | None
    ) -> None:
        if lease_id is not None and self.input_resources is not None:
            self.input_resources.release_lease(ctx, lease_id=lease_id)

    @staticmethod
    def _acceptance_payload(envelope: ExecutionEnvelope) -> dict[str, Any]:
        return {
            "definition_id": envelope.definition_id,
            "revision_selector": envelope.revision_selector,
            "profile_name": envelope.profile_name,
            "request": mutable_copy(envelope.run_request),
            "plan_fingerprint": envelope.plan_fingerprint,
            "effective_fingerprint": envelope.effective_fingerprint,
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
        envelope = ManagedApplicationService._parse_envelope(
            str(payload["execution_envelope"])
        )
        effective_fingerprint = payload.get("effective_fingerprint")
        if (
            effective_fingerprint is not None
            and effective_fingerprint != envelope.effective_fingerprint
        ):
            raise ControlPlaneError.conflict(
                "Prior acceptance has an invalid effective fingerprint"
            )
        return envelope

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
        run_id: str,
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
            run_id=run_id,
        )
        return row

    @staticmethod
    def _resource_versions(plan: PlanDocument) -> dict[str, str]:
        if isinstance(plan, AdaptivePipelinePlan):
            return {}
        versions: dict[str, str] = {}
        for identity, resource in plan.resource_refs.items():
            version = resource.get("version") or resource.get("fingerprint")
            if isinstance(version, str) and version:
                versions[str(identity)] = version
        for reference in _input_resource_references(plan):
            identity = f"input:{reference.resource_id}"
            prior = versions.get(identity)
            if prior is not None and prior != reference.version:
                raise ControlPlaneError.conflict(
                    "Accepted input resource has ambiguous versions"
                )
            versions[identity] = reference.version
        return versions

    @staticmethod
    def _quota_idempotency_key(ctx: ControlPlaneContext, idempotency_key: str) -> str:
        """Derive a secret-safe quota reservation key from the CP1 scope."""
        value = {
            "scope": list(ctx.scope_key),
            "principal": [
                ctx.principal.issuer or "",
                ctx.principal.kind,
                ctx.principal.subject,
            ],
            "operation": "run.submit",
            "idempotency_key": idempotency_key,
        }
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

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
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > 256
        or value != value.strip()
        or any(ord(character) < 0x20 for character in value)
        or redact_message(value) != value
    ):
        raise ControlPlaneError(
            "revision_selector must be a bounded, credential-free string",
            code="PMCP400",
            status=400,
            title="Bad Request",
            type="etlantic.control_plane/bad_request",
        )
    return value


def _input_resource_references(
    plan: PlanDocument,
) -> tuple[InputResourceReference, ...]:
    if isinstance(plan, AdaptivePipelinePlan):
        return ()
    references: dict[tuple[str, str], InputResourceReference] = {}
    for descriptor in plan.bindings.values():
        config: Mapping[str, object] = cast(Mapping[str, object], descriptor.config)
        if "input_resource" not in config:
            continue
        value = config.get("input_resource")
        if not isinstance(value, Mapping):
            raise ControlPlaneError.conflict(
                "Accepted input resource reference is invalid"
            )
        try:
            reference = InputResourceReference.from_dict(
                cast(Mapping[str, object], value)
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ControlPlaneError.conflict(
                "Accepted input resource reference is invalid"
            ) from exc
        key = (reference.resource_id, reference.version)
        prior = references.get(key)
        if prior is not None and prior != reference:
            raise ControlPlaneError.conflict(
                "Accepted input resource reference is ambiguous"
            )
        references[key] = reference
    return tuple(references[key] for key in sorted(references))


def _input_resource_lease_id(
    ctx: ControlPlaneContext,
    operation: str,
    idempotency_key: str,
    *,
    legacy_scope: bool = False,
) -> str:
    scope: dict[str, object] = {
        "security_domain": ctx.security_domain.domain_id,
        "tenant": ctx.tenant.tenant_id,
        "workspace": ctx.workspace.workspace_id,
        "owner": ctx.resource_owner_id or ctx.principal.subject,
        "operation": operation,
        "idempotency_key": idempotency_key,
    }
    if not legacy_scope:
        scope["environment"] = ctx.environment.name
        scope["principal"] = {
            "issuer": ctx.principal.issuer or "",
            "kind": ctx.principal.kind,
            "subject": ctx.principal.subject,
        }
    digest = hashlib.sha256(
        json.dumps(scope, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"managed-input:{digest}"


def _with_input_resource_lease(
    ctx: ControlPlaneContext,
    envelope: ExecutionEnvelope,
    *,
    operation: str,
    idempotency_key: str,
    legacy_scope: bool = False,
) -> ExecutionEnvelope:
    plan = _decode_plan_document(envelope.plan_document)
    evidence_refs = dict(envelope.evidence_refs or {})
    if _input_resource_references(plan):
        evidence_refs["input_resource_lease_id"] = _input_resource_lease_id(
            ctx, operation, idempotency_key, legacy_scope=legacy_scope
        )
    else:
        evidence_refs.pop("input_resource_lease_id", None)
    return ExecutionEnvelope.from_dict(
        {**envelope.to_dict(), "evidence_refs": evidence_refs}
    )


def _decode_plan_document(value: Mapping[str, Any]) -> PlanDocument:
    """Decode the versioned public plan union without weakening fingerprints."""
    try:
        encoded = json.dumps(
            mutable_copy(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        return plan_from_json(encoded, verify=True)
    except Exception as exc:
        raise ControlPlaneError.conflict(
            "Accepted plan failed integrity verification"
        ) from exc


def _request_with_intent(
    request: RunRequest,
    *,
    intent: RunIntent,
    metadata: Mapping[str, Any],
) -> RunRequest:
    """Copy a request while changing only its lifecycle intent and metadata."""
    return RunRequest(
        selection=request.selection,
        intent=intent,
        materialization=request.materialization,
        retry=request.retry,
        timeout=request.timeout,
        cancellation=request.cancellation,
        parameter_overrides=request.parameter_overrides,
        asset_overrides=request.asset_overrides,
        implementation_overrides=request.implementation_overrides,
        invalidation=request.invalidation,
        no_write=request.no_write,
        metadata=metadata,
        extensions=request.extensions,
        explicit_settings=request.explicit_settings,
    )


def _validate_partition_ids_by_node(
    value: Mapping[str, Sequence[str]],
    *,
    required_nodes: set[str],
    operation: str,
) -> dict[str, tuple[str, ...]]:
    """Validate a bounded, complete per-node partition selector."""
    if not isinstance(cast(Any, value), Mapping) or set(value) != required_nodes:
        raise ControlPlaneError(
            f"{operation} must provide partition ids for every selected source and sink",
            code="PMCP422",
            status=422,
            title="Unprocessable Entity",
            type="etlantic.control_plane/validation_error",
        )
    normalized: dict[str, tuple[str, ...]] = {}
    total = 0
    for node_name, raw_ids in value.items():
        if not isinstance(cast(Any, node_name), str) or not node_name.strip():
            raise ControlPlaneError(
                f"{operation} contains an invalid node identity",
                code="PMCP422",
                status=422,
                title="Unprocessable Entity",
                type="etlantic.control_plane/validation_error",
            )
        if not isinstance(raw_ids, (list, tuple)) or not raw_ids:
            raise ControlPlaneError(
                f"{operation} requires at least one partition id for {node_name!r}",
                code="PMCP422",
                status=422,
                title="Unprocessable Entity",
                type="etlantic.control_plane/validation_error",
            )
        ids = tuple(raw_ids)
        if any(
            not isinstance(cast(Any, partition_id), str)
            or not partition_id.strip()
            or len(partition_id) > 4096
            for partition_id in ids
        ) or len(set(ids)) != len(ids):
            raise ControlPlaneError(
                f"{operation} partition ids must be unique, non-blank strings of at most 4096 characters",
                code="PMCP422",
                status=422,
                title="Unprocessable Entity",
                type="etlantic.control_plane/validation_error",
            )
        total += len(ids)
        if total > 1000:
            raise ControlPlaneError(
                f"{operation} is limited to 1000 partition ids",
                code="PMCP413",
                status=413,
                title="Payload Too Large",
                type="etlantic.control_plane/payload_too_large",
            )
        normalized[node_name] = ids
    return normalized
