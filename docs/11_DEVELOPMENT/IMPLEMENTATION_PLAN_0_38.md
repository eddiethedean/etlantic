---
status: gate_ready
since: "0.39.0"
current_minor: "0.40"
target_minor: "0.38"
audience: maintainer
---

# ETLantic 0.38 Implementation Plan — Data Connectivity and Connector SDK

> **Status: Gate-ready for tag/publish rehearsal (Waves 0–8 complete in-tree).**
> Package version is **0.38.0**. Locked decisions:
> [ADR-015](adr/ADR-015-CONNECTOR-PROTOCOLS.md). Close
> [EXIT_GATE_0_38](EXIT_GATE_0_38.md) against exact candidate wheels at publish.
> The
> [main roadmap](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md)
> owns release order,
> [Capabilities](../01_GETTING_STARTED/CAPABILITIES.md) owns shipped behavior,
> and the [Adoption, Connectivity, and Operations Plan](ADOPTION_ECOSYSTEM_PLAN.md)
> owns the cross-phase program.

## Outcome

Graduate ETLantic's logical source, sink, and storage bindings into a versioned,
capability-driven connector family with supported reference implementations.
The release must provide:

- public source, sink, and storage provider protocols;
- typed, secret-free binding configuration and deterministic planning;
- connector development and capability-selected conformance tooling;
- correct cursor, transaction, publication, reconciliation, and cleanup
  semantics;
- local landing-zone, S3/Parquet, Iceberg, Snowflake, and PostgreSQL reference
  paths;
- measurable maturity and compatibility records; and
- independently maintained third-party connector evidence.

The local reference connector includes directory/glob CSV landing zones in
batch-snapshot and incremental modes. Continuous directory watching is not a
third extract kind and is not implemented in core: 0.39+ trigger/submitter
integrations submit runs against the same 0.38 bindings. See the
[Landing-Zone File Connector Plan](LANDING_ZONE_CONNECTOR_PLAN.md).

## Definition of done

The phase is complete only when all of the following are true:

1. Source, sink, and storage protocols are public, versioned, statically
   discoverable, and protected by pre-import production trust checks.
2. Structured connector bindings are validated, fingerprint-stable, and contain
   only public configuration and secret references.
3. Unsupported source, write, transaction, schema, publication, and pushdown
   semantics fail during planning without silent fallback.
4. A cursor or landing-zone ledger advances only after every required downstream
   publication has a proven committed outcome.
5. Partial object-store publication cannot appear as a committed dataset.
6. Connector plans, diagnostics, reports, compatibility records, and test
   evidence contain no resolved secrets, arbitrary source rows, or physical
   landing-root paths.
7. Local landing-zone snapshot and incremental modes pass deterministic,
   cross-platform conformance.
8. S3/Parquet, Iceberg, Snowflake, and PostgreSQL pass their declared fake and
   live capability matrices.
9. Maturity and compatibility claims are backed by executable, isolated-wheel
   evidence.
10. At least one independently governed connector passes public conformance
    without importing private core modules.
11. There are no unresolved P0 findings; every remaining P1 has an owner,
    mitigation, target phase, and non-blocking rationale.
12. Exact candidate wheels, manifests, documentation, migration guidance, and
    release evidence pass rehearsal before publication.

## Authority and boundaries

When sources disagree, use this order:

1. Current-version capabilities, API, CLI, and package documentation define
   what ships.
2. The main roadmap defines the 0.38 outcome and release sequence.
3. This document defines 0.38 implementation order, evidence, and ownership.
4. The adoption and landing-zone plans define their domain boundaries.
5. Accepted ADRs lock protocol, schema, security, and package decisions.
6. Tests, manifests, compatibility records, candidate wheels, and the exit gate
   provide completion evidence.

Non-negotiable boundaries:

- ETLantic owns logical assets, deterministic planning, capability negotiation,
  runtime coordination, and normalized evidence.
- Vendor clients, credentials, physical endpoints, and backend-specific
  behavior remain in optional provider packages.
- Core must not require Boto3, PyArrow, PyIceberg, Snowflake, SQLAlchemy,
  Psycopg, or vendor SDKs.
- Plans and reports store secret references only; resolved secrets exist only
  in non-serializable runtime contexts.
- Production profiles require `plugin_allowlist` and authorize before import.
- Schema/statistics inspection is explicit, bounded, and row-free.
- Bronze, silver, and gold vocabulary remains in Medallantic.
- Distributed checkpoint fencing, tenant/workspace isolation, and continuous
  file-drop submission remain 0.39-0.41 control-plane work.
- Airflow remains an optional compile target through `etlantic-airflow`.

## Locked implementation direction

These decisions should be recorded in accepted ADRs before public protocol
code lands. A change requires an updated ADR, compatibility analysis,
conformance changes, and documentation reconciliation.

### Protocol and discovery split

| Family | Protocol id | Entry-point group | Primary role |
|---|---|---|---|
| Source | `etlantic.source/1` | `etlantic.source_connectors` | Plan and perform bounded reads |
| Sink | `etlantic.sink/1` | `etlantic.sink_connectors` | Stage, commit, abort, and reconcile writes |
| Storage | `etlantic.storage/1` | `etlantic.storage_connectors` | Object/table storage primitives used by connectors |

Public Python interfaces live under `etlantic.connectors`. A distribution may
register more than one family. Existing `etlantic.storage.StorageBinding`
implementations remain supported through a compatibility adapter and do not
silently acquire connector capability claims.

### Reference set

| Requirement | 0.38 selection | Package boundary |
|---|---|---|
| Deterministic local | Directory/glob CSV landing-zone connector | Built-in, stdlib-only |
| Object storage + Parquet | S3-compatible connector | `etlantic-s3` |
| Open table format | Apache Iceberg through PyIceberg | `etlantic-iceberg` |
| Cloud warehouse | Snowflake native connector | `etlantic-snowflake` |
| Relational | PostgreSQL source/sink provider | Existing `etlantic-sql` distribution |

Every optional distribution is independently installable, minor-matched to
core, statically manifested, and allowlisted explicitly in production.

### Capability vocabulary

Freeze one spelling for each semantic capability before implementation. The
landing-zone plan requires these exact source/format tokens:

- `source.batch_snapshot`
- `source.incremental_cursor`
- `source.file_glob`
- `format.csv`
- `idempotency`
- `cleanup`

The connector vocabulary also covers:

- `source.partitioned`
- `source.predicate_pushdown`
- `source.projection_pushdown`
- `source.schema_discovery`
- `source.statistics_bounded`
- existing portable `write.append`, `write.overwrite`, `write.merge`,
  `write.upsert`, `write.skip_if_exists`, and `write.partition_replace`;
- `publication.atomic`;
- `transactions`; and
- `reconciliation`.

Capability implications must not overstate behavior. Transactions do not imply
cross-system atomicity; merge does not imply idempotency; and pushdown is
advertised only when semantics match the portable expression contract.

### Static plan and runtime evidence split

Ordinary `validate` and `plan` operations remain side-effect free. A static
`PipelinePlan` records connector selection, listing intent, identity algorithm,
capability decisions, config fingerprint, checkpoint reference, and secret
references. It does not list a live directory or query a service.

Concrete landing-zone files belong in a run-scoped `LandingReadManifest` and
run report. The landing-zone plan must be reconciled where it currently says
the plan records concrete file identities: static planning records the identity
scheme; runtime evidence records the identities. Any live preflight is an
explicit `inspect` operation, never an implicit plan side effect.

## Workstream 1 — Public connector contracts (`038-P`)

**Owner:** core + Plugin SDK maintainers

Create the public connector model and protocol package:

- `src/etlantic/connectors/__init__.py`
- `src/etlantic/connectors/protocol.py`
- `src/etlantic/connectors/models.py`
- `src/etlantic/connectors/capabilities.py`
- `src/etlantic/connectors/errors.py`
- `src/etlantic/connectors/inspection.py`
- `src/etlantic/connectors/compatibility.py`
- `src/etlantic/connectors/maturity.py`

| ID | Deliverable | Acceptance |
|---|---|---|
| `038-P01` | Source, sink, and storage provider protocols | Public, runtime-checkable, async-first, isolated-wheel importable |
| `038-P02` | `ConnectorInfo` and protocol/version metadata | Deterministic static identity; no live imports needed to inspect manifest |
| `038-P03` | Typed request/plan/session models | Frozen or immutable at public boundaries; bounded serialization |
| `038-P04` | `CommitReceipt` outcome model | Exactly `committed`, `rolled_back`, or `unknown` |
| `038-P05` | Read, cleanup, reconciliation, inspection evidence | Secret-free and row-free; stable schema ids |
| `038-P06` | Capability vocabulary extension | Machine vocabulary, docs, implications, and conformance selectors agree |
| `038-P07` | Compatibility adapter for `StorageBinding` | Existing local storage keeps working without false connector claims |

Required public models include `ConnectorBinding`, `SourcePlan`, `SinkPlan`,
`ReadBatch`, `CursorProposal`, `WriteSession`, `CommitReceipt`,
`CleanupReceipt`, `ReconciliationResult`, `SchemaInspection`, and
`ConnectorCompatibilityRecord`.

## Workstream 2 — Bindings, manifests, trust, and planning (`038-B`)

**Owner:** profile, planner, and security maintainers

Update binding/profile parsing, registry models, plugin discovery, manifests,
plan serialization, capability validation, and schemas.

| ID | Deliverable | Acceptance |
|---|---|---|
| `038-B01` | Structured `Profile.assets` connector descriptor | Legacy strings remain readable; structured form is canonical and deterministic |
| `038-B02` | Static connector config schema | Unknown keys, URL userinfo, scalar secrets, and secret-like arbitrary options rejected pre-import |
| `038-B03` | Manifest connector metadata | Optional maturity, config-schema, and compatibility resources verified before load |
| `038-B04` | Connector discovery groups | Profile-scoped, demand-driven, allowlist-authorized before entry-point import |
| `038-B05` | Connector-aware `BindingDescriptor` | Protocol, provider version, config fingerprint, required capabilities, and refs recorded |
| `038-B06` | Planning capability negotiation | Unsupported mode/write/transaction/schema/pushdown emits stable plan diagnostics |
| `038-B07` | Secret-free plan snapshot | Only canonical public config, root refs, and `SecretRef` metadata retained |
| `038-B08` | Old artifact compatibility | 0.37 profile/plan fixtures decode; new fields are additive or explicitly versioned |

Structured assets support `provider`, `location`, `format`, public `config`,
`secret_refs`, `required_capabilities`, and provider-specific schema-validated
fields. Planning performs no network, filesystem listing, credential
resolution, or vendor-client construction.

Introduce a sanitized `SafeIoPlanPolicy`: runtime profiles may contain physical
approved roots, but new connector plans retain root aliases/references and
policy semantics rather than absolute host paths. Old snapshots remain readable;
new snapshots use an explicit versioned shape.

## Workstream 3 — Runtime publication and cursor correctness (`038-R`)

**Owner:** runtime + reliability maintainers

Replace nominal-success cursor advancement with a run-scoped publication
barrier:

```text
source read
  -> stage cursor candidate
  -> begin sink session
  -> write batches
  -> prepare publication
  -> commit
  -> classify receipt
  -> reconcile unknown outcome when supported
  -> advance cursor only after every required publication is proven committed
```

| ID | Deliverable | Acceptance |
|---|---|---|
| `038-R01` | Connector registries in `PipelineRuntime` | Explicit and discovered providers share trust enforcement |
| `038-R02` | Staged sink lifecycle | Begin, write, prepare, commit, abort, and cleanup are observable and cancellation-safe |
| `038-R03` | Run-level commit barrier | Multiple required sinks must all commit before source state advances |
| `038-R04` | Unknown-outcome handling | Never blindly retried; state held until reconciliation proves outcome |
| `038-R05` | Cursor proposal/rollback integration | Proposal exists before execution; failed/cancelled/no-write runs discard it |
| `038-R06` | Normalized report evidence | Connector, operation, publication, cleanup, rate-limit, and retry evidence bounded |
| `038-R07` | Legacy runtime parity | Memory/CSV/JSON/callable storage paths retain documented behavior |

If one sink commits and another remains unknown, the run is partial or requires
reconciliation and no source cursor advances. Distributed CAS, fencing, and
multi-worker recovery are not claimed in 0.38.

## Workstream 4 — Local landing-zone connector (`038-LZ`)

**Owner:** connector + safe-I/O maintainers

The local reference is a new connector, not an expansion of the public
single-file `CsvStorage` contract.

### Binding model

The same logical extract is used for both modes:

```python
landing = Extract[RawEvent](asset="landing_csv")
```

The profile binding contains:

```text
provider: local-files
format: csv
root_ref: landing
root: inbox
glob: "*.csv"
mode: snapshot | incremental
consume: none | ledger | rename_done
checkpoint: landing_csv_checkpoint  # required for incremental
```

`root` and `glob` are relative. `root_ref` resolves to a physical approved root
only at execution. Changing mode re-plans the binding without changing
`Extract`, transformations, loads, or topology.

### Safe discovery and file identity

| ID | Deliverable | Acceptance |
|---|---|---|
| `038-LZ01` | Bounded safe listing | Root confinement, regular-file checks, symlink rejection, budgets, and timeout |
| `038-LZ02` | Restricted glob policy | Absolute patterns and traversal rejected; recursive `**` requires explicit support |
| `038-LZ03` | Cross-platform deterministic order | NFC-normalized root-relative POSIX paths, bytewise sort, collision failure |
| `038-LZ04` | Stable `LandingFileIdentity` | Versioned identity includes root ref, normalized relative path, size, and content digest |
| `038-LZ05` | TOCTOU protection | Opened file is revalidated; replacement/symlink/special-file races fail closed |
| `038-LZ06` | Listing/read budgets | Maximum files, file bytes, aggregate bytes, rows, and duration enforced |

Do not use modification time or the last lexicographic filename as an
incremental high-water mark. A late-arriving file must remain discoverable, and
rewritten content at the same path must receive a new identity.

Add safe-I/O helpers for bounded listing, no-follow file opening, atomic moves,
archive moves, and cleanup. Existing generic retention cleanup is not sufficient
until every deletion target is individually re-authorized.

### CSV snapshot behavior

| ID | Deliverable | Acceptance |
|---|---|---|
| `038-LZ07` | Multi-file CSV read | One ordered manifest produces one typed logical extract |
| `038-LZ08` | CSV dialect/config validation | Encoding, delimiter, quoting, escaping, newline, and header policy deterministic |
| `038-LZ09` | Cross-file contract/header validation | Incompatibility identifies root-relative file; no row content retained |
| `038-LZ10` | Empty-match policy | Explicit fail or allow-empty; no silent guess or watch behavior |
| `038-LZ11` | Run-scoped read manifest | File identities/counts/fingerprint only; no rows or physical root paths |

Files arriving after the bounded listing belong to the next run. Invalid rows
fail the extract unless an already-supported explicit quarantine policy is
selected; the connector does not invent a new implicit fallback.

### Incremental ledger and local lease

Introduce `etlantic.landing_checkpoint/1` with pipeline/extract/binding
identities, binding fingerprint, generation, committed file identities or
compacted ledger segments, last read-manifest fingerprint, publication identity,
and timestamps. It stores no rows, credentials, or absolute paths.

| ID | Deliverable | Acceptance |
|---|---|---|
| `038-LZ12` | Committed identity ledger | Selection is set difference against committed identities, not filename/mtime |
| `038-LZ13` | Config-bound checkpoint | Root/glob/format/identity changes require explicit reset or migration |
| `038-LZ14` | Bounded ledger + compaction | Size/entry budgets, versioned compaction, integrity verification |
| `038-LZ15` | Single-host exclusive lease | Concurrent local runs cannot select the same uncommitted files |
| `038-LZ16` | Generation verification | Stale checkpoint commit fails closed |
| `038-LZ17` | Downstream commit coupling | Ledger changes only after all required sinks are proven committed |

The lease is a local/single-host correctness mechanism, not a distributed
fencing claim. 0.40-0.41 own authorized durable checkpoint providers and
multi-worker fencing.

### Consume and cleanup policies

- `none`: snapshot leaves files unchanged; incremental still uses the ledger.
- `ledger`: files remain; committed identities prevent reprocessing.
- `rename_done`: always paired with the ledger; archive remains under the
  approved root and happens after checkpoint commit.

| ID | Deliverable | Acceptance |
|---|---|---|
| `038-LZ18` | Post-commit rename/archive | Failure before publication leaves files and ledger unchanged |
| `038-LZ19` | Collision-safe archive | Existing targets cannot be silently overwritten |
| `038-LZ20` | Cleanup failure evidence | Post-commit failure is reported but cannot make committed input eligible again |
| `038-LZ21` | Cross-filesystem refusal | No atomic-rename claim when filesystem cannot provide it |

## Workstream 5 — Connector development kit (`038-K`)

**Owner:** Plugin SDK maintainers

| ID | Deliverable | Acceptance |
|---|---|---|
| `038-K01` | Config and schema helpers | Generate/validate static schemas without importing vendor clients |
| `038-K02` | Redacted runtime context | Secret leases non-serializable and safe `repr` behavior |
| `038-K03` | Sync-to-async adapter | AnyIO worker boundary with cancellation/deadline propagation |
| `038-K04` | Retry and rate-limit helpers | Retry only classified safe operations; honor bounded backoff/`Retry-After` |
| `038-K05` | Pagination/batching helpers | Page/item/byte/time ceilings and bounded concurrency |
| `038-K06` | Checkpoint/publication helpers | Reusable proposals, commit receipts, reconciliation, cleanup |
| `038-K07` | Packaging/doc helpers | Manifest, compatibility record, and provider-doc templates |
| `038-K08` | Observability helpers | Normalized events/metrics without resolved configuration or rows |

The CDK uses protocol composition. Connector authors are not required to
inherit from ETLantic base classes.

## Workstream 6 — Connector conformance (`038-T`)

**Owner:** testing + integration maintainers

Export public suites from `etlantic.testing.connectors`:

- `run_source_connector_conformance_suite`
- `run_sink_connector_conformance_suite`
- `run_storage_connector_conformance_suite`
- `run_connector_live_conformance_suite`

| ID | Deliverable | Acceptance |
|---|---|---|
| `038-T01` | Capability-selected fake backend | Every advertised capability selects mandatory executable cases |
| `038-T02` | Fault model | Pagination, throttling, cancellation, rollback, lost commit response, partial publish, cleanup failure |
| `038-T03` | Secret-sentinel corpus | Zero sentinel leakage in diagnostics, plans, reports, logs, and evidence |
| `038-T04` | Landing-zone corpus | Late files, rewrites, collisions, corrupt checkpoints, archive failures, concurrency |
| `038-T05` | Live-suite control schema | Isolation, cost, byte, rate, retention, and cleanup budgets required |
| `038-T06` | Isolated-wheel execution | Public imports only; no monorepo or private-core dependency |
| `038-T07` | Reviewable snapshots | Updates explicit, deterministic, redacted, and size-bounded |

Live suites are explicit opt-in jobs. They publish account/project isolation,
resource prefixes, cleanup results, cost/byte ceilings, backend versions,
Python versions, and evidence digests.

## Workstream 7 — Reference providers (`038-REF`)

**Owner:** integration maintainers

### Local landing zone

The `038-LZ` workstream is the deterministic local reference and must reach
supported maturity for its declared snapshot/incremental CSV matrix.

### S3-compatible Parquet (`etlantic-s3`)

- Boto3 client construction only at execution.
- PyArrow Parquet read/write behind the package boundary.
- Multipart upload with explicit abort and orphan cleanup.
- Immutable data objects plus conditional commit-marker/pointer publication.
- Readers resolve only committed pointers.
- Predicate/projection claims only for proven PyArrow semantics.
- ETag/version/checksum/operation evidence without secret endpoints.
- PR fake/stub tests plus scheduled isolated AWS S3 live conformance.

### Iceberg (`etlantic-iceberg`)

- PyIceberg catalog and table APIs behind the package boundary.
- Snapshot/partition reads and supported pushdown.
- Append, overwrite, partition replace, and identifier-based upsert only when
  capability prerequisites are met.
- Iceberg snapshot id is the publication identity.
- Local catalog/filesystem CI plus scheduled S3-backed live coverage.

### Snowflake (`etlantic-snowflake`)

- Native connector with autocommit disabled for transactional paths.
- Bounded batch reads and explicit schema inspection.
- Parameterized statements and strict identifier policy.
- Staged append/replace/merge with commit, rollback, and query-id evidence.
- Operation identifiers support reconciliation after lost responses.
- Live jobs use dedicated schemas, smallest approved warehouses, query tags,
  resource monitors, and unconditional cleanup.

### PostgreSQL (`etlantic-sql`)

- Register source and sink connector entry points in the existing optional
  distribution.
- Reuse public SQL types and package-local executor behavior.
- Prove commit, rollback, merge/upsert mapping, lost commit response,
  reconciliation, and cursor coupling.
- Use PostgreSQL CI plus deterministic connection-fault injection.

## Workstream 8 — Maturity and compatibility (`038-M`)

**Owner:** release + integration maintainers

| Level | Promotion gate |
|---|---|
| Experimental | Protocol-valid; mandatory fake core cases green; limitations explicit |
| Preview | All advertised fake cases green; one declared live cell; cleanup and operations guide |
| Supported | Full declared matrix green; security review; isolated-wheel proof; live burn-in without semantic or cleanup failures |
| Deprecated | Replacement, migration path, deadline, and at least two-minor notice |

Immediate release blocking or demotion conditions include secret leakage,
partial publication exposed as committed, state advance after uncommitted or
unknown publication, overstated capability, unbounded inspection/cleanup, and
production import before allowlist authorization.

Compatibility records cover core, package, protocols, capability vocabulary,
plan/report schemas, Python, operating system, service/API or format version,
authentication modes, maturity, limitations, last verification time, and suite
artifact digest.

## Workstream 9 — Third-party proof (`038-X`)

**Owner:** ecosystem maintainers + independent connector maintainer

Select the independent project by Wave 2, not at release-candidate time.
Evidence requires:

- distinct repository governance or release authority;
- static manifest and production trust compatibility;
- public protocol and `etlantic.testing` imports only;
- isolated-wheel fake conformance in its own CI;
- compatibility record for its declared support matrix;
- documented feedback incorporated through public SDK changes; and
- no private module, monorepo path, or unpublished fixture dependency.

The third-party proof may target a connector outside the first-party reference
set, but it must exercise a real source, sink, or storage provider protocol.

## Workstream 10 — Documentation, CLI, and release (`038-D`)

**Owner:** documentation + release maintainers

| ID | Deliverable | Acceptance |
|---|---|---|
| `038-D01` | 0.38 plan, findings, exit, migration, and What's New artifacts | Indexed and mutually consistent |
| `038-D02` | Storage/plugin proposal graduation | Planned warnings replaced only when executable evidence exists |
| `038-D03` | Connector SDK tutorials | Public source/sink/storage examples and failure behavior |
| `038-D04` | Landing-zone guide | Snapshot/incremental profiles, checkpoint reset, consume policies, 0.39+ trigger boundary |
| `038-D05` | CLI/API reference | Connector kinds in plugin inspection; explicit live schema inspection; plan evidence |
| `038-D06` | Compatibility/optional-package tables | Every first-party connector and matrix represented |
| `038-D07` | Build/release workflows | New packages built, hashed, attested, smoke-tested, and published intentionally |
| `038-D08` | Exact-wheel rehearsal | Clean installs, public conformance, examples, docs, manifests, and rollback notes |

Use existing public commands rather than creating an unnecessary top-level CLI
family: `plugin` inspects connector metadata/compatibility, `validate` and
`plan` negotiate capabilities, `schema inspect` owns explicit live inspection,
and `doctor` checks configuration/trust readiness.

## Delivery sequence

### Wave 0 — Reconcile and freeze specifications

- Land this implementation plan and planning index entry.
- Write ADRs for protocols, capability spellings, structured bindings,
  plan/runtime evidence split, checkpoint schema, and reference packages.
- Reconcile the roadmap, adoption plan, landing-zone plan, protocol evolution,
  dependency strategy, and security model.
- Create `FINDINGS_0_38.md`, `EXIT_GATE_0_38.md`,
  `MIGRATION_0_37_TO_0_38.md`, and `WHATS_NEW_0_39.md` scaffolds.

### Wave 1 — Core contracts and planning

Complete `038-P` and `038-B`: protocols, models, structured binding codec,
sanitized plan snapshots, manifests, discovery, trust, planning, diagnostics,
and old-artifact compatibility.

### Wave 2 — Landing-zone snapshot vertical slice

Complete safe listing, stable file identity, CSV aggregation, snapshot mode,
runtime read manifests, and deterministic local conformance. This is the first
complete implementation of the public source protocol.

### Wave 3 — Incremental and publication correctness

Complete the landing ledger/lease, consume policies, sink lifecycle, commit
barrier, unknown outcome, reconciliation, cancellation, and cursor tests.
Cloud providers do not begin graduation until this reusable correctness gate is
green.

### Wave 4 — CDK and public conformance

Extract reusable helpers from the vertical slice, publish capability-selected
fake/live suites, and give the isolated-wheel SDK to the independent connector
maintainer.

### Wave 5 — S3 and PostgreSQL

Prove conditional object publication and relational transaction/rollback/
unknown-outcome semantics first because they exercise the highest-risk release
gates.

### Wave 6 — Iceberg and Snowflake

Complete open-table and warehouse reference paths, live controls, compatibility
records, and operational documentation.

### Wave 7 — Cross-provider acceptance and burn-in

Run one logical pipeline under local, S3, and Snowflake profiles; complete all
reference matrices, live burn-in, cleanup verification, and independent
connector evidence.

### Wave 8 — Release candidate and exit

Resolve every P0, disposition every P1, build exact candidate artifacts, run
isolated-wheel/doc/release rehearsal, verify immutable documentation, and close
the 0.38 exit gate.

## Release-blocking acceptance matrix

| ID | Scenario | Required evidence |
|---|---|---|
| `038-A01` | Same pipeline runs local, S3, and Snowflake | Logical graph/contracts unchanged; connector resolutions differ |
| `038-A02` | Unsupported semantics | Write/transaction/schema/pushdown/mode fails during plan |
| `038-A03` | Failed publication | Cursor and landing ledger unchanged |
| `038-A04` | Unknown publication | State held until reconciliation proves outcome |
| `038-A05` | Partial S3 upload | Readers see only previous committed pointer |
| `038-A06` | Concurrent object publication | Conditional commit has one winner; loser reconciles/fails safely |
| `038-A07` | Production trust | Unallowlisted connector rejected before module import |
| `038-A08` | Secret sentinel | Zero leakage across every retained/output channel |
| `038-A09` | Bounded inspection | No source rows; all schema/statistics budgets enforced |
| `038-A10` | Landing snapshot | Two ordered CSVs produce one typed extract |
| `038-A11` | Landing incremental | Only uncommitted identities selected on next run |
| `038-A12` | Late arrival | Earlier-sorting new file is not missed |
| `038-A13` | Rewritten file | Same path/new content becomes a new identity |
| `038-A14` | Landing failure | Downstream load failure does not change checkpoint or consume source |
| `038-A15` | Landing concurrency | Two local runs cannot select the same uncommitted set |
| `038-A16` | Cleanup failure | Post-commit archive failure cannot cause duplicate processing |
| `038-A17` | Profile mode switch | Snapshot/incremental changes require no `Extract` topology rewrite |
| `038-A18` | Continuous boundary | No core watcher; documented 0.39+ submitter uses same binding |
| `038-A19` | Reference matrix | Local, S3, Iceberg, Snowflake, PostgreSQL pass advertised cases |
| `038-A20` | Independent connector | Own CI, public imports, isolated wheel, compatible manifest |

## Quantified exit scorecard

| Measure | Required value |
|---|---:|
| Public versioned connector protocol families | 3 |
| Required reference paths passing | 5 / 5 |
| Advertised capability-to-conformance coverage | 100% |
| Same-pipeline portability profiles passing | 3 / 3 |
| Landing snapshot acceptance scenarios passing | 100% |
| Landing incremental acceptance scenarios passing | 100% |
| Concrete live files listed during ordinary static planning | 0 |
| Resolved secrets in retained artifacts | 0 |
| Arbitrary source rows in plans/reports/checkpoints/history | 0 |
| Physical landing-root paths in new plans/reports | 0 |
| Failed/unresolved publications advancing state | 0 |
| Partial object publications visible as committed | 0 |
| Concurrent local runs selecting the same landing files | 0 |
| Unsupported modes silently falling back | 0 |
| Core long-lived directory-watch loops | 0 |
| Production connector imports bypassing allowlist | 0 |
| Supported compatibility matrix cells passing | 100% |
| Cleanup leaks during declared burn-in | 0 |
| Independent connectors using private imports | 0 |
| Unresolved P0 findings | 0 |
| Remaining P1s without full disposition | 0 |
| Candidate wheels missing manifest/conformance evidence | 0 |

## Finding severity and closure

| Severity | Meaning | Release treatment |
|---|---|---|
| P0 | Secret/trust failure, silent semantic fallback, partial publication exposed, unsafe cursor advance, unusable artifact | Must close before 0.38 |
| P1 | Material compatibility, correctness, cleanup, adoption, cost, or support risk | Close or defer with owner, mitigation, target, and rationale |
| P2 | Localized usability, performance, or maintainability defect | May defer with owner and target |
| P3 | Cosmetic or opportunistic improvement | Backlog |

## Risk register

| Risk | Impact | Mitigation |
|---|---|---|
| Connector protocol copies current `StorageBinding` limitations | Weak third-party surface | Separate provider planning from runtime sessions; prove through independent connector |
| Structured profile change breaks old plans | Stable-foundation regression | Additive/versioned codec, old fixtures, forward/reverse isolated-wheel tests |
| Static planning touches live systems | Nondeterminism and credential use | Plan/runtime evidence split; explicit live `inspect` only |
| Absolute landing paths leak into plans | Environment/security disclosure | Root references plus sanitized Safe-I/O plan policy |
| Filename/mtime cursor misses late data | Silent data loss | Content identities plus committed membership ledger |
| Sink commits before checkpoint failure | Duplicate processing | Operation id, local lease, generation check, idempotent sink, reconciliation evidence |
| Archive occurs before downstream commit | Data disappearance | Checkpoint then post-commit archive ordering |
| Object-store rename treated as atomic | Partial publication visible | Immutable objects plus conditional commit pointer |
| Unknown transaction blindly retried | Duplicate external effect | `unknown` receipt, no auto-retry, reconciliation gate |
| Live tests incur uncontrolled cost | Budget or account risk | Explicit opt-in, isolated resources, byte/query ceilings, mandatory cleanup |
| Reference integrations pull vendor SDKs into core | Dependency and security expansion | Separate distributions and import-boundary tests |
| Maturity label becomes an SLA claim | Misleading support expectations | Measurable matrix evidence plus explicit Beta/community envelope |
| Independent proof starts too late | SDK defects discovered at RC | Select maintainer/project in Wave 2 |

## Verification commands

As implementation lands, the aggregate gate should include at minimum:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest -q tests/connectors tests/storage tests/runtime tests/plan tests/profile
uv run python scripts/check_connector_conformance.py --fake
uv run python scripts/check_plugin_manifests.py
uv run python scripts/check_protocol_freeze.py
uv run python scripts/check_surface_inventory.py
uv run python scripts/check_diagnostic_stability.py
uv run python scripts/check_docs.py
uv run python scripts/check_release.py
```

Provider live suites use separate explicit commands/jobs with their required
isolation and cost-control documents. Validate and plan example pipelines using
the public surfaces before execution:

```bash
etlantic validate TARGET --format json
etlantic plan TARGET --format json
```

## Required companion artifacts

- `docs/11_DEVELOPMENT/FINDINGS_0_38.md`
- `docs/11_DEVELOPMENT/EXIT_GATE_0_38.md`
- `docs/11_DEVELOPMENT/MIGRATION_0_37_TO_0_38.md`
- `docs/01_GETTING_STARTED/WHATS_NEW_0_39.md`
- connector ADRs under `docs/11_DEVELOPMENT/adr/`
- connector compatibility records in each provider distribution
- capability-selected fake/live evidence and exact-wheel release records
