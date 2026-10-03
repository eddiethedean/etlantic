"""Managed resume resolves durable files and retires shared references safely."""

from __future__ import annotations

import json
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


@pytest.mark.parametrize(
    "legacy_state", ["current", "untagged", "false-complete", "partial-expired"]
)
@pytest.mark.parametrize("generations", [1, 2])
@pytest.mark.parametrize("publication_fallback", [False, True])
@pytest.mark.parametrize("shared_reference", [False, True])
def test_resumed_artifacts_download_and_cleanup_the_authoritative_workspace(
    tmp_path: Path,
    generations: int,
    publication_fallback: bool,
    shared_reference: bool,
    legacy_state: str,
) -> None:
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
        "run.resume",
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
    checkpoint_id = "checkpoint:parent"

    def checkpoint_then_fail(worker_ctx: ControlPlaneContext, **kwargs: Any) -> None:
        durable.compare_and_swap_checkpoint(
            worker_ctx,
            checkpoint_id,
            expected_version=None,
            value_fingerprint="a" * 64,
            attempt_id=kwargs["attempt_id"],
            fencing_token=kwargs["fencing_token"],
        )
        raise ExecutionRejected("before any writes")

    child = parent
    for generation in range(generations):
        assert (
            ExecutionHost(
                durable, owner_id=f"failed-{generation}", runner=checkpoint_then_fail
            ).tick(ctx)
            == 1
        )
        child = service.resume_run(
            ctx,
            parent.resource_id,
            idempotency_key=f"child-{generation}",
            checkpoint_id=checkpoint_id,
        )
        if generation + 1 < generations:
            parent = child
            assert parent.resource_id is not None
            checkpoint_id = f"checkpoint:child-{generation}"

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
        for item in service.list_run_artifacts(ctx, child.resource_id)
    )
    with pytest.raises(ControlPlaneError, match="artifact"):
        service.get_run_artifact_content(
            ctx, child.resource_id, listed[0]["artifact_id"]
        )
    if shared_reference and publication_fallback:

        class UnavailableStore:
            def get(self, _run_id: str) -> PipelineRunReport | None:
                raise OSError("report provider temporarily unavailable")

        service.report_store_factory = lambda _context: UnavailableStore()
        assert not service.list_run_artifacts(ctx, child.resource_id)[0][
            "content_available"
        ]
        with pytest.raises(ControlPlaneError, match="artifact"):
            service.get_run_artifact_content(
                ctx, child.resource_id, listed[0]["artifact_id"]
            )
        fallback = service.get_run_report(ctx, child.resource_id)
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
        adapter.publish_result_publication(ctx, publication)
        recovered = managed_report_store(ctx, report_root=report_root).get(
            child.resource_id
        )
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
