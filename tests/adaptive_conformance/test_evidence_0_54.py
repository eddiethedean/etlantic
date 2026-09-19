"""Synthetic envelopes exercise verification; none are retained as CI proof."""

import copy
import json

import pytest
from scripts.adaptive_0_54_evidence import (
    BACKENDS,
    CELLS,
    aggregate,
    category_records,
    digest,
    validate_catalogue,
    validate_observation,
    verify_index,
)

SOURCE = "sha256:" + "a" * 64


def catalogue():
    case = "tests/example.py::test_behavior[nullable-duplicate]"
    return {
        "schema": "etlantic.adaptive_case_catalogue/1",
        "phase": "0.54",
        "cases": [case],
        "local_ac": {f"AC-{i:03}": [case] for i in range(1, 25)},
        "program_ac": {f"AC-{i:03}": [case] for i in range(1, 25)},
        "rows": {f"test-row-{i}": [case] for i in range(14)},
        "categories": {"adaptive_runtime_conformance_0_51.json": [case]},
    }


def observation(system="Linux", minor="3.11", *, cat=None):
    cat = catalogue() if cat is None else cat
    cases = [{"id": case, "status": "pass"} for case in cat["cases"]]
    return {
        "schema": "etlantic.adaptive_observation/1",
        "phase": "0.54",
        "started_at": "2026-09-17T00:00:00+00:00",
        "finished_at": "2026-09-17T00:01:00+00:00",
        "commit": "b" * 40,
        "tree": "c" * 40,
        "dirty": False,
        "source_before": SOURCE,
        "source_after": SOURCE,
        "environment": {
            "os": system,
            "architecture": "test-architecture",
            "python": minor + ".0",
            "dependencies": {
                **BACKENDS,
                **dict.fromkeys(
                    ("etlantic", "etlantic-polars", "etlantic-pandas"), "0.54.0"
                ),
            },
        },
        "command": ["python", "scripts/check_adaptive_0_54.py"],
        "ci": {
            "GITHUB_RUN_ID": "test-run",
            "GITHUB_RUN_ATTEMPT": "1",
            "GITHUB_JOB": system + minor,
            "GITHUB_SHA": "b" * 40,
        },
        "returncode": 0,
        "result": "pass",
        "collection_failed": False,
        "cases": cases,
        "cases_sha256": digest(json.dumps(cases, sort_keys=True).encode()),
        "catalogue_sha256": digest(
            json.dumps(cat, sort_keys=True, separators=(",", ":")).encode()
        ),
        "artifacts": {
            name: digest(content)
            for name, content in category_records(cat, cases, source=SOURCE).items()
        },
    }


def matrix(tmp_path, *, cat=None):
    cat = catalogue() if cat is None else cat
    for system, minor in sorted(CELLS):
        path = tmp_path / (system + minor)
        path.mkdir()
        (path / "observation.json").write_text(
            json.dumps(observation(system, minor, cat=cat))
        )
        for name, content in category_records(
            cat, observation(system, minor, cat=cat)["cases"], source=SOURCE
        ).items():
            (path / name).write_bytes(content)
    index = aggregate(tmp_path, cat, source=SOURCE)
    path = tmp_path / "index.json"
    path.write_text(json.dumps(index))
    return path, index


def test_readonly_complete_matrix(tmp_path):
    path, _ = matrix(tmp_path)
    before = {p: p.read_bytes() for p in tmp_path.rglob("*.json")}
    verify_index(path, catalogue(), source=SOURCE)
    assert before == {p: p.read_bytes() for p in tmp_path.rglob("*.json")}
    assert not (tmp_path / "adaptive_graduation.json").exists()


def test_category_payload_tamper_rejected(tmp_path):
    path, index = matrix(tmp_path)
    folder = (tmp_path / index["observations"][0]["path"]).parent
    (folder / next(iter(catalogue()["categories"]))).write_bytes(b"{}")
    with pytest.raises(ValueError):
        verify_index(path, catalogue(), source=SOURCE)


def test_duplicate_json_keys_rejected(tmp_path):
    from scripts.adaptive_0_54_evidence import load

    path = tmp_path / "duplicate.json"
    path.write_text('{"schema":"one","schema":"two"}')
    with pytest.raises(ValueError, match="Duplicate"):
        load(path)


@pytest.mark.parametrize(
    "mutation",
    [
        "skip",
        "xfail",
        "xpass",
        "failed",
        "missing",
        "duplicate",
        "cross-source",
        "source-changed",
        "unknown",
        "old-time",
        "naive-time",
        "pin",
        "missing-backend",
        "case-hash",
        "catalogue-hash",
        "parameter-id",
        "collection-error",
        "nonzero",
        "true-returncode",
    ],
)
def test_observation_rejects_unqualified_data(mutation):
    record = observation()
    if mutation in {"skip", "xfail", "xpass", "failed"}:
        record["cases"][0]["status"] = mutation
    elif mutation == "missing":
        record["cases"] = []
    elif mutation == "duplicate":
        record["cases"] *= 2
    elif mutation in {"cross-source", "source-changed"}:
        record["source_after"] = "sha256:" + "d" * 64
    elif mutation == "unknown":
        record["schema"] = "unknown"
    elif mutation == "old-time":
        record["finished_at"] = "2025-01-01T00:00:00+00:00"
    elif mutation == "naive-time":
        record["started_at"] = "2026-09-17T00:00:00"
    elif mutation == "pin":
        record["environment"]["dependencies"]["polars"] = "0.0"
    elif mutation == "missing-backend":
        record["environment"]["dependencies"]["pyarrow"] = None
    elif mutation == "case-hash":
        record["cases_sha256"] = SOURCE
    elif mutation == "catalogue-hash":
        record["catalogue_sha256"] = SOURCE
    elif mutation == "parameter-id":
        record["cases"][0]["id"] = "tests/example.py::test_behavior"
    elif mutation == "collection-error":
        record["collection_failed"] = True
    else:
        record["returncode"] = True if mutation == "true-returncode" else 1
    with pytest.raises((ValueError, TypeError)):
        validate_observation(record, catalogue(), source=SOURCE)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing-cell",
        "duplicate-cell",
        "artifact-hash",
        "escape",
        "absolute",
        "ci-missing",
        "dirty",
        "different-commit",
        "different-run",
        "unknown-index",
        "cross-index-source",
    ],
)
def test_index_rejects_incomplete_or_tampered_matrix(tmp_path, mutation):
    path, index = matrix(tmp_path)
    if mutation == "missing-cell":
        index["observations"].pop()
    elif mutation == "artifact-hash":
        index["observations"][0]["sha256"] = SOURCE
    elif mutation in {"escape", "absolute"}:
        index["observations"][0]["path"] = (
            "../observation.json" if mutation == "escape" else "/observation.json"
        )
    elif mutation == "unknown-index":
        index["schema"] = "unknown"
    elif mutation == "cross-index-source":
        index["source"] = "sha256:" + "d" * 64
    else:
        reference = index["observations"][0]
        artifact = path.parent / reference["path"]
        record = json.loads(artifact.read_text())
        if mutation == "duplicate-cell":
            other = json.loads(
                (path.parent / index["observations"][1]["path"]).read_text()
            )
            record["environment"] = other["environment"]
        elif mutation == "ci-missing":
            record["ci"]["GITHUB_JOB"] = None
        elif mutation == "dirty":
            record["dirty"] = True
        elif mutation == "different-run":
            record["ci"]["GITHUB_RUN_ID"] = "other-test-run"
        else:
            record["commit"] = "d" * 40
            record["ci"]["GITHUB_SHA"] = record["commit"]
        artifact.write_text(json.dumps(record))
        reference["sha256"] = digest(artifact.read_bytes())
    path.write_text(json.dumps(index))
    with pytest.raises((ValueError, OSError)):
        verify_index(path, catalogue(), source=SOURCE)


@pytest.mark.parametrize("kind", ["local_ac", "program_ac", "rows"])
def test_every_ac_and_row_is_mapped(kind):
    cat = copy.deepcopy(catalogue())
    cat[kind].pop(next(iter(cat[kind])))
    with pytest.raises(ValueError):
        validate_catalogue(cat)
