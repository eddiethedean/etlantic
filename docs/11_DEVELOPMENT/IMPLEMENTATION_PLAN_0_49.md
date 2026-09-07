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
- Additive, backward-compatible core integration needed to route any discovered
  SQL engine by its selected identity rather than by the built-in `sql` alias.
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

## Entry Criteria And Repository Findings

The package cannot satisfy the stated outcome by package-only work. The current
core surfaces expose the right plugin protocols, but the execution and
conformance paths still contain assumptions that only the built-in `sql` engine
uses them. These are phase prerequisites, not later cleanup:

1. `TransformSupportReport` is currently boolean plus an untyped negative
   finding. It cannot represent obligation, exact versus lowered support,
   unavailable or unknown support, lowering conditions, physical effects, or
   evidence identity. Extend the existing `/1` value records with optional
   defaulted fields only; do not add a required method or change existing field
   meaning. Existing third-party compiler fixtures must continue to pass.
2. SQL source, sink, execution-context, and hybrid-fetch paths resolve the
   literal `sql` plugin in several places. They must resolve the selected engine
   for the current node and the producer engine for a cross-engine fetch.
3. The local orchestrator currently admits `portable_compiled` work only for
   dataframe and Spark engines. Add a SQL portable-compiler execution path that
   invokes the planned compiler, preserves SQL relation/query handles between
   SQL nodes, and fetches only at declared boundaries.
4. SQL engine-family classification must consult runtime plugin capabilities or
   registered plugin descriptors at every dispatch point. A fake engine such as
   `acme_sql` must prove the path; adding a DuckDB-only conditional is not an
   acceptable fix.
5. Planning compiler discovery currently derives its include decision from the
   dataframe and Spark selections. A selected `sql_engine` must also cause the
   transform-compiler group to be discovered, authorized, and registered.
6. Public SQL conformance currently assumes `info.engine == "sql"`, and the
   portable fixture factory has no DuckDB adapter. Generalize both around an
   expected engine and explicit frame/relation factories without weakening the
   existing PostgreSQL/SQLite assertions.
7. End-of-run SQL cleanup currently calls a package-wide hook without run
   identity. Add an optional, backward-compatible run-specific cleanup hook and
   invoke it with the completed run context so concurrent runs cannot close one
   another's connections or staging relations.
8. Release, manifest, drift, workspace, pytest-marker, wheel-smoke, and publish
   inventories are explicit lists. The new distribution must be added to every
   applicable inventory and the core-wheel smoke test must assert that `duckdb`
   is absent.

The Plugin SDK `/1` families are frozen. All core changes above therefore use
additive optional records/hooks, capability-driven dispatch, or corrections to
existing generic behavior. Any change that would require an existing plugin to
implement a new method or reinterpret a shipped field requires a new protocol
major and is outside 0.49.

## Public Package Contract

| Surface | Contract |
|---|---|
| Package metadata | Optional `etlantic-duckdb` distribution with a tested DuckDB version range and no core dependency leakage |
| Plugin discovery | `etlantic.sql_plugins` provider key `duckdb`; authorize before import; manifest declares protocol and capability versions |
| Core routing | Selected engine identity is preserved through planning, source/step/sink dispatch, hybrid fetch, diagnostics, and cleanup |
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
| 049-K | Core compatibility and routing | Additive support-evidence records, capability-driven SQL classification, selected-engine dispatch, SQL portable execution, run-specific cleanup, generalized conformance | Existing plugin compatibility plus fake non-`sql` engine validate/plan/run fixtures | [#113](https://github.com/eddiethedean/etlantic/issues/113) |
| 049-P | Package and trust | Distribution metadata, optional dependency group, plugin manifest, discovery, allowlist, public README | Clean install/import with and without DuckDB; authorize-before-load and redaction tests | [#111](https://github.com/eddiethedean/etlantic/issues/111) |
| 049-C | Connection runtime | Run-scoped connections, read-only mode, transactions, rollback, cleanup, staging, retry/idempotency diagnostics | In-memory/file-backed/threaded lifecycle and failure campaign | [#112](https://github.com/eddiethedean/etlantic/issues/112) |
| 049-T | SQL protocol | `etlantic.sql/1` implementation, typed relation handles, bound parameters, writes, fetch/materialization boundaries | Public SQL conformance and handle/parameter tests | [#113](https://github.com/eddiethedean/etlantic/issues/113) |
| 049-D | Dialect and compiler | DuckDB SQL IR lowering, semantic edge handling, structured support findings, declared lowerings | Dialect differential corpus and requirement-level negative fixtures | [#114](https://github.com/eddiethedean/etlantic/issues/114) |
| 049-I | I/O qualification | Optional table/file source, sink, and storage capabilities with ownership and publication semantics | Connector conformance only for explicitly qualified capabilities | [#115](https://github.com/eddiethedean/etlantic/issues/115) |
| 049-Q | Security and quality | Extension policy, file-access policy, identifier validation, no-UDF/no-raw-SQL enforcement | Security, dependency-boundary, and fail-closed diagnostics report | [#116](https://github.com/eddiethedean/etlantic/issues/116) |
| 049-E | Evidence and handoff | Versioned capability matrix, package digest, conformance artifacts, phase 0.50 candidate fixture | Reproducible evidence manifest and drift/replan fixture | [#117](https://github.com/eddiethedean/etlantic/issues/117) |

## Delivery Sequence

Deliver the phase as independently reviewable slices. Each slice keeps the
repository green and may merge only after its listed evidence passes.

### Slice 1 — Core contract and routing unblockers

- Append optional `obligation`, `support`, `lowering_id`, `conditions`,
  `physical_effects`, and `evidence_fingerprint` fields to transform support
  records, with deterministic `to_dict()` output and safe defaults matching the
  current boolean behavior.
- Append an optional compiler evidence fingerprint or equivalent stable
  metadata field to compiler identity. Persist it in implementation selection
  and fail before I/O when the live fingerprint differs from the planned one.
- Include `sql_engine` when deciding whether to discover transform compilers.
- Route SQL plugins by selected engine in source, step, sink, materialization,
  and execution contexts. Resolve the producer's SQL engine at hybrid fetches.
- Admit SQL `portable_compiled` descriptors and execute them through a shared or
  SQL-specific portable compiler helper rather than a native Python callable.
- Add run-specific SQL cleanup while retaining the old cleanup behavior for
  existing plugins.
- Parameterize SQL and portable compiler conformance for non-`sql` engines.
- Prove the entire path with a dependency-free fake `acme_sql` plugin before
  DuckDB-specific code is introduced.

### Slice 2 — Package, identity, and trust boundary

- Create `packages/etlantic-duckdb` with module `etlantic_duckdb`, `py.typed`,
  README, package metadata, and a static manifest.
- Depend only on the matching ETLantic minor and the tested DuckDB range. Do not
  depend on `etlantic-sql`; that would pull SQLAlchemy and Psycopg into the
  DuckDB distribution and would make the package boundary misleading.
- Register `duckdb` in `etlantic.sql_plugins` and
  `etlantic.transform_compilers`. Register connector entry points only after the
  corresponding capability passes its gate.
- Add the package to the uv workspace/source map, root `duckdb` extra and
  dependency group, pytest path/marker, Ruff first-party inventory, manifest
  check, transform drift check, release check, build workflow, wheel smoke, and
  publish workflow; regenerate `uv.lock`.
- Prove production `plugin_allowlist={"etlantic-duckdb": "..."}` authorizes the
  manifest before importing `etlantic_duckdb` or `duckdb`.

### Slice 3 — Secure connection and transaction runtime

- Define typed, immutable public configuration containing logical target mode,
  read-only state, resource limits, root/path references, and a secret-free
  fingerprint. Resolved absolute paths and connection objects remain runtime
  private.
- Use explicit `duckdb.connect()` connection objects only. Never use module
  functions, the shared `:default:` connection, or a module-global connection.
- Use one connection per run with a per-run execution lock. This preserves an
  unnamed in-memory database across pipeline steps while isolating concurrent
  runs. A thread-local cursor is not a concurrency mechanism because DuckDB
  cursors share the same underlying connection.
- Reject read-only in-memory configurations before connect. Qualify
  multi-process file access only in read-only mode; multi-process writers remain
  unsupported.
- Implement explicit begin/commit/rollback, transaction outcome classification,
  idempotency/retry decisions, staging ownership, interruption handling, and
  deterministic `cleanup_run`.
- Treat a failure before transaction start as rolled back, a proven rollback as
  rolled back, and a connection/commit interruption with no authoritative
  receipt as unknown. Never automatically retry an unknown non-idempotent
  publication.

### Slice 4 — `etlantic.sql/1` DuckDB implementation

- Implement identifier validation and DuckDB quoting, `RelationRef` binding,
  query/write compilation, execution, fetch/load, temporary materialization,
  catalog inspection, row-fetch instrumentation, staging cleanup, and
  publication receipts.
- Keep a run-scoped registry of compiled statements and their private bound
  values. `execute()` rejects unknown, mutated, wrong-run, or already-consumed
  compiled artifacts so callers cannot construct `CompiledSql(text=...)` as a
  raw-SQL escape hatch.
- For non-fetch SELECT work, retain a private `DuckDBPyRelation` and expose only
  a logical `RelationRef` or `SqlQuery` to core. Do not call `fetch*`, `df`,
  `pl`, `arrow`, `show`, or `shape` before an explicit fetch, validation,
  transfer, or publication boundary.
- Keep native relation objects in the owning run session. They never enter a
  plan, report, durable artifact, diagnostic, or evidence file and cannot
  outlive connection cleanup.
- Implement append and insert-select first. Claim replace/snapshot/merge only
  after atomicity, retry, and semantic evidence passes; otherwise fail planning
  with an unsupported capability.

### Slice 5 — DuckDB dialect and portable compiler

- Implement DuckDB-specific lowering from the closed ETLantic SQL IR. Do not
  reuse PostgreSQL output as presumed-compatible SQL and do not import private
  implementation modules from `etlantic-sql`.
- Analyze every profile, action, function, operator, type, semantic mode,
  connector, and boundary requirement. Emit one deterministic finding per
  obligation with exact expression/node path and stable reason.
- A lowering claim names its lowering, planning-time conditions, proof fixture,
  and physical effects. An unresolved condition is not supported.
- `compile()` stores only logical IR and explain/evidence metadata in the public
  artifact; the native relation/plan is process-private. `execute()` uses the
  same run connection as the SQL plugin and returns logical handles suitable for
  same-engine consumers.
- Build a normalized differential corpus for null/missing/invalid values,
  Unicode, numeric overflow/rounding, casts, timestamps/time zones, ordering and
  null placement, join types and collision policies, union modes, aggregation,
  deduplication, empty inputs, multiple inputs, and contract-shaped outputs.
- Begin with the smallest subset that passes all mandatory fixtures. Never
  advertise an entire profile based on aggregate engine reputation.

### Slice 6 — Table and bounded-file connectors

- Qualify table source, sink, and schema inspection independently through the
  public connector protocols.
- Add CSV and Parquet capabilities separately. A file capability is eligible
  only if it works with automatic extension installation/loading disabled and
  a `SafeIoPolicy`-resolved `root_ref`, `allowed_paths`, or
  `allowed_directories` boundary.
- Keep `enable_external_access=false`; grant only the resolved local paths
  necessary for the selected connector. Reject absolute user paths, traversal,
  recursive/unbounded globs, URLs, network schemes, environment-derived cloud
  credentials, and paths outside the approved root before opening a connection.
- Prove bounded reads, row-free schema inspection, ownership, staging,
  idempotency, atomic publication, reconciliation, abort, and cleanup. Leave any
  unproven connector absent from the manifest and entry points.

### Slice 7 — Evidence, documentation, and release

- Add `tests/duckdb/` covering package/trust, routing, connection lifecycle, SQL
  protocol, compiler, differential semantics, connectors, security, and
  end-to-end validate/plan/run behavior.
- Add a deterministic `scripts/check_duckdb_0_49.py` gate that generates all
  required JSON evidence, validates schemas and redaction, and compares the
  result with checked-in artifacts. Evidence files are generated, not manually
  edited.
- Run full semantic/failure tests on Linux across the minimum and maximum tested
  DuckDB versions and supported Python versions; run install, import,
  discovery, and lifecycle smoke tests on Linux, macOS, and Windows.
- Build and inspect both wheels in isolation: core alone must have no DuckDB
  distribution/module; the plugin wheel must discover both DuckDB entry points
  and contain its manifest and typing marker.
- Add a runnable embedded example, package/API documentation, capability matrix,
  known limitations, migration guide, What's New page, changelog, findings
  ledger, package digests, and release notes.
- Recheck the `etlantic-duckdb` PyPI project name and configure trusted
  publishing before the release rehearsal. Name availability observed during
  planning is not a release guarantee.
- Mark the exit gate Met only after every advertised claim maps to current
  evidence and the final findings review has no unresolved critical/high item.

## Proposed Package Layout

```text
packages/etlantic-duckdb/
├── pyproject.toml
├── README.md
└── src/etlantic_duckdb/
    ├── __init__.py
    ├── config.py
    ├── policy.py
    ├── connection.py
    ├── relation.py
    ├── dialect.py
    ├── compiler.py
    ├── executor.py
    ├── catalog.py
    ├── writes.py
    ├── plugin.py
    ├── transform_compiler.py
    ├── connectors.py
    ├── lowering/
    │   ├── __init__.py
    │   ├── actions.py
    │   └── expressions.py
    ├── etlantic-plugin-manifest.json
    └── py.typed
```

`__init__.py` exports only stable factories and package version information.
Connection state, compiler registries, resolved paths, and backend types remain
inside the package and are not added to the ETLantic root facade.

## DuckDB Security Baseline

The connection factory applies and verifies the following default-deny posture
before any user work. Exact setting availability belongs to the tested version
matrix; an unavailable required setting makes that DuckDB version unavailable.

| Area | Required behavior |
|---|---|
| External access | `enable_external_access=false`; bounded connector paths use only `allowed_paths` or `allowed_directories` resolved from `SafeIoPolicy` |
| Extensions | `autoinstall_known_extensions=false`, `autoload_known_extensions=false`, `allow_community_extensions=false`, and `allow_unsigned_extensions=false` |
| Credentials | Disable persistent secrets and global cloud credential discovery; never use environment credentials implicitly |
| Configuration | Set resource/security options before work, allow no user-controlled configuration keys, then lock configuration |
| SQL authority | Execute only compiler-sealed closed IR; reject trusted fragments, raw statements, `INSTALL`, `LOAD`, unsafe `ATTACH`, arbitrary `COPY`, UDF registration, and unclaimed table functions |
| Resources | Apply bounded threads, memory, temporary storage, output rows/batches, statement count, and execution timeout where supported; report the enforced values by fingerprint, not secret/path value |
| Paths | Resolve logical root/path references at runtime, normalize before authorization, and serialize only logical references and fingerprints |

These settings are defense in depth. The phase does not claim safe execution of
untrusted SQL, because DuckDB SQL has the privileges of the hosting process.

## Test Matrix

| Layer | Required coverage |
|---|---|
| Core compatibility | Existing first- and third-party `/1` fixtures plus fake `acme_sql` selected-engine routing, SQL portable execution, producer-engine hybrid fetch, and concurrent-run cleanup |
| Package isolation | Core-only install/import, plugin-only install, manifest/digest, entry-point discovery, production allowlist denial/allow, supported DuckDB range, unsupported-version failure |
| Lifecycle | In-memory and file-backed runs, read-only validation, begin/commit/rollback, execute/commit/close faults, cancellation, staging cleanup, thread isolation, multi-process read-only, writer denial |
| SQL protocol | Identifiers, parameters, compiled-artifact sealing, lazy handles, fetch counters, inspection without rows, load, supported writes, atomic publication, unknown-outcome retry suppression |
| Transform compiler | Claim-to-fixture coverage, exact/lowered/negative findings, condition resolution, evidence drift, explain metadata, same-engine handle preservation, no Python/UDF fallback |
| Semantics | Null/missing/invalid, empty inputs, Unicode, numerics, casts, temporal values, ordering, joins, unions, aggregates, dedupe, multiple inputs, output contracts |
| Connectors | Capability-selected source/sink/storage conformance, bounded CSV/Parquet, schema/ownership/idempotency/atomicity/reconciliation/cleanup, negative paths and URLs |
| Security/redaction | Secret/source-row sentinels, absolute and traversal paths, raw/tampered SQL, extension commands, file functions, UDFs, persistent secrets, global credentials, configuration mutation |
| End to end | Development and production profiles using `sql_engine="duckdb"` across validate, plan, run, report, failure, cleanup, and evidence-fingerprint drift |

## Verification Commands

The final repository gate includes at least:

```bash
uv lock
uv sync --locked --group duckdb
uv run pytest -q tests/duckdb -m duckdb
uv run pytest -q tests/portable_conformance -m duckdb
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

The normal core, stable-foundation, security, connector, and package jobs remain
required; the DuckDB job is additional evidence, not a replacement.

## Exit Gates

- `etlantic-duckdb` installs independently and does not alter core dependency
  resolution or import behavior.
- A fake non-`sql` SQL engine proves capability-driven planning and runtime
  routing; no DuckDB-only dispatch branch is required.
- Discovery authorizes before loading; production profiles require an explicit
  plugin allowlist entry.
- Plans and reports contain no secrets, source rows, executable DuckDB objects,
  connection strings, or uncontrolled file paths.
- Connections are run-scoped or thread-local, close deterministically, and
  rollback on failure; read-only and multi-process restrictions are explicit.
- Concurrent runs cannot share or close one another's connection, relation
  handles, bound-parameter registry, or staging state.
- Relation handles remain lazy until a declared fetch, validation, transfer, or
  publication boundary.
- `portable_compiled` DuckDB steps execute through the planned compiler under
  the selected engine identity, not through a native Python fallback.
- Every advertised SQL, transform, connector, and mode capability maps to
  passing public fixtures and a versioned manifest entry.
- DuckDB dialect deviations, null/missing-invalid behavior, numerics, casts,
  timestamps, ordering, joins, unions, empty inputs, deduplication, and
  publication semantics are covered by deterministic evidence.
- Extension installation/loading, arbitrary file access, raw SQL, Python UDFs,
  and unsupported dialect features fail closed before external I/O.
- The security configuration is applied and verified before work, and tampered
  or caller-constructed compiled statements are rejected.
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

Each evidence document records its schema, generator version, ETLantic version,
DuckDB version, OS/Python identity, capability-manifest digest, deterministic
fixture identities, result status, and redacted diagnostics. It contains no
source rows, resolved secrets, absolute backend paths, or executable objects.

## Phase Boundaries

Phase 0.50 owns the frozen portable baseline across Local, Polars, Pandas, SQL,
PySpark, and DataFusion, and may consume DuckDB evidence as a separately
qualified optional target. Phase 0.51 owns adaptive placement and physical DAGs;
DuckDB participates only after its target, handoffs, retry, publication,
security, and whole-DAG admission evidence passes the adaptive gate.

The 0.49 handoff is descriptive evidence only. It does not add DuckDB to an
adaptive availability matrix, authorize cross-engine transfer, choose physical
boundaries, or permit runtime replanning. A changed engine, compiler,
configuration, lowering, connector, or evidence fingerprint invalidates the
candidate and requires a new plan.
