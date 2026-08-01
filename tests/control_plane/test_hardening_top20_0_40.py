"""Regression coverage for the post-release 0.40 deep-dive findings."""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.error import URLError

import pytest

from etlantic.control_plane import (
    AcceptReceipt,
    CacheInvalidationEvent,
    ControlPlaneContext,
    ControlPlaneError,
    ControlPlaneEvent,
    EnvironmentRecord,
    EnvironmentRef,
    ImpactEdge,
    LifecycleState,
    MemoryEventStore,
    MemoryHistoryStore,
    MemoryImpactIndex,
    MemoryRegistryProvider,
    MemoryRetentionHook,
    MemorySubmissionStore,
    PlanObservationRecord,
    Principal,
    RegistryRevision,
    SchemaObservationRecord,
    SecurityDomain,
    TenantRecord,
    TenantRef,
    WorkspaceRecord,
    WorkspaceRef,
    WorkspaceResourceRecord,
    content_fingerprint,
    validate_workspace_resource_record,
)


def _ctx(workspace: str = "ws-a") -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal(subject="alice"),
        tenant=TenantRef(tenant_id="tenant-a"),
        workspace=WorkspaceRef(tenant_id="tenant-a", workspace_id=workspace),
        environment=EnvironmentRef(name="development"),
        security_domain=SecurityDomain(domain_id="domain-a"),
    )


def _seed(provider: MemoryRegistryProvider, *contexts: ControlPlaneContext) -> None:
    first = contexts[0]
    provider.tenants.put(
        first,
        TenantRecord(tenant_id="tenant-a", security_domain_id="domain-a"),
    )
    for ctx in contexts:
        provider.workspaces.put(
            ctx,
            WorkspaceRecord(
                tenant_id="tenant-a", workspace_id=ctx.workspace.workspace_id
            ),
        )


def _revision(**overrides: object) -> RegistryRevision:
    content = overrides.pop("content", {"name": "orders"})
    assert isinstance(content, dict)
    values = {
        "logical_id": "pipe-orders",
        "revision_id": "rev-1",
        "tenant_id": "tenant-a",
        "workspace_id": "ws-a",
        "content_fingerprint": content_fingerprint(content),
        "content": content,
        "kind": "pipeline",
    }
    values.update(overrides)
    return RegistryRevision(**values)  # type: ignore[arg-type]


def test_public_control_plane_record_serializers_redact_metadata() -> None:
    secret_metadata = {"api_token": "super-secret-token"}
    assert TenantRecord(tenant_id="tenant-a", metadata=secret_metadata).to_dict()[
        "metadata"
    ] == {"api_token": "***"}
    assert WorkspaceResourceRecord(
        tenant_id="tenant-a", workspace_id="ws-a", metadata=secret_metadata
    ).to_dict()["metadata"] == {"api_token": "***"}
    assert SchemaObservationRecord(
        observation_id="obs",
        tenant_id="tenant-a",
        workspace_id="ws-a",
        subject_id="orders",
        schema_fingerprint="sha256:schema",
        metadata=secret_metadata,
    ).to_dict()["metadata"] == {"api_token": "***"}


def test_environment_is_not_visible_or_reassignable_cross_workspace() -> None:
    provider = MemoryRegistryProvider()
    ctx_a, ctx_b = _ctx("ws-a"), _ctx("ws-b")
    _seed(provider, ctx_a, ctx_b)
    provider.put_environment(
        ctx_a,
        EnvironmentRecord(
            tenant_id="tenant-a",
            workspace_id="ws-a",
            environment_id="prod",
            name="production",
        ),
    )

    with pytest.raises(ControlPlaneError) as read_exc:
        provider.get_environment(ctx_b, "prod")
    assert read_exc.value.status == 404
    with pytest.raises(ControlPlaneError) as write_exc:
        provider.put_environment(
            ctx_b,
            EnvironmentRecord(
                tenant_id="tenant-a",
                workspace_id="ws-b",
                environment_id="prod",
                name="forged",
            ),
        )
    assert write_exc.value.status == 404
    assert provider.get_environment(ctx_a, "prod").name == "production"


def test_environment_lifecycle_fails_closed_for_reads_and_updates() -> None:
    provider = MemoryRegistryProvider()
    ctx = _ctx()
    _seed(provider, ctx)
    suspended = EnvironmentRecord(
        tenant_id="tenant-a",
        workspace_id="ws-a",
        environment_id="prod",
        name="production",
        lifecycle=LifecycleState.SUSPENDED,
    )
    provider.put_environment(ctx, suspended)
    with pytest.raises(ControlPlaneError) as read_exc:
        provider.get_environment(ctx, "prod")
    assert read_exc.value.status == 403
    with pytest.raises(ControlPlaneError) as write_exc:
        provider.put_environment(ctx, suspended)
    assert write_exc.value.status == 403


def test_environment_operations_honor_workspace_suspension() -> None:
    provider = MemoryRegistryProvider()
    ctx = _ctx()
    _seed(provider, ctx)
    provider.workspaces.set_lifecycle(ctx, "ws-a", LifecycleState.SUSPENDED)
    with pytest.raises(ControlPlaneError) as exc:
        provider.put_environment(
            ctx,
            EnvironmentRecord(
                tenant_id="tenant-a",
                workspace_id="ws-a",
                environment_id="prod",
                name="production",
            ),
        )
    assert exc.value.status == 403


def test_revision_storage_redacts_secrets_and_reseals_fingerprint() -> None:
    provider = MemoryRegistryProvider()
    ctx = _ctx()
    _seed(provider, ctx)
    content = {"name": "orders", "password": "super-secret-token"}
    provider.revisions.put_revision(ctx, _revision(content=content))
    stored = provider.revisions.get_revision(ctx, "rev-1")
    assert stored.content["password"] == "***"
    assert stored.content_fingerprint == content_fingerprint(stored.content)


def test_revision_storage_preserves_canonical_secret_refs() -> None:
    provider = MemoryRegistryProvider()
    ctx = _ctx()
    _seed(provider, ctx)
    content = {
        "source": {"secret_ref": {"provider": "env", "name": "DATABASE_PASSWORD"}}
    }
    provider.revisions.put_revision(ctx, _revision(content=content))
    assert provider.revisions.get_revision(ctx, "rev-1").content == content


def test_revision_placeholders_are_redacted() -> None:
    provider = MemoryRegistryProvider()
    ctx = _ctx()
    _seed(provider, ctx)
    provider.revisions.put_revision(
        ctx,
        _revision(
            signature_placeholder="token=super-secret-token",
            provenance_placeholder={"password": "super-secret-token"},
        ),
    )
    stored = provider.revisions.get_revision(ctx, "rev-1")
    assert "super-secret-token" not in str(stored.to_dict())


def test_acknowledgement_notes_are_redacted() -> None:
    ctx = _ctx()
    history = MemoryHistoryStore()
    history.append_plan_observation(
        ctx,
        PlanObservationRecord(
            observation_id="obs-1",
            tenant_id="tenant-a",
            workspace_id="ws-a",
            subject_id="orders",
            plan_fingerprint="fp",
        ),
    )
    record = history.acknowledge_baseline(
        ctx, "obs-1", kind="plan", note="token=super-secret-token"
    )
    assert record.note == "token=***"


def test_history_rejects_json_encoded_rows() -> None:
    with pytest.raises(ValueError, match="must not store source rows"):
        MemoryHistoryStore().append_schema_observation(
            _ctx(),
            SchemaObservationRecord(
                observation_id="obs-1",
                tenant_id="tenant-a",
                workspace_id="ws-a",
                subject_id="orders",
                schema_fingerprint="fp",
                metadata={"blob": '[{"ssn": "123"}]'},
            ),
        )


def test_observation_wire_boole_do_not_truthify_false_strings() -> None:
    data = {
        "observation_id": "obs-1",
        "tenant_id": "tenant-a",
        "workspace_id": "ws-a",
        "subject_id": "orders",
        "plan_fingerprint": "fp",
        "acknowledged": "false",
    }
    assert PlanObservationRecord.from_dict(data).acknowledged is False
    data["acknowledged"] = "not-a-bool"
    with pytest.raises(ValueError, match="must be a boolean"):
        PlanObservationRecord.from_dict(data)


def test_scalar_sequence_fields_decode_as_one_item() -> None:
    event = CacheInvalidationEvent.from_dict(
        {
            "event_id": "evt-1",
            "tenant_id": "tenant-a",
            "workspace_id": "ws-a",
            "reason": "schema",
            "target_fingerprints": "fp-1",
        }
    )
    resource = WorkspaceResourceRecord.from_dict(
        {
            "tenant_id": "tenant-a",
            "workspace_id": "ws-a",
            "safe_root_refs": "data",
        }
    )
    assert event.target_fingerprints == ("fp-1",)
    assert resource.safe_root_refs == ("data",)


@pytest.mark.parametrize("value", ["../escape", r"..\escape"])
def test_all_workspace_ref_fields_reject_cross_platform_traversal(value: str) -> None:
    with pytest.raises(ControlPlaneError):
        validate_workspace_resource_record(
            WorkspaceResourceRecord(
                tenant_id="tenant-a",
                workspace_id="ws-a",
                safe_root_refs=(value,),
            )
        )
    with pytest.raises(ControlPlaneError):
        validate_workspace_resource_record(
            WorkspaceResourceRecord(
                tenant_id="tenant-a",
                workspace_id="ws-a",
                artifact_namespace=value,
            )
        )


def test_impact_evidence_ids_are_append_only() -> None:
    ctx = _ctx()
    index = MemoryImpactIndex()
    edge = ImpactEdge(
        edge_id="edge-1",
        tenant_id="tenant-a",
        workspace_id="ws-a",
        source_fingerprint="fp",
        target_logical_id="pipe-orders",
    )
    index.register_edge(ctx, edge)
    with pytest.raises(ControlPlaneError, match="already exists"):
        index.register_edge(ctx, edge)

    event = CacheInvalidationEvent(
        event_id="evt-1",
        tenant_id="tenant-a",
        workspace_id="ws-a",
        reason="schema",
    )
    index.record_invalidation(ctx, event)
    with pytest.raises(ControlPlaneError, match="already exists"):
        index.record_invalidation(ctx, event)


def test_retention_does_not_delete_records_with_corrupt_timestamps() -> None:
    ctx = _ctx()
    history = MemoryHistoryStore()
    history.append_plan_observation(
        ctx,
        PlanObservationRecord(
            observation_id="obs-1",
            tenant_id="tenant-a",
            workspace_id="ws-a",
            subject_id="orders",
            plan_fingerprint="fp",
            observed_at="not-a-time",
        ),
    )
    deleted = MemoryRetentionHook(history).purge_expired_observations(
        ctx, older_than=datetime.now(UTC)
    )
    assert deleted == 0
    assert history.get_plan_observation(ctx, "obs-1").observation_id == "obs-1"


def test_memory_submission_payload_is_detached_and_redacted() -> None:
    ctx = _ctx()
    store = MemorySubmissionStore()
    payload = {"definition_id": "orders", "nested": {"token": "secret"}}
    first = store.accept(ctx, idempotency_key="idem-1", payload=payload)
    payload["nested"]["token"] = "mutated"
    replay = store.accept(
        ctx,
        idempotency_key="idem-1",
        payload={"definition_id": "orders", "nested": {"token": "other"}},
    )
    assert first.created is True
    assert replay.created is False


def test_memory_event_payload_is_detached_and_redacted() -> None:
    ctx = _ctx()
    store = MemoryEventStore()
    payload = {"nested": {"password": "super-secret-token"}}
    event = store.append(ctx, kind="run.accepted", payload=payload)
    payload["nested"]["password"] = "mutated"
    stored = store.list_after_cursor(ctx, None)[0]
    assert event.payload == {"nested": {"password": "***"}}
    assert stored.payload == event.payload


def test_wire_envelopes_reject_impossible_required_values() -> None:
    with pytest.raises(ValueError, match="requires kind"):
        ControlPlaneEvent.from_dict(
            {
                "event_id": "evt-1",
                "sequence": 1,
                "cursor": "c1",
                "created_at": "2026-01-01T00:00:00Z",
            }
        )
    with pytest.raises(ValueError, match="unsupported acceptance status"):
        AcceptReceipt.from_dict(
            {
                "acceptance_id": "acc-1",
                "submission_id": "sub-1",
                "tenant_id": "tenant-a",
                "workspace_id": "ws-a",
                "idempotency_key": "idem-1",
                "created_at": "2026-01-01T00:00:00Z",
                "status": "failed",
            }
        )


def test_release_check_reports_offline_failure_without_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from scripts import check_release

    def offline(_name: str, _version: str) -> bool:
        raise URLError("offline")

    monkeypatch.setattr(check_release, "pypi_exists", offline)
    assert check_release.main() == 1
    output = capsys.readouterr().out
    assert "PyPI availability check unavailable: offline" in output


def test_release_check_success_path_initializes_network_state(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from scripts import check_release

    monkeypatch.setattr(check_release, "pypi_exists", lambda _n, _v: True)
    monkeypatch.setattr(check_release, "pypi_project_exists", lambda _n: True)
    assert check_release.main() == 0
    from etlantic._version import __version__

    assert (
        f"All packages already present on PyPI at {__version__}"
        in capsys.readouterr().out
    )
