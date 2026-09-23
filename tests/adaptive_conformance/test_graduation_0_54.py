# pyright: reportArgumentType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportUnknownVariableType=false
"""Candidate integrity is not independent Available-row authority."""

import copy
import json
from importlib.resources import files

import pytest

from etlantic.runtime.adaptive_graduation import validate_candidate, validate_graduation
from etlantic.runtime.adaptive_support import candidate_bundle, qualification_bundle


def records():
    candidate, _ = candidate_bundle()
    decision = json.loads(
        files("etlantic.runtime").joinpath("adaptive_graduation.json").read_text()
    )
    return candidate, decision


def test_pending_candidate_and_historical_parser():
    candidate, decision = records()
    validate_candidate(candidate, decision)
    historical, _ = qualification_bundle()
    assert len(historical["rows"]) == 13
    assert len(candidate["rows"]) == 14
    assert all(row["maturity"] == "Experimental" for row in candidate["rows"].values())
    assert historical["rows"]["chain/1:local"]["versions"]["etlantic"] == "0.53.0"


@pytest.mark.parametrize(
    "mutation",
    ["unknown", "available", "selfapproval", "missing-row", "borrowed-evidence"],
)
def test_candidate_cannot_promote_itself(mutation):
    candidate, decision = records()
    candidate = copy.deepcopy(candidate)
    row = next(iter(candidate["rows"].values()))
    if mutation == "unknown":
        candidate["unknown"] = True
    elif mutation == "available":
        row["maturity"] = "Available"
    elif mutation == "selfapproval":
        candidate["graduation"] = "go"
    elif mutation == "missing-row":
        candidate["rows"].pop(next(iter(candidate["rows"])))
    else:
        row["evidence_refs"] = ["sha256:" + "a" * 64]
    with pytest.raises(ValueError):
        validate_candidate(candidate, decision)


def go_decision():
    candidate, decision = records()
    decision.update(
        decision="go",
        date="2026-09-17T00:00:00+00:00",
        reviewer="independent-test-reviewer",
        release_owner="test-owner",
        source="sha256:" + "a" * 64,
        evidence="sha256:" + "b" * 64,
        rollback_trigger="uncertain publication",
    )
    for row in decision["rows"].values():
        row.update(decision="go", evidence_refs=[decision["evidence"]])
    return candidate, decision


@pytest.mark.parametrize(
    "mutation",
    [
        "weakest",
        "pending",
        "no_go",
        "same-owner",
        "high-finding",
        "primary",
        "reverse",
        "undated",
        "no-proof",
    ],
)
def test_available_requires_independent_go_and_weakest_link(mutation):
    candidate, decision = go_decision()
    row = next(iter(decision["rows"].values()))
    row["maturity"] = "Available"
    row["components"] = dict.fromkeys(row["components"], "Available")
    if mutation == "weakest":
        row["components"]["source"] = "Experimental"
    elif mutation in {"pending", "no_go"}:
        decision["decision"] = mutation
    elif mutation == "same-owner":
        decision["reviewer"] = decision["release_owner"]
    elif mutation == "high-finding":
        decision["findings"] = [
            {"id": "test-high", "severity": "high", "resolved": False}
        ]
    elif mutation in {"primary", "reverse"}:
        key = (
            "scan-filter-project-chain/1:polars-pandas"
            if mutation == "primary"
            else "chain/1:pandas-polars"
        )
        decision["rows"][key]["decision"] = "no_go"
    elif mutation == "undated":
        decision["date"] = None
    else:
        row["evidence_refs"] = []
    with pytest.raises((ValueError, TypeError)):
        validate_graduation(decision, rows=set(candidate["rows"]))


def test_valid_review_projection_is_only_validated_not_written(tmp_path):
    from scripts.adaptive_0_54_evidence import verify_qualification
    from tests.adaptive_conformance.test_evidence_0_54 import SOURCE, catalogue, matrix

    candidate, decision = go_decision()
    cat = catalogue()
    cat["rows"] = {row: cat["cases"][:] for row in candidate["rows"]}
    path, _ = matrix(tmp_path, cat=cat)
    qualification = verify_qualification(path, cat, source=SOURCE)
    decision.update(source=qualification.source, evidence=qualification.evidence)
    for identity, row in decision["rows"].items():
        row["evidence_refs"] = [sorted(qualification.row_refs[identity])[0]]
    validate_graduation(
        decision, rows=set(candidate["rows"]), qualification=qualification
    )
    _, packaged = records()
    assert packaged["decision"] == "pending"
