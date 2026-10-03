"""Fail-closed authorization-before-lookup checks for every CP operation."""

from __future__ import annotations

import threading
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from functools import wraps
from typing import Any, cast
from urllib.parse import quote

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("etlantic_fastapi")
pytest.importorskip("httpx2")

from fastapi.testclient import TestClient
from scripts.check_phase_0_56_control_coverage import as_list, as_mapping, build_openapi

from etlantic.control_plane import (
    AuthzDecision,
    ControlPlaneContext,
    ControlPlaneError,
    Disclosure,
    EnvironmentRef,
    MemoryAuthorizer,
    MemoryDefinitionRepository,
    MemoryDurableWorkStore,
    MemoryEventStore,
    MemoryInputResourceStore,
    MemorySubmissionStore,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic.control_plane.durable_protocols import DurableWorkStore
from etlantic.control_plane.protocols import EventStore, SubmissionStore
from etlantic_fastapi import (
    ETLanticAPI,
    create_app,
    membership_context_factory,
    principal_from_header,
)


class _RecordingDenyAuthorizer(MemoryAuthorizer):
    def __init__(self, trace: list[tuple[str, str]]) -> None:
        super().__init__()
        self.calls: list[tuple[str, str]] = []
        self.explicit_disclosure: str | None = None
        self.trace = trace

    def authorize(self, ctx: Any, action: str, resource: str) -> AuthzDecision:
        self.calls.append((action, resource))
        self.trace.append(("authorize", action))
        return AuthzDecision(
            allowed=False,
            reason="authorization denied",
            disclosure=self.explicit_disclosure,
        )


class _LookupCountingDefinitions(MemoryDefinitionRepository):
    def __init__(self) -> None:
        super().__init__()
        self.lookup_calls: Counter[str] = Counter()

    def get(self, ctx: Any, definition_id: str) -> Any:
        self.lookup_calls["get"] += 1
        return super().get(ctx, definition_id)

    def list(self, ctx: Any) -> Any:
        self.lookup_calls["list"] += 1
        return super().list(ctx)

    def put(self, ctx: Any, definition_id: str, document: Any) -> None:
        self.lookup_calls["put"] += 1
        return super().put(ctx, definition_id, document)

    def resolve_revision(self, ctx: Any, definition_id: str, selector: str) -> Any:
        self.lookup_calls["resolve_revision"] += 1
        return super().resolve_revision(ctx, definition_id, selector)


class _OperationCountingStore:
    def __init__(self, store: Any, trace: list[tuple[str, str]]) -> None:
        self.store = store
        self.calls: Counter[str] = Counter()
        self.trace = trace
        self._lock = threading.Lock()

    def __getattr__(self, name: str) -> Any:
        value = getattr(self.store, name)
        if not callable(value):
            return value

        @wraps(value)
        def tracked(*args: Any, **kwargs: Any) -> Any:
            with self._lock:
                self.calls[name] += 1
                self.trace.append(("store", name))
            return value(*args, **kwargs)

        return tracked


class _ExplicitRunDisclosureAuthorizer(MemoryAuthorizer):
    def __init__(self, decisions: dict[str, Disclosure]) -> None:
        super().__init__()
        self.decisions = decisions

    def authorize(self, ctx: Any, action: str, resource: str) -> AuthzDecision:
        _ = ctx, action
        run_id = resource.removeprefix("run:")
        disclosure = self.decisions.get(run_id)
        if disclosure is not None:
            return AuthzDecision(
                allowed=False,
                reason=f"explicit {disclosure} policy",
                disclosure=disclosure,
            )
        return AuthzDecision(
            allowed=False, reason="opaque denial", disclosure="not_found"
        )


class _CountingSubmissionStore(MemorySubmissionStore):
    def __init__(self) -> None:
        super().__init__()
        self.get_run_calls: Counter[str] = Counter()
        self._calls_lock = threading.Lock()

    def get_run(self, ctx: Any, run_id: str) -> dict[str, Any]:
        with self._calls_lock:
            self.get_run_calls[run_id] += 1
        return super().get_run(ctx, run_id)


def _context(
    subject: str,
    tenant: str = "tenant-a",
    workspace: str = "workspace-a",
    owner: str | None = None,
) -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal(subject=subject),
        tenant=TenantRef(tenant_id=tenant),
        workspace=WorkspaceRef(tenant_id=tenant, workspace_id=workspace),
        environment=EnvironmentRef(name="development"),
        security_domain=SecurityDomain(domain_id="default"),
        resource_owner_id=owner,
    )


def _sample(
    schema: dict[str, Any],
    components: dict[str, Any],
    seen: frozenset[str] = frozenset(),
) -> Any:
    schema = as_mapping(schema)
    ref = schema.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
        name = ref.rsplit("/", 1)[-1]
        if name in seen:
            return {}
        return _sample(as_mapping(components.get(name, {})), components, seen | {name})
    for variant_key in ("anyOf", "oneOf"):
        variants = as_list(schema.get(variant_key))
        if variants:
            for raw_variant in variants:
                variant = as_mapping(raw_variant)
                if variant and variant.get("type") != "null":
                    return _sample(variant, components, seen)
            return None
    all_of = as_list(schema.get("allOf"))
    if all_of:
        merged: dict[str, Any] = {"type": "object", "properties": {}, "required": []}
        for raw_variant in all_of:
            variant = as_mapping(raw_variant)
            value = _sample(variant, components, seen)
            if isinstance(value, dict):
                as_mapping(merged["properties"]).update(
                    as_mapping(variant.get("properties"))
                )
                as_list(merged["required"]).extend(as_list(variant.get("required", [])))
        return _sample(merged, components, seen)
    if schema.get("enum"):
        return schema["enum"][0]
    schema_type = schema.get("type")
    if schema_type == "object" or "properties" in schema:
        properties = as_mapping(schema.get("properties", {}))
        required = as_list(schema.get("required", []))
        return {
            name: _sample(as_mapping(properties[name]), components, seen)
            for name in required
            if name in properties
        }
    if schema_type == "array":
        return []
    if schema_type == "integer":
        return int(schema.get("minimum", 1))
    if schema_type == "number":
        return float(schema.get("minimum", 1))
    if schema_type == "boolean":
        return False
    if schema_type == "string":
        if schema.get("format") == "date-time":
            return "2026-01-01T00:00:00Z"
        if schema.get("format") == "date":
            return "2026-01-01"
        if schema.get("format") == "uri":
            return "https://example.invalid"
        return "coverage-test"
    return {}


def _request_parts(
    operation: dict[str, Any], components: dict[str, Any]
) -> tuple[dict[str, str], dict[str, Any], Any | None, dict[str, str]]:
    path = str(operation["path"])
    query: dict[str, Any] = {}
    headers = {
        "X-Principal": "unauthorized-coverage-user",
        "Idempotency-Key": "coverage-test",
    }
    for raw_parameter in as_list(operation.get("parameters", [])):
        parameter = as_mapping(raw_parameter)
        if not parameter.get("required"):
            continue
        name = str(parameter.get("name", ""))
        value = _sample(as_mapping(parameter.get("schema", {})), components)
        if parameter.get("in") == "path":
            path = path.replace("{" + name + "}", quote(str(value), safe=""))
        elif parameter.get("in") == "query":
            query[name] = value
        elif parameter.get("in") == "header":
            headers[name] = str(value)

    body: Any | None = None
    request_body = as_mapping(operation.get("requestBody", {}))
    if request_body.get("required"):
        content = as_mapping(request_body.get("content", {}))
        json_schema = as_mapping(content.get("application/json", {})).get("schema")
        if json_schema is not None:
            body = _sample(as_mapping(json_schema), components)
    return (
        {
            "path": path,
            "method": str(operation["method"]).upper(),
        },
        query,
        body,
        headers,
    )


def test_each_protected_cp_operation_authorizes_before_definition_lookup() -> None:
    openapi, _endpoints = build_openapi()
    trace: list[tuple[str, str]] = []
    authorizer = _RecordingDenyAuthorizer(trace)
    definitions = _LookupCountingDefinitions()
    submissions = _OperationCountingStore(MemorySubmissionStore(), trace)
    events = _OperationCountingStore(MemoryEventStore(), trace)
    durable_work = _OperationCountingStore(MemoryDurableWorkStore(), trace)
    api = ETLanticAPI(
        authorizer=authorizer,
        definitions=definitions,
        submissions=cast(SubmissionStore, submissions),
        events=cast(EventStore, events),
        durable_work=cast(DurableWorkStore, durable_work),
        context_factory=membership_context_factory(
            {
                "unauthorized-coverage-user": (
                    "tenant-a",
                    "ws-a",
                    "development",
                    "default",
                )
            }
        ),
        principal_dependency=principal_from_header,
    )
    client: Any = TestClient(create_app(api))
    components = as_mapping(
        as_mapping(openapi.get("components", {})).get("schemas", {})
    )
    tested = 0
    public = {"cp_health", "cp_ready"}

    for path_template, path_item in as_mapping(openapi["paths"]).items():
        for method, raw_operation in as_mapping(path_item).items():
            operation = as_mapping(raw_operation)
            operation_id = operation.get("operationId", "")
            if not operation_id.startswith("cp_") or operation_id in public:
                continue
            request, query, body, headers = _request_parts(
                {
                    **operation,
                    "path": str(path_template),
                    "method": str(method),
                },
                components,
            )
            auth_calls_before = len(authorizer.calls)
            trace_before = len(trace)
            response: Any = client.request(
                request["method"],
                request["path"],
                params=query,
                headers=headers,
                json=body,
            )
            assert len(authorizer.calls) > auth_calls_before, (
                operation_id,
                response.status_code,
                response.text,
            )
            assert response.status_code in {403, 404}, (
                operation_id,
                response.status_code,
                response.text,
            )
            request_trace = trace[trace_before:]
            authorization_indexes = [
                index
                for index, (kind, _name) in enumerate(request_trace)
                if kind == "authorize"
            ]
            store_indexes = [
                index
                for index, (kind, _name) in enumerate(request_trace)
                if kind == "store"
            ]
            assert authorization_indexes, (operation_id, request_trace)
            assert not store_indexes or min(authorization_indexes) < min(
                store_indexes
            ), (
                operation_id,
                request_trace,
            )
            tested += 1

    assert tested > 80
    assert definitions.lookup_calls == Counter()


def test_explicit_run_disclosure_matches_headless_and_http_under_concurrency() -> None:
    run_ids: dict[str, Disclosure] = {
        "run-opaque": "not_found",
        "run-forbidden": "forbidden",
    }
    ctx = _context("alice")
    authorizer = _ExplicitRunDisclosureAuthorizer(run_ids)
    submissions = _CountingSubmissionStore()
    api = ETLanticAPI(
        authorizer=authorizer,
        definitions=MemoryDefinitionRepository(),
        submissions=submissions,
        events=MemoryEventStore(),
        durable_work=MemoryDurableWorkStore(),
        context_factory=membership_context_factory(
            {"alice": ("tenant-a", "workspace-a", "development", "default")}
        ),
        principal_dependency=principal_from_header,
    ).enable_managed_execution()
    service = api.managed_service
    assert service is not None
    for run_id in run_ids:
        submissions.accept(
            ctx,
            idempotency_key=f"seed-{run_id}",
            payload={"definition_id": "seed"},
            resource_id=run_id,
        )
    client: Any = TestClient(create_app(api))

    def headless_outcome(run_id: str) -> tuple[int, str]:
        try:
            service.get_run_status(ctx, run_id)
        except ControlPlaneError as exc:
            return exc.status, exc.code
        raise AssertionError("explicit denial unexpectedly allowed headless access")

    def http_outcome(run_id: str) -> tuple[int, str]:
        response = client.get(f"/v1/runs/{run_id}", headers={"X-Principal": "alice"})
        return response.status_code, response.json()["code"]

    tasks: list[tuple[str, Callable[[str], tuple[int, str]]]] = [
        ("run-opaque", headless_outcome),
        ("run-opaque", http_outcome),
        ("run-forbidden", headless_outcome),
        ("run-forbidden", http_outcome),
    ]

    def run_task(task: tuple[str, Callable[[str], tuple[int, str]]]) -> tuple[int, str]:
        return task[1](task[0])

    with ThreadPoolExecutor(max_workers=4) as pool:
        outcomes: list[tuple[int, str]] = list(pool.map(run_task, tasks))

    assert outcomes == [
        (404, "PMCP404"),
        (404, "PMCP404"),
        (403, "PMCP403"),
        (403, "PMCP403"),
    ]
    # Both records exist, but explicit disclosure decisions must not probe them.
    assert submissions.get_run_calls == Counter()


@pytest.mark.parametrize(
    "foreign_context",
    [
        _context("bob", owner="owner-b"),
        _context("carol", tenant="tenant-b", owner="owner-a"),
        _context("dana", workspace="workspace-b", owner="owner-a"),
    ],
    ids=["cross-owner", "cross-tenant", "cross-workspace"],
)
def test_input_resource_isolation_matches_headless_and_http(
    foreign_context: ControlPlaneContext,
) -> None:
    owner_context = _context("alice", owner="owner-a")
    authorizer = MemoryAuthorizer()
    for context in (owner_context, foreign_context):
        authorizer.grant(context, "input.upload")
        authorizer.grant(context, "input.finalize")
        authorizer.grant(context, "input.delete")
    resources = MemoryInputResourceStore()
    subjects = {
        "alice": ("tenant-a", "workspace-a", "development", "default"),
        "bob": ("tenant-a", "workspace-a", "development", "default"),
        "carol": ("tenant-b", "workspace-a", "development", "default"),
        "dana": ("tenant-a", "workspace-b", "development", "default"),
    }
    api = ETLanticAPI(
        authorizer=authorizer,
        definitions=MemoryDefinitionRepository(),
        submissions=MemorySubmissionStore(),
        events=MemoryEventStore(),
        durable_work=MemoryDurableWorkStore(),
        input_resources=resources,
        context_factory=membership_context_factory(
            subjects,
            resource_owners={
                "alice": "owner-a",
                "bob": "owner-b",
                "carol": "owner-a",
                "dana": "owner-a",
            },
        ),
        principal_dependency=principal_from_header,
    )
    content = b"id,value\n1,private\n"
    staged = resources.stage(
        owner_context,
        content,
        media_type="text/csv",
        format="csv",
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    client: Any = TestClient(create_app(api))

    try:
        resources.abort(foreign_context, staged.upload_id)
    except ControlPlaneError as exc:
        headless = (exc.status, exc.code)
    else:
        raise AssertionError("foreign owner unexpectedly aborted the upload")

    response = client.delete(
        f"/v1/input-resources/{staged.upload_id}",
        headers={"X-Principal": foreign_context.principal.subject},
    )
    http = (response.status_code, response.json()["code"])
    assert headless == http, response.text
    assert headless[0] == 404

    # The failed foreign attempts did not mutate the owner's staged upload.
    owner_response = client.delete(
        f"/v1/input-resources/{staged.upload_id}",
        headers={"X-Principal": "alice"},
    )
    assert owner_response.status_code == 204
