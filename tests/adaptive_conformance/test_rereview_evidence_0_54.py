"""Synthetic validation regressions; these fixtures are never remote proof."""

import json
from pathlib import Path

import pytest
from scripts.adaptive_0_54_evidence import (
    bounded_digest,
    digest,
    load,
    verify_index,
    verify_qualification,
)
from tests.adaptive_conformance.test_evidence_0_54 import SOURCE, catalogue, matrix
from tests.adaptive_conformance.test_graduation_0_54 import go_decision, records

from etlantic.runtime.adaptive_graduation import validate_candidate, validate_graduation


def test_relative_index(tmp_path, monkeypatch):
    path, _ = matrix(tmp_path)
    monkeypatch.chdir(tmp_path.parent)
    verify_index(Path(tmp_path.name) / path.name, catalogue(), source=SOURCE)


@pytest.mark.parametrize("kind", ["index", "observation", "category"])
def test_qualification_uses_exact_verified_snapshots(tmp_path, monkeypatch, kind):
    import scripts.adaptive_0_54_evidence as evidence

    path, index = matrix(tmp_path)
    original_index_digest = bounded_digest(path)
    observation_path = path.parent / index["observations"][0]["path"]
    parent = json.loads(observation_path.read_text())
    category_path = observation_path.parent / next(iter(parent["artifacts"]))
    target = {
        "index": path,
        "observation": observation_path,
        "category": category_path,
    }[kind].resolve()
    original_load = evidence._load_snapshot
    reads = []

    def replace_after_read(location):
        snapshot = original_load(location)
        reads.append(location)
        if location == target:
            location.write_bytes(b"{}")
        return snapshot

    monkeypatch.setattr(evidence, "_load_snapshot", replace_after_read)
    verified = verify_qualification(path, catalogue(), source=SOURCE)
    assert reads.count(target) == 1
    assert target.read_bytes() == b"{}"
    assert verified.evidence == original_index_digest
    expected_refs = {reference["sha256"] for reference in index["observations"]}
    expected_refs.update(parent["artifacts"].values())
    assert all(refs == expected_refs for refs in verified.row_refs.values())
    # Later use of changed files must fail; never qualify the replacement bytes.
    with pytest.raises(ValueError):
        verify_qualification(path, catalogue(), source=SOURCE)


def test_hash_read_is_bounded(tmp_path):
    path = tmp_path / "oversized.json"
    with path.open("wb") as handle:
        handle.truncate(16 * 1024 * 1024 + 1)
    for reader in (bounded_digest, load):
        with pytest.raises(ValueError, match="bound"):
            reader(path)


@pytest.mark.parametrize(
    "mutation", ["empty", "source", "category", "status", "result", "unknown", "id"]
)
def test_rehashed_category_semantics(tmp_path, mutation):
    path, index = matrix(tmp_path)
    ref = index["observations"][0]
    observation_path = path.parent / ref["path"]
    parent = json.loads(observation_path.read_text())
    name = next(iter(parent["artifacts"]))
    category_path = observation_path.parent / name
    category = json.loads(category_path.read_text())
    if mutation == "empty":
        category["cases"] = []
    elif mutation in {"status", "id"}:
        category["cases"][0][mutation] = "wrong"
    else:
        category[mutation] = "wrong"
    category_path.write_text(json.dumps(category))
    parent["artifacts"][name] = digest(category_path.read_bytes())
    observation_path.write_text(json.dumps(parent))
    ref["sha256"] = digest(observation_path.read_bytes())
    path.write_text(json.dumps(index))
    with pytest.raises(ValueError):
        verify_index(path, catalogue(), source=SOURCE)


def test_windows_source_order_uses_posix_relative_paths(tmp_path, monkeypatch):
    from pathlib import PureWindowsPath

    from scripts.check_adaptive_0_54 import source_revision

    # Native Windows ordering differs for a directory separator versus '.'.
    paths = [PureWindowsPath("root/src/a/z.py"), PureWindowsPath("root/src/a.py")]
    assert sorted(paths) != sorted(
        paths, key=lambda p: p.relative_to("root").as_posix()
    )
    seen = []

    def read(path):
        seen.append(path.relative_to(tmp_path).as_posix())
        return b"synthetic source"

    (tmp_path / "src/a").mkdir(parents=True)
    (tmp_path / "src/a.py").touch()
    (tmp_path / "src/a/z.py").touch()
    monkeypatch.setattr(Path, "read_bytes", read)
    source_revision(tmp_path)
    assert seen == sorted(seen)


def test_row_cannot_borrow_unrelated_category(tmp_path):
    candidate, decision = go_decision()
    cat = catalogue()
    other = "tests/example.py::test_other"
    cat["cases"].append(other)
    cat["cases"].sort()
    cat["categories"]["unrelated.json"] = [other]
    cat["rows"] = {row: [cat["cases"][0]] for row in candidate["rows"]}
    path, index = matrix(tmp_path, cat=cat)
    verified = verify_qualification(path, cat, source=SOURCE)
    decision.update(source=verified.source, evidence=verified.evidence)
    for identity, row in decision["rows"].items():
        row["evidence_refs"] = [sorted(verified.row_refs[identity])[0]]
    parent = json.loads((path.parent / index["observations"][0]["path"]).read_text())
    next(iter(decision["rows"].values()))["evidence_refs"] = [
        parent["artifacts"]["unrelated.json"]
    ]
    with pytest.raises(ValueError, match="verified"):
        validate_graduation(
            decision, rows=set(candidate["rows"]), qualification=verified
        )


@pytest.mark.parametrize("identity", list(records()[0]["rows"]))
@pytest.mark.parametrize(
    "mutation", ["missing", "wrong", "extra", "operations", "policies"]
)
def test_exact_candidate_dependencies(identity, mutation):
    candidate, decision = records()
    row = candidate["rows"][identity]
    if mutation == "missing":
        row["versions"].pop(next(reversed(row["versions"])))
    elif mutation == "wrong":
        row["versions"]["etlantic"] = "0.53.0"
    elif mutation == "extra":
        row["versions"]["unexpected"] = "0.54.0"
    else:
        row[mutation].append("unexpected")
    with pytest.raises(ValueError):
        validate_candidate(candidate, decision)


def test_experimental_go_requires_proof():
    candidate, decision = go_decision()
    for row in decision["rows"].values():
        row["evidence_refs"] = []
    with pytest.raises(ValueError, match="verified"):
        validate_graduation(decision, rows=set(candidate["rows"]))


@pytest.mark.parametrize("mutation", ["source", "evidence", "row-ref"])
def test_graduation_binding(tmp_path, mutation):
    candidate, decision = go_decision()
    cat = catalogue()
    cat["rows"] = {row: cat["cases"][:] for row in candidate["rows"]}
    path, _ = matrix(tmp_path, cat=cat)
    verified = verify_qualification(path, cat, source=SOURCE)
    decision.update(source=verified.source, evidence=verified.evidence)
    for identity, row in decision["rows"].items():
        row["evidence_refs"] = [sorted(verified.row_refs[identity])[0]]
    if mutation == "row-ref":
        next(iter(decision["rows"].values()))["evidence_refs"] = [verified.evidence]
    else:
        decision[mutation] = "sha256:" + "f" * 64
    with pytest.raises(ValueError, match="verified"):
        validate_graduation(
            decision, rows=set(candidate["rows"]), qualification=verified
        )
