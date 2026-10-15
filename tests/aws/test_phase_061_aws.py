from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from threading import RLock
from types import SimpleNamespace
from typing import Any, cast

import pytest
from etlantic_aws import (
    ECSDispatcher,
    ECSExecutionBinding,
    EventBridgeScheduler,
    RelayRetryRequired,
    ScheduledTriggerRelay,
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


def _scheduler(
    client: _SchedulerClient | None = None, *, lambda_version: int = 12
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
        mutation_guard=lambda _record: _SCHEDULE_MUTATION_LOCK,
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
        if self.record.status != "uncertain":
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


def test_cancelled_uncertain_ecs_identity_stays_fenced_then_resolves_after_ttl() -> (
    None
):
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
    assert resolved.status == "cancelled"
    assert durable.submission.status == "cancelled"
    assert ecs.run_calls == 0
