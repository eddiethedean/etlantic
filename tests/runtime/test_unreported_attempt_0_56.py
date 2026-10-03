"""Unreported managed attempts require durable effect reconciliation (#217)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest

from etlantic import Data, Extract, Load, Pipeline
from etlantic.authoring import definition_from_pipeline
from etlantic.authoring.serialize import pipeline_to_dict
from etlantic.control_plane import (
    ControlPlaneContext,
    ControlPlaneError,
    DurableWorkStore,
    EnvironmentRef,
    MemoryAuthorizer,
    MemoryDefinitionRepository,
    MemoryDurableWorkStore,
    MemorySubmissionStore,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic.profile import Profile
from etlantic.registry import BindingDescriptor, PlanningContext
from etlantic.reports.model import PipelineRunReport
from etlantic.runtime.execution_host import ExecutionHost
from etlantic.runtime.managed_errors import ExecutionRejected
from etlantic.runtime.managed_execution import ManagedExecutionAdapter
from etlantic.runtime.state import RunStatus
from etlantic.service import ManagedApplicationService


class Row(Data):
    id: int


class FilePipeline(Pipeline):
    raw: Extract[Row] = Extract(asset="file-in")
    output: Load[Row] = Load(input=raw, asset="file-out")


class CrashBeforeReport:
    """Discard advisory reports and die after real target publication."""

    def get(self, _run_id: str) -> None:
        return None

    def put(self, report: PipelineRunReport) -> None:
        if report.status is RunStatus.SUCCEEDED:
            raise SystemExit("worker died before result publication")


@pytest.mark.parametrize(
    "store_kind", ["memory", pytest.param("sqlmodel", marks=pytest.mark.sqlmodel)]
)
@pytest.mark.parametrize("write_mode", ["append", "skip_if_exists"])
@pytest.mark.parametrize("target_committed", [True, False])
def test_unreported_attempt_blocks_retry_until_provider_reconciliation(
    tmp_path: Path, store_kind: str, write_mode: str, target_committed: bool
) -> None:
    def open_store() -> DurableWorkStore:
        if store_kind == "memory":
            return MemoryDurableWorkStore()
        pytest.importorskip("etlantic_sqlmodel")
        from etlantic_sqlmodel.control_plane import (
            SQLModelDurableWorkStore,
            create_sqlite_engine,
        )
        from etlantic_sqlmodel.migrations import apply_migrations

        engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'durable.db'}")
        apply_migrations(engine)
        return cast(DurableWorkStore, SQLModelDurableWorkStore(engine))

    def restart(store: DurableWorkStore) -> DurableWorkStore:
        if isinstance(store, MemoryDurableWorkStore):
            restored = MemoryDurableWorkStore()
            restored.load(store.dump())
            return restored
        return open_store()

    ctx = ControlPlaneContext(
        principal=Principal("alice"),
        tenant=TenantRef("tenant"),
        workspace=WorkspaceRef("tenant", "workspace"),
        environment=EnvironmentRef("development"),
        security_domain=SecurityDomain("default"),
    )
    authz = MemoryAuthorizer()
    for action in (
        "definition.write",
        "run.submit",
        "run.read",
        "run.actions",
        "run.retry",
        "run.rerun",
    ):
        authz.grant(ctx, action)
    source, target = tmp_path / "source.json", tmp_path / "target.csv"
    source.write_text('[{"id": 7}]', encoding="utf-8")

    def planning(_ctx: ControlPlaneContext, profile: Profile) -> PlanningContext:
        context = PlanningContext.create(profile=profile)
        context.registry.register_binding(
            BindingDescriptor(
                binding="file-in", provider="json", location=str(source), kind="source"
            )
        )
        context.registry.register_binding(
            BindingDescriptor(
                binding="file-out",
                provider="csv",
                location=str(target),
                kind="sink",
                mode=write_mode,
                metadata={"write_mode": write_mode},
            )
        )
        return context

    durable = open_store()
    service = ManagedApplicationService(
        authorizer=authz,
        definitions=MemoryDefinitionRepository(),
        submissions=MemorySubmissionStore(),
        durable_work=durable,
        planning_context_factory=planning,
        profile="development",
        report_root=tmp_path / "reports",
    )
    service.register_definition(
        ctx, "file", pipeline_to_dict(definition_from_pipeline(FilePipeline))
    )
    parent = service.submit_run(ctx, "file", idempotency_key="crash-parent")
    run_id = str(parent.resource_id)

    def die_before_execution(*_args: Any, **_kwargs: Any) -> None:
        raise SystemExit("worker died before execution")

    runner = ManagedExecutionAdapter(
        report_store_factory=lambda _ctx: CrashBeforeReport()
    )
    with pytest.raises(SystemExit, match="worker died"):
        ExecutionHost(
            durable,
            owner_id="dead-worker",
            runner=runner if target_committed else die_before_execution,
        ).tick(ctx)
    assert target.exists() is target_committed
    if target_committed:
        assert target.read_text().splitlines() == ["id", "7"]
    assert durable.get_latest_result_publication(ctx, parent.submission_id) is None
    prior = durable.list_attempts(ctx, parent.submission_id)[-1]
    durable.release_lease(
        ctx,
        parent.submission_id,
        owner_id="dead-worker",
        fencing_token=prior.fencing_token,
    )
    durable = restart(durable)
    service.durable_work = durable
    recovery = ExecutionHost(
        durable,
        owner_id="recovery-worker",
        runner=ManagedExecutionAdapter(report_root=tmp_path / "reports"),
    )
    assert recovery.tick(ctx) == 1
    assert durable.list_attempts(ctx, parent.submission_id)[-1].status == "lost"
    effect = durable.get_effect(ctx, f"{parent.submission_id}:execution")
    assert effect.status == "unknown"
    assert effect.authoritative
    durable = restart(durable)
    service.durable_work = durable
    assert durable.get_effect(ctx, effect.effect_id).status == "unknown"
    assert service.get_run_actions(ctx, run_id)["actions"][1] == {
        "name": "retry",
        "allowed": False,
        "reason": "effect_requires_reconciliation",
    }
    with pytest.raises(ControlPlaneError, match="effect is reconciled"):
        service.retry_run(ctx, run_id, idempotency_key="unsafe-retry")
    with pytest.raises(ControlPlaneError, match="effect is reconciled"):
        service.rerun_run(ctx, run_id, idempotency_key="unsafe-rerun")
    assert not durable.pending_outbox(ctx)

    # Provider capability or idempotency alone cannot prove a new child safe.
    for safe_status in ("none", "not_committed", "failed"):
        with pytest.raises(ControlPlaneError, match="reconciliation"):
            durable.record_effect(
                ctx,
                replace(
                    effect,
                    status=safe_status,
                    idempotency_evidence="idempotent provider",
                ),
            )
    reconciled = replace(
        effect,
        status="committed" if target_committed else "not_committed",
        reconciliation_evidence="provider target probe confirms publication"
        if target_committed
        else "provider target probe confirms no publication",
    )
    durable.record_effect(ctx, reconciled)
    if target_committed:
        with pytest.raises(ControlPlaneError, match="effect is reconciled"):
            service.retry_run(ctx, run_id, idempotency_key="committed-retry")
        # An intentional rerun remains a separate, explicit lifecycle command.
        child = service.rerun_run(ctx, run_id, idempotency_key="intentional-rerun")
    else:
        child = service.retry_run(ctx, run_id, idempotency_key="reconciled-retry")
    assert (
        ExecutionHost(
            durable,
            owner_id="child-worker",
            runner=ManagedExecutionAdapter(report_root=tmp_path / "reports"),
        ).tick(ctx)
        == 1
    )
    assert service.get_run_status(ctx, str(child.resource_id))["status"] == "completed"
    expected = (
        ["id", "7", "7"] if target_committed and write_mode == "append" else ["id", "7"]
    )
    assert target.read_text().splitlines() == expected


def test_recovery_rejection_cannot_erase_prior_execution_uncertainty() -> None:
    ctx = ControlPlaneContext(
        principal=Principal("worker"),
        tenant=TenantRef("tenant"),
        workspace=WorkspaceRef("tenant", "workspace"),
        environment=EnvironmentRef("development"),
        security_domain=SecurityDomain("default"),
    )
    durable = MemoryDurableWorkStore()
    parent, _ = durable.accept(
        ctx, idempotency_key="crash", operation="run.submit", plan_fingerprint="plan"
    )
    lease = durable.acquire_lease(
        ctx, parent.submission_id, owner_id="dead-worker", ttl_seconds=60
    )
    durable.start_attempt(
        ctx,
        parent.submission_id,
        owner_id="dead-worker",
        fencing_token=lease.fencing_token,
    )
    durable.release_lease(
        ctx,
        parent.submission_id,
        owner_id="dead-worker",
        fencing_token=lease.fencing_token,
    )

    def reject(*_args: Any, **_kwargs: Any) -> None:
        raise ExecutionRejected("recovery cannot validate the accepted envelope")

    assert ExecutionHost(durable, owner_id="recovery", runner=reject).tick(ctx) == 1
    assert (
        durable.get_effect(ctx, f"{parent.submission_id}:execution").status == "unknown"
    )
    assert durable.list_attempts(ctx, parent.submission_id)[-1].status == "lost"
