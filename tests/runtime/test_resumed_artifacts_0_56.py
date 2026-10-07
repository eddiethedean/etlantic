"""Managed artifact workspace recovery and retention behavior."""

from __future__ import annotations

import json
import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from etlantic import Data, Extract, Load, Pipeline
from etlantic.authoring import definition_from_pipeline
from etlantic.authoring.serialize import pipeline_to_dict
from etlantic.control_plane import (
    ControlPlaneContext,
    EnvironmentRef,
    ExecutionEnvelope,
    MemoryAuthorizer,
    MemoryDefinitionRepository,
    MemoryDurableWorkStore,
    MemorySubmissionStore,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic.control_plane.errors import ControlPlaneError
from etlantic.profile import Profile
from etlantic.registry import BindingDescriptor, PlanningContext
from etlantic.reports.file_store import FileReportStore
from etlantic.reports.model import PipelineRunReport
from etlantic.reports.retention import (
    ARTIFACT_STORAGE_RUN_ID_KEY,
    RUN_ARTIFACT_RETENTION_STATE_KEY,
)
from etlantic.reports.store import ReportStore
from etlantic.runtime.artifact_retention import cleanup_expired_run_artifacts
from etlantic.runtime.artifacts import artifact_storage_path
from etlantic.runtime.execution_host import ExecutionHost
from etlantic.runtime.managed_errors import ExecutionRejected
from etlantic.runtime.managed_execution import (
    ManagedExecutionAdapter,
    managed_artifact_workspace,
    managed_report_store,
)
from etlantic.runtime.request import MaterializationPolicy, RunRequest
from etlantic.service import ManagedApplicationService


class Row(Data):
    id: int


class ArtifactPipeline(Pipeline):
    source: Extract[Row] = Extract(asset="input")
    output: Load[Row] = Load(input=source, asset="output")


class SourceOnlyPipeline(Pipeline):
    source: Extract[Row] = Extract(asset="input")


@pytest.mark.parametrize("generations", [1, 2])
def test_fallback_only_rerun_artifacts_expire_without_published_report_rows(
    tmp_path: Path, generations: int
) -> None:
    ctx, service, durable, adapter, child_run_id, _, report, listed, paths = (
        _execute_shared_workspace_run(tmp_path, generations, publication_fallback=True)
    )
    root = tmp_path / "artifacts"
    report_root = tmp_path / "reports"
    store = managed_report_store(ctx, report_root=report_root)
    assert store.list() == []
    first = cleanup_expired_run_artifacts(
        ctx, report_store=store, artifact_root=root, retention_seconds=60
    )
    assert first.deleted_artifacts == 0 and all(path.is_file() for path in paths)
    now = datetime.now(UTC) + timedelta(days=2)
    expired = cleanup_expired_run_artifacts(
        ctx,
        report_store=store,
        artifact_root=root,
        retention_seconds=60,
        now=now,
        limit=1,
    )
    assert expired.processed_reports == 0
    assert expired.deleted_artifacts == len(paths)
    assert not expired.remaining_candidates and not any(path.exists() for path in paths)
    assert (
        service.get_run_report(ctx, child_run_id)["artifacts"][0]["status"] == "expired"
    )
    with pytest.raises(ControlPlaneError) as failure:
        service.get_run_artifact_content(ctx, child_run_id, listed[0]["artifact_id"])
    assert failure.value.status == 404
    # Missing report rows and restarts cannot cause completed ownership work
    # to consume every later cleanup batch, or revive the fallback reference.
    repeated = cleanup_expired_run_artifacts(
        ctx,
        report_store=managed_report_store(ctx, report_root=report_root),
        artifact_root=root,
        retention_seconds=60,
        now=now,
        limit=1,
    )
    assert repeated.deleted_artifacts == 0 and not repeated.remaining_candidates
    publication = durable.get_latest_result_publication(
        ctx,
        str(report["metadata"]["etlantic.control_plane.execution"]["submission_id"]),
    )
    assert publication is not None
    adapter.report_store_factory = None
    assert adapter.publish_result_publication(
        ctx,
        publication,
        submission_reader=lambda submission_id: durable.get_submission(
            ctx, submission_id
        ),
    )
    assert (
        service.get_run_report(ctx, child_run_id)["artifacts"][0]["status"] == "expired"
    )


def test_pending_publication_skips_busy_workspace_and_executes_independent_run(
    tmp_path: Path,
) -> None:
    from threading import Event, Thread

    from etlantic.control_plane.durable_models import (
        ResultPublicationRecord,
    )
    from etlantic.runtime.artifact_coordination import artifact_workspace_lock

    ctx, service, durable, _, _, storage_id, report, _, _ = (
        _execute_shared_workspace_run(
            tmp_path, generations=1, publication_fallback=True
        )
    )
    parent_submission = str(
        report["metadata"]["etlantic.control_plane.execution"]["submission_id"]
    )
    assert durable.pending_result_publications(ctx, limit=20)
    ready = service.submit_run(
        ctx,
        "pipe",
        idempotency_key="independent",
        request=RunRequest(materialization=MaterializationPolicy.DURABLE),
    )
    assert ready.resource_id is not None
    ready_submission = ready.submission_id
    finished = Event()
    results: list[int] = []
    errors: list[Exception] = []
    skipped: list[bool] = []

    class ObservedAdapter(ManagedExecutionAdapter):
        def publish_result_publication(
            self,
            ctx: ControlPlaneContext,
            record: ResultPublicationRecord,
            *,
            submission_reader: Any = None,
        ) -> bool:
            published = super().publish_result_publication(
                ctx, record, submission_reader=submission_reader
            )
            skipped.append(not published)
            return published

    runner = ObservedAdapter(
        report_root=tmp_path / "reports", artifact_root=tmp_path / "artifacts"
    )
    host = ExecutionHost(durable, owner_id="other-worker", runner=runner)

    def tick() -> None:
        try:
            results.append(host.tick(ctx))
        except Exception as exc:
            errors.append(exc)
        finally:
            finished.set()

    workspace = managed_artifact_workspace(
        ctx, storage_id, artifact_root=tmp_path / "artifacts"
    )
    worker = Thread(target=tick, daemon=True)
    try:
        with artifact_workspace_lock(workspace):
            worker.start()
            assert finished.wait(3)
            assert not errors and results == [1] and skipped == [True]
            assert durable.get_submission(ctx, ready_submission).status == "completed"
            publication = durable.get_latest_result_publication(ctx, parent_submission)
            assert publication is not None and publication.published_at is None
    finally:
        worker.join(10)
    assert not worker.is_alive()
    assert host.tick(ctx) == 0
    publication = durable.get_latest_result_publication(ctx, parent_submission)
    assert publication is not None and publication.published_at is not None
    assert len(durable.list_attempts(ctx, ready_submission)) == 1


@pytest.mark.parametrize("stop_reason", ["cancel", "cancel_recovered", "lease_loss"])
def test_workspace_wait_stops_before_execution_on_cancel_or_lease_loss(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stop_reason: str
) -> None:
    from collections.abc import Generator
    from contextlib import contextmanager
    from threading import Event, Thread
    from typing import NoReturn

    import etlantic.runtime.managed_execution as managed
    from etlantic.runtime.artifact_coordination import artifact_workspace_lock

    ctx, service, durable, _, _, storage_id, _, _, paths = (
        _execute_shared_workspace_run(
            tmp_path, generations=1, publication_fallback=False
        )
    )
    waiting = _accept_artifact_child(
        ctx,
        service,
        durable,
        parent_run_id=storage_id,
        artifact_parent_run_id=storage_id,
        idempotency_key="waiting",
    )
    assert waiting.resource_id is not None
    if stop_reason == "cancel_recovered":
        lease = durable.acquire_lease(
            ctx, waiting.submission_id, owner_id="prior", ttl_seconds=3
        )
        durable.start_attempt(
            ctx,
            waiting.submission_id,
            owner_id="prior",
            fencing_token=lease.fencing_token,
        )
        durable.release_lease(
            ctx,
            waiting.submission_id,
            owner_id="prior",
            fencing_token=lease.fencing_token,
        )
    independent = (
        service.submit_run(
            ctx,
            "pipe",
            idempotency_key="independent-after-cancel",
            request=RunRequest(materialization=MaterializationPolicy.DURABLE),
        )
        if stop_reason != "lease_loss"
        else None
    )
    if stop_reason == "lease_loss":

        def lose_lease(*_args: object, **_kwargs: object) -> NoReturn:
            raise OSError("Worker cannot prove lease ownership")

        monkeypatch.setattr(durable, "heartbeat", lose_lease)
    entered, finished = Event(), Event()
    events: list[Event] = []
    results: list[int] = []
    failures: list[Exception] = []
    original_lock = managed.artifact_workspace_lock

    @contextmanager
    def observed_lock(
        workspace: Path, *, blocking: bool = True, cancel_event: Event | None = None
    ) -> Generator[bool]:
        if cancel_event is not None:
            events.append(cancel_event)
            entered.set()
        with original_lock(
            workspace, blocking=blocking, cancel_event=cancel_event
        ) as acquired:
            yield acquired

    monkeypatch.setattr(managed, "artifact_workspace_lock", observed_lock)
    host = ExecutionHost(
        durable,
        owner_id="waiting-worker",
        ttl_seconds=3,
        runner=ManagedExecutionAdapter(
            report_root=tmp_path / "reports", artifact_root=tmp_path / "artifacts"
        ),
    )

    def tick() -> None:
        try:
            results.append(host.tick(ctx))
        except Exception as exc:
            failures.append(exc)
        finally:
            finished.set()

    worker = Thread(target=tick, daemon=True)
    workspace = managed_artifact_workspace(
        ctx, storage_id, artifact_root=tmp_path / "artifacts"
    )
    original_bytes = [path.read_bytes() for path in paths]
    try:
        with artifact_workspace_lock(workspace):
            worker.start()
            assert entered.wait(5)
            if stop_reason != "lease_loss":
                durable.cancel_submission(ctx, waiting.submission_id)
            assert events[0].wait(5)
            assert finished.wait(5), (
                "Cancelled/fenced wait must finish before lock release"
            )
            assert not failures
            assert [path.read_bytes() for path in paths] == original_bytes
            assert (
                managed_report_store(ctx, report_root=tmp_path / "reports").get(
                    waiting.resource_id
                )
                is None
            )
            assert (
                durable.get_latest_result_publication(ctx, waiting.submission_id)
                is None
            )
            attempts = durable.list_attempts(ctx, waiting.submission_id)
            if stop_reason == "lease_loss":
                assert results == [1] and attempts[-1].status == "running"
                assert any(
                    item.submission_id == waiting.submission_id
                    for item in durable.pending_outbox(ctx)
                )
            else:
                assert results == [2] and attempts[-1].status == "cancelled"
                assert (
                    durable.get_submission(ctx, waiting.submission_id).status
                    == "cancelled"
                )
                assert not durable.pending_outbox(ctx)
                assert independent is not None
                assert (
                    durable.get_submission(ctx, independent.submission_id).status
                    == "completed"
                )
            if stop_reason == "cancel_recovered":
                assert (
                    durable.get_effect(ctx, f"{waiting.submission_id}:execution").status
                    == "unknown"
                )
            else:
                with pytest.raises(ControlPlaneError) as missing:
                    durable.get_effect(ctx, f"{waiting.submission_id}:execution")
                assert missing.value.status == 404
    finally:
        worker.join(10)
        assert not worker.is_alive()


@pytest.mark.parametrize("has_cleanup_candidate", [False, True])
def test_expired_unpublished_child_cannot_download_retained_shared_bytes(
    tmp_path: Path, has_cleanup_candidate: bool
) -> None:
    ctx, service, durable, adapter, child_run_id, storage_id, report, listed, paths = (
        _execute_shared_workspace_run(
            tmp_path, generations=1, publication_fallback=True
        )
    )
    artifact_root = tmp_path / "artifacts"
    report_root = tmp_path / "reports"
    store = managed_report_store(ctx, report_root=report_root)
    assert store.get(child_run_id) is None
    now = datetime.now(UTC) + timedelta(days=2)
    child = PipelineRunReport.from_dict(report)
    store.put(replace(child, run_id="retained-sibling", ended_at=now))
    if has_cleanup_candidate:
        store.put(replace(child, run_id="expired-sibling"))
    result = cleanup_expired_run_artifacts(
        ctx,
        report_store=store,
        artifact_root=artifact_root,
        retention_seconds=60,
        now=now,
    )
    assert result.deleted_artifacts == 0 and all(path.is_file() for path in paths)

    class UnavailableStore:
        def get(self, _run_id: str) -> PipelineRunReport | None:
            raise OSError("report provider temporarily unavailable")

    service.report_store_factory = lambda _: UnavailableStore()
    assert not service.list_run_artifacts(ctx, child_run_id)[0]["content_available"]
    assert (
        service.get_run_report(ctx, child_run_id)["artifacts"][0]["status"] == "expired"
    )
    with pytest.raises(ControlPlaneError) as failure:
        service.get_run_artifact_content(ctx, child_run_id, listed[0]["artifact_id"])
    assert failure.value.status == 404
    assert report["metadata"][ARTIFACT_STORAGE_RUN_ID_KEY] == storage_id

    # Restoring the provider must also preserve expiry when no report row
    # exists from which reconciliation could recover physical cleanup state.
    publication = durable.get_latest_result_publication(
        ctx,
        str(report["metadata"]["etlantic.control_plane.execution"]["submission_id"]),
    )
    assert publication is not None
    service.report_store_factory = None
    adapter.report_store_factory = None
    adapter.publish_result_publication(
        ctx,
        publication,
        submission_reader=lambda submission_id: durable.get_submission(
            ctx, submission_id
        ),
    )
    restored = managed_report_store(ctx, report_root=report_root)
    reconciled = restored.get(child_run_id)
    assert reconciled is not None and reconciled.artifacts[0].status == "expired"
    assert reconciled.metadata[RUN_ARTIFACT_RETENTION_STATE_KEY] == "pending"
    final = cleanup_expired_run_artifacts(
        ctx,
        report_store=restored,
        artifact_root=artifact_root,
        retention_seconds=60,
        now=now + timedelta(days=1),
    )
    assert final.deleted_artifacts == len(paths)
    assert not any(path.exists() for path in paths)


def _execute_shared_workspace_run(
    tmp_path: Path,
    generations: int,
    publication_fallback: bool,
) -> tuple[
    ControlPlaneContext,
    ManagedApplicationService,
    MemoryDurableWorkStore,
    ManagedExecutionAdapter,
    str,
    str,
    dict[str, Any],
    list[dict[str, Any]],
    list[Path],
]:
    ctx = ControlPlaneContext(
        principal=Principal("artifact-owner"),
        tenant=TenantRef("tenant"),
        workspace=WorkspaceRef("tenant", "workspace"),
        environment=EnvironmentRef("development"),
        security_domain=SecurityDomain("artifacts"),
    )
    auth = MemoryAuthorizer()
    for action in (
        "definition.write",
        "definition.read",
        "definition.validate",
        "definition.plan",
        "run.submit",
        "run.read",
        "run.report",
        "run.rerun",
        "run.artifacts",
        "run.artifact.content",
    ):
        auth.grant(ctx, action)
    durable = MemoryDurableWorkStore()
    source = tmp_path / "input.json"
    source.write_text('[{"id": 7}]', encoding="utf-8")
    artifact_root = tmp_path / "artifacts"
    report_root = tmp_path / "reports"

    def planning(_ctx: ControlPlaneContext, profile: Profile) -> PlanningContext:
        context = PlanningContext.create(profile=profile)
        for binding, provider, path, kind in (
            ("input", "json", source, "source"),
            ("output", "csv", tmp_path / "output.csv", "sink"),
        ):
            context.registry.register_binding(
                BindingDescriptor(
                    binding=binding, provider=provider, location=str(path), kind=kind
                )
            )
        return context

    service = ManagedApplicationService(
        authorizer=auth,
        definitions=MemoryDefinitionRepository(),
        submissions=MemorySubmissionStore(),
        durable_work=durable,
        profile="development",
        planning_context_factory=planning,
        report_root=report_root,
        artifact_root=artifact_root,
    )
    service.register_definition(
        ctx, "pipe", pipeline_to_dict(definition_from_pipeline(ArtifactPipeline))
    )
    parent = service.submit_run(
        ctx,
        "pipe",
        idempotency_key="parent",
        request=RunRequest(materialization=MaterializationPolicy.DURABLE),
    )
    assert parent.resource_id is not None
    storage_id = parent.resource_id

    def fail_before_writes(_worker_ctx: ControlPlaneContext, **_kwargs: Any) -> None:
        raise ExecutionRejected("before any writes")

    child = parent
    for generation in range(generations):
        assert (
            ExecutionHost(
                durable, owner_id=f"failed-{generation}", runner=fail_before_writes
            ).tick(ctx)
            == 1
        )
        child = _accept_artifact_child(
            ctx,
            service,
            durable,
            parent_run_id=parent.resource_id,
            artifact_parent_run_id=storage_id,
            idempotency_key=f"child-{generation}",
        )
        if generation + 1 < generations:
            parent = child
            assert parent.resource_id is not None
    assert child.resource_id is not None

    first_writes: list[PipelineRunReport] = []

    class RecordingStore(FileReportStore):
        def put(self, report: PipelineRunReport) -> None:
            owner_root = (
                managed_artifact_workspace(ctx, storage_id, artifact_root=artifact_root)
                / ".artifact-owners"
            )
            assert any(owner_root.glob("*.json"))
            first_writes.append(report)
            if publication_fallback:
                raise OSError("report provider unavailable")
            super().put(report)

    def report_store(context: ControlPlaneContext) -> FileReportStore:
        ordinary = managed_report_store(context, report_root=report_root)
        return RecordingStore(ordinary.root)

    adapter = ManagedExecutionAdapter(
        report_root=report_root,
        artifact_root=artifact_root,
        report_store_factory=report_store,
    )
    assert ExecutionHost(durable, owner_id="resumed", runner=adapter).tick(ctx) == 1
    assert child.resource_id is not None
    assert first_writes[0].metadata[ARTIFACT_STORAGE_RUN_ID_KEY] == storage_id
    report = service.get_run_report(ctx, child.resource_id)
    assert report["metadata"][ARTIFACT_STORAGE_RUN_ID_KEY] == storage_id
    assert report["run_id"] == child.resource_id
    listed = service.list_run_artifacts(ctx, child.resource_id)
    assert len(listed) == 1 and all(item["content_available"] for item in listed)
    for item in listed:
        content, media_type = service.get_run_artifact_content(
            ctx, child.resource_id, item["artifact_id"]
        )
        assert media_type == "application/json" and json.loads(content) == [{"id": 7}]
    with pytest.raises(ControlPlaneError):
        service.get_run_artifact_content(
            replace(
                ctx,
                tenant=TenantRef("foreign"),
                workspace=WorkspaceRef("foreign", "foreign"),
            ),
            child.resource_id,
            listed[0]["artifact_id"],
        )

    workspace = managed_artifact_workspace(ctx, storage_id, artifact_root=artifact_root)
    paths = [artifact_storage_path(workspace, item["artifact_id"]) for item in listed]
    assert all(path.is_file() for path in paths)
    return (
        ctx,
        service,
        durable,
        adapter,
        child.resource_id,
        storage_id,
        report,
        listed,
        paths,
    )


def _accept_artifact_child(
    ctx: ControlPlaneContext,
    service: ManagedApplicationService,
    durable: MemoryDurableWorkStore,
    *,
    parent_run_id: str,
    artifact_parent_run_id: str,
    idempotency_key: str,
) -> Any:
    """Seed a legacy rerun envelope that shares its parent's artifact workspace."""
    legacy_service: Any = service
    parent_record = legacy_service._authorized_run_record(
        ctx, "run.rerun", parent_run_id
    )
    parent_submission_id = str(parent_record["submission_id"])
    parent = durable.get_submission(ctx, parent_submission_id)
    assert parent.input_snapshot is not None
    envelope = ExecutionEnvelope.from_json(parent.input_snapshot)
    envelope_data = envelope.to_dict()
    evidence_refs = dict(envelope_data.get("evidence_refs") or {})
    evidence_refs.update(
        {
            "command": "rerun",
            "parent_run_id": parent_run_id,
            "parent_submission_id": parent_submission_id,
            "artifact_parent_run_id": artifact_parent_run_id,
        }
    )
    envelope = ExecutionEnvelope.from_dict(
        {**envelope_data, "evidence_refs": evidence_refs}
    )
    return legacy_service._accept_child_run(
        ctx,
        idempotency_key=idempotency_key,
        operation="run.rerun",
        envelope=envelope,
        parent_run_id=parent_run_id,
        parent_submission_id=parent_submission_id,
    )


@pytest.mark.skipif(os.name != "posix", reason="POSIX read-only mode")
def test_non_durable_run_does_not_write_to_artifact_root(tmp_path: Path) -> None:
    ctx, service, durable, _, _, _, _, _, _ = _execute_shared_workspace_run(
        tmp_path, generations=1, publication_fallback=False
    )
    readonly_root = tmp_path / "readonly-artifacts"
    readonly_root.mkdir()
    readonly_root.chmod(0o555)
    reports = ReportStore()
    try:
        submission = service.submit_run(
            ctx,
            "pipe",
            idempotency_key="in-memory-only",
            request=RunRequest(materialization=MaterializationPolicy.NONE),
        )
        host = ExecutionHost(
            durable,
            owner_id="in-memory-worker",
            runner=ManagedExecutionAdapter(
                artifact_root=readonly_root,
                report_store_factory=lambda _context: reports,
            ),
        )
        assert host.tick(ctx) == 1
        assert (
            durable.get_submission(ctx, submission.submission_id).status == "completed"
        )
        assert submission.resource_id is not None
        report = reports.get(submission.resource_id)
        assert report is not None and report.status.value == "succeeded"
        assert not any(artifact.strategy == "durable" for artifact in report.artifacts)
        assert list(readonly_root.iterdir()) == []
    finally:
        readonly_root.chmod(0o755)


@pytest.mark.skipif(os.name != "posix", reason="POSIX read-only mode")
def test_default_in_memory_plan_does_not_write_to_artifact_root(
    tmp_path: Path,
) -> None:
    ctx, service, durable, _, _, _, _, _, _ = _execute_shared_workspace_run(
        tmp_path, generations=1, publication_fallback=False
    )
    service.register_definition(
        ctx,
        "source-only",
        pipeline_to_dict(definition_from_pipeline(SourceOnlyPipeline)),
    )
    readonly_root = tmp_path / "readonly-artifacts"
    readonly_root.mkdir()
    readonly_root.chmod(0o555)
    reports = ReportStore()
    try:
        submission = service.submit_run(
            ctx, "source-only", idempotency_key="default-in-memory"
        )
        host = ExecutionHost(
            durable,
            owner_id="default-in-memory-worker",
            runner=ManagedExecutionAdapter(
                artifact_root=readonly_root,
                report_store_factory=lambda _context: reports,
            ),
        )
        assert host.tick(ctx) == 1
        assert (
            durable.get_submission(ctx, submission.submission_id).status == "completed"
        )
        assert submission.resource_id is not None
        report = reports.get(submission.resource_id)
        assert report is not None and report.status.value == "succeeded"
        assert not any(artifact.strategy == "durable" for artifact in report.artifacts)
        assert list(readonly_root.iterdir()) == []
    finally:
        readonly_root.chmod(0o755)


@pytest.mark.parametrize(
    "legacy_state", ["current", "untagged", "false-complete", "partial-expired"]
)
@pytest.mark.parametrize("generations", [1, 2])
@pytest.mark.parametrize("publication_fallback", [False, True])
@pytest.mark.parametrize("shared_reference", [False, True])
def test_rerun_artifacts_download_and_cleanup_the_authoritative_workspace(
    tmp_path: Path,
    generations: int,
    publication_fallback: bool,
    shared_reference: bool,
    legacy_state: str,
) -> None:
    ctx, service, durable, adapter, child_run_id, _, report, listed, paths = (
        _execute_shared_workspace_run(tmp_path, generations, publication_fallback)
    )
    artifact_root = tmp_path / "artifacts"
    report_root = tmp_path / "reports"
    # A durable publication can outlive an unavailable report provider. Its
    # snapshot must already contain the storage identity before final enrichment.
    stored = managed_report_store(ctx, report_root=report_root)
    now = datetime.now(UTC)
    old_end = now - timedelta(days=2)
    persisted = replace(
        PipelineRunReport.from_dict(report),
        started_at=old_end - timedelta(minutes=1),
        ended_at=old_end,
    )
    if legacy_state != "current":
        metadata = dict(persisted.metadata)
        metadata.pop(ARTIFACT_STORAGE_RUN_ID_KEY)
        if legacy_state in {"false-complete", "partial-expired"}:
            metadata[RUN_ARTIFACT_RETENTION_STATE_KEY] = (
                "complete" if legacy_state == "false-complete" else "running"
            )
            persisted = replace(
                persisted,
                artifacts=tuple(
                    replace(item, status="expired") for item in persisted.artifacts
                ),
            )
        persisted = replace(persisted, metadata=metadata)
    stored.put(persisted)
    if shared_reference:
        stored.put(
            replace(
                PipelineRunReport.from_dict(report),
                run_id="still-retained",
                ended_at=now,
            )
        )
    restarted = managed_report_store(ctx, report_root=report_root)
    result = cleanup_expired_run_artifacts(
        ctx,
        report_store=restarted,
        report_resolver=lambda item: service.resolve_artifact_report(ctx, item),
        artifact_root=artifact_root,
        retention_seconds=1,
        now=now,
    )
    assert result.completed_reports == 1
    assert result.deleted_artifacts == (0 if shared_reference else len(paths))
    assert all(path.exists() == shared_reference for path in paths)
    assert not any(
        item["content_available"]
        for item in service.list_run_artifacts(ctx, child_run_id)
    )
    with pytest.raises(ControlPlaneError, match="artifact"):
        service.get_run_artifact_content(ctx, child_run_id, listed[0]["artifact_id"])
    if shared_reference and publication_fallback:

        class UnavailableStore:
            def get(self, _run_id: str) -> PipelineRunReport | None:
                raise OSError("report provider temporarily unavailable")

        service.report_store_factory = lambda _context: UnavailableStore()
        assert not service.list_run_artifacts(ctx, child_run_id)[0]["content_available"]
        with pytest.raises(ControlPlaneError, match="artifact"):
            service.get_run_artifact_content(
                ctx, child_run_id, listed[0]["artifact_id"]
            )
        fallback = service.get_run_report(ctx, child_run_id)
        assert fallback["artifacts"][0]["status"] == "expired"
        service.report_store_factory = None
        publication = durable.get_latest_result_publication(
            ctx,
            str(
                fallback["metadata"]["etlantic.control_plane.execution"][
                    "submission_id"
                ]
            ),
        )
        assert publication is not None
        # Reconciliation must not overwrite expiry with the immutable old copy.
        adapter.report_store_factory = None
        adapter.publish_result_publication(
            ctx,
            publication,
            submission_reader=lambda submission_id: durable.get_submission(
                ctx, submission_id
            ),
        )
        recovered = managed_report_store(ctx, report_root=report_root).get(child_run_id)
        assert recovered is not None and recovered.artifacts[0].status == "expired"

    if shared_reference:
        final = cleanup_expired_run_artifacts(
            ctx,
            report_store=restarted,
            report_resolver=lambda item: service.resolve_artifact_report(ctx, item),
            artifact_root=artifact_root,
            retention_seconds=1,
            now=now + timedelta(days=1),
        )
        assert final.deleted_artifacts == len(paths)
        assert not any(path.exists() for path in paths)
