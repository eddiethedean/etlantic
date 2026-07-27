"""Transport-neutral application service facade for authoring and lifecycle."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from etlantic.authoring.catalog import (
    discover_authoring_catalog,
    negotiate_capabilities,
)
from etlantic.authoring.definition import PipelineDefinition
from etlantic.authoring.edits import EditCommand, EditResult, apply_edit
from etlantic.authoring.lifecycle import plan_pipeline_like, validate_pipeline_like
from etlantic.authoring.preview import plan_preview, structural_validate_preview
from etlantic.authoring.serialize import (
    pipeline_fingerprint,
    pipeline_from_dict,
    pipeline_to_dict,
)
from etlantic.diagnostics import ValidationReport
from etlantic.lifecycle.runtime import PipelineRuntime
from etlantic.plan.model import PipelinePlan
from etlantic.reports.model import PipelineRunReport
from etlantic.runtime.execute import run_pipeline


@dataclass(frozen=True, slots=True)
class PolicyContext:
    """Host-supplied authority; client payloads cannot expand these grants.

    Attributes:
        tenant: Logical tenant label for the host (reference only).
        environment: Deployment environment label.
        profile: Profile name resolved for validate/plan/run.
        allowed_assets: When set, definition assets must be in this set.
        allowed_plugins: When set, profile allowlist and engine refs must match.
        allowed_actions: Actions the facade may perform.
    """

    tenant: str = "default"
    environment: str = "development"
    profile: str = "development"
    allowed_assets: tuple[str, ...] | None = None
    allowed_plugins: tuple[str, ...] | None = None
    allowed_actions: tuple[str, ...] = (
        "catalog",
        "validate",
        "plan",
        "edit",
        "run",
        "cancel",
        "report",
    )


@dataclass(frozen=True, slots=True)
class ServiceError:
    """Structured service error for adapters (not a raised exception).

    Attributes:
        code: Machine-readable error code.
        message: Human-readable summary (must not contain secrets).
        path: Optional JSON-pointer-like path segments.
        details: Extra structured context.
    """

    code: str
    message: str
    path: tuple[str, ...] = ()
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize this error.

        Returns:
            Mapping with ``code``, ``message``, ``path``, and ``details``.
        """
        return {
            "code": self.code,
            "message": self.message,
            "path": list(self.path),
            "details": dict(self.details),
        }


@dataclass
class RunJob:
    """In-memory run job record for the synchronous reference adapter."""

    job_id: str
    status: str
    created_at: str
    definition_fingerprint: str
    report: PipelineRunReport | None = None
    error: str | None = None
    sync_reference: bool = True


@dataclass
class AuthoringService:
    """In-memory facade mapping request models to public ETLantic operations.

    Not a multi-tenant control plane. HTTP adapters (for example
    ``etlantic-fastapi``) should bind host policy into ``PolicyContext``.
    """

    policy: PolicyContext = field(default_factory=PolicyContext)
    runtime: PipelineRuntime = field(default_factory=PipelineRuntime)
    definitions: dict[str, PipelineDefinition] = field(default_factory=dict)
    jobs: dict[str, RunJob] = field(default_factory=dict)

    def _require_action(self, action: str) -> None:
        if action not in self.policy.allowed_actions:
            raise PermissionError(f"Action {action!r} is not allowed by policy context")

    def _enforce_definition_policy(self, defn: PipelineDefinition) -> None:
        if self.policy.allowed_assets is not None:
            allowed = set(self.policy.allowed_assets)
            for node in defn.nodes:
                if node.asset and node.asset not in allowed:
                    raise PermissionError(
                        f"Asset {node.asset!r} on node {node.name!r} is not "
                        f"allowed by policy context"
                    )
        if self.policy.allowed_plugins is not None:
            from etlantic.profile import resolve_profile

            allowed_plugins = set(self.policy.allowed_plugins)
            profile = resolve_profile(self.policy.profile)
            for pkg in profile.plugin_allowlist or {}:
                if pkg not in allowed_plugins:
                    raise PermissionError(
                        f"Profile plugin {pkg!r} is not allowed by policy context"
                    )
            for xf in defn.transformations:
                for ref in xf.implementation_refs:
                    if (
                        ref.engine.startswith("etlantic-")
                        and ref.engine not in allowed_plugins
                    ):
                        raise PermissionError(
                            f"Plugin {ref.engine!r} is not allowed by policy context"
                        )

    def negotiation(self) -> dict[str, Any]:
        """Return capability negotiation metadata for clients.

        Returns:
            Capability negotiation payload plus ``run_model``.

        Raises:
            PermissionError: If ``catalog`` is not an allowed action.
        """
        self._require_action("catalog")
        payload = negotiate_capabilities()
        payload["run_model"] = "synchronous_reference"
        return payload

    def catalog(self, definition_id: str | None = None) -> dict[str, Any]:
        """Return the authoring catalog, optionally scoped to a definition.

        Args:
            definition_id: Optional stored definition id to enrich the catalog.

        Returns:
            Catalog document as a dict.

        Raises:
            PermissionError: If ``catalog`` is not allowed.
        """
        self._require_action("catalog")
        defn = self.definitions.get(definition_id) if definition_id else None
        return discover_authoring_catalog(definition=defn).to_dict()

    def put_definition(
        self,
        definition_id: str,
        document: dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Store a verified pipeline definition document.

        Args:
            definition_id: Host-assigned definition id.
            document: ``etlantic.pipeline/1`` mapping (fingerprint verified).
            idempotency_key: Reserved for adapters; ignored in this reference.

        Returns:
            Mapping with ``id``, ``fingerprint``, and ``definition``.

        Raises:
            PermissionError: If ``edit`` is not allowed or policy rejects the
                definition.
            ValueError: On fingerprint / schema verification failure.
            TypeError: If ``document`` is not a mapping.
        """
        self._require_action("edit")
        _ = idempotency_key
        defn = pipeline_from_dict(document, verify=True)
        self._enforce_definition_policy(defn)
        self.definitions[definition_id] = defn
        return {
            "id": definition_id,
            "fingerprint": defn.fingerprint or pipeline_fingerprint(defn),
            "definition": pipeline_to_dict(defn),
        }

    def get_definition(self, definition_id: str) -> dict[str, Any]:
        """Fetch a stored definition.

        Args:
            definition_id: Previously stored id.

        Returns:
            Mapping with ``id``, ``fingerprint``, and ``definition``.

        Raises:
            KeyError: If ``definition_id`` is unknown.
        """
        defn = self.definitions[definition_id]
        return {
            "id": definition_id,
            "fingerprint": defn.fingerprint or pipeline_fingerprint(defn),
            "definition": pipeline_to_dict(defn),
        }

    def apply_edit(
        self,
        definition_id: str,
        command: dict[str, Any],
        *,
        expected_token: str | None = None,
    ) -> dict[str, Any]:
        """Apply an immutable edit to a stored definition.

        Args:
            definition_id: Stored definition id.
            command: ``EditCommand`` mapping (``op``, optional ``path`` /
                ``payload``).
            expected_token: Optimistic concurrency token (fingerprint).

        Returns:
            Updated id, fingerprint, concurrency token, and definition.

        Raises:
            PermissionError: If ``edit`` is not allowed or policy rejects.
            KeyError: If the definition id is unknown.
            ValueError: On concurrency or edit payload failures.
        """
        self._require_action("edit")
        defn = self.definitions[definition_id]
        result: EditResult = apply_edit(
            defn, EditCommand.from_dict(command), expected_token=expected_token
        )
        self._enforce_definition_policy(result.definition)
        self.definitions[definition_id] = result.definition
        return {
            "id": definition_id,
            "fingerprint": result.fingerprint,
            "concurrency_token": result.concurrency_token,
            "definition": pipeline_to_dict(result.definition),
        }

    def validate(self, definition_id: str) -> dict[str, Any]:
        """Structurally validate a stored definition for the policy profile.

        Args:
            definition_id: Stored definition id.

        Returns:
            Mapping with ``ok``, ``diagnostics``, and ``fingerprint``.

        Raises:
            PermissionError: If ``validate`` is not allowed or policy rejects.
            KeyError: If the definition id is unknown.
        """
        self._require_action("validate")
        defn = self.definitions[definition_id]
        self._enforce_definition_policy(defn)
        report = structural_validate_preview(defn, profile=self.policy.profile)
        return {
            "ok": not report.has_errors,
            "diagnostics": [d.to_dict() for d in report.diagnostics],
            "fingerprint": defn.fingerprint or pipeline_fingerprint(defn),
        }

    def plan(self, definition_id: str) -> dict[str, Any]:
        """Plan a stored definition for the policy profile.

        Args:
            definition_id: Stored definition id.

        Returns:
            Mapping with ``ok``, ``diagnostics``, and optional ``plan`` dict.

        Raises:
            PermissionError: If ``plan`` is not allowed or policy rejects.
            KeyError: If the definition id is unknown.
        """
        self._require_action("plan")
        defn = self.definitions[definition_id]
        self._enforce_definition_policy(defn)
        plan, report = plan_preview(defn, profile=self.policy.profile)
        return {
            "ok": plan is not None and not report.has_errors,
            "diagnostics": [d.to_dict() for d in report.diagnostics],
            "plan": plan.to_dict() if plan is not None else None,
        }

    def submit_run(
        self,
        definition_id: str,
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Run synchronously (reference adapter — not a durable async queue).

        Args:
            definition_id: Stored definition id.
            idempotency_key: Reserved for adapters; ignored here.

        Returns:
            Job status mapping from ``job_status``.

        Raises:
            PermissionError: If ``run`` is not allowed or policy rejects.
            KeyError: If the definition id is unknown.
        """
        self._require_action("run")
        _ = idempotency_key
        defn = self.definitions[definition_id]
        self._enforce_definition_policy(defn)
        job_id = f"job-{uuid.uuid4().hex[:12]}"
        created = datetime.now(UTC).isoformat()
        job = RunJob(
            job_id=job_id,
            status="running",
            created_at=created,
            definition_fingerprint=defn.fingerprint or pipeline_fingerprint(defn),
            sync_reference=True,
        )
        self.jobs[job_id] = job
        try:
            report = run_pipeline(
                defn, profile=self.policy.profile, runtime=self.runtime
            )
            job.status = (
                "succeeded"
                if report.status.value == "succeeded"
                else report.status.value
            )
            job.report = report
        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)
        return self.job_status(job_id)

    def cancel_run(self, job_id: str) -> dict[str, Any]:
        """Reference adapter runs are synchronous; cancel is not supported in-flight.

        Args:
            job_id: Job id from ``submit_run``.

        Returns:
            Status mapping with ``cancellable`` / ``cancel_supported`` false.

        Raises:
            PermissionError: If ``cancel`` is not allowed.
            KeyError: If the job id is unknown.
        """
        self._require_action("cancel")
        job = self.jobs[job_id]
        status = self.job_status(job_id)
        status["cancellable"] = False
        status["cancel_supported"] = False
        status["message"] = (
            "Reference adapter runs synchronously; cancel has no effect on "
            f"terminal job status {job.status!r}."
        )
        return status

    def job_status(self, job_id: str) -> dict[str, Any]:
        """Return status for a synchronous reference job.

        Args:
            job_id: Job id from ``submit_run``.

        Returns:
            Status mapping including optional ``report``.

        Raises:
            PermissionError: If ``report`` is not allowed.
            KeyError: If the job id is unknown.
        """
        self._require_action("report")
        job = self.jobs[job_id]
        return {
            "job_id": job.job_id,
            "status": job.status,
            "created_at": job.created_at,
            "definition_fingerprint": job.definition_fingerprint,
            "error": job.error,
            "report": job.report.to_dict() if job.report is not None else None,
            "run_model": "synchronous_reference",
            "cancellable": False,
        }


# Re-export helpers used by OpenAPI adapters
__all__ = [
    "AuthoringService",
    "PipelinePlan",
    "PolicyContext",
    "RunJob",
    "ServiceError",
    "ValidationReport",
    "plan_pipeline_like",
    "validate_pipeline_like",
]
