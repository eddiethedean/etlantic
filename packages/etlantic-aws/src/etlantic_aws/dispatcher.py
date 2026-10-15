"""Durable, fenced ECS/Fargate dispatch over public managed-work operations."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, cast

from etlantic.control_plane import (
    AcceptedExecutionReference,
    ControlPlaneContext,
    ManagedBackend,
    validate_control_plane_context,
)

from etlantic_aws.binding import ECSExecutionBinding


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
        if submission.status != "accepted":
            return ECSDispatchResult(
                submission_id, "not_dispatched", error_code="submission_not_active"
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

    def reconcile(self, *, limit: int = 50) -> list[ECSDispatchResult]:
        """Poll linked tasks and rearm only proven pre-claim stopped tasks."""
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        self.binding.verify(self.ecs_client, self.sts_client)
        records = self.backend.durable_work.dispatched_for_reconciliation(
            self.context,
            execution_route=self.binding.execution_route,
            limit=limit,
        )
        results: list[ECSDispatchResult] = []
        for record in records:
            task_arn = record.remote_run_id
            if task_arn is None:
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
            if task.get("lastStatus") != "STOPPED":
                results.append(
                    ECSDispatchResult(record.submission_id, "dispatched", task_arn)
                )
                continue
            rearmed = self.backend.durable_work.rearm_dispatch_after_remote_failure(
                self.context,
                record.submission_id,
                expected_remote_run_id=task_arn,
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
                        else "canonical_execution_started"
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
