# pyright: reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownVariableType=false, reportUnusedFunction=false
"""Regression tests for 0.4.0 runtime bugfixes."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any, cast

import anyio
import pytest

from etlantic import (
    Data,
    Extract,
    Input,
    Load,
    Output,
    Pipeline,
    PipelineRuntime,
    SecretRef,
    Transformation,
)
from etlantic.exceptions import PipelineExecutionError
from etlantic.lifecycle import Inject
from etlantic.lifecycle.callbacks import FailureAction
from etlantic.registry import BindingDescriptor, PlanningContext
from etlantic.reports.model import PipelineRunReport
from etlantic.runtime.context import TrustedExecutionScope
from etlantic.runtime.events import SecurityEvent
from etlantic.runtime.request import MaterializationPolicy, RunRequest, RunSelection
from etlantic.runtime.state import RunStatus
from etlantic.schema_drift import (
    SchemaObservation,
    normalize_schema_from_fields,
    normalize_schema_from_model,
)
from etlantic.schema_policy import DriftAction, SchemaDriftPolicy, evaluate_drift
from etlantic.secrets.provider import (
    SecretLease,
    SecretProvider,
    SecretProviderCapabilities,
    SecretProviderDescriptor,
    SecretResolutionContext,
)
from etlantic.secrets.value import SecretValue


class Row(Data):
    id: int
    name: str


class Normalize(Transformation):
    rows: Input[Row]
    result: Output[Row]


@Normalize.implementation("local")
def normalize_local(rows: list[Row]) -> list[Row]:
    return [Row(id=r.id, name=r.name.strip().title()) for r in rows]


class NoImpl(Transformation):
    rows: Input[Row]
    result: Output[Row]


class SimplePipeline(Pipeline):
    raw: Extract[Row] = Extract(asset="rows")
    normalized = Normalize.step(rows=raw)
    out: Load[Row] = Load(input=normalized.result, asset="out")


class _VersionedSecretProvider:
    def __init__(
        self,
        *,
        supports_versions: bool,
        resolved_version: str,
        supports_aliases: bool | None = None,
        rotate: bool = False,
        supports_leases: bool = False,
        supports_renewal: bool = False,
        supports_revocation: bool = False,
        lease_ttl: float = 1.0,
        fail_renewal: bool = False,
        fail_revocation: bool = False,
    ) -> None:
        self.descriptor = SecretProviderDescriptor(
            name="versioned-test",
            engine="test",
            capabilities=SecretProviderCapabilities(
                versions=supports_versions,
                aliases=(
                    supports_versions if supports_aliases is None else supports_aliases
                ),
                leases=supports_leases,
                renewal=supports_renewal,
                revocation=supports_revocation,
                in_memory_cache=True,
            ),
        )
        self.resolved_version = resolved_version
        self.rotate = rotate
        self.calls = 0
        self.lease_calls = 0
        self.renewal_calls = 0
        self.revocation_calls = 0
        self.lease_ttl = lease_ttl
        self.fail_renewal = fail_renewal
        self.fail_revocation = fail_revocation
        self._leases: dict[str, SecretValue] = {}
        self.contexts: list[SecretResolutionContext] = []

    @property
    def active_lease_count(self) -> int:
        return len(self._leases)

    async def resolve(
        self, reference: SecretRef, context: SecretResolutionContext
    ) -> SecretValue:
        self.calls += 1
        self.contexts.append(context)
        return SecretValue(
            _value="version-test-secret",
            provider=reference.provider,
            name=reference.name,
            key=reference.key,
            version=(
                f"release-{41 + self.calls}" if self.rotate else self.resolved_version
            ),
        )

    async def acquire_lease(
        self, reference: SecretRef, context: SecretResolutionContext
    ) -> SecretLease:
        self.lease_calls += 1
        self.contexts.append(context)
        lease_id = f"lease-{self.lease_calls}"
        value = SecretValue(
            _value="version-test-secret",
            provider=reference.provider,
            name=reference.name,
            key=reference.key,
            version=(
                f"release-{41 + self.lease_calls}"
                if self.rotate
                else self.resolved_version
            ),
        )
        self._leases[lease_id] = value
        return SecretLease(
            lease_id=lease_id,
            value=value,
            expires_at=datetime.now(UTC) + timedelta(seconds=self.lease_ttl),
        )

    async def renew_lease(
        self, lease_id: str, context: SecretResolutionContext
    ) -> SecretLease:
        self.renewal_calls += 1
        if self.fail_renewal:
            raise RuntimeError("provider outage containing version-test-secret")
        value = self._leases[lease_id]
        return SecretLease(
            lease_id=lease_id,
            value=value,
            expires_at=datetime.now(UTC) + timedelta(seconds=self.lease_ttl),
        )

    async def revoke_lease(
        self, lease_id: str, context: SecretResolutionContext
    ) -> None:
        self.revocation_calls += 1
        if self.fail_revocation:
            raise RuntimeError("revocation failed for version-test-secret")
        self._leases.pop(lease_id, None)


class _AllowSecretAlias:
    def __init__(self) -> None:
        self.contexts: list[SecretResolutionContext] = []

    async def authorize_late_binding(
        self, reference: SecretRef, context: SecretResolutionContext
    ) -> bool:
        assert reference.version == "current"
        self.contexts.append(context)
        return (
            context.trusted_scope is not None
            and context.trusted_scope.resource_owner_id == "owner-a"
            and context.purpose == "read"
        )


class MissingImplPipeline(Pipeline):
    raw: Extract[Row] = Extract(asset="rows")
    step = NoImpl.step(rows=raw)
    out: Load[Row] = Load(input=step.result, asset="out")


def test_missing_implementation_fails_closed() -> None:
    from etlantic.exceptions import PipelineValidationError

    runtime = PipelineRuntime()
    runtime.memory.seed("rows", [Row(id=1, name="a")])
    with pytest.raises(PipelineValidationError) as exc:
        MissingImplPipeline.run(profile="development", runtime=runtime)
    assert any(d.code == "PMPLAN301" for d in exc.value.report.errors)


def test_durable_policy_controls_workspace_files(tmp_path: Path) -> None:
    none_dir = tmp_path / "none"
    durable_dir = tmp_path / "durable"

    runtime = PipelineRuntime()
    runtime.memory.seed("rows", [Row(id=1, name="ada")])
    report = SimplePipeline.run(
        profile="development",
        runtime=runtime,
        workspace=none_dir,
        request=RunRequest(materialization=MaterializationPolicy.NONE),
    )
    assert report.status is RunStatus.SUCCEEDED
    assert list(none_dir.glob("*.json")) == []

    runtime2 = PipelineRuntime()
    runtime2.memory.seed("rows", [Row(id=1, name="ada")])
    report2 = SimplePipeline.run(
        profile="development",
        runtime=runtime2,
        workspace=durable_dir,
        request=RunRequest(materialization=MaterializationPolicy.DURABLE),
    )
    assert report2.status is RunStatus.SUCCEEDED
    assert list(durable_dir.glob("*.json"))


def test_secret_reaches_storage_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PIPE_TOKEN", "top-secret")
    seen: dict[str, object] = {}

    class CapturingMemory:
        name = "memory"

        async def read(self, *, binding, location, contract_type, context):
            seen["secret"] = context.get("secret")
            return [Row(id=1, name="x")]

        async def write(self, *, binding, location, data, contract_type, context):
            return {"records": len(data) if isinstance(data, list) else 1}

    runtime = PipelineRuntime()
    runtime.storage["memory"] = CapturingMemory()  # type: ignore[assignment]
    context = PlanningContext.create(profile="development")
    context.registry.register_binding(
        BindingDescriptor(
            binding="rows",
            provider="memory",
            secret_ref=SecretRef(provider="env", name="PIPE_TOKEN", key="value"),
        )
    )
    report = SimplePipeline.run(profile="development", runtime=runtime, context=context)
    assert report.status is RunStatus.SUCCEEDED
    secret = seen["secret"]
    assert secret is not None
    assert secret.get_secret_value() == "top-secret"  # type: ignore[union-attr]
    assert "top-secret" not in report.to_json()


def test_missing_secret_fails_closed() -> None:
    runtime = PipelineRuntime()
    context = PlanningContext.create(profile="development")
    context.registry.register_binding(
        BindingDescriptor(
            binding="rows",
            provider="memory",
            secret_ref=SecretRef(
                provider="env", name="MISSING_SECRET_XYZ", key="value"
            ),
        )
    )
    report = SimplePipeline.run(profile="development", runtime=runtime, context=context)
    assert report.status in {RunStatus.FAILED, RunStatus.PARTIAL}
    assert any("Secret" in (d.message or "") for d in report.diagnostics)


def _run_with_secret_version(
    provider: _VersionedSecretProvider,
    requested_version: str,
    *,
    trusted_scope: TrustedExecutionScope | None = None,
    alias_authorizer: _AllowSecretAlias | None = None,
    also_bind_sink: bool = False,
    io_delay: float = 0.0,
) -> tuple[PipelineRuntime, PipelineRunReport]:
    runtime = PipelineRuntime()
    runtime.secret_providers["versioned-test"] = cast(SecretProvider, provider)
    runtime.trusted_execution_scope = trusted_scope
    runtime.secret_alias_authorizer = alias_authorizer
    if io_delay:
        memory = runtime.memory
        original_read = memory.read

        async def delayed_read(*args: Any, **kwargs: Any) -> Any:
            await anyio.sleep(io_delay)
            return await original_read(*args, **kwargs)

        object.__setattr__(memory, "read", delayed_read)
    planning = PlanningContext.create(profile="development")
    reference = SecretRef(
        provider="versioned-test",
        name="warehouse",
        key="password",
        version=requested_version,
        purpose="read",
    )
    planning.registry.register_binding(
        BindingDescriptor(
            binding="rows",
            provider="memory",
            secret_ref=reference,
        )
    )
    if also_bind_sink:
        planning.registry.register_binding(
            BindingDescriptor(
                binding="out",
                provider="memory",
                secret_ref=reference,
            )
        )
    try:
        report = SimplePipeline.run(
            profile="development", runtime=runtime, context=planning
        )
    except PipelineExecutionError as exc:
        if not isinstance(exc.report, PipelineRunReport):
            raise
        report = exc.report
    return runtime, report


def test_managed_secret_resolution_audits_actual_version() -> None:
    provider = _VersionedSecretProvider(
        supports_versions=True, resolved_version="release-42"
    )
    runtime, report = _run_with_secret_version(provider, "current")

    assert report.status is RunStatus.SUCCEEDED
    events = [
        event
        for event in runtime.events.events
        if isinstance(event, SecurityEvent) and event.kind == "secret_resolution"
    ]
    assert len(events) == 1
    assert events[0].metadata == {
        "requested_version": "current",
        "resolved_version": "release-42",
        "cache_hit": False,
    }
    assert "version-test-secret" not in str(events[0].to_dict())


def test_versioned_provider_must_advertise_current_alias_support() -> None:
    provider = _VersionedSecretProvider(
        supports_versions=True,
        resolved_version="release-42",
        supports_aliases=False,
    )

    _runtime, report = _run_with_secret_version(provider, "current")

    assert report.status is RunStatus.FAILED
    assert provider.calls == 0
    assert any(
        "does not support current-version aliases" in (d.message or "")
        for d in report.diagnostics
    )


def test_managed_current_secret_requires_explicit_runtime_authorization() -> None:
    provider = _VersionedSecretProvider(
        supports_versions=True, resolved_version="release-42"
    )
    scope = TrustedExecutionScope(
        principal_id="worker-a",
        principal_kind="workload",
        tenant_id="tenant-a",
        workspace_id="workspace-a",
        environment="production",
        security_domain_id="domain-a",
        resource_owner_id="owner-a",
    )

    runtime, report = _run_with_secret_version(provider, "current", trusted_scope=scope)

    assert report.status is RunStatus.FAILED
    assert provider.calls == 0
    assert runtime.secret_cache.stats()["entries"] == 0
    assert any(diagnostic.code == "PMEXEC403" for diagnostic in report.diagnostics)


def test_managed_late_binding_rechecks_policy_before_cache_reuse() -> None:
    provider = _VersionedSecretProvider(
        supports_versions=True,
        resolved_version="release-42",
        rotate=True,
    )
    scope = TrustedExecutionScope(
        principal_id="worker-a",
        principal_kind="workload",
        tenant_id="tenant-a",
        workspace_id="workspace-a",
        environment="production",
        security_domain_id="domain-a",
        resource_owner_id="owner-a",
    )
    authorizer = _AllowSecretAlias()

    runtime, report = _run_with_secret_version(
        provider,
        "current",
        trusted_scope=scope,
        alias_authorizer=authorizer,
        also_bind_sink=True,
    )

    assert report.status is RunStatus.SUCCEEDED
    assert provider.calls == 2
    assert len(authorizer.contexts) == 2
    assert all(
        context.trusted_scope == scope and context.purpose == "read"
        for context in authorizer.contexts
    )
    assert all(
        context.late_binding_authorized and context.trusted_scope == scope
        for context in provider.contexts
    )
    events = [
        event
        for event in runtime.events.events
        if isinstance(event, SecurityEvent) and event.kind == "secret_resolution"
    ]
    assert [event.metadata["cache_hit"] for event in events] == [False, False]
    assert all(event.metadata["late_binding_authorized"] for event in events)
    assert [event.metadata["resolved_version"] for event in events] == [
        "release-42",
        "release-43",
    ]


def test_managed_secret_policy_is_rechecked_before_unversioned_cache() -> None:
    provider = _VersionedSecretProvider(
        supports_versions=False,
        resolved_version="current",
        supports_aliases=False,
    )
    scope = TrustedExecutionScope(
        principal_id="worker-a",
        principal_kind="workload",
        tenant_id="tenant-a",
        workspace_id="workspace-a",
        environment="production",
        security_domain_id="domain-a",
        resource_owner_id="owner-a",
    )
    authorizer = _AllowSecretAlias()

    runtime, report = _run_with_secret_version(
        provider,
        "current",
        trusted_scope=scope,
        alias_authorizer=authorizer,
        also_bind_sink=True,
    )

    assert report.status is RunStatus.SUCCEEDED
    assert provider.calls == 1
    assert len(authorizer.contexts) == 2
    events = [
        event
        for event in runtime.events.events
        if isinstance(event, SecurityEvent) and event.kind == "secret_resolution"
    ]
    assert [event.metadata["cache_hit"] for event in events] == [False, True]
    assert all(event.metadata["late_binding_authorized"] for event in events)


def test_secret_lease_lifecycle_is_renewed_and_revoked_without_caching() -> None:
    provider = _VersionedSecretProvider(
        supports_versions=False,
        resolved_version="current",
        supports_aliases=False,
        supports_leases=True,
        supports_renewal=True,
        supports_revocation=True,
        lease_ttl=0.12,
    )

    runtime, report = _run_with_secret_version(
        provider, "current", also_bind_sink=True, io_delay=0.25
    )

    assert report.status is RunStatus.SUCCEEDED
    assert provider.calls == 0
    assert provider.lease_calls == 2
    assert provider.renewal_calls >= 1
    assert provider.revocation_calls == 2
    assert runtime.secret_cache.stats()["entries"] == 0
    assert provider.active_lease_count == 0
    events = [
        event
        for event in runtime.events.events
        if isinstance(event, SecurityEvent) and event.kind == "secret_resolution"
    ]
    assert len(events) == 2
    assert all(event.metadata["leased"] is True for event in events)
    assert all(event.metadata["resolved_version"] is None for event in events)


def test_secret_leased_late_binding_records_rotated_versions() -> None:
    provider = _VersionedSecretProvider(
        supports_versions=True,
        resolved_version="release-42",
        rotate=True,
        supports_leases=True,
        supports_renewal=True,
        supports_revocation=True,
    )
    scope = TrustedExecutionScope(
        principal_id="worker-a",
        principal_kind="workload",
        tenant_id="tenant-a",
        workspace_id="workspace-a",
        environment="production",
        security_domain_id="domain-a",
        resource_owner_id="owner-a",
    )
    authorizer = _AllowSecretAlias()

    runtime, report = _run_with_secret_version(
        provider,
        "current",
        trusted_scope=scope,
        alias_authorizer=authorizer,
        also_bind_sink=True,
    )

    assert report.status is RunStatus.SUCCEEDED
    assert provider.lease_calls == 2
    assert provider.revocation_calls == 2
    assert len(authorizer.contexts) == 2
    assert all(context.late_binding_authorized for context in provider.contexts)
    events = [
        event
        for event in runtime.events.events
        if isinstance(event, SecurityEvent) and event.kind == "secret_resolution"
    ]
    assert [event.metadata["resolved_version"] for event in events] == [
        "release-42",
        "release-43",
    ]
    assert all(event.metadata["leased"] is True for event in events)
    assert "version-test-secret" not in str([event.to_dict() for event in events])


def test_secret_lease_capability_without_renewal_method_fails_closed() -> None:
    provider = _VersionedSecretProvider(
        supports_versions=False,
        resolved_version="current",
        supports_leases=True,
        supports_renewal=True,
    )
    object.__setattr__(provider, "renew_lease", None)

    _runtime, report = _run_with_secret_version(provider, "current")

    assert report.status is RunStatus.FAILED
    assert provider.lease_calls == 0
    assert provider.calls == 0
    assert any(item.code == "PMEXEC404" for item in report.diagnostics)


def test_secret_lease_honors_exact_version_and_audits_it() -> None:
    provider = _VersionedSecretProvider(
        supports_versions=True,
        resolved_version="release-41",
        supports_leases=True,
        supports_renewal=True,
        supports_revocation=True,
    )

    runtime, report = _run_with_secret_version(provider, "release-41")

    assert report.status is RunStatus.SUCCEEDED
    assert provider.lease_calls == 1
    assert provider.revocation_calls == 1
    event = next(
        event
        for event in runtime.events.events
        if isinstance(event, SecurityEvent) and event.kind == "secret_resolution"
    )
    assert event.metadata["requested_version"] == "release-41"
    assert event.metadata["resolved_version"] == "release-41"
    assert event.metadata["leased"] is True


def test_secret_lease_expiry_cancels_io_and_revokes() -> None:
    provider = _VersionedSecretProvider(
        supports_versions=False,
        resolved_version="current",
        supports_aliases=False,
        supports_leases=True,
        supports_revocation=True,
        lease_ttl=0.06,
    )

    _runtime, report = _run_with_secret_version(provider, "current", io_delay=0.15)

    assert report.status is RunStatus.FAILED
    assert provider.lease_calls == 1
    assert provider.renewal_calls == 0
    assert provider.revocation_calls == 1
    assert any(item.code == "PMEXEC405" for item in report.diagnostics)


def test_secret_lease_renewal_outage_cancels_without_secret_leak() -> None:
    provider = _VersionedSecretProvider(
        supports_versions=False,
        resolved_version="current",
        supports_aliases=False,
        supports_leases=True,
        supports_renewal=True,
        supports_revocation=True,
        lease_ttl=0.12,
        fail_renewal=True,
    )

    runtime, report = _run_with_secret_version(provider, "current", io_delay=0.25)

    assert report.status is RunStatus.FAILED
    assert provider.renewal_calls == 1
    assert provider.revocation_calls == 1
    assert any(item.code == "PMEXEC405" for item in report.diagnostics)
    assert "version-test-secret" not in str(report.to_dict())
    assert all(
        "version-test-secret" not in str(event.to_dict())
        for event in runtime.events.events
        if isinstance(event, SecurityEvent)
    )


def test_secret_lease_revocation_failure_is_reported_as_cleanup_obligation() -> None:
    provider = _VersionedSecretProvider(
        supports_versions=False,
        resolved_version="current",
        supports_aliases=False,
        supports_leases=True,
        supports_revocation=True,
        fail_revocation=True,
    )

    runtime, report = _run_with_secret_version(provider, "current")

    assert report.status is RunStatus.FAILED
    assert provider.revocation_calls == 1
    assert any(item.code == "PMEXEC406" for item in report.diagnostics)
    assert report.metadata["etlantic.cleanup_obligations"] == [
        {
            "status": "unknown",
            "kind": "secret_lease_revocation",
            "provider": "versioned-test",
            "secret_identity": "secret:versioned-test/warehouse#password@current?purpose=read",
            "code": "PMEXEC406",
        }
    ]
    assert "version-test-secret" not in str(report.to_dict())
    assert any(
        isinstance(event, SecurityEvent)
        and event.kind == "secret_lease_revocation"
        and event.outcome == "failure"
        for event in runtime.events.events
    )


@pytest.mark.parametrize(
    ("supports_versions", "resolved_version", "expected_calls", "reason"),
    [
        (False, "release-42", 0, "does not support exact version selection"),
        (True, "release-42", 1, "did not return the requested exact version"),
    ],
)
def test_exact_secret_version_fails_closed(
    supports_versions: bool,
    resolved_version: str,
    expected_calls: int,
    reason: str,
) -> None:
    provider = _VersionedSecretProvider(
        supports_versions=supports_versions,
        resolved_version=resolved_version,
    )
    runtime, report = _run_with_secret_version(provider, "release-41")

    assert report.status is RunStatus.FAILED
    assert provider.calls == expected_calls
    assert runtime.secret_cache.stats()["entries"] == 0
    assert any(
        reason in (diagnostic.message or "") for diagnostic in report.diagnostics
    )


def test_run_selection_until_excludes_sink() -> None:
    runtime = PipelineRuntime()
    runtime.memory.seed("rows", [Row(id=1, name="a")])
    report = SimplePipeline.run(
        profile="development",
        runtime=runtime,
        request=RunRequest(selection=RunSelection.until("normalized")),
    )
    assert report.status is RunStatus.SUCCEEDED
    names = {s.step_name for s in report.steps}
    assert "out" not in names
    assert "normalized" in names


def test_lineage_on_report() -> None:
    runtime = PipelineRuntime()
    runtime.memory.seed("rows", [Row(id=1, name="a")])
    report = SimplePipeline.run(profile="development", runtime=runtime)
    assert report.lineage
    assert any("normalized" in edge["to"] for edge in report.lineage)


def test_resource_injection_and_cleanup() -> None:
    cleaned: list[str] = []

    class Counter(Transformation):
        rows: Input[Row]
        result: Output[Row]

    @Counter.implementation("local")
    def counter_local(
        rows: list[Row],
        db: Annotated[str, Inject("db")],
    ) -> list[Row]:
        assert db == "ok"
        return rows

    class InjectPipeline(Pipeline):
        raw: Extract[Row] = Extract(asset="rows")
        counted = Counter.step(rows=raw)
        out: Load[Row] = Load(input=counted.result, asset="out")

    async def provide_db(_ctx):

        @asynccontextmanager
        async def cm():
            yield "ok"
            cleaned.append("done")

        return cm()

    runtime = PipelineRuntime()
    runtime.override_resource("db", provide_db)
    runtime.memory.seed("rows", [Row(id=1, name="a")])
    report = InjectPipeline.run(profile="development", runtime=runtime)
    assert report.status is RunStatus.SUCCEEDED
    assert cleaned == ["done"]


def test_continue_failure_action_soft_skips_step() -> None:
    class Boom(Transformation):
        rows: Input[Row]
        result: Output[Row]

    @Boom.implementation("local")
    def boom_local(rows: list[Row]) -> list[Row]:
        raise RuntimeError("boom")

    class BoomPipeline(Pipeline):
        raw: Extract[Row] = Extract(asset="rows")
        step = Boom.step(rows=raw)
        out: Load[Row] = Load(input=step.result, asset="out")

    runtime = PipelineRuntime()
    runtime.callbacks.on_step_failed(lambda _ctx: FailureAction.CONTINUE)
    runtime.memory.seed("rows", [Row(id=1, name="a")])
    report = BoomPipeline.run(profile="development", runtime=runtime)
    step = next(s for s in report.steps if s.step_name == "step")
    assert step.status.value == "skipped"
    assert report.status is RunStatus.PARTIAL
    assert any(d.code == "PMEXEC301" for d in report.diagnostics)


def test_schema_drift_policy_blocks_breaking_changes() -> None:
    declared = normalize_schema_from_model(Row)
    previous = SchemaObservation(subject_id="raw", schema=declared)
    current = SchemaObservation(
        subject_id="raw",
        schema=normalize_schema_from_fields(
            [
                {"name": "id", "logical_type": "integer"},
                {"name": "name", "logical_type": "string"},
                {"name": "extra", "logical_type": "string"},
            ],
            identity="observed:raw",
        ),
    )
    decision = evaluate_drift(
        subject_id="raw",
        declared=declared,
        previous=previous,
        current=current,
        policy=SchemaDriftPolicy(default_action=DriftAction.BLOCK),
        profile_name="development",
    )
    assert decision.action is DriftAction.BLOCK
    assert decision.change_count >= 1


def test_middleware_order_observable() -> None:
    order: list[str] = []

    async def mw_a(ctx, call_next):
        order.append("a-before")
        result = await call_next()
        order.append("a-after")
        return result

    async def mw_b(ctx, call_next):
        order.append("b-before")
        result = await call_next()
        order.append("b-after")
        return result

    runtime = PipelineRuntime()
    runtime.add_run_middleware(mw_a, name="a")
    runtime.add_run_middleware(mw_b, name="b")
    runtime.memory.seed("rows", [Row(id=1, name="a")])
    SimplePipeline.run(profile="development", runtime=runtime)
    assert order == ["a-before", "b-before", "b-after", "a-after"]


def test_redact_message_in_report() -> None:
    from etlantic.runtime.logging import redact_message, redact_value

    assert "password=***" in redact_message("failed password=hunter2 for user")
    assert "hunter2" not in redact_message("token=hunter2")
    bearer = redact_message("Authorization: Bearer abc123token")
    assert "abc123token" not in bearer
    assert "Bearer ***" in bearer
    json_msg = redact_message('{"password": "hunter2", "user": "ada"}')
    assert "hunter2" not in json_msg
    assert '"password": "***"' in json_msg
    mongo = redact_message("mongodb://user:pass@host/db")
    assert "pass@" not in mongo
    assert "***@" in mongo
    assert "user:pass@" not in mongo
    redis = redact_message("redis://:s3cret@localhost:6379/0")
    assert "s3cret" not in redis
    https = redact_message("https://user:basicpass@api.example/v1")
    assert "basicpass" not in https
    assert "***@" in https
    assert "user:basicpass@" not in https
    assert redact_value({"error": "password=hunter2", "ok": 1}) == {
        "error": "password=***",
        "ok": 1,
    }
    assert redact_value({"passwd": "x", "pwd": "y", "aws_secret_access_key": "z"}) == {
        "passwd": "***",
        "pwd": "***",
        "aws_secret_access_key": "***",
    }


def test_log_record_serialization_redacts_mutated_extras() -> None:
    import json

    from etlantic.runtime.logging import LogRecord

    sentinel = "late-added-private-value"
    record = LogRecord(level="info", message="finished safely")
    record.extras["password"] = sentinel
    record.extras["nested"] = {
        "safe": "kept",
        "api_key": sentinel,
        "details": [f"Authorization: Bearer {sentinel}", f"token={sentinel}"],
    }

    serialized = record.to_dict()
    payload = json.dumps(serialized)

    assert sentinel not in payload
    assert serialized["extras"]["password"] == "***"
    assert serialized["extras"]["nested"]["api_key"] == "***"
    assert serialized["extras"]["nested"]["details"] == [
        "Bearer ***",
        "token=***",
    ]
    assert serialized["extras"]["nested"]["safe"] == "kept"


def test_continue_allows_independent_sibling() -> None:
    class Boom(Transformation):
        rows: Input[Row]
        result: Output[Row]

    class Ok(Transformation):
        rows: Input[Row]
        result: Output[Row]

    @Boom.implementation("local")
    def boom_local(rows: list[Row]) -> list[Row]:
        raise RuntimeError("boom")

    @Ok.implementation("local")
    def ok_local(rows: list[Row]) -> list[Row]:
        return list(rows)

    class BranchPipeline(Pipeline):
        raw: Extract[Row] = Extract(asset="rows")
        boom = Boom.step(rows=raw)
        ok = Ok.step(rows=raw)
        out_boom: Load[Row] = Load(input=boom.result, asset="out_boom")
        out_ok: Load[Row] = Load(input=ok.result, asset="out_ok")

    runtime = PipelineRuntime()
    runtime.callbacks.on_step_failed(lambda _ctx: FailureAction.CONTINUE)
    runtime.memory.seed("rows", [Row(id=1, name="a")])
    report = BranchPipeline.run(profile="development", runtime=runtime)
    by_name = {s.step_name: s for s in report.steps}
    assert by_name["boom"].status.value == "skipped"
    assert by_name["ok"].status.value == "succeeded"
    assert by_name["out_ok"].status.value == "succeeded"
    assert report.status is RunStatus.PARTIAL


def test_skip_abandons_dependents_not_siblings() -> None:
    class Boom(Transformation):
        rows: Input[Row]
        result: Output[Row]

    class Ok(Transformation):
        rows: Input[Row]
        result: Output[Row]

    @Boom.implementation("local")
    def boom_local(rows: list[Row]) -> list[Row]:
        raise RuntimeError("boom")

    @Ok.implementation("local")
    def ok_local(rows: list[Row]) -> list[Row]:
        return list(rows)

    class BranchPipeline(Pipeline):
        raw: Extract[Row] = Extract(asset="rows")
        boom = Boom.step(rows=raw)
        ok = Ok.step(rows=raw)
        out_boom: Load[Row] = Load(input=boom.result, asset="out_boom")
        out_ok: Load[Row] = Load(input=ok.result, asset="out_ok")

    runtime = PipelineRuntime()
    runtime.callbacks.on_step_failed(lambda _ctx: FailureAction.SKIP)
    runtime.memory.seed("rows", [Row(id=1, name="a")])
    report = BranchPipeline.run(profile="development", runtime=runtime)
    by_name = {s.step_name: s for s in report.steps}
    assert by_name["boom"].status.value == "skipped"
    assert by_name["out_boom"].status.value == "abandoned"
    assert by_name["ok"].status.value == "succeeded"
    assert by_name["out_ok"].status.value == "succeeded"
