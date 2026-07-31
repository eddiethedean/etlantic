"""CP2 history, impact, and baseline acknowledgement tests (040-H)."""

from __future__ import annotations

import json

import pytest

from etlantic.control_plane import (
    CacheInvalidationEvent,
    ControlPlaneContext,
    ControlPlaneError,
    CorrelationKey,
    EnvironmentRef,
    ImpactEdge,
    MemoryHistoryStore,
    MemoryImpactIndex,
    MemoryRegistryProvider,
    PlanObservationRecord,
    Principal,
    RegistryRevision,
    ReliabilityObservationRecord,
    SchemaObservationRecord,
    SecurityDomain,
    TenantRecord,
    TenantRef,
    WorkspaceRecord,
    WorkspaceRef,
    assert_history_metadata_only,
    assert_no_secrets,
    content_fingerprint,
    redact_control_plane_payload,
)


def _ctx(
    *,
    tenant: str = "tenant-a",
    workspace: str = "ws-1",
    subject: str = "user-a",
    domain: str = "domain-a",
) -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal(
            subject=subject, issuer="https://issuer.example", kind="human"
        ),
        tenant=TenantRef(tenant_id=tenant),
        workspace=WorkspaceRef(tenant_id=tenant, workspace_id=workspace),
        environment=EnvironmentRef(name="development"),
        security_domain=SecurityDomain(domain_id=domain),
        correlation_key=CorrelationKey(value="corr-1"),
        request_id="req-1",
    )


def _seed_workspace(provider: MemoryRegistryProvider, ctx: ControlPlaneContext) -> None:
    provider.tenants.put(
        ctx,
        TenantRecord(
            tenant_id=ctx.tenant.tenant_id,
            security_domain_id=ctx.security_domain.domain_id,
        ),
    )
    provider.workspaces.put(
        ctx,
        WorkspaceRecord(
            tenant_id=ctx.tenant.tenant_id,
            workspace_id=ctx.workspace.workspace_id,
        ),
    )


def test_acknowledge_baseline_does_not_mutate_revision_fingerprint() -> None:
    provider = MemoryRegistryProvider()
    history = MemoryHistoryStore()
    ctx = _ctx()
    _seed_workspace(provider, ctx)

    content = {"kind": "contract", "name": "orders"}
    rev = RegistryRevision(
        logical_id="contract-orders",
        revision_id="rev-c1",
        tenant_id="tenant-a",
        workspace_id="ws-1",
        content_fingerprint=content_fingerprint(content),
        content=content,
        kind="contract",
    )
    provider.revisions.put_revision(ctx, rev)
    before = provider.revisions.get_revision(ctx, "rev-c1")

    obs = history.append_schema_observation(
        ctx,
        SchemaObservationRecord(
            observation_id="obs-1",
            tenant_id="tenant-a",
            workspace_id="ws-1",
            subject_id="orders",
            schema_fingerprint="fp-schema-1",
            field_fingerprints={"id": "fp-field-id"},
            metadata={"drift": "additive"},
        ),
    )
    assert obs.acknowledged is False

    ack = history.acknowledge_baseline(ctx, "obs-1", kind="schema", note="accepted")
    assert ack.acknowledged is True
    assert ack.note == "accepted"

    after = provider.revisions.get_revision(ctx, "rev-c1")
    assert after == before
    assert after.content_fingerprint == before.content_fingerprint
    assert after.content == content


def test_impact_dependents_return_metadata_only() -> None:
    index = MemoryImpactIndex()
    ctx = _ctx()
    index.register_edge(
        ctx,
        ImpactEdge(
            tenant_id="tenant-a",
            workspace_id="ws-1",
            source_fingerprint="fp-field-amount",
            target_logical_id="pipe-orders",
            metadata={"edge": "reads"},
        ),
    )
    index.register_edge(
        ctx,
        ImpactEdge(
            tenant_id="tenant-a",
            workspace_id="ws-1",
            source_fingerprint="fp-field-amount",
            target_logical_id="pipe-billing",
        ),
    )

    deps = index.dependents(ctx, "fp-field-amount")
    assert [d.target_logical_id for d in deps] == ["pipe-billing", "pipe-orders"]
    for edge in deps:
        blob = json.dumps(edge.to_dict())
        assert "rows" not in edge.metadata
        assert "sample" not in blob.lower() or "sample" not in edge.metadata
        # Wire shape is fingerprints + logical ids only.
        assert edge.source_fingerprint == "fp-field-amount"
        assert "content" not in edge.to_dict()

    with pytest.raises(ValueError, match="source rows"):
        index.register_edge(
            ctx,
            ImpactEdge(
                tenant_id="tenant-a",
                workspace_id="ws-1",
                source_fingerprint="fp-x",
                target_logical_id="pipe-x",
                metadata={"sample_rows": [{"a": 1}]},
            ),
        )


def test_history_redaction_and_row_reject() -> None:
    history = MemoryHistoryStore()
    ctx = _ctx()

    with pytest.raises(ValueError, match="source rows"):
        assert_history_metadata_only({"rows": [{"id": 1}]})

    with pytest.raises(ValueError, match="source rows"):
        history.append_schema_observation(
            ctx,
            SchemaObservationRecord(
                observation_id="obs-bad",
                tenant_id="tenant-a",
                workspace_id="ws-1",
                subject_id="orders",
                schema_fingerprint="fp",
                metadata={"sample_rows": [{"secret": "x"}]},
            ),
        )

    stored = history.append_schema_observation(
        ctx,
        SchemaObservationRecord(
            observation_id="obs-ok",
            tenant_id="tenant-a",
            workspace_id="ws-1",
            subject_id="orders",
            schema_fingerprint="fp",
            metadata={"token": "super-secret-token", "note": "ok"},
        ),
    )
    payload = stored.to_dict()
    redacted = redact_control_plane_payload(payload)
    blob = json.dumps(redacted)
    assert_no_secrets(blob)
    assert "super-secret-token" not in blob

    listed = history.list_schema_observations(ctx)
    assert len(listed) == 1
    assert listed[0].observation_id == "obs-ok"


def test_reliability_and_plan_append_list_ack() -> None:
    history = MemoryHistoryStore()
    ctx = _ctx()

    history.append_reliability_observation(
        ctx,
        ReliabilityObservationRecord(
            observation_id="rel-1",
            tenant_id="tenant-a",
            workspace_id="ws-1",
            subject_id="orders",
            kind="freshness",
            result_fingerprint="fp-rel",
        ),
    )
    history.append_plan_observation(
        ctx,
        PlanObservationRecord(
            observation_id="plan-1",
            tenant_id="tenant-a",
            workspace_id="ws-1",
            subject_id="orders",
            plan_fingerprint="fp-plan",
        ),
    )

    assert len(history.list_reliability_observations(ctx)) == 1
    assert len(history.list_plan_observations(ctx)) == 1

    rel_ack = history.acknowledge_baseline(ctx, "rel-1", kind="reliability")
    plan_ack = history.acknowledge_baseline(ctx, "plan-1", kind="plan")
    assert rel_ack.acknowledged and plan_ack.acknowledged

    with pytest.raises(ControlPlaneError) as exc:
        history.acknowledge_baseline(ctx, "missing", kind="schema")
    assert exc.value.status == 404


def test_history_and_impact_scope_isolation() -> None:
    history = MemoryHistoryStore()
    index = MemoryImpactIndex()
    ctx_a = _ctx(tenant="tenant-a", workspace="ws-1")
    ctx_b = _ctx(tenant="tenant-b", workspace="ws-1", domain="domain-b")

    history.append_schema_observation(
        ctx_a,
        SchemaObservationRecord(
            observation_id="obs-a",
            tenant_id="tenant-a",
            workspace_id="ws-1",
            subject_id="orders",
            schema_fingerprint="fp-a",
        ),
    )
    index.register_edge(
        ctx_a,
        ImpactEdge(
            tenant_id="tenant-a",
            workspace_id="ws-1",
            source_fingerprint="fp-a",
            target_logical_id="pipe-a",
        ),
    )
    index.record_invalidation(
        ctx_a,
        CacheInvalidationEvent(
            event_id="inv-1",
            tenant_id="tenant-a",
            workspace_id="ws-1",
            reason="schema_ack",
            target_fingerprints=("fp-a",),
        ),
    )

    assert history.list_schema_observations(ctx_b) == []
    assert index.dependents(ctx_b, "fp-a") == []
    assert index.list_invalidations(ctx_b) == []
    with pytest.raises(ControlPlaneError) as exc:
        history.get_schema_observation(ctx_b, "obs-a")
    assert exc.value.status == 404
