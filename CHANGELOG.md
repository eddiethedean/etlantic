# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.11.0] - 2026-07-17

### Added

- `@Transformation.portable` symbolic authoring over `etlantic.transform`
  (`FrameExpr`, `ColumnExpr`, `functions as F`, `Window`, complex/lambda helpers)
- Emission of validated, fingerprint-stable `dtcs.transform-plan/2` plans for
  Portable Relational and Rich Portable Analytics profile families
- `Transformation.to_transform_plan()` / `portable_fingerprint()` APIs
- `PMXFORM` authoring diagnostics and definition budgets
- Golden portable fixtures under `tests/fixtures/portable/`

### Documentation

- Marked portable authoring as shipped in 0.11; compilers remain 0.12–0.15
- Refined roadmap 0.11 to full authoring scope and marked the milestone shipped

### Changed

- Package version set to 0.11.0 across core and optional plugins
- Raised the DTCS toolkit dependency floor from 0.12 to 0.13 (carried from
  unreleased 0.10 docs integration)

## [0.10.0] - 2026-07-17

### Added

- Optional `etlantic-sparkforge` migration adapter (IR → Pipeline / Profile)
- SparkForge debug/run-mode mapping to `RunSelection` / `RunIntent` / `DebugSession`
- SparkForge-shaped result normalization to `PipelineRunReport` with redaction
- Write / Delta capability compatibility helpers (fail closed)
- Representative ecommerce IR fixture and semantic parity suite
- Migration guide `docs/11_DEVELOPMENT/MIGRATION_0_9_TO_0_10.md`
- Runnable docs guides for Airflow compile and SparkForge adapter
- Docs status SSOT via CAPABILITIES + expanded `scripts/check_docs.py` guards

### Changed

- Package version advances to 0.10 (SparkForge Migration Preview)
- Plugin packages require `etlantic>=0.10.0,<1.0`
- SparkForge adoption checklist prerequisites marked complete
- Release workflow paces PyPI uploads (10 minutes between packages)
- Install docs are pip-first now that `0.10.0` is on PyPI
- Agent guidance lists `etlantic.viz` and optional `etlantic-airflow` for compile

### Fixed

- Schema history refuses row-like metadata by key (no substring false positives)
- Core `redact_message` / `redact_value` cover HTTPS basic-auth and string leaves
- SparkForge report adapter redacts free-text errors, Bearer tokens, and DSNs
- `strict_delta=False` emits warnings for missing Delta capabilities (PMSF323)
- SparkForge IR missing step names emit `PMSF310` instead of raising `KeyError`
- Retry policy mapping clamps `max_attempts` to at least 1
- Unknown validation policy names fail closed (`KeyError`) instead of inventing
  empty policies
- Testing helpers harden write-semantics, orchestrator secret scans, and missing
  secret fail-closed behavior
- Adapter stops importing private `_PipelineNamespace`
- Docs SSOT: Graphviz/HTML/lineage, Spark, Airflow, and Mermaid status drift

### Upgrade notes

- Install `etlantic-sparkforge` (or `etlantic[sparkforge]`) for the adapter
- ETLantic core remains free of bronze / silver / gold types
- Full SparkForge engine retirement remains a progressive path (see migration guide)
- Prefer `git tag v0.10.0 && git push origin v0.10.0` (not `git push --tags`)

## [0.9.0] - 2026-07-17

### Added

- CLI wrappers: `compile`, `generate`, `diff`, `plugin list|info`, schema family,
  reliability ops, viz exporters, and `report compare`
- `Profile.plugin_allowlist` with version pins; production fail-closed trust
- `FileSchemaHistoryProvider`, SARIF/GitHub diagnostic renderers
- Reliability provider protocols (quality, statistical, reconciliation, env)
- Observability protocols, JSON console logger, optional OpenTelemetry adapter
- `FileReportStore` and report comparison helpers
- Graphviz DOT / HTML lineage / JSON lineage exporters (`etlantic.viz`)
- Optional packages `etlantic-keyring` and `etlantic-sqlmodel`
- IDE command/result JSON schemas (`etlantic.ide`)
- Notebook / IPython display helpers (`etlantic.notebook`)
- Agent guidance generators + `scripts/check_agent_guidance.py`
- Expanded `etlantic.testing` (orchestrator, secrets, write-semantics parity)
- Migration guide `docs/11_DEVELOPMENT/MIGRATION_0_8_TO_0_9.md`

### Changed

- Package version advances to 0.9 (Tooling, SDK, and Ecosystem Readiness)
- Plugin packages require `etlantic>=0.9.0,<1.0`
- Graphviz / HTML / lineage docs promoted out of Future Design

### Upgrade notes

- Production profiles should set `plugin_allowlist` explicitly
- Schema history stores fingerprints only — never source rows
- Core remains free of Airflow, Spark, SQL drivers, SQLModel, keyring, and OTel
  unless extras / optional packages are installed

## [0.8.0] - 2026-07-17

### Added

- Versioned orchestration protocol (`etlantic.orchestration/1`) with compile,
  artifact transport, retry-safety, and lifecycle correlation models
- Independently installable `etlantic-airflow` reference compiler
- `compile_plan(...)` and `PipelinePlan.compile(target=...)`
- `Profile.schedule`, `Profile.execution`, and
  `required_orchestrator_capabilities`
- Entry-point group `etlantic.orchestrator_plugins`
- Runnable example `examples/airflow_compile.py`
- Migration guide `docs/11_DEVELOPMENT/MIGRATION_0_7_TO_0_8.md`

### Changed

- Package version advances to 0.8 (External Orchestration)
- Plugin packages (polars/pandas/sql/pyspark/airflow) require
  `etlantic>=0.8.0,<0.9`

### Upgrade notes

- Install `etlantic-airflow` to enable Airflow DAG compilation
- Core remains free of Airflow, PySpark, and SQL driver dependencies
- Unsupported orchestrator semantics fail compilation visibly (`PMORCH3xx`)

## [0.7.0] - 2026-07-17

### Added

- Versioned Spark execution protocol (`etlantic.spark/1`) with dataset refs,
  lazy region compile/execute, write intents, and UDF policy
- `Profile.spark_engine`, `spark_udf_policy`, `spark_streaming`, and
  `required_spark_capabilities`
- Independently installable `etlantic-pyspark` plugin with local Spark provider
- Lazy Spark region fusion preserving logical step identities
- Contract ↔ Spark schema mapping that diagnoses lossy/unknown mappings
- Delta-compatible append/overwrite/merge write intents (fail-closed)
- Structured Streaming foundation types marked **experimental**
- Entry-point groups `etlantic.spark_plugins` and `etlantic.spark_providers`
- Migration guide `docs/11_DEVELOPMENT/MIGRATION_0_6_TO_0_7.md`

### Changed

- Package version advances to 0.7 (Distributed Spark Execution)
- Planner prefers `spark_engine` over `sql_engine` / `dataframe_engine` when set
- Plugin packages (polars/pandas/sql/pyspark) require `etlantic>=0.7.0,<0.8`

### Upgrade notes

- Install `etlantic-pyspark` to enable Spark execution
- Core remains free of PySpark and Delta dependencies
- Streaming APIs are experimental; batch Spark is the production path

## [0.6.1] - 2026-07-16

### Changed

- Renamed the project, Python package, CLI, plugins, documentation, and
  distribution artifacts from Pipelantic to ETLantic
- Updated package discovery, plugin entry points, schemas, environment
  variables, examples, and repository URLs to use the `etlantic` namespace

## [0.6.0] - 2026-07-16

### Added

- Versioned SQL execution protocol (`etlantic.sql/1`) with relation refs,
  typed expressions, write intents, and dialect capability negotiation
- `Profile.sql_engine` for selecting a SQL backend during planning
- Independently installable `etlantic-sql` PostgreSQL reference plugin
  (SQLAlchemy Core; SQLite usable for local demos)
- SQL→SQL execution without intermediate Python row fetches when fusion is
  preserved
- Fail-closed merge and capability checks when a dialect cannot honor required
  semantics
- Entry-point discovery group `etlantic.sql_plugins`
- Conformance helpers under `etlantic.testing` for SQL expressions

### Changed

- Package version advances to 0.6 (SQL-Native Execution)
- Planning contexts for `sql` auto-require SQL capabilities when
  `Profile.sql_engine` is set

### Upgrade notes

- Install `etlantic-sql` separately; core stays driver-free
- Register SQL implementations with
  `@TransformationClass.implementation("sql")`
- Set `Profile(sql_engine="sql")` to select the SQL backend
- Configure connections via `ETLANTIC_SQL_URL` (or plugin-specific wiring)
- Missing plugins or unsupported capabilities (e.g. MERGE without keys) fail
  at validation/planning

## [0.5.0] - 2026-07-16

### Added

- Versioned dataframe execution protocol (`etlantic.dataframe/1`) with
  materialize → invoke → normalize → validate → metrics → cleanup phases
- Expanded capability vocabulary: eager, lazy, Arrow import/export, zero-copy,
  schema inspection, invalid-row separation, cancellation, thread-safety
- Planner recording of engine, plugin version, capabilities, collection points,
  conversion boundaries, ownership, and validation policy on `PipelinePlan`
- Runtime delegation of Polars/Pandas steps through the dataframe protocol
  without reselecting engines
- Independently installable `etlantic-polars` (eager + LazyFrame preservation)
  and `etlantic-pandas` (eager, CoW/ownership isolation)
- Optional Arrow interchange helpers (PyArrow imported only when available)
- Entry-point discovery group `etlantic.dataframe_plugins`
- Conformance helpers in `etlantic.testing`
- uv workspace packaging for core + dataframe plugins

### Changed

- Package version advances to 0.5 (Dataframe Execution)
- Built-in `local` registry plugin is a runtime/records path (`dataframe=False`),
  not a dataframe engine
- Planning contexts for `polars`/`pandas` auto-require dataframe capabilities

### Upgrade notes

- Install `etlantic-polars` or `etlantic-pandas` separately; core stays
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
- CLI: `etlantic run` and `etlantic report show|export`
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
- `SecretRef` lives under the `etlantic.secrets` package alongside runtime
  secret resolution types

## [0.3.0] - 2026-07-16

### Added

- `Data` as the preferred thin facade over ContractModel (`DataContractModel`
  remains as a deprecated alias)
- Multi-phase validation (structural, reference, semantic, policy, capability)
  with diagnostic actions and source symbols
- `Profile` templates, `SecretRef`, scoped registries, and capability negotiation
- Immutable secret-free `PipelinePlan` IR (`etlantic.plan/1`) with slicing,
  explain output, and canonical fingerprints
- Schema-drift models (`NormalizedSchema`, observations, changes, `DriftImpact`)
- Portable reliability/intent models (freshness, write/materialization intents,
  idempotency, evidence schemas)
- JSON Schemas for profiles, project config, and PipelinePlan
- `etlantic` CLI: `validate`, `inspect`, `plan`, and `plan explain`
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
- Emit transformation parameters as `etlantic:parameters` (toolkit-valid)
- Round-trip DPCS step parameter overrides
- Treat matching published ODCS ids as compatible in `PMPIPE210` checks
- Recursively validate nested subpipelines
- Clear stale cyclic graph-build errors on fresh `build_graph()`
- Fail closed on DPCS diff incompatible categories and bad DTCS parse input
- Detect published-id / filename slug collisions during bundle generation
- Resolve `odcs:`-prefixed contract registry keys in `from_dtcs`
- Expose `ValidationReport.has_errors` for the documented validation UX
- Correct getting-started imports to use `etlantic.DataContractModel`
  (ContractModel does not export `DataContractModel`)

## [0.1.0] - 2026-07-16

### Added

- First public release as **ETLantic** (PyPI package `etlantic`)
- Typed modeling kernel for authoring pipelines without an execution backend
- `Transformation`, `Input`, `Output`, and `Parameter` port annotations
- `Pipeline`, `Source`, `Step`, `Sink`, and subpipeline composition
- Typed `OutputRef` wiring with stable node and port identities
- Structural validation diagnostics (cycles, missing refs, incompatible ports)
- Logical graph inspection and Mermaid diagram generation
- ContractModel integration boundary via `DataContractModel` alias
- uv + ruff toolchain, MkDocs documentation site, shared GitHub Actions
  checks, and tag-triggered PyPI release

[0.11.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.11.0
[0.10.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.10.0
[0.9.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.9.0
[0.8.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.8.0
[0.7.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.7.0
[0.6.1]: https://github.com/eddiethedean/etlantic/releases/tag/v0.6.1
[0.6.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.6.0
[0.5.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.5.0
[0.4.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.4.0
[0.3.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.3.0
[0.2.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.2.0
[0.1.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.1.0
