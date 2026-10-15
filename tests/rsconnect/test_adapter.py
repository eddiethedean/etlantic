from __future__ import annotations

import json
import ssl
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from threading import Event, RLock
from types import SimpleNamespace
from typing import Any, cast
from urllib.parse import urlsplit

import pytest
from etlantic_rsconnect import (
    ConnectScheduleAdapter,
    ConnectScheduleBinding,
    DeploymentResult,
    PositSdkGateway,
    ScheduleOperationError,
    ScheduleOperationUnknown,
    build_trigger_bundle,
)

from etlantic.control_plane import (
    ControlPlaneContext,
    ControlPlaneError,
    EnvironmentRef,
    MemoryAuthorizer,
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


def test_apply_keeps_pending_activation_claim_until_its_writer_stops() -> None:
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

    with pytest.raises(ScheduleOperationUnknown, match="writer has stopped"):
        adapter.apply(record, in_flight)

    assert [event[0] for event in gateway.events] == []
    assert store.get(record.schedule_id) == in_flight


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

        with pytest.raises(ScheduleOperationUnknown, match="writer has stopped"):
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


def test_resume_binds_the_reanchored_timer_generation() -> None:
    context = _context()
    authorizer = MemoryAuthorizer()
    authorizer.grant(context, "schedule.read")
    authorizer.grant(context, "schedule.write")
    canonical_store = MemoryScheduleStore()
    now = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)
    service = ScheduleApplicationService(
        authorizer=authorizer,
        schedule_store=canonical_store,
        clock=lambda: now,
    )
    record = canonical_store.create(
        context,
        definition_id="pipeline-a",
        profile_name="test",
        spec=ScheduleSpec(kind="interval", interval_seconds=3600),
        workload_identity=context.principal,
        timer_owner="external",
        timer_schedule_start_at="2026-10-13T11:00:00Z",
        next_fire_at="2026-10-13T13:00:00Z",
    )
    paused = service.pause(context, record.schedule_id)
    binding = replace(
        _binding(paused),
        schedule_start_time=record.timer_schedule_start_at,
        status="paused",
    )
    gateway = Gateway()
    store = Store(binding)
    adapter = _adapter(gateway, store, clock=lambda: now)

    active = adapter.resume(service, context, record.schedule_id, binding)
    canonical = service.get(context, record.schedule_id)

    assert active.timer_owner_generation == canonical.timer_owner_generation
    assert active.timer_owner_generation == binding.timer_owner_generation + 1
    assert active.schedule_start_time == canonical.timer_schedule_start_at
    assert gateway.schedule is not None
    assert gateway.schedule.rule["start_time"] == canonical.timer_schedule_start_at


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


def test_sdk_gateway_requires_its_actual_destination_to_match_the_binding() -> None:
    class StubClient:
        def __init__(self, *, url: str, api_key: str) -> None:
            self.cfg = SimpleNamespace(url=url, api_key=api_key)

    matching_client = StubClient(
        url="https://connect.example.com/connect/__api__", api_key="test-key"
    )
    gateway = PositSdkGateway(
        matching_client, server_url="https://connect.example.com/connect"
    )
    assert gateway.server_url == "https://connect.example.com/connect"

    mismatched_client = StubClient(
        url="http://other-connect.example.com/connect/__api__", api_key="test-key"
    )
    with pytest.raises(ValueError, match="HTTPS Connect destination"):
        PositSdkGateway(
            mismatched_client, server_url="https://connect.example.com/connect"
        )

    wrong_host_client = StubClient(
        url="https://other-connect.example.com/connect/__api__", api_key="test-key"
    )
    with pytest.raises(ValueError, match="does not match"):
        PositSdkGateway(
            wrong_host_client, server_url="https://connect.example.com/connect"
        )


def test_sdk_gateway_owns_a_destination_pinned_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connect = pytest.importorskip("posit.connect")
    requests = pytest.importorskip("requests")
    content_guid = "01234567-89ab-cdef-0123-456789abcdef"
    client = connect.Client(
        url="https://connect.example.com/connect", api_key="synthetic-test-key"
    )

    class SyntheticTransport:
        def __init__(self) -> None:
            self.routes = {
                f"/connect/__api__/v1/content/{content_guid}": {
                    "guid": content_guid,
                    "app_mode": "rmd-static",
                },
                f"/connect/__api__/applications/{content_guid}/variants": [
                    {"is_default": True, "id": 2, "app_id": 1}
                ],
                "/connect/__api__/variants/2/schedules": [],
            }
            self.requests: list[tuple[str, object, object, object]] = []

        def send(
            self,
            request: Any,
            stream: bool = False,
            timeout: Any = None,
            verify: bool | str = True,
            cert: Any = None,
            proxies: Mapping[str, str] | None = None,
        ) -> Any:
            assert request.url is not None
            request_url = cast(str, request.url)
            path = urlsplit(request_url).path
            if path not in self.routes:
                pytest.fail(f"unexpected Posit SDK request path: {path}")
            self.requests.append((request_url, verify, cert, proxies))
            response = requests.Response()
            response.status_code = 200
            response.headers["Content-Type"] = "application/json"
            response.__dict__["_content"] = json.dumps(self.routes[path]).encode()
            response.request = request
            response.url = request_url
            return response

        def close(self) -> None:
            return

    transport = SyntheticTransport()
    client.session.verify = "/test/enterprise-ca.pem"
    client.session.cert = ("/test/client.pem", "/test/client.key")
    client.session.trust_env = False
    client.session.mount("http://", transport)
    client.session.mount("https://", transport)
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.invalid:8080")
    monkeypatch.setenv("https_proxy", "http://proxy.invalid:8080")
    monkeypatch.setenv("NO_PROXY", "")
    monkeypatch.setenv("no_proxy", "")
    gateway = PositSdkGateway(client, server_url="https://connect.example.com/connect")
    client.cfg.url = type(client.cfg.url)(
        "http://other-connect.example.invalid/connect"
    )

    with pytest.warns(FutureWarning, match="schedule API is experimental"):
        assert gateway.read(content_guid) is None

    assert transport.requests
    assert all(
        request[0].startswith("https://connect.example.com/connect/__api__/")
        for request in transport.requests
    )
    assert all(
        request[1] == "/test/enterprise-ca.pem" for request in transport.requests
    )
    assert all(
        request[2] == ("/test/client.pem", "/test/client.key")
        for request in transport.requests
    )
    assert all(not request[3] for request in transport.requests)


def test_sdk_gateway_preserves_custom_http_adapter_tls_configuration() -> None:
    connect = pytest.importorskip("posit.connect")
    requests = pytest.importorskip("requests")

    content_guid = "01234567-89ab-cdef-0123-456789abcdef"
    routes = {
        f"/connect/__api__/v1/content/{content_guid}": {
            "guid": content_guid,
            "app_mode": "rmd-static",
        },
        f"/connect/__api__/applications/{content_guid}/variants": [
            {"is_default": True, "id": 2, "app_id": 1}
        ],
        "/connect/__api__/variants/2/schedules": [],
    }
    tls_context = ssl.create_default_context()
    http_adapter = requests.adapters.HTTPAdapter
    sent_instances: list[Any] = []

    def adapter_init(self: Any, context: ssl.SSLContext) -> None:
        self.ssl_context = context
        http_adapter.__init__(self)

    def init_poolmanager(
        self: Any,
        connections: int,
        maxsize: int,
        block: bool = False,
        **kwargs: Any,
    ) -> None:
        kwargs["ssl_context"] = self.ssl_context
        http_adapter.init_poolmanager(self, connections, maxsize, block, **kwargs)

    def send(self: Any, request: Any, **_kwargs: Any) -> Any:
        assert self.ssl_context is tls_context
        assert request.url is not None
        request_url = cast(str, request.url)
        path = urlsplit(request_url).path
        response = requests.Response()
        response.status_code = 200
        response.headers["Content-Type"] = "application/json"
        response.__dict__["_content"] = json.dumps(routes[path]).encode()
        response.request = request
        response.url = request_url
        sent_instances.append(self)
        return response

    adapter_type: Any = type(
        "CustomTlsAdapter",
        (http_adapter,),
        {"__init__": adapter_init, "init_poolmanager": init_poolmanager, "send": send},
    )

    client = connect.Client(
        url="https://connect.example.com/connect", api_key="synthetic-test-key"
    )
    source_adapter = adapter_type(tls_context)
    client.session.mount("https://", source_adapter)
    gateway = PositSdkGateway(client, server_url="https://connect.example.com/connect")

    with pytest.warns(FutureWarning, match="schedule API is experimental"):
        assert gateway.read(content_guid) is None

    assert source_adapter not in sent_instances
    assert sent_instances
    assert all(
        adapter.ssl_context is tls_context
        and adapter.poolmanager.connection_pool_kw["ssl_context"] is tls_context
        for adapter in sent_instances
    )


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


def test_concurrent_resume_loser_cannot_disarm_winning_activation() -> None:
    paused_record = replace(_record(), status="paused")
    binding = replace(_binding(paused_record), status="paused")
    gateway = Gateway()
    store = Store(binding)

    class BlockingService:
        resume_started = Event()
        allow_resume = Event()
        resume_calls = 0

        def get(self, *_args: object) -> ScheduleRecord:
            return paused_record

        def resume(self, *_args: object) -> ScheduleRecord:
            self.resume_calls += 1
            self.resume_started.set()
            if not self.allow_resume.wait(timeout=3):
                raise TimeoutError("test did not release canonical resume")
            return replace(paused_record, status="active")

    service = BlockingService()
    adapter = _adapter(
        gateway,
        store,
        clock=lambda: datetime(2026, 10, 13, 12, 0, tzinfo=UTC),
    )
    with ThreadPoolExecutor(max_workers=1) as executor:
        first = executor.submit(
            adapter.resume,
            cast(ScheduleApplicationService, service),
            cast(ControlPlaneContext, None),
            paused_record.schedule_id,
            binding,
        )
        assert service.resume_started.wait(timeout=2)
        in_flight = store.get(paused_record.schedule_id)
        assert in_flight is not None
        assert in_flight.pending_operation == "resume"

        with pytest.raises(ScheduleOperationUnknown, match="pending"):
            adapter.resume(
                cast(ScheduleApplicationService, service),
                cast(ControlPlaneContext, None),
                paused_record.schedule_id,
                binding,
            )
        assert service.resume_calls == 1
        assert gateway.armed is False

        service.allow_resume.set()
        active = first.result(timeout=3)

    assert active.status == "active"
    assert gateway.armed is True
    assert store.get(paused_record.schedule_id) == active


def test_apply_cannot_finalize_a_resume_before_its_writer_stops() -> None:
    paused_record = replace(_record(), status="paused")
    active_record = replace(paused_record, status="active")
    binding = replace(_binding(paused_record), status="paused")

    class ReadbackBarrierGateway(Gateway):
        readback_started = Event()
        allow_readback = Event()
        hold_readback = False

        def create_or_update(
            self, content_guid: str, kwargs: Mapping[str, object]
        ) -> Any:
            result = super().create_or_update(content_guid, kwargs)
            self.hold_readback = True
            return result

        def read(self, content_guid: str) -> Any | None:
            result = super().read(content_guid)
            if self.hold_readback and not self.readback_started.is_set():
                self.readback_started.set()
                if not self.allow_readback.wait(timeout=3):
                    raise TimeoutError("test did not release Connect readback")
            return result

    class Service:
        status = "paused"
        pause_calls = 0

        def get(self, *_args: object) -> ScheduleRecord:
            return replace(paused_record, status=self.status)

        def authorize(
            self, ctx: ControlPlaneContext, action: str, resource: str
        ) -> None:
            return None

        def resume(self, *_args: object) -> ScheduleRecord:
            self.status = "active"
            return active_record

        def pause(self, *_args: object) -> ScheduleRecord:
            self.pause_calls += 1
            self.status = "paused"
            return paused_record

    gateway = ReadbackBarrierGateway()
    store = Store(binding)
    adapter = _adapter(
        gateway,
        store,
        clock=lambda: datetime(2026, 10, 13, 12, 0, tzinfo=UTC),
    )
    service = Service()
    context = _context()

    with ThreadPoolExecutor(max_workers=1) as executor:
        first = executor.submit(
            adapter.resume,
            cast(ScheduleApplicationService, service),
            context,
            paused_record.schedule_id,
            binding,
        )
        try:
            assert gateway.readback_started.wait(timeout=2)
            in_flight = store.get(paused_record.schedule_id)
            assert in_flight is not None
            assert in_flight.pending_operation == "resume"

            with pytest.raises(ScheduleOperationUnknown, match="writer has stopped"):
                adapter.apply(active_record, in_flight)
            with pytest.raises(
                ScheduleOperationUnknown, match="prior Connect mutation"
            ):
                adapter.pause(
                    cast(ScheduleApplicationService, service),
                    context,
                    paused_record.schedule_id,
                    in_flight,
                )

            assert service.pause_calls == 0
            assert gateway.armed is False
            assert store.get(paused_record.schedule_id) == in_flight
        finally:
            gateway.allow_readback.set()

        active = first.result(timeout=3)

    assert active.status == "active"
    assert gateway.armed is True
    paused = adapter.pause(
        cast(ScheduleApplicationService, service),
        context,
        paused_record.schedule_id,
        active,
    )
    assert paused.status == "paused"
    assert gateway.armed is False
    assert service.pause_calls == 1
    assert store.get(paused_record.schedule_id) == paused


def test_resume_claims_rollback_before_cleanup_side_effects() -> None:
    paused_record = replace(_record(), status="paused")
    binding = replace(_binding(paused_record), status="paused")
    trace: list[tuple[object, ...]] = []

    class TracedStore(Store):
        def put(
            self,
            binding: ConnectScheduleBinding,
            *,
            expected: ConnectScheduleBinding | None,
        ) -> None:
            trace.append(("store", binding.pending_operation))
            super().put(binding, expected=expected)

    class FailingGateway(Gateway):
        def set_trigger_armed(self, content_guid: str, armed: bool) -> None:
            trace.append(("armed", armed))
            super().set_trigger_armed(content_guid, armed)

        def create_or_update(
            self, content_guid: str, kwargs: Mapping[str, object]
        ) -> Any:
            trace.append(("create",))
            raise RuntimeError("synthetic Connect write failure")

    class Service:
        def get(self, *_args: object) -> ScheduleRecord:
            return paused_record

        def resume(self, *_args: object) -> ScheduleRecord:
            return replace(paused_record, status="active")

        def pause(self, *_args: object) -> ScheduleRecord:
            trace.append(("pause",))
            return paused_record

    gateway = FailingGateway()
    store = TracedStore(binding)
    adapter = _adapter(
        gateway,
        store,
        clock=lambda: datetime(2026, 10, 13, 12, 0, tzinfo=UTC),
    )

    with pytest.raises(RuntimeError, match="Connect write failure"):
        adapter.resume(
            cast(ScheduleApplicationService, Service()),
            _context(),
            paused_record.schedule_id,
            binding,
        )

    rollback_index = trace.index(("store", "rollback"))
    disarm_indices = [
        index for index, event in enumerate(trace) if event == ("armed", False)
    ]
    pause_index = trace.index(("pause",))
    assert len(disarm_indices) == 2
    assert rollback_index < disarm_indices[1] < pause_index
    pending = store.get(paused_record.schedule_id)
    assert pending is not None
    assert pending.status == "pending"
    assert pending.pending_operation == "rollback"


def test_resume_cleanup_cas_failure_does_not_disarm_new_owner() -> None:
    paused_record = replace(_record(), status="paused")
    binding = replace(_binding(paused_record), status="paused")

    class FailingBlockingGateway(Gateway):
        create_started = Event()
        allow_failure = Event()

        def create_or_update(
            self, content_guid: str, kwargs: Mapping[str, object]
        ) -> Any:
            super().create_or_update(content_guid, kwargs)
            self.create_started.set()
            if not self.allow_failure.wait(timeout=3):
                raise TimeoutError("test did not release failed Connect write")
            raise RuntimeError("synthetic lost write response")

    class Service:
        pause_calls = 0

        def get(self, *_args: object) -> ScheduleRecord:
            return paused_record

        def resume(self, *_args: object) -> ScheduleRecord:
            return replace(paused_record, status="active")

        def pause(self, *_args: object) -> ScheduleRecord:
            self.pause_calls += 1
            return paused_record

    gateway = FailingBlockingGateway()
    store = Store(binding)
    adapter = _adapter(
        gateway,
        store,
        clock=lambda: datetime(2026, 10, 13, 12, 0, tzinfo=UTC),
    )
    service = Service()
    context = _context()

    with ThreadPoolExecutor(max_workers=1) as executor:
        first = executor.submit(
            adapter.resume,
            cast(ScheduleApplicationService, service),
            context,
            paused_record.schedule_id,
            binding,
        )
        try:
            assert gateway.create_started.wait(timeout=2)
            in_flight = store.get(paused_record.schedule_id)
            assert in_flight is not None
            assert in_flight.pending_operation == "resume"

            # Model a successful reconciliation that wins the durable CAS
            # while the original request is still in flight.
            recovered = replace(
                in_flight,
                status="active",
                operation_id=None,
                pending_operation=None,
                pending_target_status=None,
            )
            store.put(recovered, expected=in_flight)
            gateway.armed = True
        finally:
            gateway.allow_failure.set()

        with pytest.raises(RuntimeError, match="lost write response"):
            first.result(timeout=3)

    assert store.get(paused_record.schedule_id) == recovered
    assert gateway.armed is True
    assert [event for event in gateway.events if event == ("armed", False)] == [
        ("armed", False)
    ]
    assert service.pause_calls == 0


def test_amend_refuses_remote_drift_before_pausing_or_deploying() -> None:
    record = _record()
    gateway = Gateway()
    store = Store()
    adapter, registration = _register(record, _binding(record), gateway, store)
    active = adapter.apply(record, registration)
    gateway.schedule = SimpleNamespace(
        rule={
            "type": "hour",
            "n": 99,
            "start_time": record.next_fire_at,
            "timezone": "UTC",
            "email": False,
        }
    )
    gateway.events.clear()

    class Service:
        pauses = 0
        amendments = 0

        def get(self, *_args: object) -> ScheduleRecord:
            return record

        def pause(self, *_args: object) -> ScheduleRecord:
            self.pauses += 1
            return replace(record, status="paused")

        def amend(self, *_args: object, **_kwargs: object) -> ScheduleRecord:
            self.amendments += 1
            return replace(record, status="paused")

    class Deployer:
        server_url = gateway.server_url
        deploy_calls = 0

        def deploy(self, *_args: object, **_kwargs: object) -> DeploymentResult:
            self.deploy_calls += 1
            raise AssertionError("remote drift must block deployment")

    service = Service()
    deployer = Deployer()
    with pytest.raises(ScheduleOperationError, match="drift detected"):
        adapter.amend(
            cast(ScheduleApplicationService, service),
            _context(),
            record.schedule_id,
            active,
            expected_revision_id=record.revision_id,
            spec=ScheduleSpec(kind="interval", interval_seconds=7200),
            build_bundle=lambda _record: cast(Any, None),
            deployer=cast(Any, deployer),
            title="ETLantic schedule",
            operation_id="amend-operation",
        )

    assert service.pauses == 0
    assert service.amendments == 0
    assert deployer.deploy_calls == 0
    assert store.get(record.schedule_id) == active
    assert [event[0] for event in gateway.events] == ["read"]


@pytest.mark.parametrize(
    ("operation", "target_status"), [("pause", "paused"), ("delete", "deleted")]
)
def test_pause_and_delete_claim_binding_before_canonical_mutation(
    operation: str, target_status: str
) -> None:
    context = _context()
    authorizer = MemoryAuthorizer()
    authorizer.grant(context, "schedule.read")
    authorizer.grant(context, "schedule.write")
    canonical_store = MemoryScheduleStore()
    service = ScheduleApplicationService(
        authorizer=authorizer,
        schedule_store=canonical_store,
        clock=lambda: datetime(2026, 10, 13, 12, 0, tzinfo=UTC),
    )
    record = canonical_store.create(
        context,
        definition_id="pipeline-a",
        profile_name="test",
        spec=ScheduleSpec(kind="interval", interval_seconds=3600),
        workload_identity=context.principal,
        timer_owner="external",
        next_fire_at="2026-10-13T13:00:00Z",
    )
    gateway = Gateway()
    store = Store()
    adapter, registration = _register(record, _binding(record), gateway, store)
    active = adapter.apply(record, registration)
    mutation_started = Event()
    allow_mutation = Event()

    class BarrierService:
        def get(self, ctx: ControlPlaneContext, schedule_id: str) -> ScheduleRecord:
            return service.get(ctx, schedule_id)

        def authorize(
            self, ctx: ControlPlaneContext, action: str, resource: str
        ) -> None:
            service.authorize(ctx, action, resource)

        def pause(self, ctx: ControlPlaneContext, schedule_id: str) -> ScheduleRecord:
            mutation_started.set()
            if not allow_mutation.wait(timeout=3):
                raise TimeoutError("test did not release canonical pause")
            return service.pause(ctx, schedule_id)

        def delete(self, ctx: ControlPlaneContext, schedule_id: str) -> ScheduleRecord:
            mutation_started.set()
            if not allow_mutation.wait(timeout=3):
                raise TimeoutError("test did not release canonical delete")
            return service.delete(ctx, schedule_id)

    barrier_service = BarrierService()

    class Deployer:
        server_url = gateway.server_url

        def deploy(self, *_args: object, **_kwargs: object) -> DeploymentResult:
            raise AssertionError("the concurrent amendment must lose the claim")

    with ThreadPoolExecutor(max_workers=1) as executor:
        pending_operation = executor.submit(
            getattr(adapter, operation),
            cast(ScheduleApplicationService, barrier_service),
            context,
            record.schedule_id,
            active,
        )
        try:
            assert mutation_started.wait(timeout=2)
            claimed = store.get(record.schedule_id)
            assert claimed is not None
            assert claimed.status == "pending"
            assert claimed.pending_operation == "apply"
            assert claimed.pending_target_status == target_status

            with pytest.raises(ScheduleOperationError, match="binding changed"):
                adapter.amend(
                    cast(ScheduleApplicationService, barrier_service),
                    context,
                    record.schedule_id,
                    active,
                    expected_revision_id=record.revision_id,
                    spec=ScheduleSpec(kind="interval", interval_seconds=7200),
                    build_bundle=lambda _record: cast(Any, None),
                    deployer=cast(Any, Deployer()),
                    title="ETLantic schedule",
                    operation_id="concurrent-amendment",
                )
        finally:
            allow_mutation.set()

        result = pending_operation.result(timeout=3)

    assert result.status == target_status
    assert store.get(record.schedule_id) == result
    assert gateway.schedule is None
    assert gateway.armed is False


@pytest.mark.parametrize(
    ("operation", "target_status"), [("pause", "paused"), ("delete", "deleted")]
)
def test_lifecycle_write_authorization_precedes_binding_claim(
    operation: str, target_status: str
) -> None:
    context = _context()
    authorizer = MemoryAuthorizer()
    authorizer.grant(context, "schedule.read")
    canonical_store = MemoryScheduleStore()
    service = ScheduleApplicationService(
        authorizer=authorizer,
        schedule_store=canonical_store,
        clock=lambda: datetime(2026, 10, 13, 12, 0, tzinfo=UTC),
    )
    record = canonical_store.create(
        context,
        definition_id="pipeline-a",
        profile_name="test",
        spec=ScheduleSpec(kind="interval", interval_seconds=3600),
        workload_identity=context.principal,
        timer_owner="external",
        next_fire_at="2026-10-13T13:00:00Z",
    )
    gateway = Gateway()
    store = Store()
    adapter, registration = _register(record, _binding(record), gateway, store)
    active = adapter.apply(record, registration)

    with pytest.raises(ControlPlaneError) as denied:
        getattr(adapter, operation)(service, context, record.schedule_id, active)

    assert denied.value.status == 404
    assert store.get(record.schedule_id) == active
    assert service.get(context, record.schedule_id).status == "active"
    assert gateway.armed is True

    authorizer.grant(context, "schedule.write")
    stopped = getattr(adapter, operation)(service, context, record.schedule_id, active)

    assert stopped.status == target_status
    assert store.get(record.schedule_id) == stopped
    assert gateway.armed is False


@pytest.mark.parametrize(
    ("operation", "remote_failure"),
    [
        (operation, failure)
        for operation in ("pause", "delete")
        for failure in ("missing", "unavailable")
    ],
)
def test_lifecycle_stops_canonical_admissions_before_connect_cleanup(
    operation: str, remote_failure: str
) -> None:
    context = _context()
    authorizer = MemoryAuthorizer()
    authorizer.grant(context, "schedule.read")
    authorizer.grant(context, "schedule.write")
    canonical_store = MemoryScheduleStore()
    service = ScheduleApplicationService(
        authorizer=authorizer,
        schedule_store=canonical_store,
        clock=lambda: datetime(2026, 10, 13, 12, 0, tzinfo=UTC),
    )
    record = canonical_store.create(
        context,
        definition_id="pipeline-a",
        profile_name="test",
        spec=ScheduleSpec(kind="interval", interval_seconds=3600),
        workload_identity=context.principal,
        timer_owner="external",
        next_fire_at="2026-10-13T13:00:00Z",
    )

    class FailingReadGateway(Gateway):
        fail_read = False

        def read(self, content_guid: str) -> Any | None:
            if self.fail_read:
                raise OSError("synthetic Connect outage with private details")
            return super().read(content_guid)

    gateway = FailingReadGateway()
    store = Store()
    adapter, registration = _register(record, _binding(record), gateway, store)
    active = adapter.apply(record, registration)
    if remote_failure == "missing":
        gateway.schedule = None
    else:
        gateway.fail_read = True

    expected_error = (
        ScheduleOperationError
        if remote_failure == "missing"
        else ScheduleOperationUnknown
    )
    with pytest.raises(expected_error) as failure:
        getattr(adapter, operation)(service, context, record.schedule_id, active)

    assert "private details" not in str(failure.value)
    if operation == "pause":
        assert service.get(context, record.schedule_id).status == "paused"
    else:
        with pytest.raises(ControlPlaneError) as missing_record:
            service.get(context, record.schedule_id)
        assert missing_record.value.status == 404
    pending = store.get(record.schedule_id)
    assert pending is not None
    assert pending.status == "pending"
    assert pending.pending_target_status == (
        "paused" if operation == "pause" else "deleted"
    )
    assert gateway.armed is True


def test_amend_commit_ack_loss_cannot_pause_a_newer_owner() -> None:
    context = _context()
    authorizer = MemoryAuthorizer()
    authorizer.grant(context, "schedule.read")
    authorizer.grant(context, "schedule.write")
    canonical_store = MemoryScheduleStore()
    service = ScheduleApplicationService(
        authorizer=authorizer,
        schedule_store=canonical_store,
        clock=lambda: datetime(2026, 10, 13, 12, 0, tzinfo=UTC),
    )
    record = canonical_store.create(
        context,
        definition_id="pipeline-a",
        profile_name="test",
        spec=ScheduleSpec(kind="interval", interval_seconds=3600),
        workload_identity=context.principal,
        timer_owner="external",
        next_fire_at="2026-10-13T13:00:00Z",
    )
    committed = Event()
    release_first_writer = Event()

    class CommitThenRaiseStore(Store):
        blocked = False

        def put(
            self,
            binding: ConnectScheduleBinding,
            *,
            expected: ConnectScheduleBinding | None,
        ) -> None:
            super().put(binding, expected=expected)
            if (
                not self.blocked
                and binding.status == "active"
                and expected is not None
                and expected.pending_operation == "amend"
            ):
                self.blocked = True
                committed.set()
                if not release_first_writer.wait(timeout=4):
                    raise TimeoutError("test did not release first amendment")
                raise OSError("synthetic lost COMMIT acknowledgement")

    gateway = Gateway()
    store = CommitThenRaiseStore()
    adapter, registration = _register(record, _binding(record), gateway, store)
    active = adapter.apply(record, registration)

    def build_bundle(amended: ScheduleRecord) -> Any:
        return build_trigger_bundle(
            schedule_id=amended.schedule_id,
            schedule_revision_id=amended.revision_id,
            timer_owner_generation=amended.timer_owner_generation,
            endpoint_url="https://receiver.example.com/trigger",
            credential_ref=SecretRef("env", "trigger", "token"),
            credential_env="ETLANTIC_TRIGGER_TOKEN",
            outbound_policy=OutboundPolicy(
                allowed_hosts=("receiver.example.com",),
                max_response_bytes=65_536,
            ),
        )

    class Deployer:
        server_url = gateway.server_url

        def deploy(
            self, bundle: Any, *, operation_id: str, **_kwargs: object
        ) -> DeploymentResult:
            return DeploymentResult(
                content_guid=active.content_guid,
                state="updated",
                bundle_sha256=bundle.sha256,
                server_url=self.server_url,
                operation_id=operation_id,
            )

    deployer = Deployer()

    def amend(binding: ConnectScheduleBinding, interval_seconds: int, op_id: str):
        return adapter.amend(
            service,
            context,
            record.schedule_id,
            binding,
            expected_revision_id=service.get(context, record.schedule_id).revision_id,
            spec=ScheduleSpec(kind="interval", interval_seconds=interval_seconds),
            build_bundle=build_bundle,
            deployer=cast(Any, deployer),
            title="ETLantic schedule",
            operation_id=op_id,
        )

    with ThreadPoolExecutor(max_workers=1) as executor:
        first = executor.submit(amend, active, 7200, "first-amendment")
        try:
            assert committed.wait(timeout=3)
            first_committed_binding = store.get(record.schedule_id)
            assert first_committed_binding is not None
            assert first_committed_binding.status == "active"

            latest = amend(first_committed_binding, 10_800, "second-amendment")
            assert latest.status == "active"
            assert gateway.armed is True
        finally:
            release_first_writer.set()

        with pytest.raises(ScheduleOperationUnknown, match="could not be committed"):
            first.result(timeout=3)

    canonical = service.get(context, record.schedule_id)
    assert canonical.status == "active"
    assert canonical.spec.interval_seconds == 10_800
    assert store.get(record.schedule_id) == latest
    assert latest.revision_id == canonical.revision_id
    assert latest.timer_owner_generation == canonical.timer_owner_generation
    assert latest.schedule_start_time == canonical.timer_schedule_start_at
    assert gateway.armed is True
    assert gateway.schedule is not None
    assert gateway.schedule.rule["n"] == 3
