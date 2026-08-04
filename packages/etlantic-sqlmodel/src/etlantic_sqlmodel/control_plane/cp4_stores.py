"""SQLModel-backed CP4 governance stores (snapshot dual-path)."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, TypeVar

from sqlalchemy.engine import Engine

from etlantic.control_plane.approval_memory import MemoryApprovalStore
from etlantic.control_plane.approval_models import (
    ApprovalDecisionRecord,
    ApprovalRequest,
)
from etlantic.control_plane.attestation_memory import MemoryAttestationStore
from etlantic.control_plane.attestation_models import Attestation
from etlantic.control_plane.audit_memory import MemoryAuditEvidenceStore
from etlantic.control_plane.audit_models import AuditExport, AuditRecord
from etlantic.control_plane.erasure_memory import MemoryErasureStore
from etlantic.control_plane.erasure_models import (
    ErasurePlan,
    ErasurePlanStep,
    ErasureReport,
    ErasureRequest,
    ErasureStepResult,
)
from etlantic.control_plane.errors import ControlPlaneError
from etlantic.control_plane.governance_models import GovernanceConstraints
from etlantic.control_plane.models import ControlPlaneContext
from etlantic.control_plane.objective_memory import MemoryObjectiveStore
from etlantic.control_plane.objective_models import (
    DeliveryObjective,
    ObjectiveEvaluation,
)
from etlantic.control_plane.policy_memory import MemoryPolicyProvider
from etlantic.control_plane.quota_memory import MemoryQuotaProvider
from etlantic.control_plane.quota_models import QuotaState
from etlantic_sqlmodel.control_plane.models import Cp4GovernanceSnapshotRow
from etlantic_sqlmodel.control_plane.session import session_scope
from sqlmodel import Session, SQLModel, select

T = TypeVar("T")

CP4_TABLES = (Cp4GovernanceSnapshotRow,)


def create_cp4_tables(engine: Engine) -> None:
    SQLModel.metadata.create_all(
        engine,
        tables=[cls.__table__ for cls in CP4_TABLES],  # type: ignore[list-item]
    )


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _dump_audit(store: MemoryAuditEvidenceStore) -> dict[str, Any]:
    return {
        "chains": {
            f"{t}|{w}": [r.to_dict() for r in records]
            for (t, w), records in store._chains.items()
        }
    }


def _load_audit(payload: Mapping[str, Any]) -> MemoryAuditEvidenceStore:
    store = MemoryAuditEvidenceStore()
    for key, records in dict(payload.get("chains") or {}).items():
        tenant_id, workspace_id = str(key).split("|", 1)
        loaded = []
        for item in records or []:
            loaded.append(
                AuditRecord(
                    record_id=str(item["record_id"]),
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                    actor_subject=str(item.get("actor_subject") or ""),
                    actor_issuer=item.get("actor_issuer"),
                    action=str(item.get("action") or ""),
                    resource=str(item.get("resource") or ""),
                    prev_hash=str(item.get("prev_hash") or ""),
                    record_hash=str(item.get("record_hash") or ""),
                    decision_refs=tuple(item.get("decision_refs") or ()),
                    created_at=datetime.fromisoformat(str(item["created_at"]))
                    if item.get("created_at")
                    else datetime.now(UTC),
                    metadata=dict(item.get("metadata") or {}),
                )
            )
        store._chains[(tenant_id, workspace_id)] = loaded
    return store


class _SnapshotBackedStore:
    kind: str = "generic"

    def __init__(self, engine: Engine, *, store_id: str = "default") -> None:
        self.engine = engine
        self.store_id = store_id

    def _empty(self) -> Any:
        raise NotImplementedError

    def _dump(self, mem: Any) -> dict[str, Any]:
        raise NotImplementedError

    def _load(self, payload: Mapping[str, Any]) -> Any:
        raise NotImplementedError

    def _txn(self, fn: Callable[[Any], T]) -> T:
        with session_scope(self.engine) as session:
            mem, version = self._read(session, for_update=True)
            result = fn(mem)
            self._write(session, mem, expected_version=version)
            return result

    def _read_only(self, fn: Callable[[Any], T]) -> T:
        with session_scope(self.engine) as session:
            mem, _version = self._read(session, for_update=False)
            return fn(mem)

    def _read(self, session: Session, *, for_update: bool) -> tuple[Any, int]:
        stmt = (
            select(Cp4GovernanceSnapshotRow)
            .where(Cp4GovernanceSnapshotRow.store_id == self.store_id)
            .where(Cp4GovernanceSnapshotRow.kind == self.kind)
        )
        if for_update:
            stmt = stmt.with_for_update()
        row = session.exec(stmt).first()
        if row is None:
            return self._empty(), 0
        return self._load(json.loads(row.payload_json or "{}")), int(
            row.payload_version or 0
        )

    def _write(self, session: Session, store: Any, *, expected_version: int) -> None:
        payload = json.dumps(self._dump(store), sort_keys=True, default=str)
        row = session.exec(
            select(Cp4GovernanceSnapshotRow)
            .where(Cp4GovernanceSnapshotRow.store_id == self.store_id)
            .where(Cp4GovernanceSnapshotRow.kind == self.kind)
            .with_for_update()
        ).first()
        if row is None:
            if expected_version != 0:
                raise ControlPlaneError.conflict("CP4 snapshot conflict")
            session.add(
                Cp4GovernanceSnapshotRow(
                    store_id=self.store_id,
                    kind=self.kind,
                    payload_json=payload,
                    payload_version=1,
                    updated_at=_utcnow_iso(),
                )
            )
            return
        if int(row.payload_version or 0) != expected_version:
            raise ControlPlaneError.conflict("CP4 snapshot conflict")
        row.payload_json = payload
        row.payload_version = expected_version + 1
        row.updated_at = _utcnow_iso()
        session.add(row)


class SQLModelAuditEvidenceStore(_SnapshotBackedStore):
    kind = "audit"

    def _empty(self) -> MemoryAuditEvidenceStore:
        return MemoryAuditEvidenceStore()

    def _dump(self, mem: MemoryAuditEvidenceStore) -> dict[str, Any]:
        return _dump_audit(mem)

    def _load(self, payload: Mapping[str, Any]) -> MemoryAuditEvidenceStore:
        return _load_audit(payload)

    def append(self, ctx: ControlPlaneContext, **kwargs: Any) -> AuditRecord:
        return self._txn(lambda m: m.append(ctx, **kwargs))

    def list(
        self, ctx: ControlPlaneContext, *, limit: int = 100, after_id: str | None = None
    ) -> Sequence[AuditRecord]:
        return self._read_only(lambda m: m.list(ctx, limit=limit, after_id=after_id))

    def verify_chain(self, ctx: ControlPlaneContext) -> bool:
        return self._read_only(lambda m: m.verify_chain(ctx))

    def export(self, ctx: ControlPlaneContext, *, limit: int = 1000) -> AuditExport:
        return self._read_only(lambda m: m.export(ctx, limit=limit))

    def restore(self, ctx: ControlPlaneContext, *, export: AuditExport) -> int:
        return self._txn(lambda m: m.restore(ctx, export=export))


class SQLModelPolicyProvider(_SnapshotBackedStore):
    kind = "policy"

    def _empty(self) -> MemoryPolicyProvider:
        return MemoryPolicyProvider()

    def _dump(self, mem: MemoryPolicyProvider) -> dict[str, Any]:
        return {
            "unavailable": bool(mem.unavailable),
            "global_rules": dict(mem.global_rules),
            "rules": {f"{t}|{w}|{h}": e for (t, w, h), e in mem.rules.items()},
            "constraints": mem.constraints.to_dict(),
        }

    def _load(self, payload: Mapping[str, Any]) -> MemoryPolicyProvider:
        mem = MemoryPolicyProvider(unavailable=bool(payload.get("unavailable")))
        mem.global_rules = {
            str(k): str(v) for k, v in dict(payload.get("global_rules") or {}).items()
        }
        mem.rules = {}
        for key, effect in dict(payload.get("rules") or {}).items():
            t, w, h = str(key).split("|", 2)
            mem.rules[(t, w, h)] = str(effect)  # type: ignore[assignment]
        mem.constraints = GovernanceConstraints.from_dict(payload.get("constraints"))
        return mem

    def require_available(self, ctx: ControlPlaneContext) -> None:
        return self._read_only(lambda m: m.require_available(ctx))

    def get_bundle(self, ctx: ControlPlaneContext, *, bundle_id: str | None = None):
        return self._read_only(lambda m: m.get_bundle(ctx, bundle_id=bundle_id))

    def decide(self, ctx: ControlPlaneContext, **kwargs: Any):
        return self._txn(lambda m: m.decide(ctx, **kwargs))

    def set_rule(self, hook: str, effect: str, **kwargs: Any) -> None:
        self._txn(lambda m: m.set_rule(hook, effect, **kwargs))


class SQLModelApprovalStore(_SnapshotBackedStore):
    kind = "approvals"

    def _empty(self) -> MemoryApprovalStore:
        return MemoryApprovalStore()

    def _dump(self, mem: MemoryApprovalStore) -> dict[str, Any]:
        return {
            "approvals": {
                f"{t}|{w}|{aid}": v.to_dict()
                for (t, w, aid), v in mem._approvals.items()
            }
        }

    def _load(self, payload: Mapping[str, Any]) -> MemoryApprovalStore:
        mem = MemoryApprovalStore()
        for key, raw in dict(payload.get("approvals") or {}).items():
            t, w, aid = str(key).split("|", 2)
            decisions = tuple(
                ApprovalDecisionRecord(
                    decision_id=str(d["decision_id"]),
                    approval_id=str(d["approval_id"]),
                    effect=d["effect"],
                    actor_subject=str(d["actor_subject"]),
                    actor_issuer=d.get("actor_issuer"),
                    created_at=datetime.fromisoformat(str(d["created_at"]))
                    if d.get("created_at")
                    else datetime.now(UTC),
                    reason=d.get("reason"),
                    metadata=dict(d.get("metadata") or {}),
                )
                for d in raw.get("decisions") or ()
            )
            mem._approvals[(t, w, aid)] = ApprovalRequest(
                approval_id=str(raw["approval_id"]),
                tenant_id=str(raw["tenant_id"]),
                workspace_id=str(raw["workspace_id"]),
                hook=str(raw["hook"]),
                plan_fingerprint=str(raw["plan_fingerprint"]),
                policy_fingerprint=str(raw["policy_fingerprint"]),
                revision_id=raw.get("revision_id"),
                requester_subject=str(raw["requester_subject"]),
                requester_issuer=raw.get("requester_issuer"),
                status=raw.get("status") or "pending",
                expires_at=datetime.fromisoformat(str(raw["expires_at"]))
                if raw.get("expires_at")
                else None,
                created_at=datetime.fromisoformat(str(raw["created_at"]))
                if raw.get("created_at")
                else datetime.now(UTC),
                decided_at=datetime.fromisoformat(str(raw["decided_at"]))
                if raw.get("decided_at")
                else None,
                decisions=decisions,
                metadata=dict(raw.get("metadata") or {}),
            )
        return mem

    def create(self, ctx: ControlPlaneContext, **kwargs: Any):
        return self._txn(lambda m: m.create(ctx, **kwargs))

    def get(self, ctx: ControlPlaneContext, **kwargs: Any):
        return self._read_only(lambda m: m.get(ctx, **kwargs))

    def decide(self, ctx: ControlPlaneContext, **kwargs: Any):
        return self._txn(lambda m: m.decide(ctx, **kwargs))

    def revoke(self, ctx: ControlPlaneContext, **kwargs: Any):
        return self._txn(lambda m: m.revoke(ctx, **kwargs))

    def is_satisfied(self, ctx: ControlPlaneContext, **kwargs: Any) -> bool:
        return self._read_only(lambda m: m.is_satisfied(ctx, **kwargs))


class SQLModelQuotaProvider(_SnapshotBackedStore):
    kind = "quotas"

    def _empty(self) -> MemoryQuotaProvider:
        return MemoryQuotaProvider()

    def _dump(self, mem: MemoryQuotaProvider) -> dict[str, Any]:
        return {
            "unavailable": bool(mem.unavailable),
            "default_limits": dict(mem.default_limits),
            "weights": {f"{t}|{w}": wt for (t, w), wt in mem.weights.items()},
            "states": {f"{t}|{w}": s.to_dict() for (t, w), s in mem._states.items()},
            "rr_cursor": int(mem._rr_cursor),
            "shared_pressure": bool(getattr(mem, "shared_pressure", False)),
        }

    def _load(self, payload: Mapping[str, Any]) -> MemoryQuotaProvider:
        mem = MemoryQuotaProvider(unavailable=bool(payload.get("unavailable")))
        mem.default_limits.update(
            {
                str(k): int(v)
                for k, v in dict(payload.get("default_limits") or {}).items()
            }
        )
        for key, wt in dict(payload.get("weights") or {}).items():
            t, w = str(key).split("|", 1)
            mem.weights[(t, w)] = int(wt)
        for key, raw in dict(payload.get("states") or {}).items():
            t, w = str(key).split("|", 1)
            mem._states[(t, w)] = QuotaState(
                tenant_id=str(raw["tenant_id"]),
                workspace_id=str(raw["workspace_id"]),
                suspended=bool(raw.get("suspended")),
                contained=bool(raw.get("contained")),
                usage={str(k): int(v) for k, v in dict(raw.get("usage") or {}).items()},
                updated_at=datetime.fromisoformat(str(raw["updated_at"]))
                if raw.get("updated_at")
                else datetime.now(UTC),
            )
        mem._rr_cursor = int(payload.get("rr_cursor") or 0)
        mem.shared_pressure = bool(payload.get("shared_pressure"))
        return mem

    def require_available(self, ctx: ControlPlaneContext) -> None:
        return self._read_only(lambda m: m.require_available(ctx))

    def get_budget(self, ctx: ControlPlaneContext, **kwargs: Any):
        return self._read_only(lambda m: m.get_budget(ctx, **kwargs))

    def get_state(self, ctx: ControlPlaneContext):
        return self._read_only(lambda m: m.get_state(ctx))

    def admit(self, ctx: ControlPlaneContext, **kwargs: Any):
        return self._txn(lambda m: m.admit(ctx, **kwargs))

    def release(self, ctx: ControlPlaneContext, **kwargs: Any):
        return self._txn(lambda m: m.release(ctx, **kwargs))

    def set_suspended(self, ctx: ControlPlaneContext, **kwargs: Any):
        return self._txn(lambda m: m.set_suspended(ctx, **kwargs))

    def set_contained(self, ctx: ControlPlaneContext, **kwargs: Any):
        return self._txn(lambda m: m.set_contained(ctx, **kwargs))


class SQLModelErasureStore(_SnapshotBackedStore):
    kind = "erasure"

    def _empty(self) -> MemoryErasureStore:
        return MemoryErasureStore()

    def _dump(self, mem: MemoryErasureStore) -> dict[str, Any]:
        return {
            "requests": {
                f"{t}|{w}|{rid}": v.to_dict()
                for (t, w, rid), v in mem._requests.items()
            },
            "plans": {
                f"{t}|{w}|{pid}": v.to_dict() for (t, w, pid), v in mem._plans.items()
            },
            "reports": {
                f"{t}|{w}|{rid}": v.to_dict() for (t, w, rid), v in mem._reports.items()
            },
            "plan_by_request": {
                f"{t}|{w}|{rid}": pid
                for (t, w, rid), pid in mem._plan_by_request.items()
            },
            "idempotency": {
                f"{t}|{w}|{k}": rid for (t, w, k), rid in mem._idempotency.items()
            },
        }

    def _load(self, payload: Mapping[str, Any]) -> MemoryErasureStore:
        mem = MemoryErasureStore()
        for key, raw in dict(payload.get("requests") or {}).items():
            t, w, rid = str(key).split("|", 2)
            mem._requests[(t, w, rid)] = ErasureRequest(
                request_id=str(raw["request_id"]),
                tenant_id=str(raw["tenant_id"]),
                workspace_id=str(raw["workspace_id"]),
                subject_key_fingerprint=str(raw["subject_key_fingerprint"]),
                field_paths=tuple(raw.get("field_paths") or ()),
                legal_hold=bool(raw.get("legal_hold")),
                status=raw.get("status") or "pending",
                created_at=datetime.fromisoformat(str(raw["created_at"]))
                if raw.get("created_at")
                else datetime.now(UTC),
                metadata=dict(raw.get("metadata") or {}),
            )
        for key, raw in dict(payload.get("plans") or {}).items():
            t, w, pid = str(key).split("|", 2)
            steps = tuple(
                ErasurePlanStep(
                    step_id=str(s["step_id"]),
                    provider_id=str(s["provider_id"]),
                    action=s["action"],
                    field_paths=tuple(s.get("field_paths") or ()),
                    supported=bool(s.get("supported")),
                    reason=s.get("reason"),
                )
                for s in raw.get("steps") or ()
            )
            mem._plans[(t, w, pid)] = ErasurePlan(
                plan_id=str(raw["plan_id"]),
                request_id=str(raw["request_id"]),
                steps=steps,
            )
        for key, raw in dict(payload.get("reports") or {}).items():
            t, w, rid = str(key).split("|", 2)
            results = tuple(
                ErasureStepResult(
                    step_id=str(r["step_id"]),
                    provider_id=str(r["provider_id"]),
                    status=r["status"],
                    proof_fingerprint=r.get("proof_fingerprint"),
                    reason=r.get("reason"),
                )
                for r in raw.get("results") or ()
            )
            mem._reports[(t, w, rid)] = ErasureReport(
                report_id=str(raw["report_id"]),
                request_id=str(raw["request_id"]),
                plan_id=str(raw["plan_id"]),
                status=raw["status"],
                results=results,
                reconciled=bool(raw.get("reconciled")),
            )
        for key, pid in dict(payload.get("plan_by_request") or {}).items():
            t, w, rid = str(key).split("|", 2)
            mem._plan_by_request[(t, w, rid)] = str(pid)
        for key, rid in dict(payload.get("idempotency") or {}).items():
            t, w, k = str(key).split("|", 2)
            mem._idempotency[(t, w, k)] = str(rid)
        return mem

    def create_request(self, ctx: ControlPlaneContext, **kwargs: Any):
        return self._txn(lambda m: m.create_request(ctx, **kwargs))

    def get_request(self, ctx: ControlPlaneContext, **kwargs: Any):
        return self._read_only(lambda m: m.get_request(ctx, **kwargs))

    def plan(self, ctx: ControlPlaneContext, **kwargs: Any):
        return self._txn(lambda m: m.plan(ctx, **kwargs))

    def execute(self, ctx: ControlPlaneContext, **kwargs: Any):
        return self._txn(lambda m: m.execute(ctx, **kwargs))

    def get_report(self, ctx: ControlPlaneContext, **kwargs: Any):
        return self._read_only(lambda m: m.get_report(ctx, **kwargs))


class SQLModelAttestationStore(_SnapshotBackedStore):
    kind = "attestations"

    def __init__(
        self,
        engine: Engine,
        *,
        store_id: str = "default",
        signing_secret: bytes,
    ) -> None:
        super().__init__(engine, store_id=store_id)
        self.signing_secret = signing_secret

    def _empty(self) -> MemoryAttestationStore:
        return MemoryAttestationStore(signing_secret=self.signing_secret)

    def _dump(self, mem: MemoryAttestationStore) -> dict[str, Any]:
        return {
            "attestations": {
                f"{t}|{w}|{aid}": v.to_dict()
                for (t, w, aid), v in mem._attestations.items()
            },
            "revoked": sorted(mem._revoked),
        }

    def _load(self, payload: Mapping[str, Any]) -> MemoryAttestationStore:
        mem = MemoryAttestationStore(signing_secret=self.signing_secret)
        for key, raw in dict(payload.get("attestations") or {}).items():
            t, w, aid = str(key).split("|", 2)
            created = raw.get("created_at")
            mem._attestations[(t, w, aid)] = Attestation(
                attestation_id=str(raw["attestation_id"]),
                kind=raw["kind"],
                subject_fingerprint=str(raw["subject_fingerprint"]),
                signature=str(raw["signature"]),
                signer_id=str(raw["signer_id"]),
                tenant_id=raw.get("tenant_id"),
                workspace_id=raw.get("workspace_id"),
                environment=raw.get("environment"),
                sbom_digest=raw.get("sbom_digest"),
                created_at=datetime.fromisoformat(str(created))
                if created
                else datetime.now(UTC),
                metadata=dict(raw.get("metadata") or {}),
            )
        mem._revoked.update(str(x) for x in payload.get("revoked") or ())
        return mem

    def put(self, ctx: ControlPlaneContext, **kwargs: Any):
        return self._txn(lambda m: m.put(ctx, **kwargs))

    def revoke(self, ctx: ControlPlaneContext, **kwargs: Any) -> None:
        self._txn(lambda m: m.revoke(ctx, **kwargs))

    def verify_plan(self, ctx: ControlPlaneContext, **kwargs: Any):
        return self._read_only(lambda m: m.verify_plan(ctx, **kwargs))

    def verify_schema_observation(self, ctx: ControlPlaneContext, **kwargs: Any):
        return self._read_only(lambda m: m.verify_schema_observation(ctx, **kwargs))


class SQLModelObjectiveStore(_SnapshotBackedStore):
    kind = "objectives"

    def _empty(self) -> MemoryObjectiveStore:
        return MemoryObjectiveStore()

    def _dump(self, mem: MemoryObjectiveStore) -> dict[str, Any]:
        return {
            "objectives": {
                f"{t}|{w}|{oid}": v.to_dict()
                for (t, w, oid), v in mem._objectives.items()
            },
            "evaluations": {
                f"{t}|{w}|{eid}": v.to_dict()
                for (t, w, eid), v in mem._evaluations.items()
            },
            "by_objective": {
                f"{t}|{w}|{oid}": list(ids)
                for (t, w, oid), ids in mem._by_objective.items()
            },
        }

    def _load(self, payload: Mapping[str, Any]) -> MemoryObjectiveStore:
        mem = MemoryObjectiveStore()
        for key, raw in dict(payload.get("objectives") or {}).items():
            t, w, oid = str(key).split("|", 2)
            fixed = raw.get("fixed_time")
            mem._objectives[(t, w, oid)] = DeliveryObjective(
                objective_id=str(raw["objective_id"]),
                tenant_id=str(raw["tenant_id"]),
                workspace_id=str(raw["workspace_id"]),
                pipeline_id=str(raw["pipeline_id"]),
                step_id=raw.get("step_id"),
                version=str(raw.get("version") or "1"),
                reference=raw.get("reference") or "scheduled",
                warning_after_seconds=int(raw["warning_after_seconds"]),
                hard_after_seconds=int(raw["hard_after_seconds"]),
                grace_seconds=int(raw.get("grace_seconds") or 0),
                calendar=str(raw.get("calendar") or "UTC"),
                owner=raw.get("owner"),
                severity=raw.get("severity") or "warning",
                fixed_time=datetime.fromisoformat(str(fixed)) if fixed else None,
                metadata=dict(raw.get("metadata") or {}),
            )
        for key, raw in dict(payload.get("evaluations") or {}).items():
            t, w, eid = str(key).split("|", 2)
            mem._evaluations[(t, w, eid)] = ObjectiveEvaluation(
                evaluation_id=str(raw["evaluation_id"]),
                objective_id=str(raw["objective_id"]),
                state=raw["state"],
                reference_at=datetime.fromisoformat(str(raw["reference_at"])),
                evaluated_at=datetime.fromisoformat(str(raw["evaluated_at"])),
                dedupe_key=str(raw["dedupe_key"]),
                submission_id=raw.get("submission_id"),
                reason=raw.get("reason"),
                metadata=dict(raw.get("metadata") or {}),
            )
        for key, ids in dict(payload.get("by_objective") or {}).items():
            t, w, oid = str(key).split("|", 2)
            mem._by_objective[(t, w, oid)] = [str(x) for x in ids]
        return mem

    def upsert_objective(self, ctx: ControlPlaneContext, **kwargs: Any):
        return self._txn(lambda m: m.upsert_objective(ctx, **kwargs))

    def get_objective(self, ctx: ControlPlaneContext, **kwargs: Any):
        return self._read_only(lambda m: m.get_objective(ctx, **kwargs))

    def evaluate(self, ctx: ControlPlaneContext, **kwargs: Any):
        return self._txn(lambda m: m.evaluate(ctx, **kwargs))

    def acknowledge(self, ctx: ControlPlaneContext, **kwargs: Any):
        return self._txn(lambda m: m.acknowledge(ctx, **kwargs))

    def route_notification(self, ctx: ControlPlaneContext, **kwargs: Any):
        return self._txn(lambda m: m.route_notification(ctx, **kwargs))

    def list_evaluations(self, ctx: ControlPlaneContext, **kwargs: Any):
        return self._read_only(lambda m: m.list_evaluations(ctx, **kwargs))


__all__ = [
    "CP4_TABLES",
    "SQLModelApprovalStore",
    "SQLModelAttestationStore",
    "SQLModelAuditEvidenceStore",
    "SQLModelErasureStore",
    "SQLModelObjectiveStore",
    "SQLModelPolicyProvider",
    "SQLModelQuotaProvider",
    "create_cp4_tables",
]
