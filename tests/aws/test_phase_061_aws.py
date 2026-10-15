from __future__ import annotations

import hashlib
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from threading import RLock
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

import pytest
from etlantic_aws import (
    ECSDispatcher,
    ECSExecutionBinding,
    EventBridgeScheduler,
    RelayRetryRequired,
    ScheduledTriggerRelay,
    schedule_name,
)
from etlantic_rsconnect import DeliveryConfig, HttpsTriggerDelivery

from etlantic.control_plane import (
    AcceptedExecutionReference,
    ControlPlaneContext,
    EnvironmentRef,
    MemoryScheduleStore,
    Principal,
    ScheduleRecord,
    ScheduleSpec,
    SecurityDomain,
    TenantRef,
    TriggerEnvelope,
    TriggerReceipt,
    WorkspaceRef,
)
from etlantic.outbound import OutboundPolicy
from etlantic.secrets import SecretRef

ACCOUNT = "123456789012"
REGION = "us-east-1"
_SCHEDULE_MUTATION_LOCK = RLock()
_DATETIME = datetime


def _datetime_after(value: str) -> type[datetime]:
    cursor = _DATETIME.fromisoformat(value.replace("Z", "+00:00"))
    later = cursor + timedelta(seconds=1)

    class _CompatibleDateTimeMeta(type):
        def __instancecheck__(cls, instance: object) -> bool:
            return isinstance(instance, _DATETIME)

    class _LaterDateTime(_DATETIME, metaclass=_CompatibleDateTimeMeta):
        @classmethod
        def now(cls, tz: Any = None) -> datetime:
            return later if tz is not None else later.replace(tzinfo=None)

    return _LaterDateTime


@contextmanager
def _schedule_mutation_guard(
    record: ScheduleRecord,
) -> Generator[ScheduleRecord, None, None]:
    with _SCHEDULE_MUTATION_LOCK:
        yield record


def _ecs_binding() -> ECSExecutionBinding:
    return ECSExecutionBinding(
        account_id=ACCOUNT,
        region=REGION,
        cluster_arn=f"arn:aws:ecs:{REGION}:{ACCOUNT}:cluster/etlantic",
        task_definition_arn=(
            f"arn:aws:ecs:{REGION}:{ACCOUNT}:task-definition/etlantic-worker:7"
        ),
        task_role_arn=f"arn:aws:iam::{ACCOUNT}:role/worker",
        execution_role_arn=f"arn:aws:iam::{ACCOUNT}:role/task-execution",
        container_name="worker",
        image_digest=(
            f"123456789012.dkr.ecr.{REGION}.amazonaws.com/worker@sha256:" + "a" * 64
        ),
        subnet_ids=("subnet-0123456789abcdef0",),
        security_group_ids=("sg-0123456789abcdef0",),
        cpu="1024",
        memory="2048",
    )


def _context() -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal(subject="owner", issuer="tests"),
        tenant=TenantRef("tenant"),
        workspace=WorkspaceRef("tenant", "workspace"),
        environment=EnvironmentRef("test"),
        security_domain=SecurityDomain("default"),
    )


def _schedule_record(*, schedule_id: str = "schedule-a") -> ScheduleRecord:
    ctx = _context()
    start = datetime.now(UTC).replace(microsecond=0)
    return MemoryScheduleStore().create(
        ctx,
        definition_id="pipeline-a",
        profile_name="test",
        spec=ScheduleSpec(kind="interval", interval_seconds=60),
        schedule_id=schedule_id,
        timer_owner="external",
        workload_identity=Principal("timer", issuer="tests", kind="workload"),
        next_fire_at=(start + timedelta(seconds=60)).isoformat().replace("+00:00", "Z"),
        timer_schedule_start_at=start.isoformat().replace("+00:00", "Z"),
        timer_binding_fingerprint=_scheduler().binding_fingerprint,
    )


class _SchedulerClient:
    def __init__(self) -> None:
        self.value: dict[str, Any] | None = None

    def create_schedule(self, **kwargs: Any) -> None:
        self._save(kwargs)

    def update_schedule(self, **kwargs: Any) -> None:
        self._save(kwargs)

    def get_schedule(self, *, Name: str, GroupName: str) -> Mapping[str, Any]:
        assert self.value is not None
        assert self.value["Name"] == Name
        assert self.value["GroupName"] == GroupName
        return dict(self.value)

    def delete_schedule(self, *, Name: str, GroupName: str) -> None:
        assert self.value is not None
        assert self.value["Name"] == Name
        assert self.value["GroupName"] == GroupName
        self.value = None

    def _save(self, kwargs: Mapping[str, Any]) -> None:
        self.value = {
            **kwargs,
            "Arn": (
                f"arn:aws:scheduler:{REGION}:{ACCOUNT}:schedule/etlantic/"
                f"{kwargs['Name']}"
            ),
        }


class _SchedulerNotFoundError(RuntimeError):
    response: Mapping[str, Any]

    def __init__(self) -> None:
        super().__init__("schedule does not exist")
        self.response = {"Error": {"Code": "ResourceNotFoundException"}}


class _ScopedSchedulerClient(_SchedulerClient):
    def __init__(self) -> None:
        super().__init__()
        self.schedules: dict[tuple[str, str], dict[str, Any]] = {}

    def create_schedule(self, **kwargs: Any) -> None:
        key = (kwargs["GroupName"], kwargs["Name"])
        if key in self.schedules:
            raise RuntimeError("schedule name already exists")
        self._save(kwargs)

    def update_schedule(self, **kwargs: Any) -> None:
        key = (kwargs["GroupName"], kwargs["Name"])
        if key not in self.schedules:
            raise RuntimeError("schedule does not exist")
        self._save(kwargs)

    def get_schedule(self, *, Name: str, GroupName: str) -> Mapping[str, Any]:
        schedule = self.schedules.get((GroupName, Name))
        if schedule is None:
            raise _SchedulerNotFoundError()
        return dict(schedule)

    def delete_schedule(self, *, Name: str, GroupName: str) -> None:
        if self.schedules.pop((GroupName, Name), None) is None:
            raise _SchedulerNotFoundError()

    def _save(self, kwargs: Mapping[str, Any]) -> None:
        key = (kwargs["GroupName"], kwargs["Name"])
        self.schedules[key] = {
            **kwargs,
            "Arn": (
                f"arn:aws:scheduler:{REGION}:{ACCOUNT}:schedule/"
                f"{kwargs['GroupName']}/{kwargs['Name']}"
            ),
        }


def _scheduler(
    client: _SchedulerClient | None = None,
    *,
    lambda_version: int = 12,
    mutation_guard: Any = None,
) -> EventBridgeScheduler:
    return EventBridgeScheduler(
        client or _SchedulerClient(),
        account_id=ACCOUNT,
        region=REGION,
        group_name="etlantic",
        lambda_version_arn=(
            f"arn:aws:lambda:{REGION}:{ACCOUNT}:function:trigger-relay:{lambda_version}"
        ),
        scheduler_role_arn=f"arn:aws:iam::{ACCOUNT}:role/scheduler",
        dlq_arn=f"arn:aws:sqs:{REGION}:{ACCOUNT}:scheduler-dlq",
        mutation_guard=mutation_guard or _schedule_mutation_guard,
    )


def test_scheduler_uses_stable_anchor_and_rejects_remote_drift() -> None:
    client = _SchedulerClient()
    adapter = _scheduler(client)
    record = _schedule_record()
    assert ScheduleRecord.from_dict(record.to_dict()).timer_binding_fingerprint == (
        adapter.binding_fingerprint
    )

    disabled = adapter.create_disabled(record)
    assert disabled["StartDate"].isoformat().replace("+00:00", "Z") == (
        record.timer_schedule_start_at
    )
    assert disabled["State"] == "DISABLED"
    assert adapter.activate(record)["State"] == "ENABLED"
    assert client.value is not None
    client.value["StartDate"] += timedelta(seconds=1)

    with pytest.raises(RuntimeError, match="drifted"):
        adapter.pause(record)

    changed_binding = _scheduler(lambda_version=13)
    with pytest.raises(ValueError, match="binding does not match"):
        changed_binding.create_disabled(record)


def test_scheduler_refuses_stale_activation_after_canonical_pause() -> None:
    ctx = _context()
    start = datetime.now(UTC).replace(microsecond=0)
    store = MemoryScheduleStore()
    adapter = _scheduler()
    record = store.create(
        ctx,
        definition_id="pipeline-a",
        profile_name="test",
        spec=ScheduleSpec(kind="interval", interval_seconds=60),
        schedule_id="schedule-paused",
        timer_owner="external",
        workload_identity=Principal("timer", issuer="tests", kind="workload"),
        next_fire_at=(start + timedelta(seconds=60)).isoformat().replace("+00:00", "Z"),
        timer_schedule_start_at=start.isoformat().replace("+00:00", "Z"),
        timer_binding_fingerprint=adapter.binding_fingerprint,
    )

    @contextmanager
    def canonical_guard(
        _record: ScheduleRecord,
    ) -> Generator[ScheduleRecord, None, None]:
        with _SCHEDULE_MUTATION_LOCK:
            yield store.get(ctx, record.schedule_id)

    client = _SchedulerClient()
    adapter = _scheduler(client, mutation_guard=canonical_guard)
    adapter.create_disabled(record)
    adapter.activate(record)
    paused = store.pause(ctx, record.schedule_id)
    adapter.pause(paused)

    with pytest.raises(RuntimeError, match="canonical schedule changed"):
        adapter.activate(record)

    assert client.value is not None
    assert client.value["State"] == "DISABLED"


def test_scheduler_names_are_scoped_to_tenant_and_workspace() -> None:
    client = _ScopedSchedulerClient()
    adapter = _scheduler(client)
    first = _schedule_record()
    second = ScheduleRecord.from_dict(
        {**first.to_dict(), "workspace_id": "another-workspace"}
    )

    adapter.create_disabled(first)
    adapter.create_disabled(second)

    assert schedule_name(
        first.schedule_id,
        tenant_id=first.tenant_id,
        workspace_id=first.workspace_id,
    ) != schedule_name(
        second.schedule_id,
        tenant_id=second.tenant_id,
        workspace_id=second.workspace_id,
    )
    assert adapter.schedule_arn(first) != adapter.schedule_arn(second)
    assert len(client.schedules) == 2


@pytest.mark.parametrize("use_resume", [False, True])
def test_scheduler_enable_retry_accepts_matching_enabled_schedule(
    use_resume: bool,
) -> None:
    class _LostEnableResponseClient(_SchedulerClient):
        lose_next_enable = True
        lose_readback = False

        def update_schedule(self, **kwargs: Any) -> None:
            super().update_schedule(**kwargs)
            if kwargs["State"] == "ENABLED" and self.lose_next_enable:
                self.lose_next_enable = False
                self.lose_readback = True
                raise TimeoutError("update response lost")

        def get_schedule(self, *, Name: str, GroupName: str) -> Mapping[str, Any]:
            if self.lose_readback:
                self.lose_readback = False
                raise TimeoutError("readback unavailable")
            return super().get_schedule(Name=Name, GroupName=GroupName)

    client = _LostEnableResponseClient()
    adapter = _scheduler(client)
    record = _schedule_record()
    adapter.create_disabled(record)
    if use_resume:
        client.lose_next_enable = False
        adapter.activate(record)
        adapter.pause(record)
        client.lose_next_enable = True

    enable = adapter.resume if use_resume else adapter.activate
    with pytest.raises(RuntimeError, match="observation is unavailable"):
        enable(record)

    next_fire_at = record.next_fire_at
    assert isinstance(next_fire_at, str)
    retry_time = datetime.fromisoformat(
        next_fire_at.replace("Z", "+00:00")
    ) + timedelta(seconds=1)
    overdue_record = ScheduleRecord.from_dict(
        {
            **record.to_dict(),
            "next_fire_at": retry_time.isoformat().replace("+00:00", "Z"),
        }
    )
    assert _datetime_after(cast(str, overdue_record.next_fire_at)).now(UTC) > (
        datetime.fromisoformat(
            cast(str, overdue_record.next_fire_at).replace("Z", "+00:00")
        )
    )
    with patch(
        "etlantic_aws.scheduler.datetime",
        _datetime_after(cast(str, overdue_record.next_fire_at)),
    ):
        assert enable(overdue_record)["State"] == "ENABLED"


def test_scheduler_revision_update_retry_accepts_matching_disabled_replacement() -> (
    None
):
    class _LostReplacementResponseClient(_SchedulerClient):
        previous_input: str | None = None
        lose_replacement_once = True
        lose_readback = False

        def update_schedule(self, **kwargs: Any) -> None:
            super().update_schedule(**kwargs)
            if (
                kwargs["State"] == "DISABLED"
                and kwargs["Target"]["Input"] != self.previous_input
                and self.lose_replacement_once
            ):
                self.lose_replacement_once = False
                self.lose_readback = True
                raise TimeoutError("replacement response lost")

        def get_schedule(self, *, Name: str, GroupName: str) -> Mapping[str, Any]:
            if self.lose_readback:
                self.lose_readback = False
                raise TimeoutError("readback unavailable")
            return super().get_schedule(Name=Name, GroupName=GroupName)

    client = _LostReplacementResponseClient()
    adapter = _scheduler(client)
    previous = _schedule_record()
    adapter.create_disabled(previous)
    adapter.activate(previous)
    assert client.value is not None
    client.previous_input = client.value["Target"]["Input"]
    new_start = datetime.now(UTC).replace(microsecond=0) + timedelta(seconds=2)
    replacement = ScheduleRecord.from_dict(
        {
            **previous.to_dict(),
            "revision_id": "rev-retry",
            "timer_owner_generation": previous.timer_owner_generation + 1,
            "timer_schedule_start_at": new_start.isoformat().replace("+00:00", "Z"),
            "next_fire_at": (new_start + timedelta(seconds=60))
            .isoformat()
            .replace("+00:00", "Z"),
        }
    )

    with pytest.raises(RuntimeError, match="observation is unavailable"):
        adapter.update_disabled(previous, replacement)

    assert isinstance(replacement.next_fire_at, str)
    with patch(
        "etlantic_aws.scheduler.datetime",
        _datetime_after(replacement.next_fire_at),
    ):
        assert adapter.update_disabled(previous, replacement)["State"] == "DISABLED"


def test_scheduler_update_disables_old_revision_before_rejecting_overdue_cursor() -> (
    None
):
    client = _SchedulerClient()
    adapter = _scheduler(client)
    previous = _schedule_record()
    adapter.create_disabled(previous)
    adapter.activate(previous)
    assert client.value is not None
    previous_input = client.value["Target"]["Input"]
    overdue = ScheduleRecord.from_dict(
        {
            **previous.to_dict(),
            "revision_id": "rev-overdue",
            "timer_owner_generation": previous.timer_owner_generation + 1,
            "next_fire_at": (
                datetime.now(UTC).replace(microsecond=0) - timedelta(seconds=1)
            )
            .isoformat()
            .replace("+00:00", "Z"),
        }
    )

    with pytest.raises(ValueError, match="cursor is overdue"):
        adapter.update_disabled(previous, overdue)

    assert client.value is not None
    assert client.value["State"] == "DISABLED"
    assert client.value["Target"]["Input"] == previous_input


def test_scheduler_delete_retry_accepts_an_absent_owned_resource() -> None:
    client = _ScopedSchedulerClient()
    adapter = _scheduler(client)
    record = _schedule_record()
    adapter.create_disabled(record)

    adapter.delete(record)
    adapter.delete(record)

    assert client.schedules == {}


def test_scheduler_revision_update_disables_before_replacement() -> None:
    client = _SchedulerClient()
    adapter = _scheduler(client)
    previous = _schedule_record()
    adapter.create_disabled(previous)
    adapter.activate(previous)
    assert client.value is not None
    previous_input = client.value["Target"]["Input"]
    new_start = datetime.now(UTC).replace(microsecond=0) + timedelta(seconds=2)
    replacement = type(previous).from_dict(
        {
            **previous.to_dict(),
            "revision_id": "rev-next",
            "timer_owner_generation": previous.timer_owner_generation + 1,
            "timer_schedule_start_at": new_start.isoformat().replace("+00:00", "Z"),
            "next_fire_at": (new_start + timedelta(seconds=60))
            .isoformat()
            .replace("+00:00", "Z"),
        }
    )

    updated = adapter.update_disabled(previous, replacement)
    assert updated["State"] == "DISABLED"
    assert updated["Target"]["Input"] != previous_input
    with pytest.raises(RuntimeError, match="drifted"):
        adapter.activate(previous)
    assert client.value is not None
    assert client.value["State"] == "DISABLED"
    assert adapter.activate(replacement)["State"] == "ENABLED"


def _delivery() -> HttpsTriggerDelivery:
    config = DeliveryConfig(
        endpoint_url="https://receiver.example.com/base",
        credential_ref=SecretRef("env", "receiver", "token"),
        outbound_policy=OutboundPolicy(allowed_hosts=("receiver.example.com",)),
    )
    return HttpsTriggerDelivery(config, lambda _ref: "secret")


def _event(adapter: EventBridgeScheduler, record: Any) -> dict[str, Any]:
    scheduled = (
        datetime.fromisoformat(record.next_fire_at.replace("Z", "+00:00"))
        .isoformat()
        .replace("+00:00", "Z")
    )
    return {
        "schema": "etlantic.aws.scheduler_invocation/1",
        "schedule_id": record.schedule_id,
        "schedule_revision_id": record.revision_id,
        "timer_owner_generation": record.timer_owner_generation,
        "schedule_arn": adapter.schedule_arn(record),
        "scheduled_at": scheduled,
        "execution_id": "execution-123",
        "attempt_number": "1",
    }


def test_relay_checks_durable_owner_and_reuses_canonical_receipt() -> None:
    record = _schedule_record()
    adapter = _scheduler()
    delivery = _delivery()
    seen: list[str] = []

    def receipt(envelope: TriggerEnvelope) -> TriggerReceipt:
        return TriggerReceipt(
            status="accepted",
            firing_status="accepted",
            schedule_id=envelope.schedule_id,
            schedule_revision_id=envelope.schedule_revision_id,
            occurrence_id=envelope.occurrence_id,
            submission_id="submission-1",
        )

    def reconcile(envelope: TriggerEnvelope) -> TriggerReceipt:
        return receipt(envelope)

    def deliver(envelope: TriggerEnvelope) -> None:
        seen.append(envelope.occurrence_id)

    vars(delivery)["reconcile"] = reconcile
    vars(delivery)["deliver"] = deliver
    relay = ScheduledTriggerRelay(adapter, delivery, lambda _sid: record)

    result = relay.handle_event(_event(adapter, record))
    assert result["status"] == "accepted"
    assert seen == []

    stale = _event(adapter, record)
    stale["timer_owner_generation"] += 1
    with pytest.raises(ValueError, match="stale"):
        relay.handle_event(stale)


def test_relay_raises_for_pending_canonical_admission() -> None:
    record = _schedule_record()
    adapter = _scheduler()
    delivery = _delivery()

    def reconcile(_envelope: TriggerEnvelope) -> None:
        return None

    vars(delivery)["reconcile"] = reconcile

    class Pending:
        def __init__(self, envelope: Any) -> None:
            self.receipt = TriggerReceipt(
                status="pending",
                firing_status="accepted",
                schedule_id=envelope.schedule_id,
                schedule_revision_id=envelope.schedule_revision_id,
                occurrence_id=envelope.occurrence_id,
            )

    def deliver(envelope: TriggerEnvelope) -> Any:
        return Pending(envelope)

    vars(delivery)["deliver"] = deliver
    relay = ScheduledTriggerRelay(adapter, delivery, lambda _sid: record)
    with pytest.raises(RelayRetryRequired):
        relay.handle_event(_event(adapter, record))


def test_ecs_binding_pins_worker_and_only_overrides_accepted_reference() -> None:
    digest = "sha256:" + "a" * 64
    binding = ECSExecutionBinding(
        account_id=ACCOUNT,
        region=REGION,
        cluster_arn=f"arn:aws:ecs:{REGION}:{ACCOUNT}:cluster/etlantic",
        task_definition_arn=(
            f"arn:aws:ecs:{REGION}:{ACCOUNT}:task-definition/etlantic-worker:7"
        ),
        task_role_arn=f"arn:aws:iam::{ACCOUNT}:role/worker",
        execution_role_arn=f"arn:aws:iam::{ACCOUNT}:role/task-execution",
        container_name="worker",
        image_digest=f"123456789012.dkr.ecr.{REGION}.amazonaws.com/worker@{digest}",
        subnet_ids=("subnet-0123456789abcdef0",),
        security_group_ids=("sg-0123456789abcdef0",),
        cpu="1024",
        memory="2048",
    )
    restored = ECSExecutionBinding.from_dict(binding.to_dict())
    assert restored == binding
    assert restored.execution_route == f"ecs:{binding.fingerprint}"
    request = binding.request(
        client_token="a" * 64,
        reference=AcceptedExecutionReference("submission-1", "0" * 64, "1" * 64),
    )
    assert request["launchType"] == "FARGATE"
    assert request["enableExecuteCommand"] is False
    assert (
        request["overrides"]["containerOverrides"][0]["environment"][0]["name"]
        == "ETLANTIC_ACCEPTED_REFERENCE_JSON"
    )
    assert (
        request["networkConfiguration"]["awsvpcConfiguration"]["assignPublicIp"]
        == "DISABLED"
    )
    with pytest.raises(ValueError, match="private networking"):
        ECSExecutionBinding.from_dict(binding.to_dict() | {"assign_public_ip": True})


class _DispatchStore:
    def __init__(
        self,
        binding: ECSExecutionBinding,
        *,
        status: str,
        submission_status: str,
        creation_started_at: datetime,
    ) -> None:
        self.record = SimpleNamespace(
            submission_id="submission-ecs",
            backend_kind="ecs",
            execution_route=binding.execution_route,
            binding_fingerprint=binding.fingerprint,
            plan_fingerprint="a" * 64,
            envelope_sha256="b" * 64,
            generation=1,
            creation_key="durable-creation-key",
            creation_started_at=(
                creation_started_at.isoformat().replace("+00:00", "Z")
            ),
            status=status,
            remote_run_id=None,
            lease_owner_id=None,
            lease_fencing_token=0,
            lease_expires_at=None,
            retry_after_at=None,
            last_error_code=None,
        )
        self.submission = SimpleNamespace(
            submission_id=self.record.submission_id,
            status=submission_status,
            plan_fingerprint=self.record.plan_fingerprint,
            envelope_sha256=self.record.envelope_sha256,
            input_snapshot="opaque-unread-test-snapshot",
        )
        self.cancel_reconcile_calls = 0

    def prepare_dispatch(self, _ctx: Any, _submission_id: str) -> Any:
        return self.record

    def get_submission(self, _ctx: Any, _submission_id: str) -> Any:
        return self.submission

    def get_dispatch(self, _ctx: Any, _submission_id: str) -> Any:
        return self.record

    def claim_dispatch(
        self,
        _ctx: Any,
        _submission_id: str,
        *,
        owner_id: str,
        lease_seconds: int,
        now: datetime,
    ) -> Any:
        del lease_seconds
        if self.record.status not in {
            "uncertain",
            "leased",
            "reconciliation_required",
        }:
            return None
        self.record.status = "leased"
        self.record.lease_owner_id = owner_id
        self.record.lease_fencing_token += 1
        self.record.lease_expires_at = (
            (now + timedelta(seconds=30)).isoformat().replace("+00:00", "Z")
        )
        return self.record

    def release_dispatch(
        self,
        _ctx: Any,
        _submission_id: str,
        *,
        outcome_uncertain: bool,
        cancelled: bool = False,
        error_code: str,
        **_kwargs: Any,
    ) -> Any:
        self.record.status = (
            "cancelled"
            if cancelled
            else ("uncertain" if outcome_uncertain else "pending")
        )
        self.record.lease_owner_id = None
        self.record.lease_expires_at = None
        self.record.last_error_code = error_code
        return self.record

    def quarantine_expired_ecs_dispatch(self, *_args: Any, **_kwargs: Any) -> Any:
        self.record.status = "reconciliation_required"
        self.record.lease_owner_id = None
        self.record.lease_expires_at = None
        self.record.last_error_code = "ecs_token_window_expired"
        return self.record

    def link_dispatch(
        self,
        _ctx: Any,
        _submission_id: str,
        *,
        remote_run_id: str,
        **_kwargs: Any,
    ) -> Any:
        self.record.status = "dispatched"
        self.record.remote_run_id = remote_run_id
        self.record.lease_owner_id = None
        self.record.lease_expires_at = None
        return self.record

    def dispatched_for_reconciliation(self, *_args: Any, **_kwargs: Any) -> list[Any]:
        if (
            self.record.status == "dispatched"
            and self.submission.status == "cancel_requested"
        ):
            return [self.record]
        return []

    def confirm_dispatch_cancelled(self, *_args: Any, **_kwargs: Any) -> Any:
        self.record.status = "cancelled"
        self.record.last_error_code = "remote_task_stopped_after_cancel"
        return self.record

    def reconcile_cancelled_submissions(self, *_args: Any, **_kwargs: Any) -> list[Any]:
        self.cancel_reconcile_calls += 1
        if self.record.status == "cancelled":
            self.submission.status = "cancelled"
            return [self.submission]
        return []


class _ECSClient:
    def __init__(self, binding: ECSExecutionBinding) -> None:
        self.meta = SimpleNamespace(region_name=binding.region)
        self.binding = binding
        self.task: dict[str, Any] | None = None
        self.other_tasks: list[dict[str, Any]] = []
        self.list_task_requests: list[dict[str, Any]] = []
        self.stop_calls: list[str] = []
        self.run_calls = 0

    def describe_clusters(self, *, clusters: list[str]) -> Mapping[str, Any]:
        return {"clusters": [{"status": "ACTIVE", "clusterArn": clusters[0]}]}

    def describe_task_definition(self, *, taskDefinition: str) -> Mapping[str, Any]:
        binding = self.binding
        return {
            "taskDefinition": {
                "taskDefinitionArn": taskDefinition,
                "status": "ACTIVE",
                "requiresCompatibilities": ["FARGATE"],
                "networkMode": "awsvpc",
                "runtimePlatform": {
                    "operatingSystemFamily": binding.operating_system_family,
                    "cpuArchitecture": binding.cpu_architecture,
                },
                "taskRoleArn": binding.task_role_arn,
                "executionRoleArn": binding.execution_role_arn,
                "cpu": binding.cpu,
                "memory": binding.memory,
                "containerDefinitions": [
                    {
                        "name": binding.container_name,
                        "image": binding.image_digest,
                        "essential": True,
                        "entryPoint": list(binding.entry_point),
                        "command": [],
                    }
                ],
            }
        }

    def run_task(self, **_kwargs: Any) -> Mapping[str, Any]:
        self.run_calls += 1
        raise AssertionError("a cancelled or expired dispatch must not call RunTask")

    def list_tasks(self, **request: Any) -> Mapping[str, Any]:
        assert "startedBy" not in request
        assert request["cluster"] == self.binding.cluster_arn
        assert request["desiredStatus"] in {"RUNNING", "STOPPED"}
        self.list_task_requests.append(dict(request))
        tasks = ([self.task] if self.task is not None else []) + self.other_tasks
        return {
            "taskArns": [
                task["taskArn"]
                for task in tasks
                if task["desiredStatus"] == request["desiredStatus"]
            ]
        }

    def describe_tasks(self, *, tasks: list[str], **_kwargs: Any) -> Mapping[str, Any]:
        candidates = ([self.task] if self.task is not None else []) + self.other_tasks
        found = [task for task in candidates if task["taskArn"] in tasks]
        missing = set(tasks) - {task["taskArn"] for task in found}
        return {
            "tasks": found,
            "failures": ([{"reason": "MISSING"}] if missing else []),
        }

    def stop_task(self, *, task: str, **_kwargs: Any) -> Mapping[str, Any]:
        self.stop_calls.append(task)
        return {"task": self.task or {}}


def _dispatcher(
    binding: ECSExecutionBinding,
    durable: _DispatchStore,
    ecs: _ECSClient,
    clock: list[datetime],
) -> ECSDispatcher:
    return ECSDispatcher(
        backend=cast(
            Any,
            SimpleNamespace(
                managed_service=SimpleNamespace(
                    execution_route=binding.execution_route
                ),
                durable_work=durable,
            ),
        ),
        context=_context(),
        binding=binding,
        ecs_client=ecs,
        sts_client=SimpleNamespace(
            get_caller_identity=lambda: {"Account": binding.account_id}
        ),
        owner_id="ecs-dispatcher-test",
        clock=lambda: clock[0],
    )


class _PagingStore:
    def __init__(self, records: list[Any], submissions: Mapping[str, Any]) -> None:
        self.records = records
        self.submissions = submissions

    def dispatched_for_reconciliation(
        self,
        _ctx: Any,
        *,
        execution_route: str,
        limit: int,
        after_submission_id: str | None = None,
    ) -> list[Any]:
        candidates = [
            item
            for item in self.records
            if item.execution_route == execution_route
            and (
                after_submission_id is None or item.submission_id > after_submission_id
            )
        ]
        return candidates[:limit]

    def get_submission(self, _ctx: Any, submission_id: str) -> Any:
        return self.submissions[submission_id]


def test_ecs_reconciliation_cursor_visits_later_cancelled_tasks() -> None:
    binding = _ecs_binding()
    task_arns = [
        f"arn:aws:ecs:{REGION}:{ACCOUNT}:task/etlantic/task-a",
        f"arn:aws:ecs:{REGION}:{ACCOUNT}:task/etlantic/task-b",
    ]
    records = [
        SimpleNamespace(
            submission_id=submission_id,
            execution_route=binding.execution_route,
            remote_run_id=task_arn,
            generation=1,
        )
        for submission_id, task_arn in zip(
            ("a-running", "b-cancel"), task_arns, strict=True
        )
    ]
    submissions = {
        "a-running": SimpleNamespace(status="accepted"),
        "b-cancel": SimpleNamespace(status="cancel_requested"),
    }
    durable = _PagingStore(records, submissions)
    ecs = _ECSClient(binding)
    tasks: list[dict[str, Any]] = [
        {
            "taskArn": task_arn,
            "clusterArn": binding.cluster_arn,
            "taskDefinitionArn": binding.task_definition_arn,
            "lastStatus": "RUNNING",
            "desiredStatus": "RUNNING",
            "tags": [],
        }
        for task_arn in task_arns
    ]
    ecs.task, ecs.other_tasks = tasks[0], [tasks[1]]
    dispatcher = _dispatcher(binding, cast(Any, durable), ecs, [datetime.now(UTC)])

    pages = [dispatcher.reconcile(limit=1) for _ in range(3)]

    assert [[item.submission_id for item in page] for page in pages] == [
        ["a-running"],
        ["b-cancel"],
        ["a-running"],
    ]
    assert ecs.stop_calls == [task_arns[1]]


def test_expired_ecs_client_token_is_quarantined_before_retry() -> None:
    binding = _ecs_binding()
    now = datetime(2026, 10, 15, 12, tzinfo=UTC)
    durable = _DispatchStore(
        binding,
        status="uncertain",
        submission_status="accepted",
        creation_started_at=now - timedelta(hours=2),
    )
    ecs = _ECSClient(binding)
    dispatcher = _dispatcher(binding, durable, ecs, [now])

    result = dispatcher.dispatch_submission(durable.record.submission_id)

    assert result.status == "reconciliation_required"
    assert result.error_code == "ecs_token_window_expired"
    assert ecs.run_calls == 0


def test_ecs_token_deadline_is_rechecked_after_claim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = _ecs_binding()
    created = datetime(2026, 10, 15, 12, tzinfo=UTC)
    durable = _DispatchStore(
        binding,
        status="uncertain",
        submission_status="accepted",
        creation_started_at=created,
    )
    ecs = _ECSClient(binding)
    times = iter(
        [
            created + timedelta(minutes=49),
            created + timedelta(hours=2),
            created + timedelta(hours=2),
        ]
    )
    dispatcher = _dispatcher(binding, durable, ecs, [created])
    dispatcher.clock = lambda: next(times)
    reference = AcceptedExecutionReference(
        durable.record.submission_id,
        durable.record.plan_fingerprint,
        durable.record.envelope_sha256,
    )

    def from_submission(_submission: Any) -> AcceptedExecutionReference:
        return reference

    monkeypatch.setattr(
        AcceptedExecutionReference,
        "from_submission",
        staticmethod(from_submission),
    )

    result = dispatcher.dispatch_submission(durable.record.submission_id)

    assert result.status == "reconciliation_required"
    assert result.error_code == "ecs_token_window_expired"
    assert ecs.run_calls == 0


def test_cancelled_uncertain_ecs_task_is_discovered_stopped_and_finalized() -> None:
    binding = _ecs_binding()
    now = datetime(2026, 10, 15, 12, tzinfo=UTC)
    durable = _DispatchStore(
        binding,
        status="uncertain",
        submission_status="cancel_requested",
        creation_started_at=now - timedelta(minutes=5),
    )
    token = hashlib.sha256(durable.record.creation_key.encode("utf-8")).hexdigest()
    task_arn = f"arn:aws:ecs:{REGION}:{ACCOUNT}:task/etlantic/task-a"
    ecs = _ECSClient(binding)
    ecs.task = {
        "taskArn": task_arn,
        "clusterArn": binding.cluster_arn,
        "taskDefinitionArn": binding.task_definition_arn,
        "startedBy": token[:36],
        "lastStatus": "PENDING",
        "desiredStatus": "RUNNING",
        "tags": [
            {"key": "etlantic:managed", "value": "true"},
            {"key": "etlantic:binding", "value": binding.fingerprint[:32]},
        ],
    }
    ecs.other_tasks.append(
        {
            "taskArn": f"arn:aws:ecs:{REGION}:{ACCOUNT}:task/etlantic/unrelated",
            "clusterArn": binding.cluster_arn,
            "taskDefinitionArn": binding.task_definition_arn,
            "startedBy": "another-dispatch-token",
            "lastStatus": "RUNNING",
            "desiredStatus": "RUNNING",
            "tags": [],
        }
    )
    clock = [now]
    dispatcher = _dispatcher(binding, durable, ecs, clock)

    first = dispatcher.dispatch_submission(durable.record.submission_id)
    assert first.status == "dispatched"
    assert first.remote_run_id == task_arn
    assert ecs.stop_calls == [task_arn]
    assert ecs.run_calls == 0
    assert {item["desiredStatus"] for item in ecs.list_task_requests} == {
        "RUNNING",
        "STOPPED",
    }
    assert all("startedBy" not in item for item in ecs.list_task_requests)

    ecs.task["lastStatus"] = "STOPPED"
    ecs.task["desiredStatus"] = "STOPPED"
    completed = dispatcher.reconcile()
    assert completed[0].status == "cancelled"
    assert durable.submission.status == "cancelled"
    assert ecs.run_calls == 0


def test_quarantined_ecs_cancellation_stays_uncertain_without_task_evidence() -> None:
    binding = _ecs_binding()
    now = datetime(2026, 10, 15, 12, tzinfo=UTC)
    durable = _DispatchStore(
        binding,
        status="reconciliation_required",
        submission_status="cancel_requested",
        creation_started_at=now - timedelta(hours=2),
    )
    ecs = _ECSClient(binding)
    dispatcher = _dispatcher(binding, durable, ecs, [now])

    result = dispatcher.dispatch_submission(durable.record.submission_id)

    assert result.status == "uncertain"
    assert result.error_code == "ecs_cancel_identity_unresolved"
    assert durable.submission.status == "cancel_requested"
    assert durable.record.status == "uncertain"
    assert durable.record.remote_run_id is None
    assert durable.cancel_reconcile_calls == 0
    assert ecs.list_task_requests
    assert ecs.run_calls == 0


def test_cancelled_uncertain_stopped_ecs_task_is_discovered_without_stopping() -> None:
    binding = _ecs_binding()
    now = datetime(2026, 10, 15, 12, tzinfo=UTC)
    durable = _DispatchStore(
        binding,
        status="uncertain",
        submission_status="cancel_requested",
        creation_started_at=now - timedelta(minutes=5),
    )
    token = hashlib.sha256(durable.record.creation_key.encode("utf-8")).hexdigest()
    task_arn = f"arn:aws:ecs:{REGION}:{ACCOUNT}:task/etlantic/task-stopped"
    ecs = _ECSClient(binding)
    ecs.task = {
        "taskArn": task_arn,
        "clusterArn": binding.cluster_arn,
        "taskDefinitionArn": binding.task_definition_arn,
        "startedBy": token[:36],
        "lastStatus": "STOPPED",
        "desiredStatus": "STOPPED",
        "tags": [
            {"key": "etlantic:managed", "value": "true"},
            {"key": "etlantic:binding", "value": binding.fingerprint[:32]},
        ],
    }
    dispatcher = _dispatcher(binding, durable, ecs, [now])

    result = dispatcher.dispatch_submission(durable.record.submission_id)

    assert result.status == "cancelled"
    assert result.remote_run_id == task_arn
    assert ecs.stop_calls == []
    assert durable.submission.status == "cancelled"
    assert {item["desiredStatus"] for item in ecs.list_task_requests} == {
        "RUNNING",
        "STOPPED",
    }


def test_cancelled_uncertain_ecs_identity_stays_uncertain_after_ttl() -> None:
    binding = _ecs_binding()
    created_at = datetime(2026, 10, 15, 12, tzinfo=UTC)
    clock = [created_at + timedelta(minutes=30)]
    durable = _DispatchStore(
        binding,
        status="uncertain",
        submission_status="cancel_requested",
        creation_started_at=created_at,
    )
    ecs = _ECSClient(binding)
    dispatcher = _dispatcher(binding, durable, ecs, clock)

    waiting = dispatcher.dispatch_submission(durable.record.submission_id)
    assert waiting.status == "uncertain"
    assert durable.submission.status == "cancel_requested"
    assert ecs.run_calls == 0

    clock[0] = created_at + timedelta(minutes=51)
    resolved = dispatcher.dispatch_submission(durable.record.submission_id)
    assert resolved.status == "uncertain"
    assert resolved.error_code == "ecs_cancel_identity_unresolved"
    assert durable.record.status == "uncertain"
    assert durable.submission.status == "cancel_requested"
    assert ecs.run_calls == 0
