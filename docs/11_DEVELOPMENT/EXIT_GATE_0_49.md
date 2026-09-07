# Exit Gate 0.49 — DuckDB Engine Package

> **Status: Implemented qualified subset; release gate pending.** The optional
> DuckDB package, selected-engine routing, secure runtime, portable compiler,
> and redacted evidence bundle are implemented. Unproven connectors and full
> dialect equivalence remain explicitly unclaimed.

See the [0.49 implementation plan](IMPLEMENTATION_PLAN_0_49.md) and the
DuckDB package workstream in the roadmap.

## Target Claim

| Surface | Target at gate | Entry state |
|---|---|---|
| `etlantic-duckdb` package | Independently installable Experimental package | Implemented |
| `etlantic.sql/1` plugin | Embedded DuckDB SQL target with declared capabilities | Implemented |
| Portable transform compiler | Requirement-level exact/lowered/negative findings | Implemented subset |
| In-memory execution | Available only after lifecycle and conformance evidence | Qualified |
| File-backed execution | Experimental, explicit read-only/write policy | Policy implemented; qualification pending |
| Table/file connectors | Only individually qualified capabilities | Not qualified |
| Adaptive placement | No 0.49 claim | Deferred to 0.51 |
| Generic SQL-engine routing | Selected/discovered engine preserved end to end | Implemented |
| SQL portable execution | Planned compiler executes without native fallback | Implemented |

## Quantified Exit Scorecard

| # | Measure | Required | Current |
|---|---|---:|---|
| 1 | Package metadata, optional dependency boundary, manifest, and clean install/import pass | Pass | **Pass** |
| 2 | Discovery authorizes before import and production allowlists are enforced | Pass | **Pass** |
| 3 | Engine/compiler/version/config identity is stable and artifacts contain no secrets or backend objects | Pass | **Pass** |
| 4 | Run-scoped/thread-local connections, explicit transactions, rollback, cleanup, and retry diagnostics pass | Pass | **Pass** |
| 5 | In-memory and file-backed read-only behavior is deterministic and policy-enforced | Pass | **Qualified by generated file-backed/read-only fixture** |
| 6 | SQL protocol handles remain lazy until declared fetch/materialization boundaries | Pass | **Pass** |
| 7 | Bound parameters and validated identifiers are enforced; raw SQL and UDF escape hatches fail closed | Pass | **Pass** |
| 8 | DuckDB dialect edge cases pass the declared semantic differential corpus | Pass | **Qualified subset** |
| 9 | Every advertised transform/compiler capability maps to mandatory public fixtures | 100% | **Qualified subset** |
| 10 | Partial, lowered, unsupported, unavailable, and unknown findings are stable, bounded, and fingerprinted | Pass | **Pass** |
| 11 | Optional connectors pass ownership, schema, idempotency, atomicity, publication, and cleanup evidence or remain unclaimed | Pass | **Unclaimed / fail-closed** |
| 12 | Extension installation/loading, arbitrary file access, and unsupported dialect features fail before I/O | Pass | **Pass** |
| 13 | Isolated CI covers supported DuckDB versions and dependency leakage into core | Pass | **OS/Python plus DuckDB min/max matrix wired** |
| 14 | Phase 0.50 portable and phase 0.51 adaptive handoff fixtures prove exact candidate evidence and replan-on-drift | Pass | **Pass** |
| 15 | No unresolved critical/high correctness, security, compatibility, or data-loss finding | 0 | **Pass for qualified subset** |
| 16 | Fake non-`sql` SQL engine proves capability-driven plan/source/step/sink/hybrid routing | Pass | **Generic routing and full protocol fixture implemented** |
| 17 | Additive support-evidence changes preserve frozen `/1` compatibility for existing plugins | Pass | **Pass** |
| 18 | SQL `portable_compiled` execution uses the planned compiler and selected engine with no native fallback | Pass | **Pass** |
| 19 | Run-specific cleanup isolates concurrent connection, relation, parameter, and staging state | Pass | **Pass** |
| 20 | Security settings are verified before work and unknown/tampered compiled statements are rejected | Pass | **Pass** |

## Required Evidence Manifest

| Artifact | Required content | Status |
|---|---|---|
| `duckdb_package_manifest_0_49.json` | Package, protocol, engine/version, dependency, trust, and capability identity | Generated |
| `duckdb_sql_conformance_0_49.json` | SQL protocol, relation handles, parameters, writes, fetch boundaries, and dialect cases | Generated |
| `duckdb_transform_conformance_0_49.json` | Portable transform support findings and semantic differential results | Generated |
| `duckdb_connection_lifecycle_0_49.json` | Connection, transaction, cleanup, retry, read-only, thread, and process fixtures | Generated |
| `duckdb_security_policy_0_49.json` | Extension, file-access, raw-SQL, UDF, identifier, secret, and redaction checks | Generated |
| `duckdb_requirement_support_0_49.json` | Exact, lowered, partial, unsupported, unavailable, unknown, and evidence fingerprints | Generated |
| `duckdb_adaptive_handoff_0_49.json` | Per-node eligibility, lowering effects, candidate rejection, and drift/replan fixtures | Generated |

All seven artifacts must be generated by the checked-in 0.49 evidence command,
schema-validated, deterministic for the same environment, and traceable to the
ETLantic version, DuckDB version, OS/Python identity, capability-manifest
digest, and fixture identities. Evidence must not contain source rows, resolved
secrets, absolute backend paths, or executable objects.

## Required Verification

```bash
uv lock
uv sync --locked --group duckdb
uv run pytest -q tests/duckdb -m duckdb
uv run pytest -q tests/portable_conformance -m duckdb
uv run --with duckdb==1.0.0 pytest -q tests/duckdb -m duckdb
uv run --with duckdb==1.5.5 pytest -q tests/duckdb -m duckdb
uv run python examples/duckdb_portable.py
uv run python scripts/check_duckdb_0_49.py
uv run python scripts/check_plugin_manifests.py
uv run --group polars --group pandas --group sql --group pyspark \
  --group datafusion --group duckdb python scripts/check_transform_compiler_drift.py
uv run python scripts/check_protocol_freeze.py
uv run python scripts/check_release.py
uv run python scripts/check_docs.py
uv run ruff check .
uv run ruff format --check .
uv build --package etlantic
uv build --package etlantic-duckdb
```

The standard core, stable-foundation, security, connector, package, and release
jobs remain required in addition to these phase-specific commands.

## Rollback Trigger

Rollback or downgrade any capability claim for semantic divergence, hidden
materialization, connection leak, unsafe file or extension access, raw SQL or
UDF escape, secret/source-row leakage, nondeterministic result, dependency
leakage into core, or unsupported behavior that reaches external I/O.

Rollback also triggers when selected-engine routing resolves a different plugin,
portable work falls back to a native callable, one run can close another run's
state, a caller-constructed or mutated compiled statement executes, or a
planned evidence fingerprint is accepted after drift.

An affected capability is removed from the manifest and fails closed for new
plans. Existing plans whose compiler or capability fingerprint changed are
invalidated and must be replanned; they are never silently routed to another
engine.

## Explicit Non-Claims

- No full PostgreSQL semantic-equivalence claim.
- No remote, federated, server, Quack, or multi-process writer claim.
- No automatic extension installation/loading or arbitrary file-access claim.
- No 0.50 portable-baseline qualification or 0.51 adaptive availability claim
  until those phases independently pass their gates.
