"""Closed, read-only validation of candidate observations and graduation data."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

OBSERVATION_SCHEMA = "etlantic.adaptive_observation/1"
INDEX_SCHEMA = "etlantic.adaptive_evidence_index/1"
CATALOGUE_SCHEMA = "etlantic.adaptive_case_catalogue/1"
CELLS = {
    (system, minor)
    for system in ("Linux", "Darwin", "Windows")
    for minor in ("3.11", "3.12", "3.13")
}
BACKENDS = {"polars": "1.42.1", "pandas": "2.3.3", "pyarrow": "25.0.0"}


def digest(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _closed(value: Any, fields: set[str]) -> None:
    if type(value) is not dict or set(value) != fields:
        raise ValueError("Invalid closed adaptive evidence record")


def _hash(value: Any) -> None:
    if type(value) is not str or re.fullmatch(r"sha256:[0-9a-f]{64}", value) is None:
        raise ValueError("Invalid adaptive content digest")


def _identity(value: Any) -> None:
    if (
        type(value) is not str
        or not value
        or len(value) > 4096
        or any(ord(c) < 32 for c in value)
    ):
        raise ValueError("Invalid adaptive evidence identity")


def _read_bytes(path: Path) -> bytes:
    with path.open("rb") as handle:
        content = handle.read(16 * 1024 * 1024 + 1)
    if len(content) > 16 * 1024 * 1024:
        raise ValueError("Adaptive evidence exceeds read bound")
    return content


def _load_snapshot(path: Path) -> tuple[dict[str, Any], str]:
    """Parse and hash one bounded immutable read, never separate file versions."""
    content = _read_bytes(path)

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate adaptive evidence key")
            result[key] = value
        return result

    value = json.loads(content.decode("utf-8"), object_pairs_hook=pairs)
    if type(value) is not dict:
        raise ValueError("Invalid adaptive evidence document")
    return value, digest(content)


def load(path: Path) -> dict[str, Any]:
    return _load_snapshot(path)[0]


def bounded_digest(path: Path) -> str:
    return digest(_read_bytes(path))


def validate_category(record, catalogue, parent, *, name, source):
    _closed(record, {"schema", "phase", "source", "category", "cases", "result"})
    outcomes = {case["id"]: case["status"] for case in parent["cases"]}
    expected = [
        {"id": identity, "status": outcomes[identity]}
        for identity in catalogue["categories"][name]
    ]
    if (
        record["schema"] != "etlantic.adaptive_category_observation/1"
        or record["phase"] != "0.54"
        or record["source"] != source
        or record["category"] != name
        or record["cases"] != expected
        or record["result"] != "pass"
    ):
        raise ValueError("Invalid adaptive category semantics")


def validate_catalogue(value: dict[str, Any]) -> set[str]:
    _closed(
        value,
        {"schema", "phase", "cases", "local_ac", "program_ac", "rows", "categories"},
    )
    if value["schema"] != CATALOGUE_SCHEMA or value["phase"] != "0.54":
        raise ValueError("Unknown adaptive catalogue schema")
    cases = value["cases"]
    if type(cases) is not list or not cases or len(cases) > 10000:
        raise ValueError("Invalid adaptive frozen cases")
    for case in cases:
        _identity(case)
        if not case.startswith("tests/") or "::test_" not in case:
            raise ValueError("Invalid full pytest identity")
    if len(set(cases)) != len(cases) or cases != sorted(cases):
        raise ValueError("Duplicate or unordered frozen cases")
    identities = set(cases)
    for kind in ("local_ac", "program_ac"):
        if type(value[kind]) is not dict or set(value[kind]) != {
            f"AC-{i:03}" for i in range(1, 25)
        }:
            raise ValueError("Incomplete adaptive AC mapping")
        for references in value[kind].values():
            if (
                type(references) is not list
                or not references
                or len(set(references)) != len(references)
                or not set(references) <= identities
            ):
                raise ValueError("Invalid adaptive AC case references")
    if type(value["rows"]) is not dict or len(value["rows"]) != 14:
        raise ValueError("Incomplete adaptive row catalogue")
    for row, references in value["rows"].items():
        _identity(row)
        if (
            type(references) is not list
            or not references
            or not set(references) <= identities
        ):
            raise ValueError("Invalid adaptive row case references")
    if type(value["categories"]) is not dict or not value["categories"]:
        raise ValueError("Missing adaptive category reports")
    for name, references in value["categories"].items():
        if (
            type(name) is not str
            or re.fullmatch(r"[a-z0-9_]+\.json", name) is None
            or name in {"observation.json", "index.json"}
            or type(references) is not list
            or not references
            or not set(references) <= identities
        ):
            raise ValueError("Invalid adaptive category mapping")
    return identities


def validate_observation(
    record: dict[str, Any], catalogue: dict[str, Any], *, source: str
) -> tuple[str, str]:
    expected = validate_catalogue(catalogue)
    _closed(
        record,
        {
            "schema",
            "phase",
            "started_at",
            "finished_at",
            "commit",
            "tree",
            "dirty",
            "source_before",
            "source_after",
            "environment",
            "command",
            "ci",
            "returncode",
            "result",
            "collection_failed",
            "cases",
            "cases_sha256",
            "catalogue_sha256",
            "artifacts",
        },
    )
    if record["schema"] != OBSERVATION_SCHEMA or record["phase"] != "0.54":
        raise ValueError("Unknown adaptive observation schema")
    _hash(source)
    if record["source_before"] != source or record["source_after"] != source:
        raise ValueError("Changed or cross-source adaptive observation")
    times = []
    for field in ("started_at", "finished_at"):
        parsed = datetime.fromisoformat(record[field])
        if parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
            raise ValueError("Adaptive observation requires actual UTC time")
        times.append(parsed)
    if times[1] < times[0]:
        raise ValueError("Invalid adaptive observation time order")
    for field in ("commit", "tree"):
        if (
            type(record[field]) is not str
            or re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", record[field]) is None
        ):
            raise ValueError("Invalid adaptive Git provenance")
    if (
        type(record["dirty"]) is not bool
        or type(record["returncode"]) is not int
        or record["returncode"] != 0
        or record["result"] != "pass"
        or record["collection_failed"] is not False
    ):
        raise ValueError("Nonpassing adaptive observation")
    cases = record["cases"]
    if type(cases) is not list or len(cases) != len(expected):
        raise ValueError("Missing or duplicated adaptive cases")
    for case in cases:
        _closed(case, {"id", "status"})
        if case["status"] != "pass" or type(case["id"]) is not str:
            raise ValueError("Unexecuted or failing adaptive case")
    if [case["id"] for case in cases] != sorted(expected):
        raise ValueError("Incomplete exact adaptive case coverage")
    if record["cases_sha256"] != digest(
        json.dumps(cases, sort_keys=True).encode()
    ) or record["catalogue_sha256"] != digest(
        json.dumps(catalogue, sort_keys=True, separators=(",", ":")).encode()
    ):
        raise ValueError("Adaptive case/catalogue hash mismatch")
    environment = record["environment"]
    _closed(environment, {"os", "architecture", "python", "dependencies"})
    _identity(environment["architecture"])
    if (
        type(environment["python"]) is not str
        or re.fullmatch(r"3\.(11|12|13)\.\d+", environment["python"]) is None
    ):
        raise ValueError("Unsupported adaptive Python observation")
    cell = (environment["os"], ".".join(environment["python"].split(".")[:2]))
    if cell not in CELLS:
        raise ValueError("Unsupported adaptive environment cell")
    dependencies = environment["dependencies"]
    _closed(dependencies, {"etlantic", "etlantic-polars", "etlantic-pandas", *BACKENDS})
    for name, pinned in {
        **BACKENDS,
        **{
            name: "0.54.0"
            for name in ("etlantic", "etlantic-polars", "etlantic-pandas")
        },
    }.items():
        if dependencies[name] != pinned:
            raise ValueError("Adaptive observed package pin mismatch")
    if type(record["command"]) is not list or not record["command"]:
        raise ValueError("Missing adaptive execution command")
    for argument in record["command"]:
        _identity(argument)
    _closed(
        record["ci"],
        {"GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_JOB", "GITHUB_SHA"},
    )
    for item in record["ci"].values():
        if item is not None:
            _identity(item)
    if type(record["artifacts"]) is not dict or set(record["artifacts"]) != set(
        catalogue["categories"]
    ):
        raise ValueError("Incomplete adaptive category artifacts")
    for artifact_hash in record["artifacts"].values():
        _hash(artifact_hash)
    return cell


def _relative(base: Path, location: Any) -> Path:
    _identity(location)
    relative = Path(location)
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or "\\" in location
        or ":" in location
    ):
        raise ValueError("Escaping adaptive artifact location")
    resolved = (base / relative).resolve(strict=True)
    if not resolved.is_relative_to(base.resolve()):
        raise ValueError("Escaping adaptive artifact handle")
    return resolved


def _verify_index_snapshot(
    path: Path, catalogue: dict[str, Any], *, source: str
) -> tuple[dict[str, Any], str, list[dict[str, Any]]]:
    path = path.resolve(strict=True)
    _hash(source)
    validate_catalogue(catalogue)
    index, index_digest = _load_snapshot(path)
    _closed(index, {"schema", "phase", "source", "catalogue_sha256", "observations"})
    if (
        index["schema"] != INDEX_SCHEMA
        or index["phase"] != "0.54"
        or index["source"] != source
    ):
        raise ValueError("Invalid adaptive evidence index")
    if index["catalogue_sha256"] != digest(
        json.dumps(catalogue, sort_keys=True, separators=(",", ":")).encode()
    ):
        raise ValueError("Adaptive index catalogue mismatch")
    if type(index["observations"]) is not list or len(index["observations"]) != 9:
        raise ValueError("Adaptive qualification requires nine actual CI cells")
    cells = set()
    provenance = set()
    paths = set()
    records = []
    for reference in index["observations"]:
        _closed(reference, {"path", "sha256"})
        _hash(reference["sha256"])
        artifact = _relative(path.parent, reference["path"])
        record, record_digest = _load_snapshot(artifact)
        if artifact in paths or record_digest != reference["sha256"]:
            raise ValueError("Duplicate or tampered adaptive artifact")
        paths.add(artifact)
        cell = validate_observation(record, catalogue, source=source)
        for name, expected_hash in record["artifacts"].items():
            category = _relative(
                path.parent,
                (artifact.parent / name).relative_to(path.parent).as_posix(),
            )
            category_record, category_digest = _load_snapshot(category)
            if category_digest != expected_hash:
                raise ValueError("Tampered adaptive category artifact")
            validate_category(
                category_record, catalogue, record, name=name, source=source
            )
        ci = record["ci"]
        if (
            any(ci[name] is None for name in ci)
            or ci["GITHUB_SHA"] != record["commit"]
            or record["dirty"]
        ):
            raise ValueError("Missing or inconsistent actual CI provenance")
        if cell in cells:
            raise ValueError("Duplicated adaptive environment cell")
        cells.add(cell)
        provenance.add(
            (
                record["commit"],
                record["tree"],
                ci["GITHUB_RUN_ID"],
                ci["GITHUB_RUN_ATTEMPT"],
            )
        )
        records.append(record)
    if cells != CELLS or len(provenance) != 1:
        raise ValueError("Incomplete or cross-candidate adaptive CI matrix")
    return index, index_digest, records


def verify_index(
    path: Path, catalogue: dict[str, Any], *, source: str
) -> dict[str, Any]:
    return _verify_index_snapshot(path, catalogue, source=source)[0]


def verify_qualification(path: Path, catalogue: dict[str, Any], *, source: str):
    """Verify executed evidence; this grants no review or approval authority."""
    from etlantic.runtime.adaptive_graduation import VerifiedQualification

    path = path.resolve(strict=True)
    index, index_digest, records = _verify_index_snapshot(
        path, catalogue, source=source
    )
    row_refs = {row: set() for row in catalogue["rows"]}
    for reference, record in zip(index["observations"], records, strict=True):
        for row, cases in catalogue["rows"].items():
            row_refs[row].add(reference["sha256"])
            for name, mapped in catalogue["categories"].items():
                if set(cases) <= set(mapped):
                    row_refs[row].add(record["artifacts"][name])
    return VerifiedQualification(
        source,
        index_digest,
        {row: frozenset(refs) for row, refs in row_refs.items()},
    )


def aggregate(
    directory: Path, catalogue: dict[str, Any], *, source: str
) -> dict[str, Any]:
    """Build an integrity index only. Never create a graduation decision."""
    directory = directory.resolve(strict=True)
    paths = sorted(
        directory.rglob("observation.json"),
        key=lambda path: path.relative_to(directory).as_posix(),
    )
    references = [
        {
            "path": path.relative_to(directory).as_posix(),
            "sha256": bounded_digest(
                _relative(directory, path.relative_to(directory).as_posix())
            ),
        }
        for path in paths
    ]
    index = {
        "schema": INDEX_SCHEMA,
        "phase": "0.54",
        "source": source,
        "catalogue_sha256": digest(
            json.dumps(catalogue, sort_keys=True, separators=(",", ":")).encode()
        ),
        "observations": references,
    }
    return index


def category_records(
    catalogue: dict[str, Any], cases: list[dict[str, str]], *, source: str
) -> dict[str, bytes]:
    outcomes = {case["id"]: case["status"] for case in cases}
    result = {}
    for name, references in catalogue["categories"].items():
        selected = [
            {"id": identity, "status": outcomes.get(identity, "missing")}
            for identity in references
        ]
        record = {
            "schema": "etlantic.adaptive_category_observation/1",
            "phase": "0.54",
            "source": source,
            "category": name,
            "cases": selected,
            "result": "pass"
            if all(c["status"] == "pass" for c in selected)
            else "fail",
        }
        result[name] = (json.dumps(record, sort_keys=True, indent=2) + "\n").encode()
    return result
