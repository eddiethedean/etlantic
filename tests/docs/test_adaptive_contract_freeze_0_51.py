"""Phase 0.51 contract-freeze fixture invariants."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "docs/11_DEVELOPMENT/evidence/adaptive_0_51/contract_freeze_0_51.json"
ADR = ROOT / "docs/11_DEVELOPMENT/adr/ADR-025-ADAPTIVE-EXECUTION-AND-PHYSICAL-DAG.md"


def test_adaptive_contract_freeze_is_accepted_and_non_graduating() -> None:
    data = json.loads(CONTRACT.read_text(encoding="utf-8"))

    assert data["schema"] == "etlantic.adaptive-contract-freeze/1"
    assert data["status"] == "accepted"
    assert data["authority"]["adr"] == "ADR-025-ADAPTIVE-EXECUTION-AND-PHYSICAL-DAG"
    assert data["availability"]["adaptive_execution"] == (
        "unavailable_pending_later_increment_evidence"
    )
    assert data["availability"]["stored_adaptive_downgrade"] is False
    assert data["profile"]["default_execution_strategy"] == "explicit"
    assert data["portable_boundary"]["portable_candidates_only"] is True
    assert data["portable_boundary"]["native_bodies_are_adaptive_candidates"] is False
    assert data["consumer_contract"]["unsupported_consumer_diagnostic"] == "PMADP500"
    assert data["limits"] == {
        "selected_logical_nodes": 256,
        "eligible_placement_targets": 8,
        "candidates_per_node": 8,
        "candidate_records": 2048,
        "solver_state_expansions": 1_000_000,
        "explain_evidence_items_per_node_target": 8,
        "adaptive_explain_bytes": 4 * 1024 * 1024,
        "planner_transient_bytes": 256 * 1024 * 1024,
    }
    assert ADR.is_file()
