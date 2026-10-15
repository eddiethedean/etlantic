"""Importable Prefect flow for targeted ETLantic managed execution."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import entry_points
from typing import Any, cast
from uuid import UUID, uuid4

from etlantic.control_plane import (
    ControlPlaneContext,
    ManagedBackend,
    validate_execution_route,
)
from etlantic.control_plane.managed_reference import (
    PREFECT_MANAGED_REFERENCE_SCHEMA,
    AcceptedExecutionReference,
)
from etlantic_prefect.deployment import ManagedDeploymentBinding
from prefect import flow

MANAGED_REFERENCE_SCHEMA = PREFECT_MANAGED_REFERENCE_SCHEMA
_ENTRY_POINT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


@dataclass(frozen=True, slots=True)
class ManagedExecutionReference(AcceptedExecutionReference):
    """Prefect compatibility spelling over the shared accepted-work reference."""

    schema: str = MANAGED_REFERENCE_SCHEMA

    def __post_init__(self) -> None:
        super(ManagedExecutionReference, self).__post_init__()
        if self.schema != MANAGED_REFERENCE_SCHEMA:
            raise ValueError("unsupported Prefect managed execution reference schema")

    @classmethod
    def from_submission(
        cls, submission: Any, *, schema: str = MANAGED_REFERENCE_SCHEMA
    ) -> ManagedExecutionReference:
        """Keep the deployed Prefect parameter schema stable."""
        if schema != MANAGED_REFERENCE_SCHEMA:
            raise ValueError("Prefect references must use the legacy wire schema")
        common = AcceptedExecutionReference.from_submission(submission, schema=schema)
        return cls(**common.to_dict())

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ManagedExecutionReference:
        """Accept only the established Prefect reference schema."""
        common = AcceptedExecutionReference.from_dict(value)
        if common.schema != MANAGED_REFERENCE_SCHEMA:
            raise ValueError("Prefect references must use the legacy wire schema")
        return cls(**common.to_dict())


def _load_trusted_backend() -> tuple[ManagedBackend, ControlPlaneContext]:
    """Load the backend factory pinned in worker deployment configuration."""
    ManagedDeploymentBinding.from_environment()
    configured_name = os.environ.get("ETLANTIC_PREFECT_WORKER_BACKEND")
    if configured_name is None or _ENTRY_POINT_NAME.fullmatch(configured_name) is None:
        raise RuntimeError("trusted Prefect worker backend is not configured")
    matches = tuple(
        entry_points(group="etlantic.prefect_worker_backends", name=configured_name)
    )
    if len(matches) != 1:
        raise RuntimeError(
            "configured Prefect worker backend is unavailable or ambiguous"
        )
    factory = matches[0].load()
    if not callable(factory):
        raise RuntimeError("configured Prefect worker backend factory is invalid")
    result = factory()
    if not isinstance(result, tuple):
        raise RuntimeError("worker backend factory returned an invalid backend context")
    backend_context = cast(tuple[Any, ...], result)
    if (
        len(backend_context) != 2
        or not isinstance(backend_context[0], ManagedBackend)
        or not isinstance(backend_context[1], ControlPlaneContext)
    ):
        raise RuntimeError("worker backend factory returned an invalid backend context")
    return backend_context[0], backend_context[1]


def _resolve_accepted_submission(
    reference: Mapping[str, Any],
    backend: ManagedBackend,
    context: ControlPlaneContext,
) -> tuple[ManagedExecutionReference, Any]:
    accepted = ManagedExecutionReference.from_dict(reference)
    submission = backend.durable_work.get_submission(context, accepted.submission_id)
    canonical = ManagedExecutionReference.from_submission(submission)
    if canonical != accepted:
        raise RuntimeError("accepted execution reference failed integrity checks")
    return accepted, submission


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _dispatch_for_submission(
    backend: ManagedBackend, context: ControlPlaneContext, submission: Any
) -> Any | None:
    if not str(getattr(submission, "execution_route", "local")).startswith("prefect:"):
        return None
    try:
        return backend.durable_work.get_dispatch(context, submission.submission_id)
    except Exception as exc:
        # A missing dispatch is expected between durable acceptance and the
        # first dispatcher tick. Other storage failures must remain visible.
        if getattr(exc, "status", None) == 404:
            return None
        raise


def _remote_flow_run_observation(
    dispatch: Any | None, binding: ManagedDeploymentBinding
) -> dict[str, Any]:
    """Read one correlated Prefect flow run without changing ETLantic state."""
    if dispatch is None:
        return {"status": "not_dispatched", "observed_at": None}
    if dispatch.execution_route != binding.execution_route:
        return {"status": "binding_mismatch", "observed_at": None}
    if (
        dispatch.status not in {"dispatched", "reconciliation_required"}
        or not dispatch.remote_run_id
    ):
        return {
            "status": dispatch.status,
            "observed_at": None,
            "dispatch_status": dispatch.status,
            "generation": getattr(dispatch, "generation", None),
            "dispatch_attempts": dispatch.dispatch_attempts,
            "error_code": getattr(dispatch, "last_error_code", None),
        }
    flow_run_id = str(dispatch.remote_run_id)
    from prefect.client.orchestration import get_client
    from prefect.exceptions import ObjectNotFound

    try:
        with get_client(sync_client=True) as client:
            flow_run = client.read_flow_run(UUID(flow_run_id))
        state = getattr(flow_run, "state", None)
        state_type = getattr(state, "type", None)
        state_type_value = getattr(state_type, "value", state_type)
        return {
            "status": getattr(state, "name", None) or state_type_value or "unknown",
            "state_type": state_type_value,
            "flow_run_id": flow_run_id,
            "observed_at": _utc_now(),
            "dispatch_status": dispatch.status,
            "generation": getattr(dispatch, "generation", None),
            "dispatch_attempts": dispatch.dispatch_attempts,
            "error_code": getattr(dispatch, "last_error_code", None),
        }
    except ObjectNotFound:
        return {
            "status": "missing",
            "flow_run_id": flow_run_id,
            "observed_at": _utc_now(),
            "dispatch_status": dispatch.status,
            "generation": getattr(dispatch, "generation", None),
            "dispatch_attempts": dispatch.dispatch_attempts,
            "error_code": getattr(dispatch, "last_error_code", None),
        }
    except Exception:
        # Keep transient server/auth/network details out of user-facing run
        # status and do not let a remote read rewrite the canonical result.
        return {
            "status": "unavailable",
            "flow_run_id": flow_run_id,
            "observed_at": _utc_now(),
            "dispatch_status": dispatch.status,
            "generation": getattr(dispatch, "generation", None),
            "dispatch_attempts": dispatch.dispatch_attempts,
            "error_code": getattr(dispatch, "last_error_code", None),
        }


def _request_remote_cancellation(
    dispatch: Any | None, binding: ManagedDeploymentBinding
) -> dict[str, Any]:
    """Ask Prefect to cancel after ETLantic has durably recorded the request."""
    if dispatch is None:
        return {"status": "not_dispatched"}
    if dispatch.execution_route != binding.execution_route:
        return {"status": "binding_mismatch"}
    if dispatch.status != "dispatched" or not dispatch.remote_run_id:
        return {"status": "not_dispatched"}
    flow_run_id = str(dispatch.remote_run_id)
    try:
        from prefect.client.orchestration import get_client
        from prefect.client.schemas.objects import State, StateType
        from prefect.client.schemas.responses import SetStateStatus

        with get_client(sync_client=True) as client:
            result = client.set_flow_run_state(
                flow_run_id,
                State(
                    type=StateType.CANCELLING,
                    message="Cancellation was durably requested by ETLantic.",
                ),
                force=False,
            )
        raw_status = getattr(result, "status", None)
        status = getattr(raw_status, "value", raw_status)
        state = getattr(result, "state", None)
        if raw_status == SetStateStatus.ACCEPT:
            outcome = "requested"
        elif raw_status == SetStateStatus.REJECT:
            outcome = "rejected"
        elif raw_status == SetStateStatus.ABORT:
            outcome = "aborted"
        else:
            outcome = "deferred"
        return {
            "status": outcome,
            "prefect_status": status,
            "flow_run_id": flow_run_id,
            "state": getattr(state, "name", None),
            "requested_at": _utc_now(),
        }
    except Exception:
        return {
            "status": "unavailable",
            "flow_run_id": flow_run_id,
            "requested_at": _utc_now(),
        }


def _reconciliation_projection(
    canonical_status: object, remote: Mapping[str, Any]
) -> dict[str, str]:
    """Describe status disagreement without mutating canonical ETL evidence."""
    canonical = (
        canonical_status.lower() if isinstance(canonical_status, str) else "unknown"
    )
    remote_status = remote.get("status")
    observed_at = remote.get("observed_at")
    if remote_status in {"unavailable", "missing", "binding_mismatch"}:
        relation = str(remote_status)
    elif remote_status == "not_dispatched":
        relation = "pending"
    else:
        remote_normalized = (
            str(remote_status).replace(" ", "").replace("_", "").casefold()
        )
        remote_terminal = remote_normalized in {
            "completed",
            "failed",
            "crashed",
            "cancelled",
            "canceled",
        }
        if canonical in {"completed", "failed", "cancelled"}:
            expected = {
                "completed": {"completed"},
                "failed": {"failed", "crashed"},
                "cancelled": {"cancelled", "canceled"},
            }[canonical]
            if remote_normalized in expected:
                relation = "consistent"
            elif remote_terminal:
                relation = "conflict"
            else:
                relation = "remote_lagging"
        elif canonical == "cancel_requested" and remote_terminal:
            relation = "canonical_reconciliation_required"
        elif canonical == "cancel_requested":
            relation = "cancellation_pending"
        elif remote_terminal:
            relation = "canonical_reconciliation_required"
        else:
            relation = "in_progress"
    result = {"status": relation}
    if isinstance(observed_at, str):
        result["observed_at"] = observed_at
    return result


def get_managed_run_status(reference: Mapping[str, Any]) -> Mapping[str, Any]:
    """Read the authorized canonical run projection for an accepted reference."""
    backend, context = _load_trusted_backend()
    try:
        accepted, submission = _resolve_accepted_submission(reference, backend, context)
        if not submission.run_id:
            raise RuntimeError("accepted submission has no canonical run identity")
        status = backend.managed_service.get_run_status(context, submission.run_id)
        binding = ManagedDeploymentBinding.from_environment()
        dispatch = _dispatch_for_submission(backend, context, submission)
        remote = _remote_flow_run_observation(dispatch, binding)
        return {
            "submission_id": accepted.submission_id,
            "run_id": submission.run_id,
            "status": status.get("status"),
            "created_at": status.get("created_at"),
            "updated_at": status.get("updated_at"),
            "remote_orchestration": remote,
            "reconciliation": _reconciliation_projection(status.get("status"), remote),
        }
    finally:
        backend.close()


def request_managed_run_cancellation(
    reference: Mapping[str, Any],
) -> Mapping[str, Any]:
    """Persist authorized ETLantic cancellation before remote coordination."""
    backend, context = _load_trusted_backend()
    try:
        accepted, submission = _resolve_accepted_submission(reference, backend, context)
        if not submission.run_id:
            raise RuntimeError("accepted submission has no canonical run identity")
        result = backend.managed_service.cancel_run(context, submission.run_id)
        binding = ManagedDeploymentBinding.from_environment()
        dispatch = _dispatch_for_submission(backend, context, submission)
        return {
            "submission_id": accepted.submission_id,
            "run_id": submission.run_id,
            "status": result.get("status"),
            "cancellation_durable": True,
            "remote_cancellation": _request_remote_cancellation(dispatch, binding),
        }
    finally:
        backend.close()


@flow(name="etlantic-managed-execution", retries=0, persist_result=False)
def managed_execution_flow(reference: Mapping[str, Any]) -> Mapping[str, Any]:
    """Execute one accepted reference using trusted worker-side configuration."""
    from prefect.runtime import flow_run

    accepted = ManagedExecutionReference.from_dict(reference)
    remote_flow_run_id = getattr(flow_run, "id", None)
    binding = ManagedDeploymentBinding.from_environment()
    if remote_flow_run_id is None:
        raise RuntimeError("Prefect flow run has no orchestration identity")
    from prefect.client.orchestration import get_client

    # Process workers may not expose deployment_id in the local runtime context;
    # resolve the run from Prefect's API before trusting its deployment binding.
    with get_client(sync_client=True) as client:
        remote_flow_run = client.read_flow_run(UUID(str(remote_flow_run_id)))
        remote_deployment = client.read_deployment(binding.deployment_id)
        remote_pool = client.read_work_pool(binding.spec.work_pool_name)
    if str(getattr(remote_flow_run, "deployment_id", None)) != str(
        binding.deployment_id
    ):
        raise RuntimeError("Prefect flow run does not belong to its trusted deployment")
    binding.verify_remote_deployment(remote_deployment)
    binding.verify_remote_work_pool(remote_pool)
    backend, context = _load_trusted_backend()
    try:
        accepted, submission = _resolve_accepted_submission(reference, backend, context)
        execution_route = validate_execution_route(submission.execution_route)
        if (
            not execution_route.startswith("prefect:")
            or binding.execution_route != execution_route
        ):
            raise RuntimeError("accepted work is not routed to this Prefect deployment")
        try:
            dispatch = backend.durable_work.get_dispatch(
                context, accepted.submission_id
            )
        except Exception as exc:
            raise RuntimeError(
                "accepted work has no durable Prefect dispatch intent"
            ) from exc
        if (
            dispatch.execution_route != binding.execution_route
            or dispatch.binding_fingerprint != binding.fingerprint
            or dispatch.plan_fingerprint != accepted.plan_fingerprint
            or dispatch.envelope_sha256 != accepted.envelope_sha256
            or dispatch.status not in {"leased", "uncertain", "dispatched"}
            or (
                dispatch.status == "dispatched"
                and dispatch.remote_run_id is not None
                and str(dispatch.remote_run_id) != str(remote_flow_run_id)
            )
        ):
            raise RuntimeError(
                "durable Prefect dispatch intent does not match this flow run"
            )
        result = backend.execute_submission(
            context,
            accepted.submission_id,
            owner_id=f"prefect:{remote_flow_run_id or uuid4().hex}",
            execution_route=execution_route,
        )
        status = result.get("status")
        if result.get("executed") is not True:
            if status == "completed":
                # A duplicate remote invocation resolves to the existing durable
                # outcome without starting another effectful attempt.
                return {
                    "submission_id": accepted.submission_id,
                    "status": status,
                    "executed": False,
                    "report_sha256": result.get("report_sha256"),
                    "prefect_flow_run_id": str(remote_flow_run_id)
                    if remote_flow_run_id is not None
                    else None,
                }
            if status in {"failed", "cancelled"}:
                raise RuntimeError(
                    f"accepted ETLantic execution is {status}; durable evidence retained"
                )
            return {
                "submission_id": accepted.submission_id,
                "status": status,
                "outcome": "delivery_noop",
                "executed": False,
                "reason": "target_not_claimed_by_this_invocation",
                "prefect_flow_run_id": str(remote_flow_run_id)
                if remote_flow_run_id is not None
                else None,
            }
        if status != "completed":
            raise RuntimeError(f"ETLantic execution finished with status {status!r}")
        return {
            "submission_id": accepted.submission_id,
            "status": status,
            "executed": True,
            "attempt_id": result.get("attempt_id"),
            "report_sha256": result.get("report_sha256"),
            "prefect_flow_run_id": str(remote_flow_run_id)
            if remote_flow_run_id is not None
            else None,
        }
    finally:
        backend.close()
