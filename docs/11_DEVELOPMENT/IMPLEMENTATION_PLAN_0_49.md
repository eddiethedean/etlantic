---
title: ETLantic 0.49 Implementation Plan
description: Implementation-grade plan for the full optional DuckDB engine package.
plan_status: current
plan_last_reviewed: 0.48.0
---

# ETLantic 0.49 Implementation Plan

Phase 0.49 is dedicated to delivering a complete, independently installable
`etlantic-duckdb` engine package. It establishes DuckDB as a trusted ETLantic
target through the public SQL plugin and transform-compiler protocols, with a
truthful capability manifest, safe connection lifecycle, native relational
execution, and reproducible qualification evidence.

The package is optional and Experimental at phase entry. It must be useful for
definitions whose complete requirement vectors it can prove, while rejecting
unsupported, unavailable, or unknown requirements before execution or I/O. The
portable seven-engine baseline and pushdown contract move to phase 0.50;
adaptive physical-DAG work moves to phase 0.51.

The governing backlog is [epic #110](https://github.com/eddiethedean/etlantic/issues/110),
with stories #111–#117, and the [0.49 exit gate](EXIT_GATE_0_49.md).

## Outcome

An author can install `etlantic-duckdb`, authorize it in a production profile,
select `sql_engine="duckdb"`, and validate, plan, compile, and run qualified
embedded DuckDB work without adding DuckDB to ETLantic core. Plans and reports
contain logical bindings, requirement findings, evidence fingerprints, and
stable diagnostics—not connection objects, source rows, secrets, or backend
paths that should remain private.

## Scope

- A package named `etlantic-duckdb` with engine identity `duckdb`.
- Entry-point discovery through `etlantic.sql_plugins` and
  `etlantic.transform_compilers`.
- Native `duckdb.connect` lifecycle with run-scoped connections, explicit
  transactions, deterministic cleanup, and read-only support.
- Typed SQL/relational lowering using DuckDB-native execution and
  `DuckDBPyRelation` handles where the protocol permits lazy execution.
- A versioned DuckDB dialect and capability manifest; PostgreSQL similarity is
  never treated as proof of semantic equivalence.
- A truthful requirement/support matrix using `required`, `preferred`, and
  `informational` obligations plus `supported_exact`,
  `supported_with_lowering`, `unsupported`, `unavailable`, and `unknown`.
- In-memory and local file-backed embedded targets first; connectors and bounded
  Parquet/CSV sources are separate capabilities gated by explicit ownership,
  schema, atomicity, and cleanup evidence.
- Public SQL and portable-transform conformance, security-policy tests, and a
  machine-readable phase 0.50 handoff artifact.

## Explicit Non-Goals

- A DuckDB dependency in ETLantic core.
- Server/Quack, remote, federated, or multi-process writer support.
- Automatic `INSTALL`/`LOAD`, community extensions, network file access, or
  arbitrary file functions.
- Raw SQL or trusted-fragment escape hatches in portable definitions.
- Python UDF fallback, hidden eager collection, or silent routing to another
  engine.
- DuckDB adaptive availability in phase 0.51 before its separate physical-DAG
  evidence passes.

## Public Package Contract

| Surface | Contract |
|---|---|
| Package metadata | Optional `etlantic-duckdb` distribution with a tested DuckDB version range and no core dependency leakage |
| Plugin discovery | `etlantic.sql_plugins` provider key `duckdb`; authorize before import; manifest declares protocol and capability versions |
| SQL runtime | Implement the public `etlantic.sql/1` plugin methods, parameter binding, relation handles, write execution, staging, and cleanup |
| Transform compiler | Implement structured analysis, compile, and execute reports; no aggregate capability claim can hide a required failure |
| Connection identity | Stable engine/compiler/version/config fingerprints; no secrets, executable handles, or sensitive paths in serialized plans |
| Security | Production allowlist, bounded identifiers, bound parameters, disabled extensions by default, fail-closed policy diagnostics |
| Runtime isolation | One connection per run/worker or thread-local cursor; no module-global shared connection; deterministic close/rollback |

## Requirement And Support Rules

Every claimed DuckDB operation is evaluated at the exact node, expression,
contract, connector, and physical-boundary scope. Required unknown,
unsupported, unavailable, omitted, or unresolved-conditional requirements
reject planning. Preferred unknown receives no placement benefit. A lowering is
valid only with a stable identity, resolved conditions, proof evidence, and
declared physical effects such as collection, transfer, or materialization.

Partial support is a first-class result, not a reason to claim a full DuckDB
profile. A package release may execute a supported subset, but the published
matrix must identify the exact subset and negative cases. This evidence is the
input to phase 0.50's portable qualification and phase 0.51's adaptive
candidate evaluation; neither phase may infer support from package installation
or the engine name.

## Workstreams

| ID | Workstream | Deliverables | Completion evidence | Issue |
|---|---|---|---|---|
| 049-P | Package and trust | Distribution metadata, optional dependency group, plugin manifest, discovery, allowlist, public README | Clean install/import with and without DuckDB; authorize-before-load and redaction tests | [#111](https://github.com/eddiethedean/etlantic/issues/111) |
| 049-C | Connection runtime | Run-scoped connections, read-only mode, transactions, rollback, cleanup, staging, retry/idempotency diagnostics | In-memory/file-backed/threaded lifecycle and failure campaign | [#112](https://github.com/eddiethedean/etlantic/issues/112) |
| 049-T | SQL protocol | `etlantic.sql/1` implementation, typed relation handles, bound parameters, writes, fetch/materialization boundaries | Public SQL conformance and handle/parameter tests | [#113](https://github.com/eddiethedean/etlantic/issues/113) |
| 049-D | Dialect and compiler | DuckDB SQL IR lowering, semantic edge handling, structured support findings, declared lowerings | Dialect differential corpus and requirement-level negative fixtures | [#114](https://github.com/eddiethedean/etlantic/issues/114) |
| 049-I | I/O qualification | Optional table/file source, sink, and storage capabilities with ownership and publication semantics | Connector conformance only for explicitly qualified capabilities | [#115](https://github.com/eddiethedean/etlantic/issues/115) |
| 049-Q | Security and quality | Extension policy, file-access policy, identifier validation, no-UDF/no-raw-SQL enforcement | Security, dependency-boundary, and fail-closed diagnostics report | [#116](https://github.com/eddiethedean/etlantic/issues/116) |
| 049-E | Evidence and handoff | Versioned capability matrix, package digest, conformance artifacts, phase 0.50 candidate fixture | Reproducible evidence manifest and drift/replan fixture | [#117](https://github.com/eddiethedean/etlantic/issues/117) |

## Delivery Sequence

1. Freeze package identity, protocol versions, dependency/version policy, trust
   manifest, and the supported embedded target modes.
2. Implement connection lifecycle and SQL protocol behavior before advertising
   compiler or connector capabilities.
3. Add DuckDB dialect lowering and portable-transform analysis with exact
   requirement findings; reject unsupported semantics before I/O.
4. Qualify in-memory and file-backed execution, transactions, cleanup,
   concurrency boundaries, and publication behavior.
5. Add source/sink capabilities only when their ownership, schema, idempotency,
   atomicity, and security evidence is complete.
6. Run public SQL/portable conformance, semantic differential fixtures, and the
   negative corpus in isolated environments.
7. Publish the Experimental capability matrix and emit the phase 0.50/0.51
   handoff without making an adaptive availability claim.

## Exit Gates

- `etlantic-duckdb` installs independently and does not alter core dependency
  resolution or import behavior.
- Discovery authorizes before loading; production profiles require an explicit
  plugin allowlist entry.
- Plans and reports contain no secrets, source rows, executable DuckDB objects,
  connection strings, or uncontrolled file paths.
- Connections are run-scoped or thread-local, close deterministically, and
  rollback on failure; read-only and multi-process restrictions are explicit.
- Relation handles remain lazy until a declared fetch, validation, transfer, or
  publication boundary.
- Every advertised SQL, transform, connector, and mode capability maps to
  passing public fixtures and a versioned manifest entry.
- DuckDB dialect deviations, null/missing-invalid behavior, numerics, casts,
  timestamps, ordering, joins, unions, empty inputs, deduplication, and
  publication semantics are covered by deterministic evidence.
- Extension installation/loading, arbitrary file access, raw SQL, Python UDFs,
  and unsupported dialect features fail closed before external I/O.
- Partial, unsupported, unavailable, unknown, and lowered support states remain
  visible with stable reasons and evidence fingerprints.
- The package produces a machine-readable handoff suitable for phase 0.50
  portable qualification and phase 0.51 adaptive candidate evaluation.

## Required Release Evidence

- `duckdb_package_manifest_0_49.json` and signed package/version digest.
- `duckdb_sql_conformance_0_49.json` and `duckdb_transform_conformance_0_49.json`.
- `duckdb_connection_lifecycle_0_49.json` covering transactions, cleanup,
  retries, read-only mode, and thread/process boundaries.
- `duckdb_security_policy_0_49.json` covering extension, file-access, raw-SQL,
  parameter, identifier, and UDF rejection.
- `duckdb_requirement_support_0_49.json` covering exact, lowered, partial,
  unsupported, unavailable, and unknown findings.
- `duckdb_adaptive_handoff_0_49.json` with per-node eligibility, lowering
  effects, evidence fingerprints, and replan-on-drift fixtures.

## Phase Boundaries

Phase 0.50 owns the frozen portable baseline across Local, Polars, Pandas, SQL,
PySpark, and DataFusion, and may consume DuckDB evidence as a separately
qualified optional target. Phase 0.51 owns adaptive placement and physical DAGs;
DuckDB participates only after its target, handoffs, retry, publication,
security, and whole-DAG admission evidence passes the adaptive gate.
