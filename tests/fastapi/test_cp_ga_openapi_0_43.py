"""OpenAPI stability snapshot for CP-GA (covers CP1-CP4 operationIds)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("etlantic_fastapi")
pytest.importorskip("httpx")

from etlantic.control_plane import (
    MemoryApprovalStore,
    MemoryAttestationStore,
    MemoryAuditEvidenceStore,
    MemoryAuthorizer,
    MemoryDefinitionRepository,
    MemoryErasureStore,
    MemoryEventStore,
    MemoryObjectiveStore,
    MemoryPolicyProvider,
    MemoryQuotaProvider,
    MemorySubmissionStore,
)
from etlantic_fastapi import (
    ETLanticAPI,
    create_app,
    membership_context_factory,
    principal_from_header,
)

pytestmark = pytest.mark.fastapi

SNAPSHOT = Path(__file__).parent / "openapi_cp_ga_snapshot.json"

REQUIRED_GA_OPERATION_IDS = {
    "cp_health",
    "cp_ready",
    "cp_list_definitions",
    "cp_get_definition",
    "cp_submit_run",
    "cp_get_run",
    "cp_cancel_run",
    "cp_stream_run_events",
    "cp_get_run_report",
    "cp_get_run_lineage",
    "cp_list_reliability",
    "cp_policy_decide",
    "cp_erasure_create",
    "cp_audit_list",
    "cp_quota_admit",
    "cp_objective_put",
}


def _build_api() -> ETLanticAPI:
    return ETLanticAPI(
        authorizer=MemoryAuthorizer(),
        definitions=MemoryDefinitionRepository(),
        submissions=MemorySubmissionStore(),
        events=MemoryEventStore(),
        context_factory=membership_context_factory(
            {"alice": ("tenant-a", "ws-1", "development", "default")}
        ),
        principal_dependency=principal_from_header,
        policy=MemoryPolicyProvider(),
        approvals=MemoryApprovalStore(),
        quotas=MemoryQuotaProvider(),
        erasure=MemoryErasureStore(),
        audit=MemoryAuditEvidenceStore(),
        attestations=MemoryAttestationStore.for_tests(),
        objectives=MemoryObjectiveStore(),
    )


def test_openapi_cp_ga_operation_ids_stable() -> None:
    app = create_app(_build_api())
    schema = app.openapi()
    op_ids: set[str] = set()
    for path_item in schema["paths"].values():
        for method, op in path_item.items():
            if method.startswith("x-") or not isinstance(op, dict):
                continue
            op_id = op.get("operationId")
            assert op_id, f"missing operationId on {method}"
            op_ids.add(op_id)
    dump = {"openapi": schema.get("openapi"), "operationIds": sorted(op_ids)}
    if not SNAPSHOT.exists():
        SNAPSHOT.write_text(json.dumps(dump, indent=2) + "\n", encoding="utf-8")
    expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert dump["operationIds"] == expected["operationIds"]
    missing = REQUIRED_GA_OPERATION_IDS - op_ids
    assert not missing, f"missing GA operationIds: {sorted(missing)}"
