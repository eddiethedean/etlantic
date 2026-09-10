#!/usr/bin/env python3
"""Fail-closed validation for the checked-in 0.50 portable contract artifacts."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/11_DEVELOPMENT/evidence/portable_0_50"
PROOF_AUTHORITY = ROOT / "scripts/portable_0_50_proof_authority.json"
REQUIRED = {
    "portable_evidence_index_0_50.json",
    "portable_baseline_contract_0_50.json",
    "portable_requirement_support_0_50.json",
    "portable_pushdown_contract_0_50.json",
    "portable_claim_coverage_0_50.json",
    "portable_local_conformance_0_50.json",
    "portable_polars_conformance_0_50.json",
    "portable_pandas_conformance_0_50.json",
    "portable_sql_conformance_0_50.json",
    "portable_pyspark_conformance_0_50.json",
    "portable_datafusion_conformance_0_50.json",
    "portable_duckdb_pushdown_0_50.json",
    "portable_cross_engine_0_50.json",
    "portable_canonical_pipeline_0_50.json",
    "portable_adaptive_handoff_0_50.json",
    "portable_dependency_security_0_50.json",
    "FINDINGS_0_50.md",
    "MIGRATION_0_49_TO_0_50.md",
    "WHATS_NEW_0_50.md",
}

EXPECTED_SCHEMAS = {
    "portable_evidence_index_0_50.json": "etlantic.portable-evidence-index/1",
    "portable_baseline_contract_0_50.json": "etlantic.portable-baseline/1",
    "portable_requirement_support_0_50.json": "etlantic.portable-requirement-support/1",
    "portable_pushdown_contract_0_50.json": "etlantic.portable-pushdown/1",
    "portable_claim_coverage_0_50.json": "etlantic.portable-claim-coverage/1",
    "portable_local_conformance_0_50.json": "etlantic.portable-conformance/1",
    "portable_polars_conformance_0_50.json": "etlantic.portable-conformance/1",
    "portable_pandas_conformance_0_50.json": "etlantic.portable-conformance/1",
    "portable_sql_conformance_0_50.json": "etlantic.portable-conformance/1",
    "portable_pyspark_conformance_0_50.json": "etlantic.portable-conformance/1",
    "portable_datafusion_conformance_0_50.json": "etlantic.portable-conformance/1",
    "portable_duckdb_pushdown_0_50.json": "etlantic.portable-pushdown-evidence/1",
    "portable_cross_engine_0_50.json": "etlantic.portable-cross-engine/1",
    "portable_canonical_pipeline_0_50.json": "etlantic.portable-canonical-pipeline/1",
    "portable_adaptive_handoff_0_50.json": "etlantic.portable-adaptive-handoff/1",
    "portable_dependency_security_0_50.json": "etlantic.portable-dependency-security/1",
    "FINDINGS_0_50.md": "markdown/1",
    "MIGRATION_0_49_TO_0_50.md": "markdown/1",
    "WHATS_NEW_0_50.md": "markdown/1",
}

EXPECTED_SOL_FINDINGS = frozenset(f"SOL-050-{index:03d}" for index in range(1, 27))
EXPECTED_FINAL_FINDINGS = frozenset(f"FINAL-050-{index:03d}" for index in range(1, 16))
EXPECTED_RELEASE_FINDINGS = frozenset(
    {f"FINAL-REL-{index:03d}" for index in range(1, 9)} | {"SOL-REL-009"}
)
EXPECTED_ENGINES = frozenset(
    {"local", "polars", "pandas", "sql", "pyspark", "datafusion", "duckdb"}
)
EXPECTED_CANONICAL_ACTIONS = frozenset(
    {
        "dtcs:aggregate",
        "dtcs:deduplicate",
        "dtcs:filter",
        "dtcs:join",
        "dtcs:limit",
        "dtcs:project",
        "dtcs:sort",
        "dtcs:union",
    }
)
EXPECTED_PUSHDOWN_OUTCOMES = frozenset(
    {
        "pushed_exact",
        "pushed_with_lowering",
        "not_pushed",
        "not_applicable",
        "unsupported",
        "unavailable",
        "unknown",
    }
)
EXPECTED_PUSHDOWN_ACTIONS = (
    ("f", "dtcs:filter"),
    ("p", "dtcs:project"),
    ("w", "dtcs:with_fields"),
    ("d", "dtcs:drop_fields"),
    ("n", "dtcs:rename_fields"),
    ("j", "dtcs:join"),
    ("u", "dtcs:union"),
    ("a", "dtcs:aggregate"),
    ("s", "dtcs:sort"),
    ("x", "dtcs:distinct"),
    ("k", "dtcs:deduplicate"),
    ("l", "dtcs:limit"),
)
EXPECTED_PUSHDOWN_BOUNDARIES = ("source", "relational", "sink")
EXPECTED_NATIVE_PUSHDOWN_ENGINES = frozenset({"sql", "pyspark", "datafusion", "duckdb"})


def _canonical_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode(
            "utf-8"
        )
    ).hexdigest()


def _proof_authority() -> dict[str, Any]:
    """Load the reviewed source authority outside the generated evidence tree."""
    payload = json.loads(PROOF_AUTHORITY.read_text(encoding="utf-8"))
    if payload.get("schema") != "etlantic.portable-proof-authority/1":
        raise SystemExit("portable proof authority schema is invalid")
    targets = payload.get("compiler_targets")
    proof_digests = payload.get("native_proof_digests")
    if not isinstance(targets, dict) or set(targets) != EXPECTED_ENGINES:
        raise SystemExit("portable compiler target authority is incomplete")
    if (
        not isinstance(proof_digests, dict)
        or set(proof_digests) != EXPECTED_NATIVE_PUSHDOWN_ENGINES
        or any(
            not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
            for value in proof_digests.values()
        )
    ):
        raise SystemExit("portable native proof authority is incomplete")
    return payload


def _installed_compiler(engine: str, target: Mapping[str, Any]) -> Any:
    """Instantiate the first-party compiler named by a support target.

    Evidence fingerprints are compiler identities, not values copied from the
    checked-in report.  Recomputing them from the installed implementations
    makes coordinated report/index edits fail closed.
    """
    if engine == "local":
        from etlantic.transform.local_compiler import LocalTransformCompiler

        return LocalTransformCompiler()
    if engine == "sql":
        from etlantic_sql import SqlTransformCompiler

        authority_target = _proof_authority()["compiler_targets"].get(engine)
        environment = (
            authority_target.get("environment")
            if isinstance(authority_target, Mapping)
            else None
        )
        dialect = (
            environment.get("dialect") if isinstance(environment, Mapping) else None
        )
        return SqlTransformCompiler(dialect=dialect)
    factories: dict[str, Any] = {}
    if engine == "polars":
        from etlantic_polars import create_transform_compiler

        factories[engine] = create_transform_compiler
    elif engine == "pandas":
        from etlantic_pandas import create_transform_compiler

        factories[engine] = create_transform_compiler
    elif engine == "pyspark":
        from etlantic_pyspark import create_transform_compiler

        factories[engine] = create_transform_compiler
    elif engine == "datafusion":
        from etlantic_datafusion import create_transform_compiler

        factories[engine] = create_transform_compiler
    elif engine == "duckdb":
        from etlantic_duckdb import create_transform_compiler

        factories[engine] = create_transform_compiler
    else:
        raise SystemExit(f"unsupported compiler evidence engine: {engine}")
    try:
        return factories[engine]()
    except Exception as exc:
        raise SystemExit(f"cannot load compiler evidence for {engine}") from exc


def validate_installed_compiler_evidence(
    reports: Mapping[str, Any],
) -> None:
    """Bind every report fingerprint to the installed first-party compiler."""
    authoritative_targets = _proof_authority()["compiler_targets"]
    for engine in EXPECTED_ENGINES:
        report = reports.get(engine)
        if not isinstance(report, Mapping):
            raise SystemExit(f"support report is missing for {engine}")
        target = report.get("target")
        records = report.get("evidence")
        if (
            not isinstance(target, Mapping)
            or not isinstance(records, list)
            or len(records) != 1
        ):
            raise SystemExit(f"support evidence is incomplete for {engine}")
        if target != authoritative_targets.get(engine):
            raise SystemExit(
                f"support target differs from source-controlled authority: {engine}"
            )
        try:
            compiler = _installed_compiler(engine, target)
        except ModuleNotFoundError:
            # Core CI intentionally omits optional backend runtimes.  Their
            # dedicated qualification jobs run this same identity check with
            # the backend installed; source-controlled target metadata and
            # evidence bindings are still validated above and below here.
            continue
        info = compiler.info
        expected = {
            "engine": info.engine,
            "compiler": info.name,
            "version": info.version,
            "package": info.package or info.name,
            "implementation": info.implementation or info.name,
            "protocol": info.compiler_protocol,
        }
        if any(target.get(key) != value for key, value in expected.items()):
            raise SystemExit(
                f"support target identity differs from installed compiler: {engine}"
            )
        if info.environment is not None and target.get("environment") != dict(
            info.environment
        ):
            raise SystemExit(
                f"support target environment differs from installed compiler: {engine}"
            )
        fingerprint = info.evidence_fingerprint
        if (
            not isinstance(fingerprint, str)
            or records[0].get("fingerprint") != fingerprint
        ):
            raise SystemExit(
                f"support evidence fingerprint is not compiler-derived: {engine}"
            )


def validate_findings_ledger(findings_doc: str) -> None:
    """Require every known review finding to have an explicit resolution."""
    expected = (
        EXPECTED_SOL_FINDINGS | EXPECTED_FINAL_FINDINGS | EXPECTED_RELEASE_FINDINGS
    )
    found = set(re.findall(r"(?:SOL|FINAL)-(?:050|REL)-\d{3}", findings_doc))
    if found != expected:
        raise SystemExit("findings ledger is incomplete")
    for finding_id in sorted(expected):
        row = next(
            (line for line in findings_doc.splitlines() if f"| {finding_id} |" in line),
            "",
        )
        if not row or "resolved" not in row.lower():
            raise SystemExit(f"findings ledger does not resolve {finding_id}")
    if "Sol re-review pending" not in findings_doc:
        raise SystemExit("findings ledger must retain the independent review status")


def validate_artifact_schema(name: str, schema: object) -> None:
    """Require the frozen schema assigned to an evidence artifact."""
    expected = EXPECTED_SCHEMAS.get(name)
    if expected is None or schema != expected:
        raise SystemExit(f"invalid evidence schema: {name}")


def _qualified_source_tree_digest(repository_commit: str) -> str:
    """Hash raw tracked blobs without checkout or archive conversions."""
    tree = subprocess.check_output(
        ["git", "ls-tree", "-rz", "--full-tree", repository_commit], cwd=ROOT
    )
    evidence_prefix = b"docs/11_DEVELOPMENT/evidence/portable_0_50/"
    entries: list[tuple[bytes, bytes]] = []
    for record in tree.split(b"\0"):
        if not record:
            continue
        metadata, path = record.split(b"\t", 1)
        _mode, object_type, object_id = metadata.split(b" ", 2)
        if object_type != b"blob" or path.startswith(evidence_prefix):
            continue
        entries.append((path, object_id))

    ordered = sorted(entries)
    objects = subprocess.run(
        ["git", "cat-file", "--batch"],
        cwd=ROOT,
        input=b"".join(object_id + b"\n" for _, object_id in ordered),
        capture_output=True,
        check=True,
    ).stdout
    offset = 0
    digest = hashlib.sha256()
    for path, expected_object_id in ordered:
        header_end = objects.index(b"\n", offset)
        header = objects[offset:header_end].split(b" ")
        if len(header) != 3 or header[0] != expected_object_id or header[1] != b"blob":
            raise SystemExit(f"cannot read qualified source blob: {path.decode()}")
        size = int(header[2])
        content_start = header_end + 1
        content_end = content_start + size
        if objects[content_end : content_end + 1] != b"\n":
            raise SystemExit(f"invalid qualified source blob framing: {path.decode()}")
        digest.update(path)
        digest.update(b"\0")
        digest.update(objects[content_start:content_end])
        digest.update(b"\0")
        offset = content_end + 1
    if offset != len(objects):
        raise SystemExit("unexpected trailing qualified source blob data")
    return digest.hexdigest()


def validate_cross_engine_digests(payload: dict[str, object]) -> None:
    """Require normalized, PostgreSQL, and SQLite canonical results to agree."""
    normalized = payload.get("normalized_result_digest")
    if not re.fullmatch(r"[0-9a-f]{64}", str(normalized or "")):
        raise SystemExit("cross-engine digest must be derived from canonical output")
    canonical = payload.get("canonical_result_digests")
    if (
        not isinstance(canonical, dict)
        or set(canonical) != {"postgresql", "sqlite"}
        or any(
            not re.fullmatch(r"[0-9a-f]{64}", str(value))
            for value in canonical.values()
        )
        or normalized != canonical["postgresql"]
        or canonical["postgresql"] != canonical["sqlite"]
    ):
        raise SystemExit("cross-engine canonical digests are incomplete")


def validate_requirement_campaign(payload: dict[str, object]) -> None:
    """Require exact canonical-plan and negative-state reports for every engine."""
    from etlantic.transform.compiler import validate_requirement_support_payload

    fingerprint = payload.get("canonical_definition_fingerprint")
    if not re.fullmatch(r"[0-9a-f]{64}", str(fingerprint or "")):
        raise SystemExit("canonical support evidence lacks a definition fingerprint")
    if payload.get("canonical_action_count") != len(EXPECTED_CANONICAL_ACTIONS):
        raise SystemExit("canonical support evidence has the wrong action count")
    reports = payload.get("reports")
    baseline_reports = payload.get("baseline_reports")
    negative_reports = payload.get("negative_reports")
    if (
        not isinstance(reports, dict)
        or set(reports) != EXPECTED_ENGINES
        or not isinstance(baseline_reports, dict)
        or set(baseline_reports) != EXPECTED_ENGINES
        or not isinstance(negative_reports, dict)
        or set(negative_reports) != EXPECTED_ENGINES
    ):
        raise SystemExit("requirement evidence does not cover all seven engines")
    for engine, report in reports.items():
        if not isinstance(report, dict):
            raise SystemExit(f"canonical requirement evidence is invalid for {engine}")
        try:
            validate_requirement_support_payload(report)
            validate_requirement_support_payload(baseline_reports[engine])
        except (TypeError, ValueError) as exc:
            raise SystemExit(
                f"invalid requirement evidence for {engine}: {exc}"
            ) from exc
        if (
            report["target"].get("engine") != engine
            or baseline_reports[engine]["target"].get("engine") != engine
        ):
            raise SystemExit(f"requirement evidence target disagrees for {engine}")
        requirements = {
            str(item.get("id")): item for item in report.get("requirements") or []
        }
        findings_by_requirement = {
            str(item.get("requirement")): item for item in report.get("findings") or []
        }
        action_requirements = {
            requirement_id: item
            for requirement_id, item in requirements.items()
            if item.get("scope") == "actions"
        }
        canonical_actions = {
            str((item.get("parameters") or {}).get("value"))
            for item in action_requirements.values()
        }
        if (
            canonical_actions != EXPECTED_CANONICAL_ACTIONS
            or len(action_requirements) != len(EXPECTED_CANONICAL_ACTIONS)
            or {item.get("path") for item in action_requirements.values()}
            != {f"actions/{index}" for index in range(len(EXPECTED_CANONICAL_ACTIONS))}
            or any(
                findings_by_requirement.get(requirement_id, {}).get("path")
                != requirement.get("path")
                for requirement_id, requirement in action_requirements.items()
            )
        ):
            raise SystemExit(
                f"canonical action-level support evidence is incomplete for {engine}"
            )
        for requirement_id, requirement in requirements.items():
            if (
                requirement.get("applicability") == "applicable"
                and requirement.get("obligation") == "required"
            ):
                finding = findings_by_requirement.get(requirement_id)
                if finding is None or finding.get("support") not in {
                    "supported_exact",
                    "supported_with_lowering",
                }:
                    raise SystemExit(
                        "required canonical support evidence is not positive for "
                        f"{engine}: {requirement_id}"
                    )

        engine_negatives = negative_reports[engine]
        if (
            not isinstance(engine_negatives, list)
            or {item.get("expected_state") for item in engine_negatives}
            != {"unsupported", "unavailable", "unknown"}
            or {item.get("fixture_id") for item in engine_negatives}
            != {"unsupported-action", "unavailable-runtime", "unknown-runtime"}
        ):
            raise SystemExit(f"negative support corpus is incomplete for {engine}")
        for negative in engine_negatives:
            negative_report = negative.get("support_report")
            expected_state = negative.get("expected_state")
            if not re.fullmatch(
                r"[0-9a-f]{64}", str(negative.get("definition_digest") or "")
            ) or not isinstance(negative_report, dict):
                raise SystemExit(f"negative support evidence is invalid for {engine}")
            provenance = negative.get("provenance")
            if not isinstance(provenance, dict) or provenance.get("kind") not in {
                "compiler_analyze",
                "target_availability_probe",
            }:
                raise SystemExit(
                    f"negative {expected_state} evidence lacks execution provenance for {engine}"
                )
            try:
                validate_requirement_support_payload(negative_report)
            except ValueError as exc:
                raise SystemExit(
                    f"negative support evidence is invalid for {engine}: {exc}"
                ) from exc
            if negative_report["target"].get("engine") != engine:
                raise SystemExit(f"negative support target disagrees for {engine}")
            if provenance.get("compiler") != negative_report["target"].get("compiler"):
                raise SystemExit(
                    f"negative {expected_state} provenance disagrees for {engine}"
                )
            if (
                expected_state == "unavailable"
                and provenance.get("kind") != "target_availability_probe"
            ):
                raise SystemExit(
                    "unavailable support must come from a target availability probe"
                )
            if (
                expected_state == "unknown"
                and provenance.get("kind") != "compiler_analyze"
            ):
                raise SystemExit("unknown support must come from compiler analysis")
            matching = [
                item
                for item in negative_report.get("findings") or []
                if item.get("support") == expected_state
            ]
            if not matching or any(
                not item.get("reason_code")
                or not item.get("reason")
                or not item.get("path")
                for item in matching
            ):
                raise SystemExit(
                    f"negative {expected_state} finding is absent for {engine}"
                )
            if expected_state == "unsupported":
                unsupported_ids = {
                    str(item.get("id"))
                    for item in negative_report.get("requirements") or []
                    if item.get("scope") == "actions"
                    and item.get("path") == "actions/0"
                    and (item.get("parameters") or {}).get("value")
                    == "dtcs:not-supported"
                }
                if not unsupported_ids or not any(
                    item.get("requirement") in unsupported_ids
                    and item.get("path") not in {None, "", "findings"}
                    for item in matching
                ):
                    raise SystemExit(
                        f"unsupported action finding is not plan-scoped for {engine}"
                    )
                if any(
                    item.get("action") == "dtcs:not-supported"
                    and item.get("outcome") in {"pushed_exact", "pushed_with_lowering"}
                    for item in negative_report.get("pushdown") or []
                ):
                    raise SystemExit(
                        f"unsupported action has contradictory positive pushdown for {engine}"
                    )


def validate_pushdown_campaign(payload: dict[str, object]) -> None:
    """Require executable wire fixtures for every frozen pushdown outcome."""
    from etlantic.transform.compiler import validate_requirement_support_payload

    outcomes = payload.get("outcomes")
    fixtures = payload.get("outcome_fixtures")
    if (
        not isinstance(outcomes, list)
        or len(outcomes) != len(EXPECTED_PUSHDOWN_OUTCOMES)
        or set(outcomes) != EXPECTED_PUSHDOWN_OUTCOMES
        or not isinstance(fixtures, list)
        or len(fixtures) != len(EXPECTED_PUSHDOWN_OUTCOMES)
    ):
        raise SystemExit("pushdown outcome corpus is incomplete")
    by_outcome = {
        str(item.get("outcome")): item for item in fixtures if isinstance(item, dict)
    }
    if set(by_outcome) != EXPECTED_PUSHDOWN_OUTCOMES:
        raise SystemExit("pushdown outcome corpus is incomplete")
    expected_obligations = {
        "pushed_exact": "required",
        "pushed_with_lowering": "required",
        "not_pushed": "preferred",
        "not_applicable": "informational",
        "unsupported": "required",
        "unavailable": "required",
        "unknown": "required",
    }
    for outcome, fixture in by_outcome.items():
        report = fixture.get("support_report")
        if not isinstance(report, dict):
            raise SystemExit("pushdown outcome fixture lacks support evidence")
        try:
            validate_requirement_support_payload(report)
        except ValueError as exc:
            raise SystemExit("pushdown outcome fixture is invalid") from exc
        findings = report.get("pushdown")
        if not isinstance(findings, list) or len(findings) != 1:
            raise SystemExit("pushdown outcome fixture must have exactly one finding")
        finding = findings[0]
        obligation = expected_obligations[outcome]
        if (
            not isinstance(finding, dict)
            or finding.get("outcome") != outcome
            or finding.get("obligation") != obligation
            or fixture.get("obligation") != obligation
        ):
            raise SystemExit("pushdown outcome fixture disagrees with the contract")
        expected_eligible = outcome in {"pushed_exact", "pushed_with_lowering"} or (
            obligation != "required"
        )
        if fixture.get("expected_eligible") is not expected_eligible:
            raise SystemExit("pushdown outcome eligibility is incorrect")
        if outcome == "pushed_with_lowering" and (
            finding.get("lowering_id") != "lowering/pushdown-outcome-v1"
            or finding.get("conditions") != ["preserve-null"]
            or finding.get("proof_reference") != "proof/pushdown-outcome-v1"
            or finding.get("physical_effects") != ["materialization"]
        ):
            raise SystemExit("lowered pushdown evidence is incomplete")


def validate_pushdown_findings(
    findings: object,
    proofs: object,
    payload: dict[str, object],
    *,
    expected_evidence_fingerprints: Mapping[str, str] | None = None,
    proof_attestations: Mapping[str, Mapping[str, Any] | None] | None = None,
    authoritative_proof_digests: Mapping[str, str] | None = None,
) -> None:
    """Require the checked-in pushdown matrix and native proofs to be complete."""
    if payload.get("boundaries") != list(EXPECTED_PUSHDOWN_BOUNDARIES):
        raise SystemExit("pushdown boundary inventory is incomplete")
    evidence = payload.get("evidence")
    if not isinstance(evidence, list) or len(evidence) != len(EXPECTED_ENGINES):
        raise SystemExit("pushdown evidence fingerprint inventory is incomplete")
    if any(
        not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
        for value in evidence
    ) or len(set(evidence)) != len(evidence):
        raise SystemExit("pushdown evidence fingerprint inventory is incomplete")
    if expected_evidence_fingerprints is not None and (
        set(expected_evidence_fingerprints) != EXPECTED_ENGINES
        or any(
            not re.fullmatch(r"[0-9a-f]{64}", str(value))
            for value in expected_evidence_fingerprints.values()
        )
    ):
        raise SystemExit("pushdown expected evidence fingerprints are invalid")
    if not isinstance(findings, list):
        raise SystemExit("pushdown findings must be a list")
    expected_actions = dict(EXPECTED_PUSHDOWN_ACTIONS)
    expected_keys = {
        (engine, boundary, action_id)
        for engine in EXPECTED_ENGINES
        for boundary in EXPECTED_PUSHDOWN_BOUNDARIES
        for action_id in expected_actions
    }
    actual_keys: set[tuple[str, str, str]] = set()
    expected_required: set[tuple[str, str]] = set()
    finding_evidence: dict[str, set[str]] = {
        engine: set() for engine in EXPECTED_ENGINES
    }
    for item in findings:
        if not isinstance(item, dict):
            raise SystemExit("pushdown finding is not an object")
        identity = tuple(
            item.get(name) for name in ("engine", "boundary", "action", "target")
        )
        if not all(isinstance(value, str) for value in identity):
            raise SystemExit("pushdown finding identity is incomplete")
        engine, boundary, action, target = cast(tuple[str, str, str, str], identity)
        if engine not in EXPECTED_ENGINES:
            raise SystemExit("pushdown finding names an unknown engine")
        evidence_fingerprint = item.get("evidence_fingerprint")
        if not isinstance(evidence_fingerprint, str) or not re.fullmatch(
            r"[0-9a-f]{64}", evidence_fingerprint
        ):
            raise SystemExit("pushdown finding evidence fingerprint is invalid")
        finding_evidence[engine].add(evidence_fingerprint)
        if ":" not in boundary:
            raise SystemExit("pushdown finding boundary is invalid")
        boundary_name, boundary_index = boundary.split(":", 1)
        if (
            boundary_name not in EXPECTED_PUSHDOWN_BOUNDARIES
            or not boundary_index.isdigit()
            or int(boundary_index) >= len(expected_actions)
        ):
            raise SystemExit("pushdown finding boundary is invalid")
        if action not in expected_actions.values() or target not in expected_actions:
            raise SystemExit("pushdown finding action identity is invalid")
        action_id = target
        if action != expected_actions[action_id]:
            raise SystemExit("pushdown finding action and target disagree")
        action_index = tuple(expected_actions).index(action_id)
        if boundary_index != str(action_index):
            raise SystemExit("pushdown finding boundary and target disagree")
        key = (engine, boundary_name, action_id)
        if key in actual_keys:
            raise SystemExit("pushdown findings contain a duplicate identity")
        actual_keys.add(key)

        native = engine in EXPECTED_NATIVE_PUSHDOWN_ENGINES
        relational = boundary_name == "relational"
        expected_outcome = "pushed_exact" if native and relational else "not_applicable"
        expected_obligation = "required" if native and relational else "informational"
        if (
            item.get("outcome") != expected_outcome
            or item.get("obligation") != expected_obligation
        ):
            raise SystemExit(
                "pushdown finding disagrees with the frozen boundary contract"
            )
        expected_reason = (
            "action lowered into the native relational plan"
            if native and relational
            else (
                "connector source pushdown is outside the native plan contract"
                if native and boundary_name == "source"
                else (
                    "sink pushdown is outside the native plan contract"
                    if native
                    else "host-owned execution has no backend pushdown boundary"
                )
            )
        )
        if item.get("reason") != expected_reason:
            raise SystemExit("pushdown finding reason disagrees with the contract")
        expected_effects = (
            {"materialization", "lost_fusion"}
            if native and relational and engine in {"sql", "duckdb"}
            else set()
        )
        effects = item.get("physical_effects")
        if not isinstance(effects, list) or set(effects) != expected_effects:
            raise SystemExit("pushdown finding physical effects are invalid")
        proof = item.get("proof_reference")
        if native and relational:
            expected_proof = f"native-execution:{engine}:{action_id}"
            if proof != expected_proof:
                raise SystemExit(
                    "required pushdown finding has an invalid native proof reference"
                )
            expected_required.add((engine, action_id))
        elif proof not in (None, ""):
            raise SystemExit(
                "informational pushdown finding must not claim native proof"
            )
    if actual_keys != expected_keys:
        raise SystemExit("pushdown findings matrix is incomplete")
    if any(len(values) != 1 for values in finding_evidence.values()):
        raise SystemExit("pushdown findings lack consistent evidence fingerprints")
    if set().union(*finding_evidence.values()) != set(evidence):
        raise SystemExit("pushdown evidence does not match finding fingerprints")
    if expected_evidence_fingerprints is not None and any(
        finding_evidence[engine] != {expected_evidence_fingerprints[engine]}
        for engine in EXPECTED_ENGINES
    ):
        raise SystemExit("pushdown findings are not bound to engine evidence")

    if not isinstance(proofs, dict) or set(proofs) != EXPECTED_ENGINES:
        raise SystemExit("pushdown proof engine inventory is incomplete")
    if proof_attestations is not None and set(proof_attestations) != EXPECTED_ENGINES:
        raise SystemExit("pushdown proof attestation inventory is incomplete")
    expected_proof_keys = {
        (engine, action_id)
        for engine in EXPECTED_NATIVE_PUSHDOWN_ENGINES
        for action_id in expected_actions
    }
    actual_proof_keys: set[tuple[str, str]] = set()
    for engine in EXPECTED_ENGINES:
        engine_proofs = proofs.get(engine)
        if not isinstance(engine_proofs, dict):
            raise SystemExit("pushdown proof record is invalid")
        actions = engine_proofs.get("actions")
        if not isinstance(actions, dict):
            raise SystemExit("pushdown proof action inventory is invalid")
        expected_action_ids = (
            set(expected_actions)
            if engine in EXPECTED_NATIVE_PUSHDOWN_ENGINES
            else set()
        )
        if set(actions) != expected_action_ids:
            raise SystemExit("pushdown proof action inventory is incomplete")
        if engine in EXPECTED_NATIVE_PUSHDOWN_ENGINES:
            if authoritative_proof_digests is not None and (
                _canonical_digest(engine_proofs)
                != authoritative_proof_digests.get(engine)
            ):
                raise SystemExit(
                    "native pushdown proof differs from source-controlled authority"
                )
            if proof_attestations is not None:
                attestation = proof_attestations.get(engine)
                if (
                    not isinstance(attestation, Mapping)
                    or dict(attestation) != engine_proofs
                ):
                    raise SystemExit(
                        "native pushdown proof is not independently attested"
                    )
            for digest_key in ("result_digest", "native_explain_digest"):
                if not re.fullmatch(
                    r"[0-9a-f]{64}", str(engine_proofs.get(digest_key) or "")
                ):
                    raise SystemExit("native pushdown proof digest is invalid")
        elif any(
            engine_proofs.get(digest_key) is not None
            for digest_key in ("result_digest", "native_explain_digest")
        ):
            raise SystemExit("host pushdown proof must not claim native digests")
        for action_id, action_proof in actions.items():
            if not isinstance(action_proof, dict):
                raise SystemExit("pushdown action proof is invalid")
            expected = f"native-execution:{engine}:{action_id}"
            if (
                action_proof.get("proof_id") != expected
                or action_proof.get("action") != expected_actions[action_id]
                or not isinstance(action_proof.get("physical_effects"), list)
                or set(action_proof["physical_effects"])
                != (
                    {"materialization", "lost_fusion"}
                    if engine in {"sql", "duckdb"}
                    else set()
                )
                or action_proof.get("host_fallback") is not False
                or action_proof.get("proof_basis")
                != "native_explain_and_execution_trace"
                or any(
                    not re.fullmatch(r"[0-9a-f]{64}", str(action_proof.get(name) or ""))
                    for name in (
                        "native_explain_digest",
                        "action_explain_digest",
                        "action_native_digest",
                        "result_digest",
                    )
                )
                or action_proof.get("result_digest")
                != engine_proofs.get("result_digest")
                or action_proof.get("native_explain_digest")
                != engine_proofs.get("native_explain_digest")
            ):
                raise SystemExit("native pushdown proof is incomplete")
            actual_proof_keys.add((engine, action_id))
    if (
        actual_proof_keys != expected_proof_keys
        or actual_proof_keys != expected_required
    ):
        raise SystemExit("pushdown proofs do not match required findings")

    sql_execution = (cast(dict[str, object], proofs["sql"])).get("sqlite_execution")
    if not isinstance(sql_execution, dict):
        raise SystemExit("SQL pushdown proof lacks SQLite execution evidence")
    for digest_key in ("result_digest", "native_explain_digest"):
        if not re.fullmatch(r"[0-9a-f]{64}", str(sql_execution.get(digest_key) or "")):
            raise SystemExit("SQL SQLite execution digest is invalid")
    if sql_execution.get("host_fallback") is not False:
        raise SystemExit("SQL SQLite execution used host fallback")
    for digest_map_key in ("action_native_digests", "action_explain_digests"):
        digest_map = sql_execution.get(digest_map_key)
        if (
            not isinstance(digest_map, dict)
            or set(digest_map) != set(expected_actions)
            or any(
                not re.fullmatch(r"[0-9a-f]{64}", str(value or ""))
                for value in digest_map.values()
            )
        ):
            raise SystemExit("SQL SQLite action evidence is incomplete")


def validate_adaptive_lowering_binding(
    candidate: dict[str, object],
    requirements: dict[str, Any],
    support_findings: dict[str, dict[str, Any]],
    resolved: dict[str, str | None],
) -> None:
    """Require lowering records to match the candidate's support findings exactly."""
    lowered = sorted(
        key for key, value in requirements.items() if value == "supported_with_lowering"
    )
    expected_groups: dict[
        tuple[str, str, tuple[object, ...], tuple[object, ...]], list[str]
    ] = {}
    for requirement in lowered:
        finding_id = resolved.get(requirement)
        finding = (
            support_findings.get(str(finding_id)) if finding_id is not None else None
        )
        if not isinstance(finding, dict):
            raise SystemExit("adaptive lowering evidence is incomplete")
        lowering_id = str(finding.get("lowering_id") or "")
        proof = str(finding.get("proof_reference") or "")
        conditions = tuple(finding.get("conditions") or ())
        effects = tuple(finding.get("physical_effects") or ())
        if not lowering_id or not proof or not effects:
            raise SystemExit("adaptive lowering evidence is incomplete")
        expected_groups.setdefault(
            (lowering_id, proof, conditions, effects), []
        ).append(requirement)
    expected = [
        {
            "id": lowering_id,
            "requirements": sorted(group_requirements),
            "proof": proof,
            "conditions": list(conditions),
            "physical_effects": list(effects),
        }
        for (lowering_id, proof, conditions, effects), group_requirements in sorted(
            expected_groups.items(), key=lambda item: item[0]
        )
    ]
    raw_lowerings = candidate.get("lowerings")
    if raw_lowerings is None:
        singular = candidate.get("lowering")
        raw_lowerings = [] if singular is None else [singular]
    if not isinstance(raw_lowerings, list) or any(
        not isinstance(item, dict) for item in raw_lowerings
    ):
        raise SystemExit("adaptive lowering evidence is incomplete")
    actual = [dict(item) for item in cast(list[dict[str, object]], raw_lowerings)]
    if candidate.get("lowering") is not None and len(expected) != 1:
        raise SystemExit("adaptive lowering evidence is not evidence-backed")
    if candidate.get("lowering") is not None and len(expected) == 1:
        singular = candidate.get("lowering")
        if not isinstance(singular, dict) or not actual or singular != actual[0]:
            raise SystemExit("adaptive lowering evidence is not evidence-backed")
    if sorted(actual, key=lambda item: json.dumps(item, sort_keys=True)) != sorted(
        expected, key=lambda item: json.dumps(item, sort_keys=True)
    ):
        raise SystemExit("adaptive lowering evidence is not evidence-backed")


def validate_adaptive_target_binding(
    candidate: dict[str, object],
    *,
    node: str,
    seen_targets: set[tuple[str, str]],
) -> str:
    """Require each candidate to bind to one unique support-report target."""
    support_report = candidate.get("support_report")
    target = candidate.get("target")
    report_target = (
        support_report.get("target") if isinstance(support_report, dict) else None
    )
    if (
        not isinstance(target, dict)
        or not isinstance(report_target, dict)
        or target != report_target
    ):
        raise SystemExit("adaptive candidate target is not evidence-backed")
    target_key = json.dumps(target, sort_keys=True, separators=(",", ":"))
    target_identity = (node, target_key)
    if target_identity in seen_targets:
        raise SystemExit("adaptive placement target is ambiguous")
    seen_targets.add(target_identity)
    return target_key


def validate_adaptive_target_matrix(
    targets_by_node: dict[str, set[str]], nodes: list[object]
) -> None:
    """Require every logical node to retain the same target inventory."""
    node_ids = {str(node) for node in nodes if isinstance(node, str) and node}
    if not node_ids or node_ids != set(targets_by_node):
        raise SystemExit("adaptive target matrix does not cover every node")
    inventories = [targets_by_node[node] for node in sorted(node_ids)]
    if not inventories[0] or any(
        inventory != inventories[0] for inventory in inventories[1:]
    ):
        raise SystemExit("adaptive target matrix does not cover every node and target")


def validate_adaptive_selection(evaluation: dict[str, Any]) -> None:
    """Require recorded selections to reference the evaluated candidates.

    The handoff is evidence, so checking only the selected value's JSON type is
    insufficient: a fabricated candidate id (or an ineligible candidate) would
    otherwise pass the release verifier after the artifact digest is updated.
    """
    candidates = evaluation.get("candidates")
    nodes = evaluation.get("nodes")
    if not isinstance(candidates, list) or not isinstance(nodes, list):
        raise SystemExit("adaptive candidate selection is incomplete")
    node_ids = [node for node in nodes if isinstance(node, str) and node]
    if len(node_ids) != len(nodes) or len(set(node_ids)) != len(node_ids):
        raise SystemExit("adaptive candidate selection has duplicate or invalid nodes")

    by_identity: dict[tuple[str, str], dict[str, Any]] = {}
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise SystemExit("adaptive candidate selection is incomplete")
        node = candidate.get("node")
        candidate_id = candidate.get("id")
        if not isinstance(node, str) or not isinstance(candidate_id, str):
            raise SystemExit("adaptive candidate selection is incomplete")
        identity = (node, candidate_id)
        if identity in by_identity:
            raise SystemExit("adaptive candidate selection has duplicate ids")
        by_identity[identity] = candidate

    selected = evaluation.get("selected")
    if len(node_ids) == 1 and not isinstance(selected, dict):
        selected_by_node: dict[str, object] = {node_ids[0]: selected}
    elif isinstance(selected, dict):
        if set(selected) != set(node_ids):
            raise SystemExit("adaptive candidate selection is invalid")
        selected_by_node = selected
    else:
        raise SystemExit("adaptive candidate selection is invalid")

    graph_valid = evaluation.get("graph_valid")
    graph_failures = evaluation.get("graph_failures")
    if graph_valid is True and graph_failures:
        raise SystemExit("graph-valid adaptive selection records graph failures")
    for node in node_ids:
        candidate_id = selected_by_node.get(node)
        if candidate_id is None:
            if graph_valid is True:
                raise SystemExit("graph-valid adaptive selection is incomplete")
            continue
        if not isinstance(candidate_id, str):
            raise SystemExit("adaptive candidate selection is invalid")
        candidate = by_identity.get((node, candidate_id))
        if candidate is None:
            raise SystemExit("adaptive selection references an unknown candidate")
        if graph_valid is True and candidate.get("eligible") is not True:
            raise SystemExit(
                "graph-valid adaptive selection chose an ineligible candidate"
            )


def main() -> int:
    if set(EXPECTED_SCHEMAS) != REQUIRED:
        raise SystemExit("evidence schema map does not cover the frozen artifact set")
    missing = sorted(name for name in REQUIRED if not (EVIDENCE / name).is_file())
    if missing:
        raise SystemExit("missing 0.50 contract artifacts: " + ", ".join(missing))
    baseline = json.loads(
        (EVIDENCE / "portable_baseline_contract_0_50.json").read_text()
    )
    if baseline.get("schema") != "etlantic.portable-baseline/1":
        raise SystemExit("invalid baseline schema")
    manifest = baseline.get("manifest") or {}
    if len(manifest.get("actions", [])) != 12:
        raise SystemExit("baseline must enumerate exactly 12 actions")
    if (
        len(manifest.get("scalar_functions", [])) != 23
        or len(manifest.get("aggregate_functions", [])) != 7
    ):
        raise SystemExit("baseline function inventory is incomplete")
    required_manifest_keys = {
        "plan",
        "profiles",
        "profile_aliases",
        "actions",
        "scalar_functions",
        "aggregate_functions",
        "operators",
        "types",
        "join_modes",
        "collision_policy",
        "union_modes",
        "semantic_modes",
        "function_arities",
        "defaults",
        "semantic_rules",
        "leaf_fixture_ids",
        "literal_constraints",
        "action_parameters",
        "aggregate_empty_results",
        "numeric_rules",
        "string_unicode_rules",
        "multi_input_identity",
        "output_contract",
    }
    if not required_manifest_keys.issubset(manifest):
        raise SystemExit("baseline manifest is missing normative contract fields")
    aliases = manifest.get("profile_aliases")
    if not isinstance(aliases, dict):
        raise SystemExit("baseline profile aliases must be an object")
    expected_aliases = {
        "dtcs:profile/portable-relational-kernel/2": "dtcs:profile/portable-relational-kernel/1",
        "dtcs:profile/portable-relational/2": "dtcs:profile/portable-relational/1",
    }
    for alias, canonical in expected_aliases.items():
        details = aliases.get(alias)
        if (
            not isinstance(details, dict)
            or details.get("canonical") != canonical
            or details.get("proof") != "exact-vocabulary-equivalence"
            or canonical not in manifest.get("profiles", [])
        ):
            raise SystemExit(
                f"profile alias lacks normative equivalence proof: {alias}"
            )
    from etlantic.transform.portable_baseline import baseline_manifest

    if manifest != baseline_manifest():
        raise SystemExit("baseline evidence manifest differs from runtime manifest")
    index = json.loads((EVIDENCE / "portable_evidence_index_0_50.json").read_text())
    validate_artifact_schema("portable_evidence_index_0_50.json", index.get("schema"))
    repository_commit = str(index.get("repository_commit") or "")
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", repository_commit):
        raise SystemExit("evidence index repository_commit is invalid")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", repository_commit, head],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    if ancestor.returncode != 0:
        raise SystemExit(
            "evidence repository_commit must be an ancestor of the current revision"
        )
    source_digest = index.get("source_tree_digest")
    if not isinstance(source_digest, str) or not re.fullmatch(
        r"[0-9a-f]{64}", source_digest
    ):
        raise SystemExit("evidence index source_tree_digest is missing or invalid")
    if _qualified_source_tree_digest(repository_commit) != source_digest:
        raise SystemExit(
            "evidence source tree digest does not match its recorded qualification commit"
        )
    if index.get("result") not in {"pass", "blocked"}:
        raise SystemExit(
            "evidence index result must be pass or an explicit blocked no-go"
        )
    if index.get("result") == "pass" and index.get("qualification") != "qualified":
        raise SystemExit("passing evidence requires qualification=qualified")
    if index.get("result") == "blocked" and index.get("qualification") != "no-go":
        raise SystemExit("blocked evidence requires qualification=no-go")
    listed = set(index.get("artifacts") or [])
    if listed != REQUIRED - {"portable_evidence_index_0_50.json"}:
        raise SystemExit("evidence index does not enumerate the frozen artifact set")
    if len(index.get("artifacts") or []) != len(listed):
        raise SystemExit("evidence index contains duplicate artifacts")
    if any(Path(name).is_absolute() or ".." in Path(name).parts for name in listed):
        raise SystemExit("evidence index contains an absolute or escaping path")
    digests = index.get("digests")
    if not isinstance(digests, dict) or set(digests) != listed:
        raise SystemExit("evidence index must provide one digest per artifact")
    metadata = index.get("artifact_metadata")
    if not isinstance(metadata, dict) or set(metadata) != listed:
        raise SystemExit("evidence index must provide metadata for every artifact")
    for name in listed:
        item = metadata.get(name)
        schema = EXPECTED_SCHEMAS[name]
        artifact_schema = (
            json.loads((EVIDENCE / name).read_text()).get("schema")
            if name.endswith(".json")
            else "markdown/1"
        )
        if (
            not isinstance(item, dict)
            or item.get("path") != name
            or not str(item.get("id") or "").strip()
            or item.get("schema") != schema
            or artifact_schema != schema
            or item.get("sha256") != digests.get(name)
            or not str(item.get("command") or "").strip()
            or not isinstance(item.get("environment"), dict)
            or item.get("result") != "pass"
        ):
            raise SystemExit(f"evidence index metadata is incomplete: {name}")
    for name in REQUIRED - {"portable_evidence_index_0_50.json"}:
        artifact = EVIDENCE / name
        if artifact.suffix == ".json":
            payload = json.loads(artifact.read_text())
            if (
                payload.get("schema") != EXPECTED_SCHEMAS[name]
                or "repository_commit" not in payload
                or "result" not in payload
            ):
                raise SystemExit(f"artifact metadata is incomplete: {name}")
            if payload.get("repository_commit") != repository_commit:
                raise SystemExit(f"artifact commit differs from evidence index: {name}")
            if payload.get("source_tree_digest") != source_digest:
                raise SystemExit(
                    f"artifact source digest differs from evidence index: {name}"
                )
            if (
                not isinstance(payload.get("command"), str)
                or not payload["command"].strip()
            ):
                raise SystemExit(f"artifact command is missing: {name}")
            if not isinstance(payload.get("environment"), dict):
                raise SystemExit(f"artifact environment is missing: {name}")
            result = payload.get("result")
            if result not in {"pass", "blocked"}:
                raise SystemExit(f"artifact has non-final result: {name}")
            if (
                result == "blocked"
                and not str(payload.get("notes") or payload.get("note") or "").strip()
            ):
                raise SystemExit(
                    f"blocked artifact lacks a blocker explanation: {name}"
                )
            if index.get("result") == "pass" and result != "pass":
                raise SystemExit(
                    f"qualified index references non-passing artifact: {name}"
                )
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        if digests.get(name) != digest:
            raise SystemExit(f"evidence digest mismatch: {name}")
    from etlantic.transform.compiler import validate_requirement_support_payload

    support = json.loads(
        (EVIDENCE / "portable_requirement_support_0_50.json").read_text()
    )
    validate_requirement_campaign(support)
    reports = cast(dict[str, dict[str, Any]], support["reports"])
    expected_pushdown_evidence: dict[str, str] = {}
    for engine in EXPECTED_ENGINES:
        records = reports[engine].get("evidence")
        if (
            not isinstance(records, list)
            or len(records) != 1
            or not isinstance(records[0], dict)
            or records[0].get("id") != "compiler"
            or not isinstance(records[0].get("fingerprint"), str)
        ):
            raise SystemExit(
                f"support evidence is incomplete for pushdown engine: {engine}"
            )
        expected_pushdown_evidence[engine] = records[0]["fingerprint"]
    validate_installed_compiler_evidence(reports)
    coverage = json.loads((EVIDENCE / "portable_claim_coverage_0_50.json").read_text())
    claims = coverage.get("claims")
    expected_fixtures = sorted(set((manifest.get("leaf_fixture_ids") or {}).values()))
    if not isinstance(claims, list) or {item.get("engine") for item in claims} != set(
        reports
    ):
        raise SystemExit("claim coverage must contain exactly one claim per engine")
    if coverage.get("required_fixture_ids") != expected_fixtures:
        raise SystemExit("claim coverage fixture inventory differs from baseline")
    expected_matrix = {
        ("local", "host", None),
        ("polars", "eager", None),
        ("polars", "lazy", None),
        ("pandas", "eager", None),
        ("sql", "relation", "sqlite"),
        ("sql", "relation", "postgresql"),
        ("pyspark", "native", "jvm"),
        ("datafusion", "lazy", "native"),
        ("duckdb", "lazy", "native"),
    }
    matrix = coverage.get("qualification_matrix")
    campaigns = coverage.get("campaign_results")
    campaign_ids = {
        item.get("id")
        for item in campaigns
        if isinstance(item, dict)
        and item.get("result") == "pass"
        and item.get("exit_code") == 0
    }
    if (
        not isinstance(matrix, list)
        or not isinstance(campaigns, list)
        or len(campaign_ids) != len(campaigns)
        or len(campaign_ids) < 4
        or {
            (item.get("engine"), item.get("mode"), item.get("dialect"))
            for item in matrix
            if isinstance(item, dict)
        }
        != expected_matrix
        or any(
            item.get("result") != "pass"
            or not item.get("campaign_ids")
            or not set(item.get("campaign_ids") or {}).issubset(campaign_ids)
            or set(item.get("campaign_ids") or ())
            != (
                {f"public-{item.get('dialect')}", f"canonical-{item.get('dialect')}"}
                if item.get("engine") == "sql"
                else campaign_ids
            )
            for item in matrix
            if isinstance(item, dict)
        )
    ):
        raise SystemExit("qualification matrix is incomplete or not passing")
    from etlantic.testing.portable_fixtures import FIXTURES

    fixture_names = {case.name for case in FIXTURES}
    bindings = manifest.get("leaf_fixture_ids") or {}
    if set(bindings.values()) - fixture_names:
        raise SystemExit(
            "baseline manifest references fixture IDs absent from the corpus"
        )
    for claim in claims:
        if claim.get("fixture_coverage") != "complete":
            raise SystemExit("claim coverage is not complete")
        if claim.get("required_fixture_ids") != expected_fixtures:
            raise SystemExit("claim is missing a baseline fixture binding")
        if claim.get("fixture_bindings") != bindings:
            raise SystemExit("claim fixture bindings differ from the baseline manifest")
        fixture_ids = claim.get("fixture_ids")
        if not isinstance(fixture_ids, list) or not set(expected_fixtures).issubset(
            fixture_ids
        ):
            raise SystemExit(
                "claim fixture coverage is not backed by selected fixtures"
            )
        fixture_results = claim.get("fixture_results")
        if not isinstance(fixture_results, list) or {
            item.get("fixture_id") for item in fixture_results if isinstance(item, dict)
        } != set(fixture_ids):
            raise SystemExit("claim fixture results do not cover the selected fixtures")
        if any(
            not isinstance(item, dict)
            or item.get("result") != "pass"
            or not isinstance(item.get("command"), str)
            or not item["command"].strip()
            for item in fixture_results
        ):
            raise SystemExit("claim fixture result is missing a passing command link")
        modes = claim.get("execution_modes")
        if not isinstance(modes, dict) or not {"eager", "lazy"}.issubset(modes):
            raise SystemExit("claim is missing eager/lazy execution dimensions")
        if not isinstance(claim.get("semantic_modes"), list):
            raise SystemExit("claim is missing semantic mode dimensions")
        mode_results = claim.get("mode_results")
        if not isinstance(mode_results, list) or any(
            item.get("result") != "pass"
            for item in mode_results
            if isinstance(item, dict)
        ):
            raise SystemExit("claim is missing passing mode results")
    pushdown = json.loads(
        (EVIDENCE / "portable_pushdown_contract_0_50.json").read_text()
    )
    validate_pushdown_campaign(pushdown)
    proofs = pushdown.get("proofs")
    findings = pushdown.get("findings")
    proof_attestations: dict[str, Mapping[str, Any] | None] = {}
    conformance_names = {
        "duckdb": "portable_duckdb_pushdown_0_50.json",
        **{
            engine: f"portable_{engine}_conformance_0_50.json"
            for engine in EXPECTED_ENGINES - {"duckdb"}
        },
    }
    for engine, name in conformance_names.items():
        conformance = json.loads((EVIDENCE / name).read_text())
        attestation = conformance.get("pushdown_proof_attestation")
        proof_attestations[engine] = (
            cast(Mapping[str, Any], attestation)
            if isinstance(attestation, Mapping)
            else None
        )
    validate_pushdown_findings(
        findings,
        proofs,
        pushdown,
        expected_evidence_fingerprints=expected_pushdown_evidence,
        proof_attestations=proof_attestations,
        authoritative_proof_digests=_proof_authority()["native_proof_digests"],
    )
    adaptive = json.loads(
        (EVIDENCE / "portable_adaptive_handoff_0_50.json").read_text()
    )
    adaptive_fixtures = adaptive.get("fixtures")
    adaptive_command = str(adaptive.get("command") or "")
    if (
        not isinstance(adaptive_fixtures, list)
        or not adaptive_fixtures
        or any(
            not isinstance(fixture, str) or fixture not in adaptive_command
            for fixture in adaptive_fixtures
        )
    ):
        raise SystemExit(
            "adaptive handoff must link each recorded fixture to its executed command"
        )
    scenarios = adaptive.get("scenarios")
    required_scenarios = {
        "partial-required-unknown",
        "preferred-unknown",
        "lowering-effects",
        "graph-valid-alternative",
        "graph-invalid",
        "region-fusion",
        "physical-unit",
        "retry-semantics",
        "security-policy",
        "contract-compatibility",
        "publication-semantics",
        "whole-dag",
        "evidence-drift",
    }
    graph_constraint_expectations = {
        "region-fusion": ("region", "fusion:preserve"),
        "physical-unit": ("physical_unit", "physical_unit:compatible"),
        "retry-semantics": ("whole_dag", "retry:idempotent"),
        "security-policy": ("whole_dag", "security:policy"),
        "contract-compatibility": ("whole_dag", "contract:compatible"),
        "publication-semantics": ("whole_dag", "publication:atomic"),
        "whole-dag": ("whole_dag", "dag:feasible"),
    }
    if (
        not isinstance(scenarios, list)
        or {item.get("id") for item in scenarios if isinstance(item, dict)}
        != required_scenarios
    ):
        raise SystemExit("adaptive handoff scenario coverage is incomplete")
    for scenario in scenarios:
        if (
            not isinstance(scenario, dict)
            or scenario.get("result")
            not in {"pass", "rejected_before_io", "rejected_graph_invalid"}
            or str(scenario.get("fixture") or "") not in adaptive_fixtures
            or str(scenario.get("fixture") or "") not in adaptive_command
        ):
            raise SystemExit(
                "adaptive handoff scenario is not tied to an executed fixture"
            )
        if scenario["id"] != "evidence-drift":
            evaluation = scenario.get("candidate_evaluation")
            if (
                not isinstance(evaluation, dict)
                or not isinstance(evaluation.get("candidates"), list)
                or not evaluation["candidates"]
            ):
                raise SystemExit(
                    "adaptive scenario lacks candidate evaluation evidence"
                )
            seen_targets: set[tuple[str, str]] = set()
            targets_by_node: dict[str, set[str]] = {}
            for candidate in evaluation["candidates"]:
                if (
                    not isinstance(candidate, dict)
                    or not isinstance(candidate.get("id"), str)
                    or not isinstance(candidate.get("node"), str)
                    or not candidate.get("node")
                    or not isinstance(candidate.get("eligible"), bool)
                    or candidate.get("decision")
                    not in {"eligible", "eliminated_before_preference_scoring"}
                    or (
                        candidate["eligible"]
                        and not isinstance(candidate.get("preferred_score"), int)
                    )
                    or (
                        not candidate["eligible"]
                        and candidate.get("preferred_score") is not None
                    )
                ):
                    raise SystemExit("adaptive candidate evaluation is incomplete")
                requirements = candidate.get("requirements")
                if not isinstance(requirements, dict):
                    raise SystemExit("adaptive candidate requirements are missing")
                support_report = candidate.get("support_report")
                if not isinstance(support_report, dict):
                    raise SystemExit("adaptive candidate support evidence is missing")
                target_key = validate_adaptive_target_binding(
                    candidate,
                    node=str(candidate["node"]),
                    seen_targets=seen_targets,
                )
                targets_by_node.setdefault(str(candidate["node"]), set()).add(
                    target_key
                )
                try:
                    validate_requirement_support_payload(support_report)
                except ValueError as exc:
                    raise SystemExit(
                        "adaptive candidate support evidence is invalid"
                    ) from exc
                support_requirements = {
                    str(item["id"]): item for item in support_report["requirements"]
                }
                support_findings = {
                    str(item["requirement"]): item
                    for item in support_report["findings"]
                }
                aliases = {
                    str((item.get("parameters") or {}).get("value")): identifier
                    for identifier, item in support_requirements.items()
                    if (item.get("parameters") or {}).get("value") is not None
                }
                resolved = {
                    requirement: (
                        requirement
                        if requirement in support_findings
                        else aliases.get(requirement)
                    )
                    for requirement in requirements
                }
                if (
                    None in resolved.values()
                    or set(resolved.values())
                    != {
                        identifier
                        for identifier, item in support_requirements.items()
                        if item.get("applicability") == "applicable"
                    }
                    or any(
                        identifier is None
                        or support_findings[identifier].get("support")
                        != requirements[requirement]
                        for requirement, identifier in resolved.items()
                    )
                ):
                    raise SystemExit("adaptive support vector is not evidence-backed")
                validate_adaptive_lowering_binding(
                    candidate,
                    requirements,
                    support_findings,
                    resolved,
                )
            nodes = evaluation.get("nodes")
            if not isinstance(nodes, list) or len(nodes) < 2:
                raise SystemExit(
                    "adaptive evaluation must cover multiple logical nodes"
                )
            validate_adaptive_target_matrix(targets_by_node, nodes)
            if scenario["id"] in {"graph-invalid", *graph_constraint_expectations} and (
                evaluation.get("graph_valid") is not False
                or not evaluation.get("graph_failures")
            ):
                raise SystemExit("adaptive graph-invalid fixture is not rejected")
            if scenario["id"] in graph_constraint_expectations:
                expected_kind, expected_requirement = graph_constraint_expectations[
                    scenario["id"]
                ]
                failures = evaluation["graph_failures"]
                if any(
                    failure.get("constraint") != scenario["id"]
                    or failure.get("kind") != expected_kind
                    or failure.get("requirement") != expected_requirement
                    or failure.get("node") not in evaluation["nodes"]
                    for failure in failures
                ) or {failure.get("node") for failure in failures} != set(
                    evaluation["nodes"]
                ):
                    raise SystemExit("adaptive graph constraint evidence is incomplete")
            if scenario["id"] == "graph-valid-alternative" and (
                evaluation.get("graph_valid") is not True
                or evaluation.get("graph_failures")
            ):
                raise SystemExit("adaptive graph-valid alternative is not selected")
            validate_adaptive_selection(evaluation)
    if adaptive.get("execution") != "planning-only; no adaptive execution":
        raise SystemExit("adaptive handoff must declare planning-only execution")
    dependency = json.loads(
        (EVIDENCE / "portable_dependency_security_0_50.json").read_text()
    )
    if "check_portable_0_50_dependencies.py" not in str(
        dependency.get("command") or ""
    ):
        raise SystemExit("dependency evidence must run isolated wheel checks")
    if "isolated_local_conformance" not in set(dependency.get("checks") or ()):
        raise SystemExit("dependency evidence must run isolated Local conformance")
    findings_doc = (EVIDENCE / "FINDINGS_0_50.md").read_text()
    migration_doc = (EVIDENCE / "MIGRATION_0_49_TO_0_50.md").read_text()
    whats_new_doc = (EVIDENCE / "WHATS_NEW_0_50.md").read_text()
    validate_findings_ledger(findings_doc)
    for phrase in ("baseline", "repin", "rollback", "native"):
        if phrase not in migration_doc.lower():
            raise SystemExit("migration guidance is incomplete")
    for phrase in ("Qualified matrix", "Local", "Polars", "SQL", "does not claim"):
        if phrase.lower() not in whats_new_doc.lower():
            raise SystemExit("what's-new qualification matrix is incomplete")
    cross_engine = json.loads(
        (EVIDENCE / "portable_cross_engine_0_50.json").read_text()
    )
    validate_cross_engine_digests(cross_engine)
    print("0.50 evidence artifact set is complete and structurally valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
