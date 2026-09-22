from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts import check_inference_0_55 as checker


def _campaign_fixture(root: Path, *, commit: str, tree: str) -> None:
    gates = root / "gates"
    gates.mkdir()
    results: dict[str, str] = {}
    for gate in checker.GATES:
        result_path = gates / f"{gate}.json"
        result_path.write_text(
            json.dumps(
                {
                    "schema": "etlantic.inference-gate-result/1",
                    "phase": "0.55",
                    "gate": gate,
                    "result": "pass",
                    "commit": commit,
                    "tree": tree,
                    "dirty": False,
                }
            ),
            encoding="utf-8",
        )
        results[gate] = f"gates/{gate}.json"
    (root / "index.json").write_text(
        json.dumps(
            {
                "schema": "etlantic.inference-gate-campaign/1",
                "phase": "0.55",
                "evaluated_commit": commit,
                "evaluated_tree": tree,
                "dirty": False,
                "required_gates": list(checker.GATES),
                "results": results,
                "result": "pass",
            }
        ),
        encoding="utf-8",
    )


def test_pending_capability_rows_are_rejected() -> None:
    matrix = {
        "schema": "etlantic.inference-capability-matrix/1",
        "entries": [
            {
                "surface": "records",
                "kind": "source",
                "state": "pending-qualification",
                "evidence": None,
            }
        ],
    }

    with pytest.raises(ValueError, match="silently pending"):
        checker._validate_capability_matrix(matrix)


def test_gate_verification_rejects_a_stale_result(tmp_path, monkeypatch) -> None:
    commit = "a" * 40
    tree = "b" * 40
    _campaign_fixture(tmp_path, commit=commit, tree=tree)
    stale = tmp_path / "gates" / "wire_security.json"
    stale_payload = json.loads(stale.read_text(encoding="utf-8"))
    stale_payload["commit"] = "d" * 40
    stale.write_text(json.dumps(stale_payload), encoding="utf-8")
    monkeypatch.setattr(
        checker,
        "_git_identity",
        lambda: {"commit": commit, "tree": tree, "dirty": False},
    )
    monkeypatch.setattr(checker, "_is_ancestor", lambda *_: True)
    monkeypatch.setattr(checker, "_validate_manifest", lambda *_: None)

    with pytest.raises(ValueError, match="stale or mismatched"):
        checker._verify_campaign(tmp_path, {}, {}, {})


def test_gate_verification_rejects_missing_required_result(
    tmp_path, monkeypatch
) -> None:
    commit = "a" * 40
    tree = "b" * 40
    _campaign_fixture(tmp_path, commit=commit, tree=tree)
    campaign = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    campaign["results"].pop("race_tests")
    (tmp_path / "index.json").write_text(json.dumps(campaign), encoding="utf-8")
    monkeypatch.setattr(
        checker,
        "_git_identity",
        lambda: {"commit": commit, "tree": tree, "dirty": False},
    )
    monkeypatch.setattr(checker, "_is_ancestor", lambda *_: True)
    monkeypatch.setattr(checker, "_validate_manifest", lambda *_: None)

    with pytest.raises(ValueError, match="missing a required gate"):
        checker._verify_campaign(tmp_path, {}, {}, {})


def test_gate_campaign_records_are_row_free(tmp_path) -> None:
    commit = "a" * 40
    tree = "b" * 40
    _campaign_fixture(tmp_path, commit=commit, tree=tree)

    for path in tmp_path.rglob("*.json"):
        checker._load(path)
