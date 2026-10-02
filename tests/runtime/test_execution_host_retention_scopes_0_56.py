"""Bounded and fair artifact-retention scope discovery for execution hosts."""

from __future__ import annotations

from etlantic.control_plane import (
    ControlPlaneContext,
    EnvironmentRef,
    ExecutionScopePage,
    MemoryDurableWorkStore,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic.runtime.execution_host import ExecutionHost
from etlantic.runtime.managed_execution import ManagedExecutionAdapter


def _ctx(
    *, principal: str = "worker", domain: str = "worker-domain"
) -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal(principal, issuer="tests"),
        tenant=TenantRef("tenant-a"),
        workspace=WorkspaceRef("tenant-a", "workspace-a"),
        environment=EnvironmentRef("development"),
        security_domain=SecurityDomain(domain),
    )


class _CountingStore(MemoryDurableWorkStore):
    def __init__(self) -> None:
        super().__init__()
        self.scope_pages: list[tuple[str | None, int]] = []

    def list_execution_scopes(
        self,
        ctx: ControlPlaneContext,
        *,
        after_submission_id: str | None = None,
        limit: int = 100,
    ) -> ExecutionScopePage:
        self.scope_pages.append((after_submission_id, limit))
        return super().list_execution_scopes(
            ctx, after_submission_id=after_submission_id, limit=limit
        )


class _RecordingRunner:
    run_artifact_retention_enabled = True

    def __init__(self) -> None:
        self.cleaned: list[ControlPlaneContext] = []

    def artifact_retention_scope_key(self, ctx: ControlPlaneContext) -> tuple[str, ...]:
        return (
            ctx.tenant.tenant_id,
            ctx.workspace.workspace_id,
            ctx.security_domain.domain_id,
        )

    def cleanup_expired_run_artifacts(self, ctx: ControlPlaneContext) -> None:
        self.cleaned.append(ctx)

    def __call__(self, *_args: object, **_kwargs: object) -> None:
        return None


def _accept_scope(
    store: MemoryDurableWorkStore,
    base: ControlPlaneContext,
    *,
    index: int,
    domain: str,
) -> None:
    accepted = _ctx(principal=f"accepted-{index:02}", domain=domain)
    submission, _created = store.accept(
        accepted,
        idempotency_key=f"retention-{index:02}",
        operation="run.submit",
        plan_fingerprint="plan",
        submission_id=f"submission-{index:02}",
    )
    for item in store.pending_outbox(base):
        if item.submission_id == submission.submission_id:
            store.mark_published(base, item.outbox_id)


def test_disabled_managed_retention_skips_scope_discovery() -> None:
    durable = _CountingStore()
    host = ExecutionHost(durable, runner=ManagedExecutionAdapter())

    assert host.tick(_ctx()) == 0
    assert durable.scope_pages == []


def test_retention_pages_are_bounded_and_rotate_fairly() -> None:
    base = _ctx()
    durable = _CountingStore()
    for index in range(25):
        _accept_scope(durable, base, index=index, domain=f"domain-{index:02}")
    runner = _RecordingRunner()
    host = ExecutionHost(durable, runner=runner)

    host.tick(base)
    assert len(runner.cleaned) == 21  # worker scope plus 20 accepted scopes
    assert durable.scope_pages == [(None, 20)]

    host.tick(base)
    assert len(runner.cleaned) == 26
    assert durable.scope_pages == [(None, 20), ("submission-19", 20)]
    assert {ctx.principal.subject for ctx in runner.cleaned} == {
        "worker",
        *(f"accepted-{index:02}" for index in range(25)),
    }


def test_retention_deduplicates_storage_partitions_across_pages() -> None:
    base = _ctx()
    durable = _CountingStore()
    for index in range(25):
        _accept_scope(durable, base, index=index, domain="shared-domain")
    runner = _RecordingRunner()
    host = ExecutionHost(durable, runner=runner)

    for _ in range(2):
        host.tick(base)

    assert [ctx.security_domain.domain_id for ctx in runner.cleaned].count(
        "shared-domain"
    ) == 1
    assert [ctx.security_domain.domain_id for ctx in runner.cleaned].count(
        "worker-domain"
    ) == 1
    assert durable.scope_pages == [(None, 20), ("submission-19", 20)]
