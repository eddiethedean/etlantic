from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from etlantic_aws import (
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
