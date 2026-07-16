# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.0] - 2026-07-16

### Added

- Versioned SQL execution protocol (`pipelantic.sql/1`) with relation refs,
  typed expressions, write intents, and dialect capability negotiation
- `Profile.sql_engine` for selecting a SQL backend during planning
- Independently installable `pipelantic-sql` PostgreSQL reference plugin
  (SQLAlchemy Core; SQLite usable for local demos)
- SQL→SQL execution without intermediate Python row fetches when fusion is
  preserved
- Fail-closed merge and capability checks when a dialect cannot honor required
  semantics
- Entry-point discovery group `pipelantic.sql_plugins`
- Conformance helpers under `pipelantic.testing` for SQL expressions

### Changed

- Package version advances to 0.6 (SQL-Native Execution)
- Planning contexts for `sql` auto-require SQL capabilities when
  `Profile.sql_engine` is set

### Upgrade notes

- Install `pipelantic-sql` separately; core stays driver-free
- Register SQL implementations with
  `@TransformationClass.implementation("sql")`
- Set `Profile(sql_engine="sql")` to select the SQL backend
- Configure connections via `PIPELANTIC_SQL_URL` (or plugin-specific wiring)
- Missing plugins or unsupported capabilities (e.g. MERGE without keys) fail
  at validation/planning

## [0.5.0] - 2026-07-16

### Added

- Versioned dataframe execution protocol (`pipelantic.dataframe/1`) with
  materialize → invoke → normalize → validate → metrics → cleanup phases
- Expanded capability vocabulary: eager, lazy, Arrow import/export, zero-copy,
  schema inspection, invalid-row separation, cancellation, thread-safety
- Planner recording of engine, plugin version, capabilities, collection points,
  conversion boundaries, ownership, and validation policy on `PipelinePlan`
- Runtime delegation of Polars/Pandas steps through the dataframe protocol
  without reselecting engines
- Independently installable `pipelantic-polars` (eager + LazyFrame preservation)
  and `pipelantic-pandas` (eager, CoW/ownership isolation)
- Optional Arrow interchange helpers (PyArrow imported only when available)
- Entry-point discovery group `pipelantic.dataframe_plugins`
- Conformance helpers in `pipelantic.testing`
- uv workspace packaging for core + dataframe plugins

### Changed

- Package version advances to 0.5 (Dataframe Execution)
- Built-in `local` registry plugin is a runtime/records path (`dataframe=False`),
  not a dataframe engine
- Planning contexts for `polars`/`pandas` auto-require dataframe capabilities

### Upgrade notes

- Install `pipelantic-polars` or `pipelantic-pandas` separately; core stays
  engine-free
- Register dataframe implementations with
  `@TransformationClass.implementation("polars")` or `"pandas"`
- Set `Profile.dataframe_engine` to `"polars"` or `"pandas"` to select a backend
- Missing plugins or unsupported capabilities (e.g. Pandas + lazy) fail at
  validation/planning

### Fixed

- Default `Pipeline.run` / CLI planning now uses plugins discovered on
  `PipelineRuntime` (and entry-point discovery for plan-only contexts)
- Fan-out / unconsumed / cross-engine ports map to in-memory strategies instead
  of durable records; durable conversion only follows durable strategies
- Per-port collect and validation; quarantine/reject populate invalid artifacts
  and metrics
- Schema observation uses plugin `inspect_schema` for native frames
- Durable `ArtifactStore` refuses native frames/LazyFrames (fail closed)
- Discovery load failures emit warnings; LazyFrame dtype checks without row
  collect; invoke kwargs prefer inputs over colliding parameters
- Core `from_arrow_table` no longer imports Polars/Pandas

## [0.4.0] - 2026-07-16

### Upgrade notes

- Register local executable transformations with
  `@TransformationClass.implementation("local")`.
- Use the `development` profile for the built-in local runtime examples.
- Pandas, Polars, SQL, Spark, and Airflow plugins are not part of this release.

### Known limitations

- The local report store is process-scoped.
- The package remains alpha and 0.x releases may contain breaking changes.

### Added

- Local async-first runtime that executes `PipelinePlan`s in-process
- `Pipeline.run` / `Pipeline.arun` / `Pipeline.debug` entry points
- `RunIntent`, `RunSelection`, `RunRequest`, and materialization/retry/timeout
  policies
- `PipelineRuntime` with lifespan, middleware, resource injection, callbacks,
  and outbound event types
- Runtime-only `SecretValue` with env and mounted-file `SecretProvider`s,
  bounded cache, and fail-closed resolution (planning remains secret-free)
- Storage bindings: `memory`, `callable`, `json`, `csv`, and `null` (no-write)
- Versioned `PipelineRunReport` with text/JSON/HTML renderers and in-process
  report store
- Structured logging with central secret redaction and lifecycle/security events
- `SchemaDriftPolicy` observation hooks and local reliability helpers
  (freshness, partition completeness, retry-safety, backfill/repair/no-write)
- CLI: `pipelantic run` and `pipelantic report show|export`
- Hard dependency on `anyio` for structured concurrency

### Fixed

- Durable materialization no longer always writes workspace files; strategy
  comes from the plan/request
- Missing transformation implementations fail closed (no silent identity
  fallback or engine swap)
- Cancellation uses `anyio` cancelled-exc handling and returns a partial report
- Exception and diagnostic messages are redacted before entering reports/logs
- Binding `SecretRef` values are passed into storage context; unresolved
  secrets still fail closed
- Plan `retry_max_attempts` / `timeout_seconds` merge into default `RunRequest`
  policies
- Planner default binding provider is `memory` (`local`/`python` remain aliases)
- Binding overrides resolve registry descriptors for provider/location/secret
- Retry honors backoff/`retry_on` and retry-safety declarations; `CONTINUE`
  soft-skips without failing the step status as hard failure
- Schema observations fingerprint observed data (not only the contract class)
- CLI `run` prints embedded reports on `PipelineExecutionError`
- Debug session invalidation clears shared artifact/memory state across reruns
- Resource `Inject` wiring, outbound `Emit` capture, report lineage, and
  run/region lifespan helpers

### Changed

- Package version and public status advance to 0.4 (Local Runtime and
  Operational Model)
- `SecretRef` lives under the `pipelantic.secrets` package alongside runtime
  secret resolution types

## [0.3.0] - 2026-07-16

### Added

- `Data` as the preferred thin facade over ContractModel (`DataContractModel`
  remains as a deprecated alias)
- Multi-phase validation (structural, reference, semantic, policy, capability)
  with diagnostic actions and source symbols
- `Profile` templates, `SecretRef`, scoped registries, and capability negotiation
- Immutable secret-free `PipelinePlan` IR (`pipelantic.plan/1`) with slicing,
  explain output, and canonical fingerprints
- Schema-drift models (`NormalizedSchema`, observations, changes, `DriftImpact`)
- Portable reliability/intent models (freshness, write/materialization intents,
  idempotency, evidence schemas)
- JSON Schemas for profiles, project config, and PipelinePlan
- `pipelantic` CLI: `validate`, `inspect`, `plan`, and `plan explain`
  (plus `plan --explain` alias, `--nodes`, and mutual exclusion for
  `--run-one` / `--run-until`)
- `Pipeline.plan()` / `Pipeline.explain_plan()`

### Fixed

- `run_until` selects declaration-order prefix (not only upstream closure)
- Unknown plan selections fail closed with `PMPLAN501`
- Multi-engine regions and cross-engine durable artifact strategies
- Profile snapshot included in plan fingerprint
- Strict policy requires registered transformation implementations
- Subpipeline validation inherits parent planning context
- Plan JSON round-trip restores `secret_ref` and verifies fingerprints
- Schema-only DTCS ports map `datetime`/`decimal`/`binary` correctly
- Diff APIs return diagnostics for malformed toolkit input

### Changed

- Package version and public status advance to 0.3 (Validation and Pipeline Plan IR)
- Explicit `click` dependency for the CLI plan command group (Typer 0.15+ no
  longer pulls it in transitively)

## [0.2.0] - 2026-07-16

### Added

- Contract interoperability for ODCS (via ContractModel), DTCS, and DPCS
- `Transformation.to_dtcs` / `from_dtcs` and `Pipeline.to_dpcs` / `from_dpcs`
- Deterministic `ContractBundle` generation via `generate_contracts` /
  `write_contracts` / `load_bundle`
- ODCS facades `load_data_contract` and `write_odcs`
- Diff hooks: `diff_data_contracts`, `diff_transformations`, `diff_pipelines`
- Supported-version policy, bounded safe loaders, and source-aware diagnostics
- Dependencies on the published `dtcs` and `dpcs` toolkits

### Fixed

- Map ContractModel `number`/`datetime` fields to DTCS `decimal`/`datetime`
- Emit transformation parameters as `pipelantic:parameters` (toolkit-valid)
- Round-trip DPCS step parameter overrides
- Treat matching published ODCS ids as compatible in `PMPIPE210` checks
- Recursively validate nested subpipelines
- Clear stale cyclic graph-build errors on fresh `build_graph()`
- Fail closed on DPCS diff incompatible categories and bad DTCS parse input
- Detect published-id / filename slug collisions during bundle generation
- Resolve `odcs:`-prefixed contract registry keys in `from_dtcs`
- Expose `ValidationReport.has_errors` for the documented validation UX
- Correct getting-started imports to use `pipelantic.DataContractModel`
  (ContractModel does not export `DataContractModel`)

## [0.1.0] - 2026-07-16

### Added

- First public release as **Pipelantic** (PyPI package `pipelantic`)
- Typed modeling kernel for authoring pipelines without an execution backend
- `Transformation`, `Input`, `Output`, and `Parameter` port annotations
- `Pipeline`, `Source`, `Step`, `Sink`, and subpipeline composition
- Typed `OutputRef` wiring with stable node and port identities
- Structural validation diagnostics (cycles, missing refs, incompatible ports)
- Logical graph inspection and Mermaid diagram generation
- ContractModel integration boundary via `DataContractModel` alias
- uv + ruff toolchain, MkDocs documentation site, shared GitHub Actions
  checks, and tag-triggered PyPI release

[0.6.0]: https://github.com/eddiethedean/pipelantic/releases/tag/v0.6.0
[0.5.0]: https://github.com/eddiethedean/pipelantic/releases/tag/v0.5.0
[0.4.0]: https://github.com/eddiethedean/pipelantic/releases/tag/v0.4.0
[0.3.0]: https://github.com/eddiethedean/pipelantic/releases/tag/v0.3.0
[0.2.0]: https://github.com/eddiethedean/pipelantic/releases/tag/v0.2.0
[0.1.0]: https://github.com/eddiethedean/pipelantic/releases/tag/v0.1.0
