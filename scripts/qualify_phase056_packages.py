#!/usr/bin/env python3
"""Qualify installed ETLantic 0.55 wheels outside the workspace source tree.

Run this script with ``python -I`` from a clean environment that installed the
candidate wheel set. The report is safe to publish: it contains package names,
versions, export names/counts, schema hashes, and migration identities only.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata as metadata
import importlib.util
import json
import platform
import re
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from email.parser import Parser
from pathlib import Path
from typing import Any, cast
from zipfile import ZipFile

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

PACKAGES = {
    "etlantic": "etlantic",
    "etlantic-airflow": "etlantic_airflow",
    "etlantic-datafusion": "etlantic_datafusion",
    "etlantic-duckdb": "etlantic_duckdb",
    "etlantic-fastapi": "etlantic_fastapi",
    "etlantic-foundry": "etlantic_foundry",
    "etlantic-iceberg": "etlantic_iceberg",
    "etlantic-k8s": "etlantic_k8s",
    "etlantic-kafka": "etlantic_kafka",
    "etlantic-keyring": "etlantic_keyring",
    "etlantic-lsp": "etlantic_lsp",
    "etlantic-mcp": "etlantic_mcp",
    "etlantic-openlineage": "etlantic_openlineage",
    "etlantic-pandas": "etlantic_pandas",
    "etlantic-polars": "etlantic_polars",
    "etlantic-prefect": "etlantic_prefect",
    "etlantic-pyspark": "etlantic_pyspark",
    "etlantic-s3": "etlantic_s3",
    "etlantic-schemaregistry": "etlantic_schemaregistry",
    "etlantic-snowflake": "etlantic_snowflake",
    "etlantic-spark-connect": "etlantic_spark_connect",
    "etlantic-sparkforge": "etlantic_sparkforge",
    "etlantic-sql": "etlantic_sql",
    "etlantic-sqlmodel": "etlantic_sqlmodel",
    "medallantic": "medallantic",
}


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _wheel_report(repo: Path, wheel_dir: Path) -> dict[str, Any]:
    manifest_path = repo / "docs/11_DEVELOPMENT/evidence/phase_0_56/WHEEL_MANIFEST.json"
    expected_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    wheels = sorted(wheel_dir.glob("*.whl"))
    observed: dict[str, dict[str, Any]] = {}
    for wheel in wheels:
        digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
        with ZipFile(wheel) as archive:
            metadata_path = next(
                name
                for name in archive.namelist()
                if name.endswith(".dist-info/METADATA")
            )
            package_metadata = Parser().parsestr(
                archive.read(metadata_path).decode("utf-8")
            )
        distribution = canonicalize_name(package_metadata["Name"])
        observed[wheel.name] = {
            "distribution": distribution,
            "version": package_metadata["Version"],
            "sha256": digest,
            "size_bytes": wheel.stat().st_size,
        }
    expected = {
        row["filename"]: {
            "sha256": row["sha256"],
            "size_bytes": row["size_bytes"],
        }
        for row in expected_manifest["packages"]
    }
    if expected_manifest.get("package_count") != len(expected) or set(expected) != set(
        observed
    ):
        raise RuntimeError("Built wheel inventory differs from WHEEL_MANIFEST.json")
    expected_distributions = {canonicalize_name(name) for name in PACKAGES}
    if {row["distribution"] for row in observed.values()} != expected_distributions:
        raise RuntimeError(
            "Built wheel set does not cover the 25 supported distributions"
        )
    for filename, identity in expected.items():
        if any(
            observed[filename][field] != identity[field]
            for field in ("sha256", "size_bytes")
        ):
            raise RuntimeError(f"Built wheel hash/size differs for {filename}")
    if any(row["version"] != "0.55.0" for row in observed.values()):
        raise RuntimeError("Candidate wheel set has an unexpected package version")
    return {
        "package_count": len(observed),
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "wheel_directory": str(wheel_dir.resolve()),
        "packages": [observed[key] | {"filename": key} for key in sorted(observed)],
        "status": "passed",
    }


def _snapshot(repo: Path, name: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads((repo / "tests" / "fastapi" / name).read_text(encoding="utf-8")),
    )


def _validate_schema_references(document: dict[str, Any]) -> int:
    references: list[str] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            mapping = cast(dict[str, Any], value)
            reference = mapping.get("$ref")
            if isinstance(reference, str):
                references.append(reference)
            for child in mapping.values():
                visit(child)
        elif isinstance(value, list):
            for child in cast(list[Any], value):
                visit(child)

    visit(document)
    for reference in references:
        if not reference.startswith("#/"):
            raise RuntimeError(f"OpenAPI has a non-local schema reference: {reference}")
        target: Any = cast(Any, document)
        for part in reference[2:].split("/"):
            key = part.replace("~1", "/").replace("~0", "~")
            if not isinstance(target, dict) or key not in target:
                raise RuntimeError(
                    f"OpenAPI schema reference does not resolve: {reference}"
                )
            target = cast(Any, target)[key]
    return len(references)


def _operation_ids(openapi: Mapping[str, Any]) -> list[str]:
    paths = cast(Mapping[str, Any], openapi["paths"])
    operation_ids: list[str] = []
    for path in paths.values():
        for method, operation in cast(Mapping[str, Any], path).items():
            if method.startswith("x-") or not isinstance(operation, dict):
                continue
            operation_id = cast(dict[str, Any], operation).get("operationId")
            if isinstance(operation_id, str):
                operation_ids.append(operation_id)
    return operation_ids


def _openapi_report(repo: Path) -> dict[str, Any]:
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

    common: dict[str, Any] = {
        "authorizer": MemoryAuthorizer(),
        "definitions": MemoryDefinitionRepository(),
        "submissions": MemorySubmissionStore(),
        "events": MemoryEventStore(),
        "context_factory": membership_context_factory(
            {
                "qualification-user": (
                    "qualification-tenant",
                    "qualification-workspace",
                    "development",
                    "default",
                )
            }
        ),
        "principal_dependency": principal_from_header,
    }
    cp1: dict[str, Any] = create_app(ETLanticAPI(**common)).openapi()
    cp1_reference_count = _validate_schema_references(cp1)
    cp1_dump: dict[str, Any] = {
        "openapi": cp1["openapi"],
        "paths": sorted(cast(Mapping[str, Any], cp1["paths"])),
        "operationIds": sorted(_operation_ids(cp1)),
    }
    cp1_expected = _snapshot(repo, "openapi_cp1_snapshot.json")
    if cp1_dump != cp1_expected:
        raise RuntimeError("Installed CP1 OpenAPI differs from its committed snapshot")

    ga_services: dict[str, Any] = {
        **common,
        "policy": MemoryPolicyProvider(),
        "approvals": MemoryApprovalStore(),
        "quotas": MemoryQuotaProvider(),
        "erasure": MemoryErasureStore(),
        "audit": MemoryAuditEvidenceStore(),
        "attestations": MemoryAttestationStore.for_tests(),
        "objectives": MemoryObjectiveStore(),
    }
    ga: dict[str, Any] = create_app(ETLanticAPI(**ga_services)).openapi()
    ga_reference_count = _validate_schema_references(ga)
    ga_dump: dict[str, Any] = {
        "openapi": ga.get("openapi"),
        "operationIds": sorted(_operation_ids(ga)),
    }
    ga_expected = _snapshot(repo, "openapi_cp_ga_snapshot.json")
    if ga_dump != ga_expected:
        raise RuntimeError(
            "Installed CP-GA OpenAPI differs from its committed snapshot"
        )

    return {
        "cp1": {
            **cp1_dump,
            "component_schema_count": len(cp1.get("components", {}).get("schemas", {})),
            "schema_reference_count": cp1_reference_count,
            "components_sha256": _digest(cp1.get("components", {})),
        },
        "cp_ga": {
            **ga_dump,
            "component_schema_count": len(ga.get("components", {}).get("schemas", {})),
            "schema_reference_count": ga_reference_count,
            "components_sha256": _digest(ga.get("components", {})),
        },
    }


def _package_report(repo: Path) -> dict[str, Any]:
    package_rows: list[dict[str, Any]] = []
    for distribution, module_name in PACKAGES.items():
        installed_version = metadata.version(distribution)
        if installed_version != "0.55.0":
            raise RuntimeError(
                f"Unexpected installed version for {distribution}: {installed_version}"
            )
        spec = importlib.util.find_spec(module_name)
        if spec is None or spec.origin is None:
            raise RuntimeError(f"Public package {module_name} cannot be resolved")
        origin = Path(spec.origin).resolve()
        if Path(repo).resolve() in origin.parents:
            raise RuntimeError(f"{module_name} imported from the workspace: {origin}")
        package = importlib.import_module(module_name)
        exports_raw: object = getattr(package, "__all__", ())
        if not isinstance(exports_raw, (tuple, list)):
            raise RuntimeError(f"{module_name}.__all__ is not a public export sequence")
        exports = cast(tuple[str, ...] | list[str], exports_raw)
        unresolved = [name for name in exports if not hasattr(package, name)]
        if unresolved:
            raise RuntimeError(f"{module_name} has unresolved exports: {unresolved}")
        package_rows.append(
            {
                "distribution": distribution,
                "version": installed_version,
                "module": module_name,
                "public_export_count": len(exports),
                "public_exports_sha256": _digest(sorted(exports)),
                "import_origin": str(origin),
                "status": "passed",
            }
        )

    version_skew: list[dict[str, str]] = []
    for distribution in PACKAGES:
        if distribution == "etlantic":
            continue
        requirements = metadata.requires(distribution) or []
        base_distribution = (
            "medallantic" if distribution == "etlantic-sparkforge" else "etlantic"
        )
        core_requirements = [
            Requirement(line)
            for line in requirements
            if Requirement(line).name.lower().replace("_", "-") == base_distribution
            and not Requirement(line).marker
        ]
        if len(core_requirements) != 1:
            raise RuntimeError(
                f"{distribution} must declare one unconditional {base_distribution} range"
            )
        requirement = core_requirements[0]
        installed_base = Version(metadata.version(base_distribution))
        if installed_base not in requirement.specifier:
            raise RuntimeError(
                f"Installed {base_distribution} {installed_base} is outside {distribution}'s "
                f"declared range {requirement.specifier}"
            )
        version_skew.append(
            {
                "distribution": distribution,
                "base_distribution": base_distribution,
                "base_requirement": str(requirement.specifier),
                "candidate_base_accepted": str(installed_base in requirement.specifier),
                "outside_0_55_major_minor_rejected": str(
                    Version("0.54.99") not in requirement.specifier
                    and Version("0.56.0") not in requirement.specifier
                ),
            }
        )

    return {
        "package_count": len(package_rows),
        "packages": package_rows,
        "version_skew": version_skew,
        "resolved_dependency_versions": {
            name: metadata.version(name)
            for name in (
                "anyio",
                "fastapi",
                "pydantic",
                "sqlalchemy",
                "sqlmodel",
                "alembic",
                "duckdb",
                "datafusion",
                "pandas",
                "polars",
                "pyarrow",
                "prefect",
                "pyspark",
                "pygls",
                "lsprotocol",
                "keyring",
                "httpx2",
            )
        },
    }


def _migration_report() -> dict[str, Any]:
    from etlantic.control_plane import (
        ControlPlaneContext,
        EnvironmentRef,
        Principal,
        SecurityDomain,
        TenantRef,
        WorkspaceRef,
    )
    from etlantic_sqlmodel.control_plane import (
        SQLModelDefinitionRepository,
        SqlModelEventStore,
        SQLModelSubmissionStore,
        create_sqlite_engine,
    )
    from etlantic_sqlmodel.migrations import (
        VERSIONS,
        current_version,
        downgrade,
        upgrade,
    )

    context = ControlPlaneContext(
        principal=Principal(subject="qualification-user"),
        tenant=TenantRef(tenant_id="qualification-tenant"),
        workspace=WorkspaceRef(
            tenant_id="qualification-tenant", workspace_id="qualification-workspace"
        ),
        environment=EnvironmentRef(name="development"),
        security_domain=SecurityDomain(domain_id="default"),
    )
    with tempfile.TemporaryDirectory(prefix="etlantic-ac056-040-") as directory:
        engine = create_sqlite_engine(
            f"sqlite:///{Path(directory) / 'qualification.db'}"
        )
        if upgrade(engine) != VERSIONS[-1]:
            raise RuntimeError("Migration chain did not reach its latest head")
        definitions = SQLModelDefinitionRepository(engine)
        submissions = SQLModelSubmissionStore(engine)
        events = SqlModelEventStore(engine)
        definition = {"name": "qualification-record", "schema": "compatibility/1"}
        definitions.put(context, "compatibility-definition", definition)
        acceptance = submissions.accept(
            context,
            idempotency_key="compatibility-submission",
            payload={"definition_id": "compatibility-definition"},
        )
        receipt = acceptance.receipt
        event = events.append(
            context,
            kind="run.accepted",
            payload={"submission_id": receipt.submission_id},
        )

        rollback_heads: list[str] = []
        for head in VERSIONS[4:-1]:
            if downgrade(engine, target=head) != head:
                raise RuntimeError(f"Downgrade failed to reach {head}")
            if upgrade(engine) != VERSIONS[-1]:
                raise RuntimeError(f"Upgrade failed after rollback from {head}")
            if definitions.get(context, "compatibility-definition") != definition:
                raise RuntimeError(f"Definition record was lost across {head} rollback")
            recovered = submissions.lookup_idempotency(
                context, "compatibility-submission"
            )
            if recovered is None or recovered.submission_id != receipt.submission_id:
                raise RuntimeError(
                    f"Submission identity changed across {head} rollback"
                )
            replayed = events.list_after_cursor(context, None, limit=20)
            if [item.event_id for item in replayed] != [event.event_id]:
                raise RuntimeError(f"Event history changed across {head} rollback")
            rollback_heads.append(head)
        version = current_version(engine)
        engine.dispose()

    return {
        "migration_versions": list(VERSIONS),
        "latest_head": version,
        "fresh_upgrade": "passed",
        "rollback_heads_reupgraded": rollback_heads,
        "core_records_preserved": ["definition", "submission_idempotency", "event"],
        "status": "passed",
    }


def _verification_report(repo: Path) -> list[dict[str, Any]]:
    suites = [
        [
            "tests/sqlmodel/test_cp1_migrations_0_51.py",
            "tests/fastapi/test_cp1_openapi.py",
            "tests/fastapi/test_cp_ga_openapi_0_43.py",
            "tests/plan/test_wire_schemas_0_19.py",
            "tests/plan/test_schema_version_0_19.py",
        ],
        [
            "tests/compatibility",
            "tests/connectors/test_connector_configuration_schemas_0_56.py",
            "tests/schema_drift/test_schema_drift.py",
            "tests/schema_drift/test_schema_history_hardening_0_34.py",
        ],
    ]
    results: list[dict[str, Any]] = []
    for paths in suites:
        command = [sys.executable, "-I", "-m", "pytest", "-q", *paths]
        completed = subprocess.run(
            command,
            cwd=repo,
            check=False,
            capture_output=True,
            text=True,
        )
        output = f"{completed.stdout}\n{completed.stderr}".strip()
        summary = re.search(
            r"(\d+ passed(?:, \d+ skipped)?(?:, \d+ deselected)?)", output
        )
        if completed.returncode != 0 or summary is None:
            raise RuntimeError(
                "Installed-wheel compatibility suite failed: " + output[-4000:]
            )
        fields = summary.group(1)
        passed = re.search(r"(\d+) passed", fields)
        skipped = re.search(r"(\d+) skipped", fields)
        results.append(
            {
                "command": command[2:],
                "test_paths": paths,
                "passed": int(passed.group(1)) if passed else 0,
                "skipped": int(skipped.group(1)) if skipped else 0,
                "summary": fields,
                "status": "passed",
            }
        )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--wheel-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    repo = args.repo_root.resolve()
    if sys.prefix == sys.base_prefix:
        raise SystemExit("Run this qualifier inside a clean virtual environment")
    if any(Path(path or ".").resolve() == repo for path in sys.path):
        raise SystemExit(
            "Run with python -I so the workspace cannot shadow installed wheels"
        )

    report = {
        "schema": "etlantic.phase056.package_qualification/1",
        "environment": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "isolated_mode": sys.flags.isolated == 1,
        },
        "built_wheels": _wheel_report(repo, args.wheel_dir.resolve()),
        "package_exports": _package_report(repo),
        "openapi_and_schemas": _openapi_report(repo),
        "migrations": _migration_report(),
        "verification_suites": _verification_report(repo),
        "status": "passed",
    }
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
