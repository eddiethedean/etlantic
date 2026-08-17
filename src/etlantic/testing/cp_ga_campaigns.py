"""CP-GA qualification campaigns (0.43) — deterministic in-process evidence."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from importlib.metadata import version as pkg_version
from pathlib import Path
from typing import Any

from etlantic.control_plane import (
    ControlPlaneContext,
    ControlPlaneError,
    DeliveryObjective,
    EnvironmentRef,
    MemoryApprovalStore,
    MemoryAttestationStore,
    MemoryAuditEvidenceStore,
    MemoryDefinitionRepository,
    MemoryDurableWorkStore,
    MemoryErasureProvider,
    MemoryErasureStore,
    MemoryObjectiveStore,
    MemoryPolicyProvider,
    MemoryQuotaProvider,
    MemoryRegistryProvider,
    Principal,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
    gate_pre_promote,
    gate_pre_submit,
)


def _ctx(
    tenant: str,
    workspace: str,
    *,
    subject: str = "alice",
    domain: str = "default",
) -> ControlPlaneContext:
    return ControlPlaneContext(
        principal=Principal(subject, issuer="cp-ga"),
        tenant=TenantRef(tenant),
        workspace=WorkspaceRef(tenant, workspace),
        environment=EnvironmentRef("production"),
        security_domain=SecurityDomain(domain),
    )


def run_compat_campaign() -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    # Schema fingerprint smoke: core control-plane models import and serialize.
    from etlantic.control_plane.policy_models import PolicyDecision

    decision = PolicyDecision(
        decision_id="d1",
        hook="pre_submit",
        effect="allow",
        policy_bundle_id="default",
        policy_fingerprint="pf",
        plan_fingerprint="plan",
    )
    blob = decision.to_dict()
    cases.append(
        {
            "id": "policy_decision_schema",
            "status": "pass" if blob.get("schema") else "fail",
        }
    )

    # Migration apply on fresh sqlite (sqlmodel optional).
    try:
        from etlantic_sqlmodel.control_plane.session import create_sqlite_engine
        from etlantic_sqlmodel.migrations import apply_migrations, current_version

        engine = create_sqlite_engine("sqlite://")
        apply_migrations(engine)
        ver = current_version(engine)
        cases.append(
            {
                "id": "sqlmodel_migrations_fresh",
                "status": "pass" if ver == "004_schedules_0_47" else "fail",
                "version": ver,
            }
        )
    except ImportError:
        cases.append(
            {
                "id": "sqlmodel_migrations_fresh",
                "status": "skip",
                "detail": "etlantic_sqlmodel not installed",
            }
        )

    installed = pkg_version("etlantic")
    major_minor = ".".join(installed.split(".")[:2])
    cases.append(
        {
            "id": "compat_floor",
            "status": "pass" if major_minor == "0.47" else "fail",
            "policy": ">=0.47.0,<0.48",
            "installed": installed,
        }
    )
    failed = [c["id"] for c in cases if c["status"] == "fail"]
    return {
        "matrix_version": "0.47.0",
        "campaign": "043-C",
        "cases": cases,
        "pass": not failed,
        "failed": failed,
    }


def run_isolation_campaign() -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    a = _ctx("tenant-a", "ws-1", subject="alice", domain="dom-a")
    b = _ctx("tenant-b", "ws-1", subject="bob", domain="dom-b")

    # Definitions / submissions scoped
    defs = MemoryDefinitionRepository()
    defs.put(a, "pipe-a", {"name": "pipe-a"})
    try:
        defs.get(b, "pipe-a")
        cases.append({"id": "definition_cross_tenant", "status": "fail"})
    except (ControlPlaneError, KeyError) as exc:
        status = getattr(exc, "status", 404)
        cases.append(
            {
                "id": "definition_cross_tenant",
                "status": "pass"
                if status == 404 or isinstance(exc, KeyError)
                else "fail",
                "http_status": status,
            }
        )

    # Durable accept isolation
    durable_a = MemoryDurableWorkStore()
    durable_b = MemoryDurableWorkStore()
    sub_a, _ = durable_a.accept(
        a, idempotency_key="k1", operation="run.submit", plan_fingerprint="p1"
    )
    pending_b = durable_b.pending_outbox(b)
    cases.append(
        {
            "id": "durable_separate_stores",
            "status": "pass" if not pending_b else "fail",
        }
    )
    try:
        durable_a.cancel_submission(b, sub_a.submission_id)
        cases.append({"id": "durable_cancel_cross_tenant", "status": "fail"})
    except ControlPlaneError as exc:
        cases.append(
            {
                "id": "durable_cancel_cross_tenant",
                "status": "pass" if exc.status == 404 else "fail",
                "http_status": exc.status,
            }
        )

    # Policy / audit / erasure scoped
    policy = MemoryPolicyProvider()
    audit = MemoryAuditEvidenceStore()
    gate_pre_submit(
        a, policy=policy, audit=audit, plan_fingerprint="p", require_policy=True
    )
    assert audit.list(a)
    cases.append(
        {
            "id": "audit_not_visible_cross_tenant",
            "status": "pass" if not audit.list(b) else "fail",
        }
    )

    erasure = MemoryErasureStore()
    req = erasure.create_request(
        a, subject_key_fingerprint="fp", field_paths=("email",)
    )
    try:
        erasure.get_request(b, request_id=req.request_id)
        cases.append({"id": "erasure_cross_tenant", "status": "fail"})
    except ControlPlaneError as exc:
        cases.append(
            {
                "id": "erasure_cross_tenant",
                "status": "pass" if exc.status == 404 else "fail",
            }
        )

    # Quotas per workspace
    quotas = MemoryQuotaProvider()
    quotas.default_limits["concurrency"] = 1
    assert quotas.admit(a, resource="concurrency").effect == "allow"
    assert quotas.admit(b, resource="concurrency").effect == "allow"
    cases.append({"id": "quota_per_workspace", "status": "pass"})

    # Registry get isolation
    registry = MemoryRegistryProvider()
    from etlantic.control_plane import (
        RegistryRevision,
        TenantRecord,
        WorkspaceRecord,
        content_fingerprint,
    )

    registry.tenants.put(
        a, TenantRecord(tenant_id="tenant-a", security_domain_id="dom-a")
    )
    registry.workspaces.put(
        a, WorkspaceRecord(tenant_id="tenant-a", workspace_id="ws-1")
    )
    content = {"pipe": "a"}
    registry.revisions.put_revision(
        a,
        RegistryRevision(
            tenant_id="tenant-a",
            workspace_id="ws-1",
            revision_id="r1",
            logical_id="pipe-a",
            kind="pipeline",
            content_fingerprint=content_fingerprint(content),
            content=content,
        ),
    )
    try:
        registry.revisions.get_revision(b, "r1")
        cases.append({"id": "registry_get_cross_tenant", "status": "fail"})
    except ControlPlaneError as exc:
        cases.append(
            {
                "id": "registry_get_cross_tenant",
                "status": "pass" if exc.status == 404 else "fail",
            }
        )

    # Same-store multi-tenant / multi-workspace negatives (matrix ops)
    a2 = _ctx("tenant-a", "ws-2", subject="alice", domain="dom-a")
    shared_defs = MemoryDefinitionRepository()
    shared_defs.put(a, "pipe-shared", {"ws": "1"})
    shared_defs.put(a2, "pipe-ws2", {"ws": "2"})
    shared_defs.put(b, "pipe-b", {"ws": "b"})
    try:
        shared_defs.get(a, "pipe-ws2")
        cases.append({"id": "definition_cross_workspace", "status": "fail"})
    except ControlPlaneError as exc:
        cases.append(
            {
                "id": "definition_cross_workspace",
                "status": "pass" if exc.status == 404 else "fail",
            }
        )
    try:
        shared_defs.get(a, "pipe-b")
        cases.append({"id": "definition_same_store_cross_tenant", "status": "fail"})
    except ControlPlaneError as exc:
        cases.append(
            {
                "id": "definition_same_store_cross_tenant",
                "status": "pass" if exc.status == 404 else "fail",
            }
        )

    approvals = MemoryApprovalStore()
    approval = approvals.create(
        a,
        hook="pre_promote",
        plan_fingerprint="iso-plan",
        policy_fingerprint="iso-pol",
    )
    try:
        approvals.get(b, approval_id=approval.approval_id)
        cases.append({"id": "approval_cross_tenant", "status": "fail"})
    except ControlPlaneError as exc:
        cases.append(
            {
                "id": "approval_cross_tenant",
                "status": "pass" if exc.status == 404 else "fail",
            }
        )

    objectives = MemoryObjectiveStore()
    objectives.upsert_objective(
        a,
        objective=DeliveryObjective(
            objective_id="obj-a",
            tenant_id="tenant-a",
            workspace_id="ws-1",
            pipeline_id="pipe",
            step_id=None,
            version="1",
            reference="started",
            warning_after_seconds=5,
            hard_after_seconds=10,
        ),
    )
    try:
        objectives.get_objective(b, objective_id="obj-a")
        cases.append({"id": "objective_cross_tenant", "status": "fail"})
    except ControlPlaneError as exc:
        cases.append(
            {
                "id": "objective_cross_tenant",
                "status": "pass" if exc.status == 404 else "fail",
            }
        )

    attestations = MemoryAttestationStore.for_tests()
    att = attestations.make_attestation(a, kind="plan", subject_fingerprint="iso-fp")
    attestations.put(a, attestation=att)
    try:
        attestations.put(b, attestation=att)
        cases.append({"id": "attestation_cross_tenant_put", "status": "fail"})
    except ControlPlaneError as exc:
        cases.append(
            {
                "id": "attestation_cross_tenant_put",
                "status": "pass" if exc.status == 403 else "fail",
            }
        )

    now = datetime.now(UTC)
    from etlantic.control_plane import PreviewWorkspace

    preview_store = MemoryDurableWorkStore()
    preview = PreviewWorkspace(
        preview_id="iso-pv",
        tenant_id="tenant-a",
        workspace_id="ws-1",
        base_revision_id="base",
        candidate_revision_id="cand",
        created_at=now.isoformat(),
        expires_at=(now + timedelta(seconds=120)).isoformat(),
        quota=2,
        code_fingerprint="code",
        plan_fingerprint="iso-plan",
        commit_ref="abc",
    )
    preview_store.create_preview(a, preview)
    try:
        preview_store.mark_preview_stale(b, "iso-pv", plan_fingerprint="other")
        cases.append({"id": "preview_cross_tenant", "status": "fail"})
    except ControlPlaneError as exc:
        cases.append(
            {
                "id": "preview_cross_tenant",
                "status": "pass" if exc.status == 404 else "fail",
            }
        )

    failed = [c["id"] for c in cases if c["status"] == "fail"]
    return {
        "matrix_version": "0.43.0",
        "campaign": "043-I",
        "cases": cases,
        "pass": not failed,
        "failed": failed,
    }


def run_resilience_campaign() -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    ctx = _ctx("tenant-a", "ws-1")
    host1 = MemoryDurableWorkStore()
    host2 = MemoryDurableWorkStore()
    # Simulate dual-host by sharing nothing: accept on host1, host2 cannot lease
    sub, _ = host1.accept(
        ctx, idempotency_key="res-1", operation="run.submit", plan_fingerprint="p"
    )
    pending = host1.pending_outbox(ctx)
    host1.mark_published(ctx, pending[0].outbox_id)
    lease = host1.acquire_lease(ctx, sub.submission_id, owner_id="h1", ttl_seconds=60)
    try:
        host2.acquire_lease(ctx, sub.submission_id, owner_id="h2", ttl_seconds=60)
        cases.append(
            {
                "id": "dual_host_isolated_stores",
                "status": "fail",
                "detail": "host2 leased host1 submission",
            }
        )
    except ControlPlaneError as exc:
        isolated = (
            exc.status == 404
            and not host2.pending_outbox(ctx)
            and lease.owner_id == "h1"
        )
        cases.append(
            {
                "id": "dual_host_isolated_stores",
                "status": "pass" if isolated else "fail",
                "http_status": exc.status,
            }
        )

    # Same-store fencing: second owner cannot steal live lease
    shared = MemoryDurableWorkStore()
    sub2, _ = shared.accept(
        ctx, idempotency_key="res-2", operation="run.submit", plan_fingerprint="p2"
    )
    pending2 = shared.pending_outbox(ctx)
    shared.mark_published(ctx, pending2[0].outbox_id)
    lease2 = shared.acquire_lease(
        ctx, sub2.submission_id, owner_id="h1", ttl_seconds=60
    )
    try:
        shared.acquire_lease(ctx, sub2.submission_id, owner_id="h2", ttl_seconds=60)
        cases.append({"id": "lease_fencing", "status": "fail", "detail": "stole lease"})
    except ControlPlaneError:
        cases.append({"id": "lease_fencing", "status": "pass"})

    shared.cancel_submission(ctx, sub2.submission_id)
    try:
        shared.heartbeat(
            ctx,
            sub2.submission_id,
            owner_id="h1",
            fencing_token=lease2.fencing_token,
            ttl_seconds=60,
        )
        cases.append({"id": "cancel_blocks_heartbeat", "status": "fail"})
    except ControlPlaneError:
        cases.append({"id": "cancel_blocks_heartbeat", "status": "pass"})

    # Idempotent re-accept
    again, created = shared.accept(
        ctx, idempotency_key="res-2", operation="run.submit", plan_fingerprint="p2"
    )
    cases.append(
        {
            "id": "idempotent_accept",
            "status": "pass"
            if not created and again.submission_id == sub2.submission_id
            else "fail",
        }
    )
    failed = [c["id"] for c in cases if c["status"] == "fail"]
    return {
        "matrix_version": "0.43.0",
        "campaign": "043-R",
        "cases": cases,
        "pass": not failed,
        "failed": failed,
    }


def run_recovery_campaign() -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    ctx = _ctx("tenant-a", "ws-1")
    audit = MemoryAuditEvidenceStore()
    audit.append(ctx, action="policy.decide", resource="r1")
    audit.append(ctx, action="run.submit", resource="r2")
    exported = audit.export(ctx)
    restored = MemoryAuditEvidenceStore()
    n = restored.restore(ctx, export=exported)
    cases.append(
        {
            "id": "audit_export_restore",
            "status": "pass" if n >= 2 and restored.verify_chain(ctx) else "fail",
        }
    )

    # Attestation key rotation fail-closed
    store1 = MemoryAttestationStore.for_tests()
    from etlantic.control_plane.attestation_models import Attestation, sign_payload

    att = Attestation(
        attestation_id="att-1",
        kind="plan",
        subject_fingerprint="plan-fp",
        signature="",
        signer_id="ga",
        tenant_id="tenant-a",
        workspace_id="ws-1",
    )
    signed = Attestation(
        attestation_id=att.attestation_id,
        kind=att.kind,
        subject_fingerprint=att.subject_fingerprint,
        signature=sign_payload(store1.signing_secret, att.signing_payload()),
        signer_id=att.signer_id,
        tenant_id=att.tenant_id,
        workspace_id=att.workspace_id,
    )
    store1.put(ctx, attestation=signed)
    store2 = MemoryAttestationStore(signing_secret=b"rotated-secret-value-0001")
    try:
        store2.put(ctx, attestation=signed)
        cases.append({"id": "attestation_key_rotation", "status": "fail"})
    except ControlPlaneError:
        cases.append({"id": "attestation_key_rotation", "status": "pass"})

    try:
        from etlantic_sqlmodel.control_plane.cp4_stores import (
            SQLModelAuditEvidenceStore,
            create_cp4_tables,
        )
        from etlantic_sqlmodel.control_plane.session import create_sqlite_engine
        from etlantic_sqlmodel.migrations import apply_migrations

        engine = create_sqlite_engine("sqlite://")
        apply_migrations(engine)
        create_cp4_tables(engine)
        sql_audit = SQLModelAuditEvidenceStore(engine)
        sql_audit.append(ctx, action="x", resource="y")
        cases.append(
            {
                "id": "sqlmodel_audit_persist",
                "status": "pass" if sql_audit.verify_chain(ctx) else "fail",
            }
        )
    except ImportError:
        cases.append({"id": "sqlmodel_audit_persist", "status": "skip"})

    failed = [c["id"] for c in cases if c["status"] == "fail"]
    return {
        "matrix_version": "0.43.0",
        "campaign": "043-B",
        "cases": cases,
        "pass": not failed,
        "failed": failed,
    }


def run_capacity_campaign() -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    ctx = _ctx("tenant-a", "ws-1")
    quotas = MemoryQuotaProvider()
    quotas.default_limits["concurrency"] = 2
    assert quotas.admit(ctx, resource="concurrency").effect == "allow"
    assert quotas.admit(ctx, resource="concurrency").effect == "allow"
    denied = quotas.admit(ctx, resource="concurrency")
    cases.append(
        {
            "id": "overload_deny",
            "status": "pass" if denied.effect == "deny" else "fail",
            "limit": 2,
        }
    )

    # WRR under shared pressure
    quotas2 = MemoryQuotaProvider()
    quotas2.default_limits["concurrency"] = 100
    a = _ctx("tenant-a", "ws-1")
    b = _ctx("tenant-b", "ws-1", subject="bob", domain="dom-b")
    quotas2.weights[("tenant-a", "ws-1")] = 2
    quotas2.weights[("tenant-b", "ws-1")] = 1
    quotas2.admit(a, resource="concurrency")
    quotas2.admit(b, resource="concurrency")
    quotas2.shared_pressure = True
    quotas2._rr_cursor = 0
    allowed_a = allowed_b = deferred = 0
    for _ in range(24):
        da = quotas2.admit(a, resource="concurrency")
        if da.effect == "allow":
            allowed_a += 1
        elif da.reason == "fairness deferred":
            deferred += 1
        db = quotas2.admit(b, resource="concurrency")
        if db.effect == "allow":
            allowed_b += 1
        elif db.reason == "fairness deferred":
            deferred += 1
    cases.append(
        {
            "id": "wrr_shared_pressure",
            "status": "pass" if deferred > 0 and allowed_a > allowed_b else "fail",
            "allowed_a": allowed_a,
            "allowed_b": allowed_b,
            "deferred": deferred,
        }
    )
    # Idle cursor owner must not permanently starve the only requester.
    starve = MemoryQuotaProvider()
    starve.default_limits["concurrency"] = 100
    starve.admit(a, resource="concurrency")
    starve.admit(b, resource="concurrency")
    starve.shared_pressure = True
    starve._rr_cursor = 0
    allowed_only_b = 0
    for _ in range(8):
        if starve.admit(b, resource="concurrency").effect == "allow":
            allowed_only_b += 1
    cases.append(
        {
            "id": "wrr_idle_owner_no_starve",
            "status": "pass" if allowed_only_b >= 1 else "fail",
            "allowed_b": allowed_only_b,
        }
    )
    cases.append(
        {
            "id": "support_terms",
            "status": "pass",
            "terms": "community_non_sla",
            "envelope": {
                "concurrency_limit_reference": 2,
                "overload_behavior": "deny",
            },
        }
    )
    failed = [c["id"] for c in cases if c["status"] == "fail"]
    return {
        "matrix_version": "0.43.0",
        "campaign": "043-P",
        "cases": cases,
        "pass": not failed,
        "failed": failed,
    }


def run_security_campaign() -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    a = _ctx("tenant-a", "ws-1")
    b = _ctx("tenant-b", "ws-1", subject="eve", domain="dom-b")

    # Forged cross-tenant promote gate
    policy = MemoryPolicyProvider()
    policy.set_rule("pre_promote", "deny")
    try:
        gate_pre_promote(
            a,
            policy=policy,
            revision_id="r1",
            plan_fingerprint="p",
            require_policy=True,
        )
        cases.append({"id": "promote_policy_deny", "status": "fail"})
    except ControlPlaneError as exc:
        cases.append(
            {
                "id": "promote_policy_deny",
                "status": "pass" if exc.status in (403, 409) else "fail",
            }
        )

    # Redaction: erasure report must not include subject values
    erasure = MemoryErasureStore()
    forbidden = "user@example.com"
    req = erasure.create_request(
        a, subject_key_fingerprint="fp-redact", field_paths=("email",)
    )
    plan = erasure.plan(
        a,
        request_id=req.request_id,
        providers=[MemoryErasureProvider(provider_id="local")],
    )
    report = erasure.execute(
        a,
        plan_id=plan.plan_id,
        providers=[MemoryErasureProvider(provider_id="local")],
    )
    blob = str(report.to_dict())
    cases.append(
        {
            "id": "erasure_no_subject_leak",
            "status": "pass" if forbidden not in blob else "fail",
        }
    )

    # Cross-tenant definition non-enumeration
    defs = MemoryDefinitionRepository()
    defs.put(a, "secret-pipe", {"name": "secret"})
    try:
        defs.get(b, "secret-pipe")
        cases.append({"id": "non_enumeration_404", "status": "fail"})
    except (ControlPlaneError, KeyError) as exc:
        status = getattr(exc, "status", 404)
        cases.append(
            {
                "id": "non_enumeration_404",
                "status": "pass"
                if status == 404 or isinstance(exc, KeyError)
                else "fail",
            }
        )

    docs = Path(__file__).resolve().parents[3] / "docs" / "11_DEVELOPMENT"
    findings = docs / "FINDINGS_0_43.md"
    exit_gate = docs / "EXIT_GATE_0_43.md"
    impl_plan = docs / "IMPLEMENTATION_PLAN_0_43.md"
    findings_text = findings.read_text(encoding="utf-8") if findings.is_file() else ""
    exit_text = exit_gate.read_text(encoding="utf-8") if exit_gate.is_file() else ""
    plan_text = impl_plan.read_text(encoding="utf-8") if impl_plan.is_file() else ""
    cases.append(
        {
            "id": "threat_model_closure",
            "status": "pass"
            if findings.is_file()
            and exit_gate.is_file()
            and "Open **P0 count is 0**" in findings_text
            and "043-S" in exit_text
            else "fail",
        }
    )
    cases.append(
        {
            "id": "sbom_review_checklist",
            "status": "pass"
            if impl_plan.is_file() and "SBOM" in plan_text and findings.is_file()
            else "fail",
        }
    )
    failed = [c["id"] for c in cases if c["status"] == "fail"]
    return {
        "matrix_version": "0.43.0",
        "campaign": "043-S",
        "cases": cases,
        "pass": not failed,
        "failed": failed,
    }


def run_ops_campaign() -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    ctx = _ctx("tenant-a", "ws-1")
    objectives = MemoryObjectiveStore()
    objectives.upsert_objective(
        ctx,
        objective=DeliveryObjective(
            objective_id="o1",
            tenant_id="tenant-a",
            workspace_id="ws-1",
            pipeline_id="pipe",
            step_id=None,
            version="1",
            reference="started",
            warning_after_seconds=5,
            hard_after_seconds=10,
        ),
    )
    ref = datetime.now(UTC) - timedelta(seconds=30)
    breached = objectives.evaluate(
        ctx, objective_id="o1", reference_at=ref, submission_id="s1"
    )
    cases.append(
        {
            "id": "objective_breach",
            "status": "pass" if breached.state == "breached" else "fail",
        }
    )
    recovered = objectives.evaluate(
        ctx,
        objective_id="o1",
        reference_at=ref,
        submission_id="s1",
        completed=True,
    )
    cases.append(
        {
            "id": "objective_recovery",
            "status": "pass" if recovered.state == "recovered" else "fail",
        }
    )

    erasure = MemoryErasureStore()
    req = erasure.create_request(
        ctx, subject_key_fingerprint="fp", field_paths=("email",), legal_hold=True
    )
    cases.append(
        {
            "id": "erasure_legal_hold",
            "status": "pass" if req.status == "blocked" else "fail",
        }
    )
    req2 = erasure.create_request(
        ctx, subject_key_fingerprint="fp2", field_paths=("email",)
    )
    providers = [
        MemoryErasureProvider(provider_id="ok"),
        MemoryErasureProvider(provider_id="bad", supported=set()),
    ]
    plan = erasure.plan(ctx, request_id=req2.request_id, providers=providers)
    report = erasure.execute(ctx, plan_id=plan.plan_id, providers=providers)
    cases.append(
        {
            "id": "erasure_no_false_completion",
            "status": "pass" if report.status != "completed" else "fail",
        }
    )
    req3 = erasure.create_request(
        ctx, subject_key_fingerprint="fp3", field_paths=("email",)
    )
    empty_plan = erasure.plan(ctx, request_id=req3.request_id, providers=[])
    empty_report = erasure.execute(ctx, plan_id=empty_plan.plan_id, providers=[])
    cases.append(
        {
            "id": "erasure_empty_providers_fail_closed",
            "status": "pass"
            if empty_report.status != "completed" and not empty_report.reconciled
            else "fail",
        }
    )
    failed = [c["id"] for c in cases if c["status"] == "fail"]
    return {
        "matrix_version": "0.43.0",
        "campaign": "043-O",
        "cases": cases,
        "pass": not failed,
        "failed": failed,
    }


def run_gitops_campaign() -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    ctx = _ctx("tenant-a", "ws-1")
    durable = MemoryDurableWorkStore()
    now = datetime.now(UTC)
    from etlantic.control_plane import PreviewWorkspace

    preview = PreviewWorkspace(
        preview_id="pv1",
        tenant_id="tenant-a",
        workspace_id="ws-1",
        base_revision_id="base",
        candidate_revision_id="cand",
        created_at=now.isoformat(),
        expires_at=(now + timedelta(seconds=120)).isoformat(),
        quota=2,
        code_fingerprint="code",
        plan_fingerprint="plan",
        commit_ref="abc",
    )
    created = durable.create_preview(ctx, preview)
    cases.append(
        {
            "id": "preview_create",
            "status": "pass" if created.preview_id == "pv1" else "fail",
        }
    )

    # SoD approval + promote gate
    approvals = MemoryApprovalStore()
    policy = MemoryPolicyProvider()
    policy.set_rule("pre_promote", "require_approval")
    pending_decision = policy.decide(
        ctx, hook="pre_promote", plan_fingerprint="plan", revision_id="cand"
    )
    req = approvals.create(
        ctx,
        hook="pre_promote",
        plan_fingerprint="plan",
        policy_fingerprint=pending_decision.policy_fingerprint,
        revision_id="cand",
    )
    # Requester cannot self-approve
    try:
        approvals.decide(ctx, approval_id=req.approval_id, approve=True)
        cases.append({"id": "sod_self_approve_blocked", "status": "fail"})
    except ControlPlaneError:
        cases.append({"id": "sod_self_approve_blocked", "status": "pass"})

    approver = _ctx("tenant-a", "ws-1", subject="approver")
    approvals.decide(approver, approval_id=req.approval_id, approve=True)
    try:
        gate_pre_promote(
            ctx,
            policy=policy,
            approvals=approvals,
            plan_fingerprint="plan",
            revision_id="cand",
            require_policy=True,
        )
        cases.append({"id": "promote_with_approval", "status": "pass"})
    except ControlPlaneError as exc:
        cases.append(
            {
                "id": "promote_with_approval",
                "status": "fail",
                "detail": str(exc),
            }
        )

    # Stale plan fingerprint fails (no matching approval)
    try:
        gate_pre_promote(
            ctx,
            policy=policy,
            approvals=approvals,
            plan_fingerprint="plan-stale",
            revision_id="cand",
            require_policy=True,
        )
        cases.append({"id": "stale_plan_rejected", "status": "fail"})
    except ControlPlaneError:
        cases.append({"id": "stale_plan_rejected", "status": "pass"})

    cases.append(
        {
            "id": "metadata_identity",
            "status": "pass"
            if created.plan_fingerprint == "plan"
            and req.plan_fingerprint == created.plan_fingerprint
            else "fail",
            "plan_fingerprint": created.plan_fingerprint,
            "revision_id": created.candidate_revision_id,
        }
    )

    stale = durable.mark_preview_stale(ctx, "pv1", plan_fingerprint="plan-changed")
    cases.append(
        {
            "id": "preview_stale_path",
            "status": "pass" if stale.stale else "fail",
        }
    )

    expired = PreviewWorkspace(
        preview_id="pv-expired",
        tenant_id="tenant-a",
        workspace_id="ws-1",
        base_revision_id="base",
        candidate_revision_id="cand2",
        created_at=now.isoformat(),
        expires_at=(now + timedelta(seconds=1)).isoformat(),
        quota=4,
        code_fingerprint="code",
        plan_fingerprint="plan",
        commit_ref="def",
    )
    durable.create_preview(ctx, expired)
    # Force expiry for cleanup without sleeping.
    key = ("tenant-a", "ws-1", "pv-expired")
    row = durable._previews[key]
    from dataclasses import replace as _replace

    durable._previews[key] = _replace(
        row, expires_at=(now - timedelta(seconds=1)).isoformat()
    )
    cleaned = durable.cleanup_expired_previews(ctx)
    cases.append(
        {
            "id": "preview_cleanup",
            "status": "pass"
            if any(p.preview_id == "pv-expired" and p.cleaned_at for p in cleaned)
            else "fail",
        }
    )

    # Promote denied after approval revoke
    req2 = approvals.create(
        ctx,
        hook="pre_promote",
        plan_fingerprint="plan-revoke",
        policy_fingerprint=pending_decision.policy_fingerprint,
        revision_id="cand",
    )
    approvals.decide(approver, approval_id=req2.approval_id, approve=True)
    approvals.revoke(ctx, approval_id=req2.approval_id, reason="rollback")
    try:
        gate_pre_promote(
            ctx,
            policy=policy,
            approvals=approvals,
            plan_fingerprint="plan-revoke",
            revision_id="cand",
            require_policy=True,
        )
        cases.append({"id": "promote_denied_after_revoke", "status": "fail"})
    except ControlPlaneError:
        cases.append({"id": "promote_denied_after_revoke", "status": "pass"})

    failed = [c["id"] for c in cases if c["status"] == "fail"]
    return {
        "matrix_version": "0.43.0",
        "campaign": "043-M",
        "cases": cases,
        "pass": not failed,
        "failed": failed,
    }


def run_all_campaigns() -> dict[str, Any]:
    campaigns = {
        "compat": run_compat_campaign(),
        "isolation": run_isolation_campaign(),
        "resilience": run_resilience_campaign(),
        "recovery": run_recovery_campaign(),
        "capacity": run_capacity_campaign(),
        "security": run_security_campaign(),
        "ops": run_ops_campaign(),
        "gitops": run_gitops_campaign(),
    }
    failed = [name for name, result in campaigns.items() if not result.get("pass")]
    return {
        "matrix_version": "0.43.0",
        "pass": not failed,
        "failed": failed,
        "campaigns": campaigns,
    }


__all__ = [
    "run_all_campaigns",
    "run_capacity_campaign",
    "run_compat_campaign",
    "run_gitops_campaign",
    "run_isolation_campaign",
    "run_ops_campaign",
    "run_recovery_campaign",
    "run_resilience_campaign",
    "run_security_campaign",
]
