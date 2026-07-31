# ADR-015: Connector Protocols and Capability Vocabulary

Date: 2026-07-31  
Status: Accepted

## Context

ETLantic 0.38 freezes the stable-foundation surface but still binds logical
assets through built-in storage helpers and design-study storage-plugin pages.
Adopters need versioned source, sink, and storage provider protocols so
directory landing zones, object stores, table formats, warehouses, and
relational systems can negotiate capabilities at plan time without embedding
vendor SDKs in core.

Without a locked split between static plan evidence and run-scoped read
manifests, ordinary `validate` / `plan` would list live files or query
services, breaking determinism and leaking environment detail. Without a
dedicated checkpoint schema and explicit publication barrier, incremental
landing-zone and cursor advances risk advancing after uncommitted writes.

This ADR locks the protocol family, discovery entry points, public package,
capability spellings, plan/runtime evidence split, checkpoint schema id,
reference package set, and StorageBinding compatibility posture for the 0.38
connectivity program. Continuous directory watching remains out of core.

Authoritative sequencing:
[IMPLEMENTATION_PLAN_0_38](../IMPLEMENTATION_PLAN_0_38.md),
[Landing-Zone File Connector Plan](../LANDING_ZONE_CONNECTOR_PLAN.md), and
[ROADMAP § 0.38](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md).

## Decision

### Protocol and discovery split

| Family | Protocol id | Entry-point group | Primary role |
|---|---|---|---|
| Source | `etlantic.source/1` | `etlantic.source_connectors` | Plan and perform bounded reads |
| Sink | `etlantic.sink/1` | `etlantic.sink_connectors` | Stage, commit, abort, and reconcile writes |
| Storage | `etlantic.storage/1` | `etlantic.storage_connectors` | Object/table storage primitives used by connectors |

Public Python interfaces live under `etlantic.connectors`. A distribution may
register more than one family.

### Capability vocabulary

Freeze these exact spellings before public protocol code lands:

**Landing-zone / local source (required tokens):**

- `source.batch_snapshot`
- `source.incremental_cursor`
- `source.file_glob`
- `format.csv`
- `idempotency`
- `cleanup`

**Extended connector vocabulary:**

- `source.partitioned`
- `source.predicate_pushdown`
- `source.projection_pushdown`
- `source.schema_discovery`
- `source.statistics_bounded`
- `write.append`, `write.overwrite`, `write.merge`, `write.upsert`,
  `write.skip_if_exists`, `write.partition_replace`
- `publication.atomic`
- `transactions`
- `reconciliation`

Capability implications must not overstate behavior. Transactions do not imply
cross-system atomicity; merge does not imply idempotency; pushdown is
advertised only when semantics match the portable expression contract.
Unsupported modes fail at plan time with no silent fallback.

### Static plan vs runtime evidence

Ordinary `validate` and `plan` remain side-effect free. A static
`PipelinePlan` records connector selection, listing intent, **identity
scheme**, capability decisions, config fingerprint, checkpoint reference, and
secret references. It does **not** list a live directory or query a service.

Concrete landing-zone file identities belong only in a run-scoped
`LandingReadManifest` and the run report. Any live preflight is an explicit
`inspect` operation, never an implicit plan side effect.

### Checkpoint schema

Incremental landing-zone state uses schema id `etlantic.landing_checkpoint/1`.
Checkpoints store pipeline/extract/binding identities, binding fingerprint,
generation, committed file identities or compacted ledger segments, last
read-manifest fingerprint, publication identity, and timestamps. They store no
rows, credentials, or absolute host paths.

### Reference packages

| Requirement | 0.38 selection | Package boundary |
|---|---|---|
| Deterministic local | Directory/glob CSV landing-zone connector | Built-in (`local-files`), stdlib-only |
| Object storage + Parquet | S3-compatible connector | `etlantic-s3` |
| Open table format | Apache Iceberg through PyIceberg | `etlantic-iceberg` |
| Cloud warehouse | Snowflake native connector | `etlantic-snowflake` |
| Relational | PostgreSQL source/sink provider | Existing `etlantic-sql` distribution |

Core must not require Boto3, PyArrow, PyIceberg, Snowflake, SQLAlchemy,
Psycopg, or vendor SDKs. Optional distributions are independently installable,
minor-matched to core, statically manifested, and allowlisted explicitly in
production.

### StorageBinding compatibility

Existing `etlantic.storage.StorageBinding` implementations remain supported
through a compatibility adapter. They do **not** silently acquire connector
capability claims. The local landing-zone connector is a new connector surface,
not an expansion of the public single-file `CsvStorage` contract.

### Continuous watch out of core

Long-lived directory-watch loops are **not** implemented in core in 0.38.
Continuous file-drop watching is a trigger/submitter concern composed in
**0.39+** against the same snapshot/incremental bindings.

## Consequences

- Plugin authors implement against `etlantic.connectors` and the three
  entry-point groups; conformance selects cases from the frozen vocabulary.
- Planners emit identity schemes and capability decisions without touching live
  filesystems or services.
- Runtime owns `LandingReadManifest`, publication receipts, and checkpoint
  advances only after required sinks prove `committed`.
- First-party reference packages and `etlantic-sql` PostgreSQL connectors prove
  the exit matrix; maturity labels require executable evidence.
- Docs that previously said the plan records concrete file identities must
  describe the identity-scheme / runtime-manifest split instead.

## Alternatives

| Alternative | Why rejected |
|---|---|
| Single storage protocol only | Sources and sinks need distinct plan/session and publication semantics |
| Extend `CsvStorage` public contract for directories | Would overload single-file Safe I/O helpers and confuse maturity claims |
| List live files in `PipelinePlan` | Breaks deterministic planning and leaks host paths |
| Filename/mtime incremental cursors | Miss late arrivals and rewritten content at the same path |
| Embed watch loops in core extract | Couples library semantics to daemons; owned by 0.39+ control plane |
| Vendor SDKs in core | Violates dependency and security boundaries |

## Compatibility

- Additive for 0.38 profiles/plans that do not use connector descriptors; old
  artifacts remain readable (`038-B08`).
- New connector plan fields are additive or explicitly versioned; sanitized
  Safe I/O plan policy retains root aliases rather than absolute paths.
- StorageBinding adapters preserve existing local memory/CSV/JSON/callable
  paths without claiming connector capabilities.
- Plugin floor for 0.38 connectors will be `etlantic>=0.39.0,<0.40` when the
  package version bumps (not part of this ADR wave).
- Continuous watch documentation must not claim core availability before 0.39+.
