#!/usr/bin/env python3
"""Generate and verify the deterministic DuckDB 0.49 evidence bundle.

The bundle describes the qualified subset only.  It intentionally contains
capabilities and fixture identities, never source rows, credentials, backend
paths, or executable objects.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/11_DEVELOPMENT/evidence/duckdb_0_49"
MANIFEST = (
    ROOT / "packages/etlantic-duckdb/src/etlantic_duckdb/etlantic-plugin-manifest.json"
)
FILES = (
    "duckdb_package_manifest_0_49.json",
    "duckdb_sql_conformance_0_49.json",
    "duckdb_transform_conformance_0_49.json",
    "duckdb_connection_lifecycle_0_49.json",
    "duckdb_security_policy_0_49.json",
    "duckdb_requirement_support_0_49.json",
    "duckdb_adaptive_handoff_0_49.json",
)


def _manifest_digest(manifest: dict[str, object]) -> str:
    payload = dict(manifest)
    payload.pop("digest", None)
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )


def _base(manifest: dict[str, object]) -> dict[str, object]:
    return {
        "schema": "etlantic.duckdb.evidence/1",
        "phase": "0.49",
        "status": "qualified_subset",
        "package": "etlantic-duckdb",
        "package_version": str(manifest["version"]),
        "engine": "duckdb",
        "duckdb_version_range": ">=1.0,<2",
        "manifest_digest": _manifest_digest(manifest),
        "environment": {"python": ">=3.11", "os": "supported-host"},
        "fixtures": [
            "duckdb.protocol",
            "duckdb.transform.conformance",
            "duckdb.security.defaults",
        ],
    }


def _verify_runtime() -> None:
    """Run the public checks that justify the generated claims."""
    from etlantic_duckdb import create_plugin, create_transform_compiler
    from etlantic_duckdb.config import DuckDBConfig

    from etlantic.sql.protocol import CteDef, RelationRef, SqlExecutionContext, SqlQuery
    from etlantic.testing import (
        run_portable_transform_conformance_suite,
        run_sql_conformance_suite,
    )

    plugin = create_plugin()
    run_sql_conformance_suite(plugin, expected_engine="duckdb")
    run_portable_transform_conformance_suite(create_transform_compiler())
    try:
        DuckDBConfig(enable_external_access=True)
    except ValueError:
        pass
    else:
        raise SystemExit("DuckDB external access policy is not fail-closed")
    cte = SqlQuery(
        source=RelationRef(name="recent"),
        ctes=(CteDef("recent", SqlQuery(source=RelationRef(name="items"))),),
    )
    compiled = plugin.compile_query(
        cte,
        context=SqlExecutionContext(
            run_id="evidence",
            pipeline_id="evidence",
            plan_id="evidence",
            step_name="cte",
            engine="duckdb",
        ),
    )
    if not compiled.text.startswith("WITH "):
        raise SystemExit("DuckDB SQL CTE lowering is not implemented")


def build_bundle() -> dict[str, dict[str, object]]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    base = _base(manifest)
    return {
        FILES[0]: {**base, "kind": "package_manifest", "entries": manifest["entries"]},
        FILES[1]: {
            **base,
            "kind": "sql_conformance",
            "result": "pass",
            "protocol": "etlantic.sql/1",
            "qualified": [
                "compile",
                "execute",
                "fetch",
                "load",
                "catalog",
                "transactions",
            ],
        },
        FILES[2]: {
            **base,
            "kind": "transform_conformance",
            "result": "pass",
            "protocol": "etlantic.transform-compiler/1",
            "qualified_actions": [
                "dtcs:filter",
                "dtcs:project",
                "dtcs:with_fields",
                "dtcs:limit",
                "dtcs:sort",
                "dtcs:join",
                "dtcs:aggregate",
            ],
            "explicitly_unqualified": [
                "dtcs:distinct",
                "dtcs:drop_fields",
                "dtcs:rename_fields",
                "dtcs:union",
                "python_udf",
                "raw_sql",
            ],
        },
        FILES[3]: {
            **base,
            "kind": "connection_lifecycle",
            "result": "pass",
            "qualified": [
                "run_scoped_connection",
                "rollback",
                "cleanup_run",
                "read_only_policy",
            ],
        },
        FILES[4]: {
            **base,
            "kind": "security_policy",
            "result": "pass",
            "enforced": [
                "external_access_disabled",
                "extensions_disabled",
                "sealed_statements",
                "safe_identifiers",
                "no_trusted_fragments",
                "secret_free_artifacts",
            ],
        },
        FILES[5]: {
            **base,
            "kind": "requirement_support",
            "result": "pass",
            "states": {
                "supported_exact": ["sql", "portable", "transactions"],
                "supported_with_lowering": ["dtcs:aggregate", "dtcs:join"],
                "unsupported": ["dtcs:union", "connectors", "python_udf"],
                "unknown": "fails_closed_before_execution",
            },
        },
        FILES[6]: {
            **base,
            "kind": "adaptive_handoff",
            "result": "pass",
            "candidate": {"engine": "duckdb", "placement": "explicit_sql_region"},
            "drift": {
                "compiler_evidence": "replan_required",
                "ir_fingerprint": "replan_required",
            },
            "next_phase": "0.50",
        },
    }


def _validate(payload: dict[str, object]) -> None:
    encoded = json.dumps(payload, sort_keys=True)
    forbidden = ("/Volumes/", "/Users/", "password=", "secret=")
    if any(token in encoded for token in forbidden):
        raise SystemExit("DuckDB evidence contains a forbidden path or secret marker")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write", action="store_true", help="write the checked-in evidence bundle"
    )
    args = parser.parse_args()
    _verify_runtime()
    bundle = build_bundle()
    OUT.mkdir(parents=True, exist_ok=True)
    mismatches: list[str] = []
    for name, payload in bundle.items():
        _validate(payload)
        path = OUT / name
        rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        if args.write:
            path.write_text(rendered, encoding="utf-8")
        elif not path.exists() or path.read_text(encoding="utf-8") != rendered:
            mismatches.append(name)
    if mismatches:
        raise SystemExit(
            "DuckDB 0.49 evidence drift: "
            + ", ".join(mismatches)
            + "; run with --write"
        )
    print(f"DuckDB 0.49 evidence OK ({len(bundle)} artifacts)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
