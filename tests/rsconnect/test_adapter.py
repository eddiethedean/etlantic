from __future__ import annotations

from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from threading import Event, RLock
from types import SimpleNamespace
from typing import Any, cast

import pytest
from etlantic_rsconnect import (
    ConnectScheduleAdapter,
    ConnectScheduleBinding,
    DeploymentResult,
    ScheduleOperationError,
    ScheduleOperationUnknown,
    build_trigger_bundle,
)

from etlantic.control_plane import (
    ControlPlaneContext,
    EnvironmentRef,
    MemoryScheduleStore,
    Principal,
    ScheduleSpec,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic.control_plane.schedule_models import ScheduleRecord
from etlantic.outbound import OutboundPolicy
from etlantic.secrets import SecretRef
from etlantic.service.schedule import ScheduleApplicationService


def _context() -> ControlPlaneContext:
    workload = Principal(subject="connect-timer", issuer="tests", kind="workload")
    return ControlPlaneContext(
        principal=workload,
        tenant=TenantRef(tenant_id="tenant-a"),
        workspace=WorkspaceRef(tenant_id="tenant-a", workspace_id="workspace-a"),
        environment=EnvironmentRef(name="test"),
        security_domain=SecurityDomain(domain_id="default"),
    )


def _record() -> ScheduleRecord:
    context = _context()
    workload = context.principal
    return MemoryScheduleStore().create(
        context,
        definition_id="pipeline-a",
        profile_name="test",
        spec=ScheduleSpec(kind="interval", interval_seconds=3600),
        workload_identity=workload,
        timer_owner="external",
        next_fire_at="2026-10-13T13:00:00Z",
    )


def _binding(record: ScheduleRecord) -> ConnectScheduleBinding:
    return ConnectScheduleBinding(
        schedule_id=record.schedule_id,
        revision_id=record.revision_id,
        content_guid="01234567-89ab-cdef-0123-456789abcdef",
        timer_owner_generation=record.timer_owner_generation,
        server_url="https://connect.example.com",
        target_url="https://receiver.example.com/trigger",
        bundle_sha256="a" * 64,
    )


class Store:
    def __init__(self, binding: ConnectScheduleBinding | None = None) -> None:
        self._lock = RLock()
        self.values: dict[str, ConnectScheduleBinding] = (
            {} if binding is None else {binding.schedule_id: binding}
        )

    def get(self, schedule_id: str) -> ConnectScheduleBinding | None:
        with self._lock:
            return self.values.get(schedule_id)

    def put(
        self,
        binding: ConnectScheduleBinding,
        *,
        expected: ConnectScheduleBinding | None,
    ) -> None:
        with self._lock:
            if self.values.get(binding.schedule_id) != expected:
                raise RuntimeError("compare-and-swap conflict")
            self.values[binding.schedule_id] = binding

    def delete(self, schedule_id: str, *, expected: ConnectScheduleBinding) -> None:
        with self._lock:
            if self.values.get(schedule_id) != expected:
                raise RuntimeError("compare-and-swap conflict")
            del self.values[schedule_id]


class Gateway:
    server_url = "https://connect.example.com"

    def __init__(self, rule: object | None = None) -> None:
        self.schedule = None if rule is None else SimpleNamespace(rule=rule)
        self.events: list[tuple[object, ...]] = []
        self.armed = False

    def read(self, content_guid: str) -> Any | None:
        self.events.append(("read",))
        return self.schedule

    def set_trigger_armed(self, content_guid: str, armed: bool) -> None:
        self.events.append(("armed", armed))
        self.armed = armed

    def can_set_trigger_armed(self, content_guid: str) -> bool:
        return True

    def create_or_update(self, content_guid: str, kwargs: Mapping[str, object]) -> Any:
        self.events.append(("create", dict(kwargs)))
        self.schedule = SimpleNamespace(rule=dict(kwargs))

    def delete(self, content_guid: str) -> None:
        self.events.append(("delete",))
        self.schedule = None


class BlockingGateway(Gateway):
    def __init__(self) -> None:
        super().__init__()
        self.create_started = Event()
        self.allow_create = Event()

    def create_or_update(self, content_guid: str, kwargs: Mapping[str, object]) -> Any:
        self.events.append(("create-start", dict(kwargs)))
        self.create_started.set()
        if not self.allow_create.wait(timeout=3):
            raise TimeoutError("test did not release the Connect mutation")
        self.events.append(("create", dict(kwargs)))
        self.schedule = SimpleNamespace(rule=dict(kwargs))


def _adapter(
    gateway: Gateway, store: Store, *, clock: Callable[[], datetime] | None = None
) -> ConnectScheduleAdapter:
    if clock is None:
        return ConnectScheduleAdapter(
            gateway,
            store,
            allow_experimental_schedule_api=True,
        )
    return ConnectScheduleAdapter(
        gateway,
        store,
        allow_experimental_schedule_api=True,
        clock=clock,
    )


def _register(
    record: ScheduleRecord,
    binding: ConnectScheduleBinding,
    gateway: Gateway,
    store: Store,
) -> tuple[ConnectScheduleAdapter, ConnectScheduleBinding]:
    adapter = _adapter(gateway, store)
    bundle = build_trigger_bundle(
        schedule_id=record.schedule_id,
        schedule_revision_id=record.revision_id,
        timer_owner_generation=record.timer_owner_generation,
        endpoint_url=binding.target_url,
        credential_ref=SecretRef("env", "trigger", "token"),
        credential_env="ETLANTIC_TRIGGER_TOKEN",
        outbound_policy=OutboundPolicy(
            allowed_hosts=("receiver.example.com",),
            max_response_bytes=65_536,
        ),
    )
    binding = replace(binding, bundle_sha256=bundle.sha256)
    deployment = DeploymentResult(
        content_guid=binding.content_guid,
        state="deployed",
        bundle_sha256=binding.bundle_sha256,
        server_url=binding.server_url,
        operation_id="deployment-operation-1",
    )

    class Deployer:
        server_url = binding.server_url

    pending = adapter.register_deployed_content(
        record,
        bundle,
        deployment,
        Deployer(),
    )
    return adapter, pending


def test_apply_creates_only_after_durable_deployment_registration() -> None:
    record = _record()
    binding = _binding(record)
    gateway = Gateway()
    store = Store()
    adapter, pending = _register(record, binding, gateway, store)

    active = adapter.apply(record, pending)

    assert active.status == "active"
    assert [event[0] for event in gateway.events] == [
        "read",
        "read",
        "armed",
        "create",
        "read",
        "armed",
    ]
    assert gateway.events[2] == ("armed", False)
    assert gateway.events[-1] == ("armed", True)
    assert store.get(record.schedule_id) == active


def test_apply_recovers_pending_activation_from_matching_remote_readback() -> None:
    record = _record()
    binding = _binding(record)
    gateway = Gateway()
    store = Store()
    adapter, pending = _register(record, binding, gateway, store)
    in_flight = replace(
        pending,
        operation_id="operation-in-progress",
        pending_operation="apply",
        pending_target_status="active",
    )
    store.put(in_flight, expected=pending)
    gateway.schedule = SimpleNamespace(
        rule={
            "type": "hour",
            "n": 1,
            "start_time": record.next_fire_at,
            "timezone": "UTC",
            "email": False,
        }
    )
    gateway.events.clear()

    active = adapter.apply(record, in_flight)

    assert active.status == "active"
    assert [event[0] for event in gateway.events] == ["read", "armed"]
    assert gateway.events[-1] == ("armed", True)
    assert store.get(record.schedule_id) == active


def test_apply_does_not_replace_or_disarm_a_concurrent_pending_operation() -> None:
    record = _record()
    binding = _binding(record)
    gateway = BlockingGateway()
    store = Store()
    adapter, pending = _register(record, binding, gateway, store)

    with ThreadPoolExecutor(max_workers=1) as executor:
        first = executor.submit(adapter.apply, record, pending)
        assert gateway.create_started.wait(timeout=2)
        in_flight = store.get(record.schedule_id)
        assert in_flight is not None
        assert in_flight.pending_operation == "apply"
        assert in_flight.pending_target_status == "active"

        with pytest.raises(ScheduleOperationUnknown, match="not yet visible"):
            adapter.apply(record, pending)

        assert store.get(record.schedule_id) == in_flight
        gateway.allow_create.set()
        active = first.result(timeout=3)

    assert active.status == "active"
    assert gateway.armed is True
    assert store.get(record.schedule_id) == active


def test_apply_fails_closed_on_an_unclassified_pending_binding() -> None:
    record = _record()
    gateway = Gateway()
    store = Store()
    adapter, registration = _register(record, _binding(record), gateway, store)
    unclassified = replace(registration, pending_operation=None)
    store.put(unclassified, expected=registration)

    with pytest.raises(ScheduleOperationUnknown, match="no recognized operation type"):
        adapter.apply(record, unclassified)

    assert store.get(record.schedule_id) == unclassified
    assert [event[0] for event in gateway.events] == ["read"]


def test_sdk_decoded_schedule_shape_is_normalized_and_cursor_advance_is_not_drift() -> (
    None
):
    record = _record()
    binding = _binding(record)
    gateway = Gateway()
    store = Store()
    adapter, pending = _register(record, binding, gateway, store)
    active = adapter.apply(record, pending)
    gateway.schedule = SimpleNamespace(
        type="hour",
        rule={"N": 1},
        start_time=record.next_fire_at,
        timezone="UTC",
        email=False,
    )

    advanced = replace(record, next_fire_at="2026-10-13T14:00:00Z")
    drift = adapter.inspect_drift(advanced, active)

    assert drift.state == "in_sync"
    assert drift.expected == {
        "type": "hour",
        "n": 1,
        "start_time": "2026-10-13T13:00:00Z",
        "timezone": "UTC",
        "email": False,
    }
    assert drift.observed == drift.expected


def test_resume_retains_the_new_recurrence_anchor_in_active_binding() -> None:
    paused_record = replace(
        _record(), status="paused", next_fire_at="2026-10-13T14:00:00Z"
    )
    binding = replace(
        _binding(paused_record),
        schedule_start_time="2026-10-13T13:00:00Z",
        status="paused",
    )
    gateway = Gateway()
    store = Store(binding)
    adapter = _adapter(gateway, store)

    active = adapter.apply(replace(paused_record, status="active"), binding)
    later_cursor = replace(
        paused_record, status="active", next_fire_at="2026-10-13T15:00:00Z"
    )

    assert active.schedule_start_time == "2026-10-13T14:00:00Z"
    assert store.get(paused_record.schedule_id) == active
    assert adapter.inspect_drift(later_cursor, active).state == "in_sync"


def test_apply_refuses_to_adopt_an_unbound_connect_schedule() -> None:
    record = _record()
    gateway = Gateway({"type": "hour", "n": 1})
    store = Store()

    with pytest.raises(ScheduleOperationError, match="already has a Connect schedule"):
        _register(record, _binding(record), gateway, store)

    assert [event[0] for event in gateway.events] == ["read"]
    assert store.get(record.schedule_id) is None


@pytest.mark.parametrize(
    ("stale_revision", "unsupported_recurrence"),
    [(True, False), (False, True)],
)
def test_amend_preflight_rejects_before_pausing_or_deploying(
    stale_revision: bool,
    unsupported_recurrence: bool,
) -> None:
    record = _record()
    binding = _binding(record)
    gateway = Gateway()
    store = Store()
    adapter, pending = _register(record, binding, gateway, store)
    active = adapter.apply(record, pending)
    events_before = tuple(gateway.events)

    class Service:
        pauses = 0
        amendments = 0

        def get(self, context: ControlPlaneContext, schedule_id: str) -> ScheduleRecord:
            return record

        def pause(
            self, context: ControlPlaneContext, schedule_id: str
        ) -> ScheduleRecord:
            self.pauses += 1
            return replace(record, status="paused")

        def amend(
            self,
            context: ControlPlaneContext,
            schedule_id: str,
            *,
            expected_revision_id: str,
            spec: ScheduleSpec,
        ) -> ScheduleRecord:
            self.amendments += 1
            return replace(record, spec=spec, status="paused")

    class Deployer:
        server_url = gateway.server_url
        deploy_calls = 0

        def deploy(self, *_args: object, **_kwargs: object) -> DeploymentResult:
            self.deploy_calls += 1
            raise AssertionError("preflight rejection must happen before deploy")

    service = Service()
    deployer = Deployer()
    requested_spec = ScheduleSpec(
        kind="interval",
        interval_seconds=90 if unsupported_recurrence else 3600,
    )
    expected_revision_id = "stale-revision" if stale_revision else record.revision_id

    def build_bundle(_record: ScheduleRecord) -> Any:
        raise AssertionError("preflight rejection must happen before bundle build")

    with pytest.raises(ScheduleOperationError):
        adapter.amend(
            cast(ScheduleApplicationService, service),
            _context(),
            record.schedule_id,
            active,
            expected_revision_id=expected_revision_id,
            spec=requested_spec,
            build_bundle=build_bundle,
            deployer=cast(Any, deployer),
            title="ETLantic schedule",
            operation_id="amend-operation",
        )

    assert service.pauses == 0
    assert service.amendments == 0
    assert deployer.deploy_calls == 0
    assert store.get(record.schedule_id) == active
    assert tuple(gateway.events) == events_before
    assert gateway.armed is True


def test_apply_refuses_to_overwrite_remote_schedule_drift() -> None:
    record = _record()
    binding = _binding(record)
    store = Store(binding)
    gateway = Gateway(
        {
            "type": "hour",
            "n": 2,
            "start_time": record.next_fire_at,
            "timezone": "UTC",
            "email": False,
        }
    )

    with pytest.raises(ScheduleOperationError, match="drift detected"):
        _adapter(gateway, store).apply(record, binding)

    assert [event[0] for event in gateway.events] == ["read"]


def test_pause_path_disarms_before_deleting_the_owned_timer() -> None:
    record = _record()
    binding = _binding(record)
    desired = {
        "type": "hour",
        "n": 1,
        "start_time": record.next_fire_at,
        "timezone": "UTC",
        "email": False,
    }
    gateway = Gateway(desired)
    store = Store(binding)

    paused = _adapter(gateway, store).apply(replace(record, status="paused"), binding)

    assert paused.status == "paused"
    assert [event[0] for event in gateway.events] == [
        "read",
        "armed",
        "delete",
        "read",
    ]
    assert gateway.events[1] == ("armed", False)
    assert store.get(record.schedule_id) == paused


def test_binding_rejects_non_guid_content_id() -> None:
    record = _record()

    with pytest.raises(ValueError, match="Connect GUID"):
        replace(_binding(record), content_guid="customer-name")


def test_schedule_write_readback_failure_keeps_binding_pending_and_disarmed() -> None:
    record = _record()
    binding = _binding(record)

    class DriftedAfterWrite(Gateway):
        def create_or_update(
            self, content_guid: str, kwargs: Mapping[str, object]
        ) -> Any:
            super().create_or_update(content_guid, kwargs)
            self.schedule = SimpleNamespace(rule={**kwargs, "n": 99})

    gateway = DriftedAfterWrite()
    store = Store()
    adapter, pending = _register(record, binding, gateway, store)

    with pytest.raises(ScheduleOperationUnknown, match="readback"):
        adapter.apply(record, pending)

    assert [event[0] for event in gateway.events] == [
        "read",
        "read",
        "armed",
        "create",
        "read",
    ]
    pending = store.get(record.schedule_id)
    assert pending is not None and pending.status == "pending"


def test_resume_refuses_a_passed_canonical_cursor_before_enabling_timer() -> None:
    record = replace(_record(), status="paused")
    binding = replace(_binding(record), status="paused")
    gateway = Gateway()
    store = Store(binding)

    class Service:
        resumed = False

        def get(self, *_args: object) -> ScheduleRecord:
            return record

        def resume(self, *_args: object) -> ScheduleRecord:
            self.resumed = True
            return replace(record, status="active")

    service = Service()
    adapter = _adapter(
        gateway,
        store,
        clock=lambda: datetime(2026, 10, 13, 14, 0, tzinfo=UTC),
    )

    with pytest.raises(ScheduleOperationError, match="cursor before resuming"):
        adapter.resume(
            cast(ScheduleApplicationService, service),
            cast(ControlPlaneContext, None),
            record.schedule_id,
            binding,
        )

    assert not service.resumed
    assert gateway.events == []
