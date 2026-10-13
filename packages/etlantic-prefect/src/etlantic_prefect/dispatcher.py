"""Durable, idempotent dispatch from accepted ETLantic work to Prefect."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any

from etlantic.control_plane import (
    ControlPlaneContext,
    ManagedBackend,
    validate_control_plane_context,
)
from etlantic.runtime.role import RuntimeRoleLifecycle, RuntimeRoleStatus
from etlantic_prefect.deployment import ManagedDeploymentBinding
from etlantic_prefect.worker import ManagedExecutionReference


@dataclass(slots=True)
class _DispatcherDiagnostics:
    """Process-local counters; identifiers and provider payloads are excluded."""

    ticks: int = 0
    failed_ticks: int = 0
    dispatch_attempts: int = 0
    uncertain_creates: int = 0
    remote_api_failures: int = 0
    remote_missing_observations: int = 0
    remote_terminal_failure_observations: int = 0
    dispatch_errors: int = 0
    queue_age_high_water_seconds: float | None = None
    last_observed_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat().replace("+00:00", "Z")
    )


@dataclass(slots=True)
class PrefectDispatcher:
    """One bounded dispatch tick over the trusted route's accepted work."""

    backend: ManagedBackend
    context: ControlPlaneContext
    binding: ManagedDeploymentBinding
    owner_id: str
    lease_seconds: int = 30
    missing_run_grace_seconds: int = 300
    _role: RuntimeRoleLifecycle = field(
        default_factory=lambda: RuntimeRoleLifecycle(
            "dispatcher",
            capabilities=(
                "read_status",
                "cooperative_drain",
                "bounded_dispatch",
                "idempotent_recovery",
            ),
        ),
        init=False,
        repr=False,
    )
    _reconciliation_cursor: str | None = field(default=None, init=False, repr=False)
    _diagnostics: _DispatcherDiagnostics = field(
        default_factory=_DispatcherDiagnostics, init=False, repr=False
    )
    _diagnostics_lock: Lock = field(default_factory=Lock, init=False, repr=False)

    def __post_init__(self) -> None:
        validate_control_plane_context(self.context)
        self.binding.spec.assert_local_runtime()
        if not self.owner_id.strip() or len(self.owner_id) > 256:
            raise ValueError("owner_id must contain 1 to 256 characters")
        if type(self.lease_seconds) is not int or not 1 <= self.lease_seconds <= 600:
            raise ValueError("lease_seconds must be between 1 and 600")
        if (
            type(self.missing_run_grace_seconds) is not int
            or not 30 <= self.missing_run_grace_seconds <= 86_400
        ):
            raise ValueError("missing_run_grace_seconds must be between 30 and 86400")
        register_runtime_role = getattr(self.backend, "register_runtime_role", None)
        if callable(register_runtime_role):
            register_runtime_role(self._role)

    @classmethod
    def from_environment(
        cls,
        backend: ManagedBackend,
        context: ControlPlaneContext,
        *,
        owner_id: str,
        lease_seconds: int = 30,
        missing_run_grace_seconds: int = 300,
    ) -> PrefectDispatcher:
        """Build from worker/deployment identifiers in trusted process config."""
        binding = ManagedDeploymentBinding.from_environment()
        return cls(
            backend=backend,
            context=context,
            binding=binding,
            owner_id=owner_id,
            lease_seconds=lease_seconds,
            missing_run_grace_seconds=missing_run_grace_seconds,
        )

    async def tick(self, *, limit: int = 20) -> list[dict[str, Any]]:
        """Dispatch a bounded page, preserving uncertain creates for recovery."""
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        if not self._role.begin_tick():
            return []
        self._record_diagnostic(ticks=1)
        try:
            await self._verify_remote_binding()
            await self._reconcile_remote_failures(limit=limit)
            candidates = self.backend.durable_work.pending_dispatches(
                self.context,
                execution_route=self.binding.execution_route,
                limit=limit,
            )
            results: list[dict[str, Any]] = []
            reason_code: str | None = None
            for candidate in candidates:
                if not self._role.begin_dispatch():
                    break
                try:
                    receipt = await self._dispatch_submission(candidate.submission_id)
                    results.append(receipt)
                    if receipt.get("error_code"):
                        self._record_diagnostic(dispatch_errors=1)
                        reason_code = (
                            "prefect_unavailable"
                            if receipt["error_code"] == "prefect_create_uncertain"
                            else "dispatch_store_unavailable"
                        )
                        if receipt["error_code"] == "prefect_create_uncertain":
                            self._record_diagnostic(uncertain_creates=1)
                    queue_age = receipt.get("queue_age_seconds")
                    if isinstance(queue_age, (int, float)):
                        self._record_queue_age(float(queue_age))
                finally:
                    self._role.end_dispatch()
            self._role.observe_prerequisites(
                "unusable" if reason_code else "usable", reason_code=reason_code
            )
            return results
        except Exception:
            self._record_diagnostic(failed_ticks=1)
            self._role.observe_prerequisites(
                "unusable", reason_code="dispatch_tick_failed"
            )
            raise
        finally:
            self._role.end_tick()

    async def _reconcile_remote_failures(
        self, *, limit: int, now: datetime | None = None
    ) -> None:
        """Rearm only pre-claim remote failures or old missing run records."""
        from uuid import UUID

        from prefect.client.orchestration import get_client
        from prefect.exceptions import ObjectNotFound

        candidates = self.backend.durable_work.dispatched_for_reconciliation(
            self.context,
            execution_route=self.binding.execution_route,
            limit=limit,
            after_submission_id=self._reconciliation_cursor,
        )
        if not candidates and self._reconciliation_cursor is not None:
            self._reconciliation_cursor = None
            candidates = self.backend.durable_work.dispatched_for_reconciliation(
                self.context,
                execution_route=self.binding.execution_route,
                limit=limit,
            )
        if not candidates:
            return
        self._reconciliation_cursor = candidates[-1].submission_id
        client_ready = False
        try:
            async with get_client() as client:
                client_ready = True
                for dispatch in candidates:
                    flow_run_id = dispatch.remote_run_id
                    if flow_run_id is None:
                        continue
                    try:
                        flow_run = await client.read_flow_run(UUID(flow_run_id))
                    except ObjectNotFound:
                        self._record_diagnostic(remote_missing_observations=1)
                        self.backend.durable_work.rearm_dispatch_after_remote_missing(
                            self.context,
                            dispatch.submission_id,
                            expected_remote_run_id=flow_run_id,
                            minimum_age_seconds=self.missing_run_grace_seconds,
                            now=now,
                        )
                        continue
                    except Exception:
                        self._record_diagnostic(remote_api_failures=1)
                        raise
                    state = getattr(flow_run, "state", None)
                    state_type = getattr(state, "type", None)
                    state_value = getattr(state_type, "value", state_type)
                    if state_value not in {"FAILED", "CRASHED"}:
                        continue
                    self._record_diagnostic(remote_terminal_failure_observations=1)
                    self.backend.durable_work.rearm_dispatch_after_remote_failure(
                        self.context,
                        dispatch.submission_id,
                        expected_remote_run_id=flow_run_id,
                        now=now,
                    )
        except Exception:
            if not client_ready:
                self._record_diagnostic(remote_api_failures=1)
            raise

    async def _verify_remote_binding(self) -> None:
        """Fail before a claim if the remote deployment or pool has drifted."""
        from prefect.client.orchestration import get_client

        try:
            async with get_client() as client:
                deployment = await client.read_deployment(self.binding.deployment_id)
                pool = await client.read_work_pool(self.binding.spec.work_pool_name)
        except Exception:
            self._record_diagnostic(remote_api_failures=1)
            raise
        self.binding.verify_remote_deployment(deployment)
        self.binding.verify_remote_work_pool(pool)

    def status(self) -> RuntimeRoleStatus:
        """Return cached local dispatcher readiness without provider I/O."""
        return self._role.status()

    def diagnostics(self) -> dict[str, int | float | str | None]:
        """Return bounded process-local dispatch counters without provider I/O."""
        with self._diagnostics_lock:
            snapshot = self._diagnostics
            return {
                "schema": "etlantic.prefect_dispatcher_diagnostics/1",
                "ticks": snapshot.ticks,
                "failed_ticks": snapshot.failed_ticks,
                "dispatch_attempts": snapshot.dispatch_attempts,
                "uncertain_creates": snapshot.uncertain_creates,
                "remote_api_failures": snapshot.remote_api_failures,
                "dispatch_errors": snapshot.dispatch_errors,
                "remote_missing_observations": snapshot.remote_missing_observations,
                "remote_terminal_failure_observations": (
                    snapshot.remote_terminal_failure_observations
                ),
                "queue_age_high_water_seconds": (snapshot.queue_age_high_water_seconds),
                "observed_at": snapshot.last_observed_at,
            }

    def _record_diagnostic(self, **increments: int) -> None:
        with self._diagnostics_lock:
            for name, amount in increments.items():
                if name not in {
                    "ticks",
                    "failed_ticks",
                    "dispatch_attempts",
                    "uncertain_creates",
                    "remote_api_failures",
                    "remote_missing_observations",
                    "remote_terminal_failure_observations",
                    "dispatch_errors",
                }:
                    raise ValueError("unknown dispatcher diagnostic counter")
                setattr(
                    self._diagnostics, name, getattr(self._diagnostics, name) + amount
                )
            self._diagnostics.last_observed_at = (
                datetime.now(UTC).isoformat().replace("+00:00", "Z")
            )

    def _record_queue_age(self, queue_age_seconds: float) -> None:
        with self._diagnostics_lock:
            current = self._diagnostics.queue_age_high_water_seconds
            if current is None or queue_age_seconds > current:
                self._diagnostics.queue_age_high_water_seconds = queue_age_seconds
            self._diagnostics.last_observed_at = (
                datetime.now(UTC).isoformat().replace("+00:00", "Z")
            )

    def request_drain(self) -> RuntimeRoleStatus:
        """Stop new dispatcher ticks and claims while an active create finishes."""
        return self._role.request_drain()

    @property
    def draining(self) -> bool:
        return self._role.draining

    async def _dispatch_submission(self, submission_id: str) -> dict[str, Any]:
        """Create or recover one Prefect flow run using its stable creation key."""
        durable = self.backend.durable_work
        dispatch = durable.prepare_dispatch(self.context, submission_id)
        if dispatch.execution_route != self.binding.execution_route:
            raise RuntimeError("accepted work belongs to a different Prefect route")
        if dispatch.status in {"dispatched", "cancelled"}:
            return self._receipt(dispatch)

        claim = durable.claim_dispatch(
            self.context,
            submission_id,
            owner_id=self.owner_id,
            lease_seconds=self.lease_seconds,
        )
        if claim is None:
            return self._receipt(durable.get_dispatch(self.context, submission_id))

        remote_create_started = False
        uncertain_resolution_started = False
        try:
            submission = durable.get_submission(self.context, submission_id)
            if submission.status not in {"accepted", "dispatched"}:
                if dispatch.status == "uncertain" and submission.status in {
                    "cancel_requested",
                    "cancelled",
                }:
                    uncertain_resolution_started = True
                    return await self._resolve_cancelled_uncertain_create(
                        submission_id,
                        creation_key=claim.creation_key,
                        owner_id=self.owner_id,
                        fencing_token=claim.lease_fencing_token,
                    )
                durable.release_dispatch(
                    self.context,
                    submission_id,
                    owner_id=self.owner_id,
                    fencing_token=claim.lease_fencing_token,
                    outcome_uncertain=False,
                    cancelled=True,
                    error_code="submission_not_active",
                )
                return {
                    "submission_id": submission_id,
                    "status": "not_dispatched",
                    "reason": "submission_not_active",
                }
            reference = ManagedExecutionReference.from_submission(submission)
            if (
                reference.plan_fingerprint != claim.plan_fingerprint
                or reference.envelope_sha256 != claim.envelope_sha256
            ):
                raise RuntimeError(
                    "accepted envelope changed after dispatch preparation"
                )

            from prefect.client.orchestration import get_client

            async with get_client() as client:
                remote_create_started = True
                self._record_diagnostic(dispatch_attempts=1)
                try:
                    flow_run = await client.create_flow_run_from_deployment(
                        self.binding.deployment_id,
                        parameters={"reference": reference.to_dict()},
                        idempotency_key=claim.creation_key,
                        name=f"etlantic-{claim.envelope_sha256[:16]}",
                        tags=["etlantic-managed"],
                    )
                except Exception:
                    self._record_diagnostic(remote_api_failures=1)
                    raise
            linked = durable.link_dispatch(
                self.context,
                submission_id,
                owner_id=self.owner_id,
                fencing_token=claim.lease_fencing_token,
                remote_run_id=str(flow_run.id),
            )
            return self._receipt(linked)
        except Exception:
            # A lost response may follow a successful remote create. The same
            # persisted key and parameters are reused by the next dispatcher.
            with suppress(Exception):
                durable.release_dispatch(
                    self.context,
                    submission_id,
                    owner_id=self.owner_id,
                    fencing_token=claim.lease_fencing_token,
                    outcome_uncertain=(
                        remote_create_started or uncertain_resolution_started
                    ),
                    error_code=(
                        "prefect_create_uncertain"
                        if remote_create_started or uncertain_resolution_started
                        else "dispatch_prepare_failed"
                    ),
                )
            current = durable.get_dispatch(self.context, submission_id)
            return self._receipt(current)

    async def _resolve_cancelled_uncertain_create(
        self,
        submission_id: str,
        *,
        creation_key: str,
        owner_id: str,
        fencing_token: int,
    ) -> dict[str, Any]:
        """Resolve a lost create response without creating or replaying work."""
        from prefect.client.orchestration import get_client
        from prefect.client.schemas.filters import (
            FlowRunFilter,
            FlowRunFilterIdempotencyKey,
        )

        durable = self.backend.durable_work
        async with get_client() as client:
            runs = await client.read_flow_runs(
                flow_run_filter=FlowRunFilter(
                    idempotency_key=FlowRunFilterIdempotencyKey(any_=[creation_key])
                ),
                limit=2,
            )
            # An empty response can be transiently stale; multiple matches are
            # ambiguous. In either case retain the uncertain record for retry.
            if len(runs) != 1:
                durable.release_dispatch(
                    self.context,
                    submission_id,
                    owner_id=owner_id,
                    fencing_token=fencing_token,
                    outcome_uncertain=True,
                    error_code="prefect_create_uncertain",
                )
                return self._receipt(durable.get_dispatch(self.context, submission_id))

            flow_run = runs[0]
            durable.link_dispatch(
                self.context,
                submission_id,
                owner_id=owner_id,
                fencing_token=fencing_token,
                prefect_flow_run_id=str(flow_run.id),
            )
            state = getattr(flow_run, "state", None)
            state_type = getattr(state, "type", None)
            state_value = getattr(state_type, "value", state_type)
            if state_value not in {
                "CANCELLED",
                "COMPLETED",
                "FAILED",
                "CRASHED",
            }:
                from prefect.client.schemas.objects import State, StateType

                await client.set_flow_run_state(
                    flow_run.id,
                    State(
                        type=StateType.CANCELLING,
                        message="ETLantic cancellation resolved an uncertain dispatch.",
                    ),
                    force=False,
                )

        durable.reconcile_cancelled_submissions(
            self.context,
            limit=1,
            submission_id=submission_id,
            execution_route=self.binding.execution_route,
        )
        return self._receipt(durable.get_dispatch(self.context, submission_id))

    @staticmethod
    def _receipt(dispatch: Any) -> dict[str, Any]:
        try:
            queued_at = datetime.fromisoformat(
                dispatch.created_at.replace("Z", "+00:00")
            )
            queue_age_seconds = max(
                0.0, (datetime.now(UTC) - queued_at).total_seconds()
            )
        except (AttributeError, TypeError, ValueError):
            queue_age_seconds = None
        return {
            "submission_id": dispatch.submission_id,
            "status": dispatch.status,
            "generation": dispatch.generation,
            "backend_kind": dispatch.backend_kind,
            "remote_run_id": dispatch.remote_run_id,
            "prefect_flow_run_id": dispatch.prefect_flow_run_id,
            "dispatch_attempts": dispatch.dispatch_attempts,
            "error_code": dispatch.last_error_code,
            "retry_after_at": dispatch.retry_after_at,
            "queue_age_seconds": queue_age_seconds,
        }


__all__ = ["PrefectDispatcher"]
