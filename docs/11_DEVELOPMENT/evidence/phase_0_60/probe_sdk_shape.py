"""Offline research probe; emits observations, not a release pass/fail result.

From the repository root:
  PYTHONPATH=src:packages/etlantic-rsconnect/src uv run --no-sync \
    --with posit-sdk==0.17.0 python \
    docs/11_DEVELOPMENT/evidence/phase_0_60/probe_sdk_shape.py

The real SDK and public gateway consume synthetic HTTP responses. Both HTTP
schemes are intercepted; no request can leave this process. No SDK method is
patched. This probe does not validate TLS or a live Connect server.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import inspect
import json
import warnings
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit

from etlantic_rsconnect import (
    ConnectScheduleAdapter,
    ConnectScheduleBinding,
    PositSdkGateway,
)
from requests import Response
from requests.adapters import BaseAdapter

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

SERVER = "https://connect.example.invalid/connect"
GUID = "01234567-89ab-cdef-0123-456789abcdef"
START = "2026-10-13T13:00:00Z"


class SyntheticResponses(BaseAdapter):
    """Strict read-only transport at the HTTP boundary below the actual SDK."""

    def __init__(self) -> None:
        super().__init__()
        self.trace: list[dict[str, str]] = []
        self.routes = {
            f"/connect/__api__/v1/content/{GUID}": {
                "guid": GUID,
                "app_mode": "quarto-static",
            },
            f"/connect/__api__/applications/{GUID}/variants": [
                {"id": 5, "app_id": 3, "is_default": True}
            ],
            "/connect/__api__/variants/5/schedules": [
                {
                    "id": 9,
                    "app_id": 3,
                    "variant_id": 5,
                    "type": "hour",
                    "schedule": '{"N": 1}',
                    "start_time": START,
                    "timezone": "UTC",
                    "email": False,
                    "activate": True,
                    "next_run": START,
                }
            ],
        }

    def send(
        self,
        request: Any,
        stream: bool = False,
        timeout: Any = None,
        verify: bool | str = True,
        cert: Any = None,
        proxies: Mapping[str, str] | None = None,
    ) -> Response:
        if request.url is None or request.method is None:
            raise AssertionError("synthetic SDK request is incomplete")
        request_url = cast(str, request.url)
        request_method = cast(str, request.method)
        url = urlsplit(request_url)
        if (
            request_method != "GET"
            or url.scheme != "https"
            or url.netloc != "connect.example.invalid"
            or url.path not in self.routes
        ):
            raise AssertionError("unexpected request in offline research probe")
        self.trace.append({"method": request.method, "path": url.path})
        response = Response()
        response.status_code = 200
        response.headers["Content-Type"] = "application/json"
        response.__dict__["_content"] = json.dumps(self.routes[url.path]).encode()
        response.request = request
        response.url = request_url
        return response

    def close(self) -> None:
        pass


class RejectStore:
    """A read-only drift probe must not read or mutate ownership storage."""

    def get(self, schedule_id: str) -> ConnectScheduleBinding | None:
        raise AssertionError("unexpected store access")

    def put(
        self,
        binding: ConnectScheduleBinding,
        *,
        expected: ConnectScheduleBinding | None,
    ) -> None:
        raise AssertionError("unexpected store mutation")

    def delete(self, schedule_id: str, *, expected: ConnectScheduleBinding) -> None:
        raise AssertionError("unexpected store mutation")


def main() -> None:
    transport = SyntheticResponses()
    connect = cast(Any, importlib.import_module("posit")).connect
    client = connect.Client(url=SERVER, api_key="synthetic-probe-credential")
    client.session.trust_env = False
    client.session.mount("http://", transport)
    client.session.mount("https://", transport)
    gateway = PositSdkGateway(client, server_url=SERVER)
    principal = Principal(subject="timer", issuer="research", kind="workload")
    context = ControlPlaneContext(
        principal=principal,
        tenant=TenantRef(tenant_id="research"),
        workspace=WorkspaceRef(tenant_id="research", workspace_id="local"),
        environment=EnvironmentRef(name="test"),
        security_domain=SecurityDomain(domain_id="test"),
    )
    record = MemoryScheduleStore().create(
        context,
        definition_id="synthetic-pipeline",
        profile_name="test",
        spec=ScheduleSpec(kind="interval", interval_seconds=3600),
        workload_identity=principal,
        timer_owner="external",
        next_fire_at=START,
    )
    binding = ConnectScheduleBinding(
        schedule_id=record.schedule_id,
        revision_id=record.revision_id,
        content_guid=GUID,
        timer_owner_generation=record.timer_owner_generation,
        server_url=SERVER,
        target_url="https://receiver.example.invalid/trigger",
        bundle_sha256="a" * 64,
        schedule_start_time=START,
    )
    # inspect_drift is read-only and does not access the binding store.
    with warnings.catch_warnings(record=True) as observed_warnings:
        warnings.simplefilter("always")
        schedule = gateway.read(GUID)
        adapter = ConnectScheduleAdapter(gateway, binding_store=RejectStore())
        drift = adapter.inspect_drift(record, binding)
    if schedule is None:
        raise AssertionError("synthetic SDK response did not produce a schedule")
    root = Path(__file__).resolve().parents[4]
    schedule_module = cast(Any, importlib.import_module("posit.connect.schedules"))
    schedule_type = schedule_module.Schedule
    source_files = {
        "adapter": root
        / "packages/etlantic-rsconnect/src/etlantic_rsconnect/adapter.py",
        "existing_adapter_tests": root / "tests/rsconnect/test_adapter.py",
        "sdk_schedule": Path(inspect.getfile(schedule_type)),
    }
    result = {
        "schema": "etlantic.rsconnect.simulation_research/1",
        "evidence_kind": "offline_sdk_contract_probe",
        "live_connect": False,
        "sdk_version": importlib.metadata.version("posit-sdk"),
        "fixture_origin": "synthetic; shaped from pinned SDK source",
        "sdk_rule": schedule.rule,
        "adapter_expected": drift.expected,
        "adapter_observed": drift.observed,
        "adapter_status": drift.state,
        "http_trace": transport.trace,
        "warning_categories": sorted(
            {warning.category.__name__ for warning in observed_warnings}
        ),
        "source_sha256": {
            name: hashlib.sha256(path.read_bytes()).hexdigest()
            for name, path in source_files.items()
        },
        "qualification": "SDK object shape only; no platform or TLS qualification",
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    client.session.close()


if __name__ == "__main__":
    main()
