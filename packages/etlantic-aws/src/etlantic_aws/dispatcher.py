"""Durable, fenced ECS/Fargate dispatch over public managed-work operations."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable, Mapping
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from etlantic.control_plane import (
    AcceptedExecutionReference,
    ControlPlaneContext,
    ManagedBackend,
    validate_control_plane_context,
)

from etlantic_aws.binding import ECSExecutionBinding

# RunTask idempotency expires at the earlier of 24 hours or one hour after
# the task stops. A task can stop immediately, so keep a ten-minute margin.
_ECS_CLIENT_TOKEN_SAFE_RETRY_WINDOW = timedelta(minutes=50)
_ECS_ACTIVE_TASK_STATES = frozenset(
    {
        "PROVISIONING",
        "PENDING",
        "ACTIVATING",
        "RUNNING",
        "DEACTIVATING",
        "STOPPING",
        "DEPROVISIONING",
    }
)


def _as_mapping(value: object, message: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RuntimeError(message)
    return cast(Mapping[str, Any], value)


def _mapping_rows(value: object) -> list[Mapping[str, Any]] | None:
    if not isinstance(value, list) or any(
        not isinstance(item, Mapping) for item in cast(Iterable[object], value)
    ):
        return None
    return [cast(Mapping[str, Any], item) for item in cast(Iterable[object], value)]


@dataclass(frozen=True, slots=True)
class ECSDispatchResult:
    submission_id: str
    status: str
    remote_run_id: str | None = None
    error_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "submission_id": self.submission_id,
            "backend_kind": "ecs",
            "status": self.status,
            "remote_run_id": self.remote_run_id,
            "error_code": self.error_code,
        }


@dataclass(slots=True)
class ECSDispatcher:
    """Dispatch accepted work to one immutable Fargate task binding."""

    backend: ManagedBackend
    context: ControlPlaneContext
    binding: ECSExecutionBinding
    ecs_client: Any
    sts_client: Any
    owner_id: str
    lease_seconds: int = 30
    clock: Callable[[], datetime] | None = None
    _reconciliation_cursor: str | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        validate_control_plane_context(self.context)
        if not isinstance(cast(object, self.binding), ECSExecutionBinding):
            raise TypeError("binding must be an ECSExecutionBinding")
        owner_id: object = cast(object, self.owner_id)
        if not isinstance(owner_id, str) or not owner_id.strip():
            raise ValueError("owner_id must be a non-empty trusted worker identity")
        if len(self.owner_id) > 256:
            raise ValueError("owner_id must be at most 256 characters")
        if type(self.lease_seconds) is not int or not 1 <= self.lease_seconds <= 600:
            raise ValueError("lease_seconds must be between 1 and 600")
        configured_route = getattr(
            self.backend.managed_service, "execution_route", None
        )
        if configured_route != self.binding.execution_route:
            raise ValueError("managed backend route does not match the ECS binding")

    def tick(self, *, limit: int = 20) -> list[ECSDispatchResult]:
        """Verify the pinned AWS tuple, then submit a bounded pending page."""
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        self.binding.verify(self.ecs_client, self.sts_client)
        pending = self.backend.durable_work.pending_dispatches(
            self.context,
            execution_route=self.binding.execution_route,
            limit=limit,
        )
        return [self._dispatch_submission(item.submission_id) for item in pending]

    def dispatch_submission(self, submission_id: str) -> ECSDispatchResult:
        """Create one task with durable identity and response-loss recovery."""
        self.binding.verify(self.ecs_client, self.sts_client)
        return self._dispatch_submission(submission_id)

    def _dispatch_submission(self, submission_id: str) -> ECSDispatchResult:
        """Dispatch after the pinned account/cluster/task tuple was checked."""
        submission_id_value: object = cast(object, submission_id)
        if not isinstance(submission_id_value, str) or not submission_id_value.strip():
            raise ValueError("submission_id must be a non-empty identifier")
        durable = self.backend.durable_work
        intent = durable.prepare_dispatch(self.context, submission_id)
        if (
            intent.backend_kind != "ecs"
            or intent.execution_route != self.binding.execution_route
            or intent.binding_fingerprint != self.binding.fingerprint
        ):
            raise RuntimeError("durable dispatch does not match this ECS binding")
        submission = durable.get_submission(self.context, submission_id)
        if (
            intent.status in {"uncertain", "leased", "reconciliation_required"}
            and submission.status == "cancel_requested"
        ):
            return self._resolve_cancelled_uncertain(submission_id, intent)
        if (
            submission.status == "cancelled"
            and intent.backend_kind == "ecs"
            and intent.status in {"uncertain", "leased", "reconciliation_required"}
            and intent.remote_run_id is None
        ):
            if durable.list_attempts(self.context, submission_id):
                settled = durable.settle_terminal_ecs_dispatch(
                    self.context,
                    submission_id,
                    expected_generation=intent.generation,
                    now=self._now(),
                )
                return ECSDispatchResult(
                    submission_id,
                    settled.status if settled is not None else intent.status,
                    error_code=(
                        settled.last_error_code
                        if settled is not None
                        else "ecs_terminal_recovery_waiting"
                    ),
                )
            return self._resolve_cancelled_uncertain(submission_id, intent)
        if (
            submission.status in {"completed", "failed"}
            and intent.backend_kind == "ecs"
            and intent.status in {"uncertain", "leased", "reconciliation_required"}
            and intent.remote_run_id is None
        ):
            settled = durable.settle_terminal_ecs_dispatch(
                self.context,
                submission_id,
                expected_generation=intent.generation,
                now=self._now(),
            )
            return ECSDispatchResult(
                submission_id,
                settled.status if settled is not None else intent.status,
                remote_run_id=(settled.remote_run_id if settled is not None else None),
                error_code=(
                    settled.last_error_code
                    if settled is not None
                    else "ecs_terminal_recovery_waiting"
                ),
            )
        if submission.status != "accepted":
            return ECSDispatchResult(
                submission_id, "not_dispatched", error_code="submission_not_active"
            )
        if (
            intent.backend_kind == "ecs"
            and intent.status in {"uncertain", "leased"}
            and intent.remote_run_id is None
        ):
            current_time = self._now()
            lease_expires_at = self._parse_time(intent.lease_expires_at)
            if (
                intent.status == "leased"
                and lease_expires_at is not None
                and lease_expires_at > current_time
            ):
                return ECSDispatchResult(submission_id, intent.status)
            creation_started_at = self._parse_time(intent.creation_started_at)
            retry_deadline = (
                creation_started_at + _ECS_CLIENT_TOKEN_SAFE_RETRY_WINDOW
                if creation_started_at is not None
                else current_time
            )
            if current_time >= retry_deadline:
                quarantined = durable.quarantine_expired_ecs_dispatch(
                    self.context,
                    submission_id,
                    expected_generation=intent.generation,
                    expected_creation_started_at=intent.creation_started_at,
                    safe_retry_deadline=retry_deadline,
                    now=current_time,
                )
                return ECSDispatchResult(
                    submission_id,
                    quarantined.status,
                    remote_run_id=quarantined.remote_run_id,
                    error_code=quarantined.last_error_code,
                )
        reference = AcceptedExecutionReference.from_submission(submission)
        if (
            reference.plan_fingerprint != intent.plan_fingerprint
            or reference.envelope_sha256 != intent.envelope_sha256
        ):
            raise RuntimeError("accepted envelope changed after dispatch preparation")
        claim = durable.claim_dispatch(
            self.context,
            submission_id,
            owner_id=self.owner_id,
            lease_seconds=self.lease_seconds,
            now=self._now(),
        )
        if claim is None:
            current = durable.get_dispatch(self.context, submission_id)
            return ECSDispatchResult(
                submission_id,
                current.status,
                remote_run_id=current.remote_run_id,
                error_code=current.last_error_code,
            )
        if (
            claim.backend_kind != "ecs"
            or claim.execution_route != self.binding.execution_route
            or claim.binding_fingerprint != self.binding.fingerprint
        ):
            durable.release_dispatch(
                self.context,
                submission_id,
                owner_id=self.owner_id,
                fencing_token=claim.lease_fencing_token,
                outcome_uncertain=False,
                error_code="ecs_binding_mismatch",
            )
            raise RuntimeError("claimed dispatch does not match this ECS binding")

        # RunTask permits at most 64 printable ASCII characters. The durable
        # creation key is stable per dispatch generation and fits after hashing.
        token = hashlib.sha256(claim.creation_key.encode("utf-8")).hexdigest()
        request = self.binding.request(client_token=token, reference=reference)
        # The pre-claim check can become stale while the durable claim waits on
        # storage. Recheck immediately before the non-transactional RunTask call.
        claimed_at = self._now()
        creation_started_at = self._parse_time(claim.creation_started_at)
        retry_deadline = (
            creation_started_at + _ECS_CLIENT_TOKEN_SAFE_RETRY_WINDOW
            if creation_started_at is not None
            else claimed_at
        )
        if claimed_at >= retry_deadline:
            quarantined = durable.quarantine_expired_ecs_dispatch(
                self.context,
                submission_id,
                expected_generation=claim.generation,
                expected_creation_started_at=claim.creation_started_at,
                safe_retry_deadline=retry_deadline,
                owner_id=self.owner_id,
                fencing_token=claim.lease_fencing_token,
                now=claimed_at,
            )
            return ECSDispatchResult(
                submission_id,
                quarantined.status,
                remote_run_id=quarantined.remote_run_id,
                error_code=quarantined.last_error_code,
            )
        create_started = False
        try:
            create_started = True
            response = _as_mapping(
                self.ecs_client.run_task(**request), "ECS RunTask response is malformed"
            )
            tasks = _mapping_rows(response.get("tasks", []))
            failures = _mapping_rows(response.get("failures", []))
            if tasks is None or failures is None:
                released = durable.release_dispatch(
                    self.context,
                    submission_id,
                    owner_id=self.owner_id,
                    fencing_token=claim.lease_fencing_token,
                    outcome_uncertain=True,
                    error_code="ecs_run_task_uncertain",
                )
                return ECSDispatchResult(
                    submission_id,
                    released.status,
                    error_code=released.last_error_code,
                )
            if len(tasks) != 1 or failures:
                uncertain = bool(tasks) or not failures
                released = durable.release_dispatch(
                    self.context,
                    submission_id,
                    owner_id=self.owner_id,
                    fencing_token=claim.lease_fencing_token,
                    outcome_uncertain=uncertain,
                    error_code=(
                        "ecs_run_task_uncertain"
                        if uncertain
                        else "ecs_run_task_rejected"
                    ),
                )
                return ECSDispatchResult(
                    submission_id,
                    released.status,
                    error_code=released.last_error_code,
                )
            task_arn = tasks[0].get("taskArn")
            task_prefix = (
                f"arn:{self.binding.partition}:ecs:{self.binding.region}:"
                f"{self.binding.account_id}:task/"
            )
            if not isinstance(task_arn, str) or not task_arn.startswith(task_prefix):
                released = durable.release_dispatch(
                    self.context,
                    submission_id,
                    owner_id=self.owner_id,
                    fencing_token=claim.lease_fencing_token,
                    outcome_uncertain=True,
                    error_code="ecs_run_task_uncertain",
                )
                return ECSDispatchResult(
                    submission_id,
                    released.status,
                    error_code=released.last_error_code,
                )
            linked = durable.link_dispatch(
                self.context,
                submission_id,
                owner_id=self.owner_id,
                fencing_token=claim.lease_fencing_token,
                remote_run_id=task_arn,
            )
            return ECSDispatchResult(
                submission_id, linked.status, remote_run_id=linked.remote_run_id
            )
        except Exception:
            # Any exception after the request begins can follow an accepted
            # RunTask, so retain the lease outcome as uncertain and reuse the
            # same generation token and complete request on retry.
            if create_started:
                with suppress(Exception):
                    durable.release_dispatch(
                        self.context,
                        submission_id,
                        owner_id=self.owner_id,
                        fencing_token=claim.lease_fencing_token,
                        outcome_uncertain=True,
                        error_code="ecs_run_task_uncertain",
                    )
                current = durable.get_dispatch(self.context, submission_id)
                return ECSDispatchResult(
                    submission_id,
                    current.status,
                    remote_run_id=current.remote_run_id,
                    error_code=current.last_error_code,
                )
            raise

    def _resolve_cancelled_uncertain(
        self, submission_id: str, intent: Any
    ) -> ECSDispatchResult:
        """Find and stop a task whose successful RunTask response was lost."""
        durable = self.backend.durable_work
        current_time = self._now()
        claim = durable.claim_dispatch(
            self.context,
            submission_id,
            owner_id=self.owner_id,
            lease_seconds=self.lease_seconds,
            now=current_time,
        )
        if claim is None:
            current = durable.get_dispatch(self.context, submission_id)
            return ECSDispatchResult(
                submission_id,
                current.status,
                remote_run_id=current.remote_run_id,
                error_code=current.last_error_code,
            )

        token = hashlib.sha256(intent.creation_key.encode("utf-8")).hexdigest()
        task_arns: set[str] = set()
        try:
            # startedBy cannot be combined with desiredStatus. Enumerate both
            # valid desired-status sets and verify the durable token locally
            # from DescribeTasks. PENDING is not a useful desired status.
            for desired_status in ("RUNNING", "STOPPED"):
                next_token: str | None = None
                for _page in range(10):
                    request: dict[str, Any] = {
                        "cluster": self.binding.cluster_arn,
                        "desiredStatus": desired_status,
                        "maxResults": 100,
                    }
                    if next_token is not None:
                        request["nextToken"] = next_token
                    response = _as_mapping(
                        self.ecs_client.list_tasks(**request),
                        "ECS task lookup response is malformed",
                    )
                    task_arn_rows: object = response.get("taskArns", [])
                    if not isinstance(task_arn_rows, list) or any(
                        not isinstance(item, str) or not item
                        for item in cast(Iterable[object], task_arn_rows)
                    ):
                        raise RuntimeError("ECS task lookup response is malformed")
                    task_arns.update(cast(list[str], task_arn_rows))
                    following = response.get("nextToken")
                    if following is None:
                        next_token = None
                        break
                    if not isinstance(following, str) or not following:
                        raise RuntimeError("ECS task lookup pagination is malformed")
                    next_token = following
                if next_token is not None:
                    released = durable.release_dispatch(
                        self.context,
                        submission_id,
                        owner_id=self.owner_id,
                        fencing_token=claim.lease_fencing_token,
                        outcome_uncertain=True,
                        error_code="ecs_cancel_lookup_incomplete",
                        now=self._now(),
                    )
                    return ECSDispatchResult(
                        submission_id,
                        released.status,
                        error_code=released.last_error_code,
                    )
        except Exception:
            released = durable.release_dispatch(
                self.context,
                submission_id,
                owner_id=self.owner_id,
                fencing_token=claim.lease_fencing_token,
                outcome_uncertain=True,
                error_code="ecs_cancel_lookup_unavailable",
                now=self._now(),
            )
            return ECSDispatchResult(
                submission_id,
                released.status,
                error_code=released.last_error_code,
            )

        task_rows: list[Mapping[str, Any]] = []
        try:
            ordered_arns = sorted(task_arns)
            for offset in range(0, len(ordered_arns), 100):
                response = _as_mapping(
                    self.ecs_client.describe_tasks(
                        cluster=self.binding.cluster_arn,
                        tasks=ordered_arns[offset : offset + 100],
                        include=["TAGS"],
                    ),
                    "ECS task lookup response is malformed",
                )
                described_task_rows = _mapping_rows(response.get("tasks", []))
                failures = _mapping_rows(response.get("failures", []))
                if described_task_rows is None or failures is None or failures:
                    raise RuntimeError("ECS task lookup is incomplete")
                task_rows.extend(described_task_rows)
        except Exception:
            released = durable.release_dispatch(
                self.context,
                submission_id,
                owner_id=self.owner_id,
                fencing_token=claim.lease_fencing_token,
                outcome_uncertain=True,
                error_code="ecs_cancel_observation_incomplete",
                now=self._now(),
            )
            return ECSDispatchResult(
                submission_id,
                released.status,
                error_code=released.last_error_code,
            )

        by_arn: dict[str, Mapping[str, Any]] = {}
        for row in task_rows:
            arn = row.get("taskArn")
            if not isinstance(arn, str) or arn not in task_arns or arn in by_arn:
                by_arn = {}
                break
            by_arn[arn] = row
        if set(by_arn) != task_arns:
            released = durable.release_dispatch(
                self.context,
                submission_id,
                owner_id=self.owner_id,
                fencing_token=claim.lease_fencing_token,
                outcome_uncertain=True,
                error_code="ecs_cancel_identity_mismatch",
                now=self._now(),
            )
            return ECSDispatchResult(
                submission_id,
                released.status,
                error_code=released.last_error_code,
            )

        rows: list[Mapping[str, Any]] = []
        for arn, row in by_arn.items():
            if row.get("startedBy") != token[:36]:
                continue
            if not self._matches_dispatch_task(row, arn, token):
                released = durable.release_dispatch(
                    self.context,
                    submission_id,
                    owner_id=self.owner_id,
                    fencing_token=claim.lease_fencing_token,
                    outcome_uncertain=True,
                    error_code="ecs_cancel_identity_mismatch",
                    now=self._now(),
                )
                return ECSDispatchResult(
                    submission_id,
                    released.status,
                    error_code=released.last_error_code,
                )
            rows.append(row)

        rows.sort(key=lambda row: cast(str, row["taskArn"]))
        if not rows:
            released = durable.release_dispatch(
                self.context,
                submission_id,
                owner_id=self.owner_id,
                fencing_token=claim.lease_fencing_token,
                outcome_uncertain=True,
                error_code="ecs_cancel_identity_unresolved",
                now=self._now(),
            )
            return ECSDispatchResult(
                submission_id,
                released.status,
                remote_run_id=released.remote_run_id,
                error_code=released.last_error_code,
            )

        if any(
            row.get("lastStatus") != "STOPPED"
            and row.get("lastStatus") not in _ECS_ACTIVE_TASK_STATES
            for row in rows
        ):
            released = durable.release_dispatch(
                self.context,
                submission_id,
                owner_id=self.owner_id,
                fencing_token=claim.lease_fencing_token,
                outcome_uncertain=True,
                error_code="ecs_cancel_task_state_unknown",
                now=self._now(),
            )
            return ECSDispatchResult(
                submission_id,
                released.status,
                error_code=released.last_error_code,
            )

        active_rows = [row for row in rows if row.get("lastStatus") != "STOPPED"]
        if len(rows) == 1:
            linked = durable.link_dispatch(
                self.context,
                submission_id,
                owner_id=self.owner_id,
                fencing_token=claim.lease_fencing_token,
                remote_run_id=cast(str, rows[0]["taskArn"]),
                now=self._now(),
            )
            if active_rows:
                try:
                    self.ecs_client.stop_task(
                        cluster=self.binding.cluster_arn,
                        task=linked.remote_run_id,
                        reason="ETLantic canonical cancellation requested",
                    )
                except Exception:
                    return ECSDispatchResult(
                        submission_id,
                        linked.status,
                        remote_run_id=linked.remote_run_id,
                        error_code="ecs_cancel_stop_unavailable",
                    )
                return ECSDispatchResult(
                    submission_id,
                    linked.status,
                    remote_run_id=linked.remote_run_id,
                    error_code="ecs_cancel_stop_requested",
                )
        elif active_rows:
            try:
                for row in active_rows:
                    self.ecs_client.stop_task(
                        cluster=self.binding.cluster_arn,
                        task=cast(str, row["taskArn"]),
                        reason="ETLantic canonical cancellation requested",
                    )
            except Exception:
                pass
            released = durable.release_dispatch(
                self.context,
                submission_id,
                owner_id=self.owner_id,
                fencing_token=claim.lease_fencing_token,
                outcome_uncertain=True,
                error_code="ecs_cancel_tasks_stopping",
                now=self._now(),
            )
            return ECSDispatchResult(
                submission_id,
                released.status,
                error_code=released.last_error_code,
            )
        else:
            # If several tasks were already stopped, link one verified identity
            # so durable cancellation has a stable audit reference.
            linked = durable.link_dispatch(
                self.context,
                submission_id,
                owner_id=self.owner_id,
                fencing_token=claim.lease_fencing_token,
                remote_run_id=cast(str, rows[0]["taskArn"]),
                now=self._now(),
            )

        cancelled = durable.confirm_dispatch_cancelled(
            self.context,
            submission_id,
            expected_generation=linked.generation,
            expected_remote_run_id=cast(str, linked.remote_run_id),
            now=self._now(),
        )
        durable.reconcile_cancelled_submissions(
            self.context,
            limit=1,
            submission_id=submission_id,
            execution_route=self.binding.execution_route,
        )
        return ECSDispatchResult(
            submission_id,
            cancelled.status,
            remote_run_id=cancelled.remote_run_id,
            error_code=cancelled.last_error_code,
        )

    def _matches_dispatch_task(
        self, task: Mapping[str, Any], task_arn: str, token: str
    ) -> bool:
        task_prefix = (
            f"arn:{self.binding.partition}:ecs:{self.binding.region}:"
            f"{self.binding.account_id}:task/"
        )
        tags = _mapping_rows(task.get("tags"))
        if tags is None:
            return False
        tag_values = {
            tag.get("key"): tag.get("value")
            for tag in tags
            if isinstance(tag.get("key"), str)
        }
        return (
            task.get("taskArn") == task_arn
            and task_arn.startswith(task_prefix)
            and task.get("clusterArn") == self.binding.cluster_arn
            and task.get("taskDefinitionArn") == self.binding.task_definition_arn
            and task.get("startedBy") == token[:36]
            and tag_values.get("etlantic:managed") == "true"
            and tag_values.get("etlantic:binding") == self.binding.fingerprint[:32]
        )

    def _now(self) -> datetime:
        value = self.clock() if self.clock is not None else datetime.now(UTC)
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("dispatcher clock must return an aware datetime")
        return value.astimezone(UTC)

    @staticmethod
    def _parse_time(value: str | None) -> datetime | None:
        if value is None:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (AttributeError, TypeError, ValueError):
            return None
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return parsed.astimezone(UTC)

    def reconcile(self, *, limit: int = 50) -> list[ECSDispatchResult]:
        """Poll linked tasks, recover STOPPED work, and settle lost responses."""
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        self.binding.verify(self.ecs_client, self.sts_client)
        durable = self.backend.durable_work
        candidates = durable.dispatched_for_reconciliation(
            self.context,
            execution_route=self.binding.execution_route,
            limit=limit,
            after_submission_id=self._reconciliation_cursor,
        )
        if not candidates and self._reconciliation_cursor is not None:
            self._reconciliation_cursor = None
            candidates = durable.dispatched_for_reconciliation(
                self.context,
                execution_route=self.binding.execution_route,
                limit=limit,
            )
        if candidates:
            self._reconciliation_cursor = candidates[-1].submission_id
        records = candidates
        results: list[ECSDispatchResult] = []
        for record in records:
            task_arn = record.remote_run_id
            if task_arn is None:
                submission = durable.get_submission(self.context, record.submission_id)
                if submission.status == "cancel_requested":
                    intent = durable.prepare_dispatch(
                        self.context, record.submission_id
                    )
                    results.append(
                        self._resolve_cancelled_uncertain(record.submission_id, intent)
                    )
                elif submission.status == "cancelled" and not durable.list_attempts(
                    self.context, record.submission_id
                ):
                    intent = durable.prepare_dispatch(
                        self.context, record.submission_id
                    )
                    results.append(
                        self._resolve_cancelled_uncertain(record.submission_id, intent)
                    )
                elif submission.status in {"completed", "failed", "cancelled"}:
                    settled = durable.settle_terminal_ecs_dispatch(
                        self.context,
                        record.submission_id,
                        expected_generation=record.generation,
                        now=self._now(),
                    )
                    results.append(
                        ECSDispatchResult(
                            record.submission_id,
                            settled.status if settled is not None else record.status,
                            error_code=(
                                settled.last_error_code
                                if settled is not None
                                else "ecs_terminal_recovery_waiting"
                            ),
                        )
                    )
                continue
            try:
                response = _as_mapping(
                    self.ecs_client.describe_tasks(
                        cluster=self.binding.cluster_arn,
                        tasks=[task_arn],
                        include=["TAGS"],
                    ),
                    "ECS task observation is malformed",
                )
            except Exception:
                results.append(
                    ECSDispatchResult(
                        record.submission_id,
                        "dispatched",
                        remote_run_id=task_arn,
                        error_code="ecs_observation_unavailable",
                    )
                )
                continue
            tasks = _mapping_rows(response.get("tasks", []))
            failures = _mapping_rows(response.get("failures", []))
            if tasks is None or failures is None or failures or len(tasks) != 1:
                # Absence, throttling and eventual visibility are not evidence
                # that a task never ran. Leave canonical work linked.
                results.append(
                    ECSDispatchResult(
                        record.submission_id,
                        "dispatched",
                        remote_run_id=task_arn,
                        error_code="ecs_observation_incomplete",
                    )
                )
                continue
            task = tasks[0]
            if (
                task.get("taskArn") != task_arn
                or task.get("clusterArn") != self.binding.cluster_arn
                or task.get("taskDefinitionArn") != self.binding.task_definition_arn
            ):
                results.append(
                    ECSDispatchResult(
                        record.submission_id,
                        "dispatched",
                        remote_run_id=task_arn,
                        error_code="ecs_observation_mismatch",
                    )
                )
                continue
            submission = self.backend.durable_work.get_submission(
                self.context, record.submission_id
            )
            if submission.status == "cancel_requested":
                if task.get("lastStatus") == "STOPPED":
                    cancelled = self.backend.durable_work.confirm_dispatch_cancelled(
                        self.context,
                        record.submission_id,
                        expected_generation=record.generation,
                        expected_remote_run_id=task_arn,
                        now=self._now(),
                    )
                    self.backend.durable_work.reconcile_cancelled_submissions(
                        self.context,
                        limit=1,
                        submission_id=record.submission_id,
                        execution_route=self.binding.execution_route,
                    )
                    results.append(
                        ECSDispatchResult(
                            record.submission_id,
                            cancelled.status,
                            remote_run_id=task_arn,
                            error_code=cancelled.last_error_code,
                        )
                    )
                    continue
                try:
                    self.ecs_client.stop_task(
                        cluster=self.binding.cluster_arn,
                        task=task_arn,
                        reason="ETLantic canonical cancellation requested",
                    )
                except Exception:
                    results.append(
                        ECSDispatchResult(
                            record.submission_id,
                            "dispatched",
                            remote_run_id=task_arn,
                            error_code="ecs_cancel_stop_unavailable",
                        )
                    )
                else:
                    results.append(
                        ECSDispatchResult(
                            record.submission_id,
                            "dispatched",
                            remote_run_id=task_arn,
                            error_code="ecs_cancel_stop_requested",
                        )
                    )
                continue
            if task.get("lastStatus") != "STOPPED":
                results.append(
                    ECSDispatchResult(record.submission_id, "dispatched", task_arn)
                )
                continue
            rearmed = self.backend.durable_work.rearm_ecs_dispatch_after_remote_stop(
                self.context,
                record.submission_id,
                expected_generation=record.generation,
                expected_remote_run_id=task_arn,
                now=self._now(),
            )
            status = rearmed.status if rearmed is not None else "dispatched"
            results.append(
                ECSDispatchResult(
                    record.submission_id,
                    status,
                    remote_run_id=(rearmed.remote_run_id if rearmed else task_arn),
                    error_code=(
                        rearmed.last_error_code
                        if rearmed
                        else "ecs_stopped_task_recovery_required"
                    ),
                )
            )
        return results

    def stop_cancelled_task(self, submission_id: str) -> bool:
        """Stop only after canonical services durably recorded cancellation."""
        self.binding.verify(self.ecs_client, self.sts_client)
        submission = self.backend.durable_work.get_submission(
            self.context, submission_id
        )
        if submission.status != "cancel_requested":
            raise ValueError("canonical cancellation must be recorded before StopTask")
        dispatch = self.backend.durable_work.get_dispatch(self.context, submission_id)
        if dispatch.execution_route != self.binding.execution_route:
            raise ValueError("submission is assigned to a different execution route")
        if dispatch.remote_run_id is None or dispatch.status != "dispatched":
            return False
        self.ecs_client.stop_task(
            cluster=self.binding.cluster_arn,
            task=dispatch.remote_run_id,
            reason="ETLantic canonical cancellation requested",
        )
        return True


__all__ = ["ECSDispatchResult", "ECSDispatcher"]
