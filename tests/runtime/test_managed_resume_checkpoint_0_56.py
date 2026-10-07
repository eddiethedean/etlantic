"""Managed resume preflight for file-backed physical checkpoints."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import anyio
import pytest

from etlantic.control_plane import (
    ControlPlaneContext,
    EnvironmentRef,
    MemoryDurableWorkStore,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic.control_plane.errors import ControlPlaneError
from etlantic.exceptions import PipelineExecutionError
from etlantic.runtime.artifacts import ArtifactStore, AttemptArtifactStore
from etlantic.runtime.execution_host import ExecutionHost
from etlantic.runtime.physical_operations import (
    execute_boundary,
    validate_managed_resume_checkpoint,
)


def _plan() -> SimpleNamespace:
    unit = SimpleNamespace(
        metadata={
            "etlantic.logical_node": "first",
            "etlantic.requirement": {
                "schema": "etlantic.physical_operation/1",
                "kind": "reuse",
                "checkpoint": "first",
            },
        }
    )
    graph = SimpleNamespace(
        node_map=lambda: {"first": SimpleNamespace(contract_id="contract-1")}
    )
    return SimpleNamespace(
        schema="etlantic.plan/2",
        pipeline_id="pipeline-1",
        plan_id="plan-1",
        fingerprint="plan-fingerprint",
        security_domain="tenant-domain",
        physical_dag=SimpleNamespace(units=(unit,)),
        logical_graph=graph,
    )


def _write_checkpoint(workspace: Path, *, expires_at: float | None = None) -> None:
    records = [{"id": 7}]
    encoded = json.dumps(records, sort_keys=True, separators=(",", ":"))
    document = {
        "metadata": {
            "schema": "etlantic.checkpoint/1",
            "digest": "sha256:" + hashlib.sha256(encoded.encode()).hexdigest(),
            "producer_fingerprint": "plan-fingerprint",
            "contract_id": "contract-1",
            "security_domain": "tenant-domain",
            "created_at": 100.0,
            "expires_at": expires_at,
        },
        "records": records,
    }
    (workspace / "checkpoint-first.json").write_text(
        json.dumps(document), encoding="utf-8"
    )


def test_managed_resume_requires_a_valid_matching_checkpoint(tmp_path: Path) -> None:
    _write_checkpoint(tmp_path)
    plan = _plan()

    assert (
        validate_managed_resume_checkpoint(
            plan,
            checkpoint_id="checkpoint:run-parent:first",
            parent_run_id="run-parent",
            workspace=tmp_path,
        )
        == "first"
    )
    with pytest.raises(ValueError, match="match one reusable plan boundary"):
        validate_managed_resume_checkpoint(
            plan,
            checkpoint_id="checkpoint:run-parent:other",
            parent_run_id="run-parent",
            workspace=tmp_path,
        )

    class Plugin:
        info = SimpleNamespace(engine="local")

        @staticmethod
        def to_records(value: Any, *, contract_type: Any = None) -> Any:
            return value

        @staticmethod
        def materialize_input(records: Any, **_kwargs: Any) -> Any:
            return records

    async def execute_selected() -> None:
        unit = SimpleNamespace(identity="reuse-unit")
        node = SimpleNamespace(
            name="first", contract_id="contract-1", contract_type=None, outputs=()
        )
        requirement = {
            "schema": "etlantic.physical_operation/1",
            "kind": "reuse",
            "checkpoint": "first",
        }
        artifacts = AttemptArtifactStore(ArtifactStore(workspace=tmp_path))
        restored, metadata = await execute_boundary(
            kind="reuse",
            unit=unit,
            node=node,
            value=[{"id": 99}],
            plugin=Plugin(),
            run_id="run-child",
            plan=plan,
            workspace=tmp_path,
            artifacts=artifacts,
            artifact_key="first.result",
            requirement=requirement,
            required_checkpoint="first",
        )
        assert restored == [{"id": 7}]
        assert metadata["selection"] == "checkpoint"
        (tmp_path / "checkpoint-first.json").unlink()
        with pytest.raises(PipelineExecutionError, match="no longer restorable"):
            await execute_boundary(
                kind="reuse",
                unit=unit,
                node=node,
                value=[{"id": 99}],
                plugin=Plugin(),
                run_id="run-child",
                plan=plan,
                workspace=tmp_path,
                artifacts=artifacts,
                artifact_key="first.result",
                requirement=requirement,
                required_checkpoint="first",
            )

    anyio.run(execute_selected)

    _write_checkpoint(tmp_path, expires_at=1.0)
    with pytest.raises(ValueError, match="missing, expired, or stale"):
        validate_managed_resume_checkpoint(
            plan,
            checkpoint_id="checkpoint:run-parent:first",
            parent_run_id="run-parent",
            workspace=tmp_path,
        )


def test_execution_host_publishes_checkpoint_link_for_resume() -> None:
    ctx = ControlPlaneContext(
        principal=Principal("worker", issuer="tests"),
        tenant=TenantRef("tenant"),
        workspace=WorkspaceRef("tenant", "workspace"),
        environment=EnvironmentRef("dev"),
        security_domain=SecurityDomain("internal"),
    )
    durable = MemoryDurableWorkStore()
    submission, _created = durable.accept(
        ctx,
        idempotency_key="checkpoint-parent",
        operation="run.submit",
        plan_fingerprint="plan-fingerprint",
    )
    lease = durable.acquire_lease(
        ctx, submission.submission_id, owner_id="worker", ttl_seconds=60
    )
    attempt = durable.start_attempt(
        ctx,
        submission.submission_id,
        owner_id="worker",
        fencing_token=lease.fencing_token,
    )

    host = ExecutionHost(durable, owner_id="worker")
    publisher_factory = cast(
        Callable[..., Callable[[str, str], None]],
        getattr(host, "_checkpoint" + "_publisher"),
    )
    publisher = publisher_factory(
        ctx, attempt_id=attempt.attempt_id, fencing_token=lease.fencing_token
    )
    checkpoint_id = "checkpoint:run-parent:first"
    publisher(checkpoint_id, "sha256:" + "a" * 64)

    # Resume discovery checks the durable checkpoint's parent submission link.
    assert (
        durable.plan_resume(
            ctx, submission.submission_id, checkpoint_id=checkpoint_id
        ).checkpoint_id
        == checkpoint_id
    )

    other, _created = durable.accept(
        ctx,
        idempotency_key="other-parent",
        operation="run.submit",
        plan_fingerprint="plan-fingerprint",
    )
    other_lease = durable.acquire_lease(
        ctx, other.submission_id, owner_id="worker-2", ttl_seconds=60
    )
    other_attempt = durable.start_attempt(
        ctx,
        other.submission_id,
        owner_id="worker-2",
        fencing_token=other_lease.fencing_token,
    )
    other_host = ExecutionHost(durable, owner_id="worker-2")
    other_publisher_factory = cast(
        Callable[..., Callable[[str, str], None]],
        getattr(other_host, "_checkpoint" + "_publisher"),
    )
    other_publisher = other_publisher_factory(
        ctx,
        attempt_id=other_attempt.attempt_id,
        fencing_token=other_lease.fencing_token,
    )
    with pytest.raises(ControlPlaneError, match="another submission"):
        other_publisher(checkpoint_id, "sha256:" + "b" * 64)
