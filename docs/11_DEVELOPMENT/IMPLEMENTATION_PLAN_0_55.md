---
title: ETLantic 0.55 Implementation Plan
description: Optional data-first authoring with forward and target-guided inference for portable sources, transformations, and write targets.
plan_status: planned
plan_last_reviewed: 0.54.0
---

# ETLantic 0.55 Implementation Plan — Inferred Model Authoring

> **Status:** planned next phase after 0.54. None of the API examples below is
> available in 0.54. The [roadmap](../../ROADMAP.md) owns phase order; the
> [capabilities page](../01_GETTING_STARTED/CAPABILITIES.md) owns shipped claims.
> The [execution plan](EXECUTION_PLAN_0_55.md) owns implementation order,
> code boundaries, fixtures, and merge gates.

## Outcome

A user can bring a dataframe, mapping records, a file, or a qualified
relation/connector source into ETLantic, apply portable expressions, and
inspect inferred data models at every step without declaring `Data` classes,
`Extract` nodes, or `Transformation` classes. An existing write target can
also provide its own observed model, which ETLantic compares with the
transformed output model before proposing a write. Its schema can also
constrain ambiguous earlier models through the portable transformation graph.
If the target is absent, the output model supplies a proposed new target model.
The existing typed class API remains fully supported.

Illustrative API, subject to public naming review:

```python
import etlantic as etl
from etlantic.transform import functions as F

orders = etl.from_pandas(df, name="orders")
clean = (
    orders.filter(F.col("amount") > 0)
    .withColumn("total", F.col("price") * F.col("quantity"))
    .select("order_id", "total")
)

clean.schema              # logical fields, types, nullability, and provenance
clean.model               # generated Data model when the schema is resolvable
clean.preview()           # bounded local result, explicitly requested
```

The introductory examples also include `etl.from_polars(df, name="orders")`,
`etl.from_records(records, name="orders")`, and
`etl.read_csv("orders.csv", name="orders")`. The latter two are proposed
public names for one shared, engine-neutral records inference capability;
CSV parsing supplies mapping records to that capability. All four paths feed
the same logical schema and portable transformation propagation. Other
qualified source forms use the inspection matrix below. The exact public
names must be settled by executable examples and user review before
implementation.

A standalone `etl.infer_records(records, ...)` is also proposed for callers
who only want to inspect a schema. Its result exposes the logical schema,
diagnostics, inspected count, and a single-use replay stream when the input
was a one-shot iterator. `from_records` consumes this same result internally;
`read_csv` uses the same inferencer after parsing. This keeps inference useful
outside pipeline authoring and avoids two sets of type rules.

## Current Boundary and Ownership

- `Extract` still requires an `asset` name, although its contract type can be
  omitted. `@Transformation.portable` lowers immediately from declared ports
  and expects declared outputs. It cannot currently wait for a dataframe's
  schema before binding its input and output models.
- Dataframe plugins expose `inspect_schema`; `NormalizedSchema` provides a
  fingerprinted operational schema; `PipelineDefinition` already carries
  data-only `ContractDefinition` objects. These are starting points, not a
  complete model inference API.
- Local, Pandas, Polars, PySpark, and DataFusion have frame inspection paths;
  SQL and DuckDB expose relation/catalog inspection. The optional connector
  `StorageConnector.inspect_schema` surface exists for several table/object
  providers. These return different shapes and levels of evidence; they are
  not yet one qualified inferred-model pathway.
- The local dataframe inspector currently uses the first record to infer a
  schema, and generic record conversion does not consume arbitrary mapping
  iterables. Neither path is sufficient for mixed records or one-shot sources.
  The existing local CSV reader parses bounded files, but does not provide a
  general inferred model or resolve CSV string types.
- `FrameExpr` tracks names through many actions, but the current portable
  builder can fill undeclared output types with `string` and nullable defaults.
  The phase must replace that approximation for inferred contracts.
- `SinkConnector` does not expose target-schema inspection. Some storage and
  SQL plugins can inspect a destination through separate APIs, but a returned
  empty field list does not reliably distinguish a missing target from an
  existing empty target or an inspection failure. Target models and write
  compatibility therefore need an explicit normalized observation path.
- ETLantic owns the optional authoring facade, schema propagation, diagnostics,
  binding, and plan integration. ContractModel owns `Data` and
  [ODCS](../03_DATA_CONTRACTS/ODCS.md) semantics.
  [DTCS](../04_TRANSFORMATIONS/DTCS.md) owns portable transformation semantics.
  Engine, file, and connector plugins own physical schema inspection and
  execution. The records inferencer is shared across record and text-file
  entry points and reports engine-neutral logical evidence.

## Design Contract

### 1. Inspect an explicit input

`from_pandas` and `from_polars` inspect an object the caller explicitly passes.
`from_records` accepts `Iterable[Mapping[str, object]]`, including lists,
tuples, and one-shot generators. `read_csv` supplies records through a bounded
CSV parser. ETLantic creates an implicit source node and a secret-free schema
snapshot with stable identity, inspector/version, method, and limitations. It
does not serialize rows into definitions, plans, reports, diagnostics, or
schema history. Inspection must not occur during ordinary module import,
validation, or planning of an unrelated pipeline.

The records inferencer is a single engine-neutral component used by both
record and CSV entry points. It accepts explicit row and byte limits,
cooperative elapsed-time limits, and schema hints. An arbitrary blocking
iterator cannot be forcibly stopped mid-`next()` call. The inferencer buffers
only the inspected prefix of a one-shot iterator and replays that prefix once
ahead of its uninspected remainder when the session source is read; inference
must neither exhaust an unbounded source nor drop or duplicate sampled rows.
A one-shot source has one execution lifetime. Repeated execution requires a
replayable source factory or explicit materialization. Durable export requires
a stable, rebindable asset.
Preview of a one-shot source reads only its buffered prefix and reports
truncation; it does not advance the remaining iterator before the run.

For mapping records, inference scans the bounded sample across rows instead
of trusting its first row. It tracks missing keys separately from explicit
nulls, promotes compatible types by documented deterministic rules, preserves
field order by first appearance, and marks claims unproven by a truncated
sample as provisional. Late fields and incompatible values must be validated
against the inferred schema during execution and reported as drift or an
actionable error. Non-string keys and unsupported nested/object values get
diagnostics or require explicit hints; they are not silently converted.

For CSV, the header supplies field names but every parsed cell starts as text.
Configured delimiter, quoting, encoding, null tokens, and type parsing policy
are part of inference provenance. Numeric, boolean, date, and timestamp
recognition follows deterministic, documented promotion rules; ambiguous or
all-empty columns stay unknown/provisional until a user supplies a hint.
Blank or duplicate headers, ragged rows, inconsistent files, and parser errors
receive row/column diagnostics without including cell values. File count and
size limits and safe path handling apply before inspection.

Physical dtype, logical type, required presence, nullability, and inference
confidence are separate facts. An empty column, Pandas object dtype, CSV text
column, or sample with no nulls must not silently become a precise non-null
contract.
Prefer schema metadata to row sampling. Any sample is bounded and explicitly
identified as provisional. A conservative nullable model may be previewed,
but publication must disclose unproven guarantees and require hints where
logical types cannot be resolved.

### 2. Cover every qualified portable source

Source inference is a capability of the source form, not the transformation
engine chosen later. Every first-party readable binding and every qualified
first-party portable engine must either produce a normalized observation or a
stable diagnostic explaining which inspector, schema document, or hint is
needed. The published matrix records the exact package, source form, method,
evidence quality, and maturity; an engine's portable compiler claim alone
does not imply source inference support.

| Source form | Inspection path and boundary |
|---|---|
| Local records/memory, Pandas, Polars, PySpark, DataFusion frames | Use the shared records inferencer or native frame/Arrow/Spark schema as appropriate; map physical types, nullability, and unknowns into one logical observation. |
| SQL and DuckDB relations | Use catalog/relation metadata by stable relation identity, without fetching rows. Record absence, inaccessible catalogs, and unsupported types distinctly. |
| CSV, JSON arrays/JSON Lines, and qualified Parquet files | Use safe bounded text parsing for CSV/JSON and qualified footer/schema metadata for Parquet. Reuse records inference for parsed mappings; do not deserialize untrusted extension metadata. |
| Local-files, PostgreSQL, Snowflake, Iceberg, and S3 connector sources | Adapt qualified `StorageConnector.inspect_schema` or provider metadata to the same result. Mark adapters that rely on bounded row samples as provisional rather than claiming row-free evidence. |
| Kafka or other streaming sources | Use a qualified schema document/provider when available. A registry fingerprint alone is only an identity and cannot produce field models; require a supplied schema/hint or emit an unsupported diagnostic. Never consume a live stream merely to plan. |
| Callable, null, and third-party sources | Accept a qualified optional inspector or explicit schema hint. A null binding has no physical schema to infer; an uninspectable source cannot silently become a generic string model. |

The same source may be read by more than one engine. Inference must not change
its logical schema merely because execution moves between qualified engines.
Connector inspection is explicit and authorized, respects allowlists, tenant
scope and safe I/O, and produces secret-free bounded metadata. Normal
module import, validation, and deterministic planning use a pinned observation
instead of contacting a live system.

### 3. Infer models for existing and new write targets

An explicit target inspection precedes a proposed write. A normalized target
observation contains `exists = present | absent | unknown`, the target
identity and revision/snapshot, logical fields, required/nullability and
available key, default, generated-column, partition, and constraint metadata,
plus method, confidence, limitations, and fingerprint. Empty fields never
stand for absence. Unknown existence, denied access, stale metadata, and
unsupported inspection fail closed with diagnostics.

For a **present** target, ETLantic generates a reviewable target model from
the observed destination schema, separately from the upstream output model.
It compares them for the selected write mode (append, overwrite/replace,
merge/upsert, or partition replace where supported): missing required target
fields, incompatible types, nullability, key/partition requirements, and
provider-specific constraints must be reported before write. Neither model
silently overwrites the other, and an observed destination does not become an
accepted production contract without review. A target schema change between
inspection and publication requires revalidation or a provider-enforced
revision guard.

The target also supplies expected types at the write boundary for the
backward inference pass below. These are constraints on values to be written,
not proof that an earlier source physically stores those types. Target-guided
assumptions are labeled separately from observed facts and cannot silently
rewrite a source observation or accepted contract.

For an **absent** target, ETLantic derives a proposed target model from the
portable output schema. Creation is an explicit write intent and requires a
qualified provider capability, complete required types, and normal
validation/approval. It must not create a table, file, or topic during
inspection or planning. A target that appears before creation is treated as a
conflict and re-inspected; there is no implicit replace. Physical schema
details that cannot be deduced from output fields, such as keys, partitioning,
or storage format, require user settings.

| Target form | Existing-target model | Absent-target behavior |
|---|---|---|
| SQL/DuckDB relations and PostgreSQL/Snowflake/Iceberg tables | Catalog/table metadata with types, nullability, and available keys/defaults/partitions; preserve provider revision. | Propose a table model from the output, then require explicit qualified create intent. |
| Local CSV, JSON/JSON Lines, and memory bindings | Safe bounded file/record inspection; text-derived types may remain provisional. CSV headers alone do not prove field types. | Propose a file or session model; create only through a qualified writable binding. |
| S3 objects and qualified Parquet datasets | Committed-object metadata, manifest, or safe footer/schema inspection; unsupported or inconsistent objects produce diagnostics. | Propose an object/dataset model only where a provider advertises creation. The current qualified Parquet source is read-only. |
| Kafka topics or other streams | Qualified registry schema document or explicit model hint; a fingerprint alone cannot generate fields. | Topic/schema creation requires a separate explicit qualified capability and policy. |
| Callable, null, and third-party sinks | Qualified optional inspector or explicit contract; null has no physical target schema. | Provider-specific qualified creation or explicit contract; otherwise unsupported. |

Inspection does not imply write or create support. Add target inspection as an
optional negotiated adapter rather than changing the frozen
`etlantic.sink/1` contract.

### 4. Propagate schema through portable IR

The same `etlantic.transform` expressions used by typed transformations drive
the new facade. A schema transfer function computes the output of each action
without executing the transformation on sample rows. It accounts for field
order and identity, type promotion, null/missing behavior, and provenance.

The first qualified matrix covers projection, filtering, field addition and
replacement, dropping, renaming, explicit casts, arithmetic and common scalar
functions, joins, unions, and grouping/aggregation. Outer joins, unions with
different types, empty/all-null inputs, decimals, timestamps, and ambiguous
expressions need explicit conformance fixtures. Advanced portable families
may be added only with qualified transfer rules. Unsupported inference emits a
field- and operation-specific diagnostic and accepts an explicit user hint;
it never fabricates a type to pass validation.

Portable functions must bind after the input schema is known. A reusable
function applied to two different schemas yields two resolved definitions and
fingerprints. Binding/lowering remains data-only and obeys existing IR budgets.
No arbitrary Python tracing or native UDF inference is introduced.

### 5. Propagate target constraints backward

For an existing target, start with its inspected schema and explicit
source-to-target field mapping at the write boundary. Propagate type
requirements backward only through qualified portable IR rules, then run
forward inference again. Iterate to a bounded fixed point or emit a stable
non-convergence diagnostic. Keep four separate states for each field:
observed source evidence, inferred logical type, target requirement, and
write compatibility (`proven`, `conditional`, or `conflict`). Record the
constraint's target identity, field, revision, operation path, rule, and
confidence in provenance. The user-facing schema explanation must show both
the observed type and the target-guided logical proposal; a generated model
must identify any runtime parsing or validation obligation.

| Portable operation | Backward rule |
|---|---|
| Filter, sort, limit, distinct, direct projection, rename, or unchanged field | Carry an expected type to the corresponding input field, subject to any stronger observation. |
| Explicit `cast` / `try_cast` | Treat the declared output type as a boundary; check input convertibility under the qualified conversion policy. Do not relabel the input as the output type. |
| Literal, arithmetic, scalar call, window, or aggregate | Apply a qualified inverse signature only when it gives a sound constraint. A result type usually does not uniquely determine operand types; otherwise retain unknown and ask for a hint or explicit cast. |
| Join, union, and multi-input expression | Follow field lineage to contributing branches and intersect compatible requirements. Join-generated nullability and union promotion remain explicit. Conflicting branch requirements are diagnostics. |
| Dropped fields, opaque/native functions, or unqualified portable operations | Stop propagation at the boundary and emit an actionable diagnostic rather than guessing an upstream type. |

For example, a CSV cell is physically text. If its logical type is unresolved
and the mapped destination column is integer, ETLantic may propose an integer
logical parse for that source field. It must validate every value at execution
under an explicit deterministic parse policy; bad values fail or enter the
configured invalid-record path. The source observation still says text.
If a Pandas column is definitively string, the integer destination instead
produces a type conflict and a suggested explicit cast or mapping. A target's
non-null constraint likewise creates a validation obligation, not evidence
that upstream data contains no nulls.

Different targets may constrain the same upstream field differently. Resolve
them only if qualified transformations make both writes valid; otherwise
report the conflict by branch and require an explicit conversion or hint.
The chosen write mode, target revision, parse policy, and hints are part of
the resolved model's deterministic identity. Reinspection or a changed
target schema reruns both passes and produces a reviewable diff before export
or publication. An absent target supplies no independent backward evidence.

### 6. Generate reviewable models and pipeline definitions

Each source, transformed result, and inspectable write target has a canonical
logical schema and derived `ContractDefinition`. Source and target models
retain their inspected identity and provenance; transformed models also
include portable IR provenance. A generated `Data` subclass is an optional
Python view of the definition, not a second source of truth. Runtime-generated
classes cannot supply static IDE typing on their own; a code export or stub
must be available for projects that want committed Python models.

An in-memory dataframe or iterable is a session source. Its pipeline can be
run locally; a one-shot iterator can be consumed only once. A CSV path is a
rebindable source only when its identity, parser options, and schema snapshot
are reviewed. A durable or externally compiled pipeline requires an explicit
rebindable asset and a reviewed schema snapshot. Export creates the existing
`PipelineDefinition`, `etlantic.plan/1`, ODCS, DTCS, and
[DPCS](../05_PIPELINES/DPCS.md) artifacts and lineage through normal
validation and planning. It never embeds the dataframe itself.
Reinspection of a source or target creates a proposal/diff; it never silently
rewrites an accepted contract or production plan.

### 7. Keep the feature optional

No optional engine or connector dependency enters ETLantic core. Import safety
and all existing class-authored fingerprints remain unchanged when this facade
is unused. The interactive facade uses the same qualified compilers and fails
closed when a target cannot realize its portable operations. Production
plugin trust, safe I/O, tenant boundaries, and schema-drift policy still apply.

## Workstreams and Order

| ID | Workstream | Deliverable |
|---|---|---|
| 055-R | Records inference | Shared bounded mapping-record inferencer, one-shot prefix replay, CSV/JSON adapters and parser/type policies |
| 055-I | Source inspection | Local/Pandas/Polars/PySpark/DataFusion frame, SQL/DuckDB relation, file, and first-party connector adapters; normalized evidence and gap matrix |
| 055-W | Target inspection | Explicit existence state, optional destination-inspector adapter, existing-target model, missing-target proposal, and write-mode compatibility checks |
| 055-T | Type propagation | Portable IR transfer rules, diagnostics, and cross-engine semantic fixtures |
| 055-B | Backward constraints | Qualified inverse transfer rules, bounded forward/backward solver, target-guided provenance, conversion and contradiction diagnostics |
| 055-A | Authoring | Optional data-first facade for qualified sources, portable steps, target inspection and bounded preview |
| 055-M | Models | Canonical source, transformed, and target contracts; generated `Data` view, code export, lineage and provenance |
| 055-P | Promotion | Session-to-durable binding, deterministic definition/plan export, source/target drift and review workflow |
| 055-Q | Qualification | Source-by-engine and target-by-write-mode coverage, security, performance, compatibility, and documentation evidence |

Implement records inference, source/target inspection, forward transfer, and
backward constraint rules before promising generated models. Qualify the
interactive path and existing-target comparison before durable export.
CLI/notebook helpers should consume the same public result model rather than
duplicate inference rules.

## Non-Goals

- Replacing the explicit typed authoring path or making every pipeline inspect
  a live source during planning.
- Inferring arbitrary Python, native backend expressions, user functions, or
  business constraints from rows.
- Assuming a destination type proves an upstream physical or declared type,
  or inserting an implicit lossy conversion to satisfy a sink.
- Treating observed schema as an automatically accepted production contract.
- Treating an existing destination as new because its inspector returned no
  fields, or deriving physical keys/partitioning from row samples.
- Storing source rows in schema history, generated artifacts, or plan metadata.
- Claiming exact static Python type checking for a model created at runtime.
- Adding a fourth top-level contract standard or moving ContractModel/DTCS
  semantics into ETLantic.

## Acceptance and Exit Gates

- The proposed examples run from Pandas and Polars inputs, finite mapping
  collections, one-shot mapping generators, and CSV files with no handwritten
  source, transformation, or output model. Equivalent logical input schemas
  and portable expressions derive equivalent canonical output schemas and
  portable logical IR for the qualified operation matrix.
- The published source matrix covers Local, Pandas, Polars, PySpark,
  DataFusion, SQL, and DuckDB portable engines; core records/memory,
  CSV/JSON/JSON Lines and qualified Parquet files; first-party local-files,
  PostgreSQL, Snowflake, Iceberg, S3, and Kafka connectors; and callable/null
  boundaries. Every schema-bearing, qualified first-party source yields a
  normalized model; opaque or unqualified cells carry a stable diagnostic
  naming the missing inspector or explicit hint and are excluded from the
  inference support claim. A compiler claim alone never counts as inspection
  evidence.
- A present destination produces a model from its own inspected schema; an
  absent destination receives a proposed model from the transformed output;
  unknown existence fails closed. Coverage includes local file/memory,
  SQL/DuckDB, and qualified first-party connector targets. Write-mode
  compatibility checks include types, nullability, required/default fields,
  keys, partitions, and supported provider constraints.
- An existing target constrains ambiguous upstream logical models through
  qualified portable lineage. The resolved result distinguishes observed
  source facts, target-guided hypotheses, explicit conversions, and proven,
  conditional, or conflicting write compatibility. An absent target supplies
  no backward evidence.
- Golden fixtures cover ambiguous CSV text mapped to an integer destination,
  a definite string source requiring a cast, invalid numeric values, a
  non-null destination with nullable input, rename/project pass-through,
  cast barriers, ambiguous arithmetic, join/union branches, conflicting
  targets, and unsupported/native expressions. No fixture silently changes a
  source observation or accepted contract.
- Existing-target inspection performs no writes, never equates zero fields
  with nonexistence, and compares a pinned target revision before publication.
  New-target creation requires explicit intent and qualified provider support;
  a target appearing meanwhile produces a conflict rather than an overwrite.
- Direct `infer_records` inspection and the `from_records` and `read_csv`
  authoring paths agree on schema, diagnostics, and provenance for equivalent
  parsed records and inference options.
- Shared records inference uses bounded row/byte inspection and cooperative
  elapsed-time checks, preserves sampled rows exactly once for one-shot
  iterators, and never exhausts an unbounded source. Repeated runs of one-shot
  inputs require a replayable factory or materialization. One-shot preview
  leaves the remaining iterator untouched. CSV parsing obeys safe I/O limits
  and reports malformed headers or rows without exposing values.
- Missing keys, explicit nulls, mixed scalar types, nested values, late
  fields, empty/header-only CSV, ambiguous text columns, and values beyond
  the sample have deterministic type-promotion, hint, and diagnostic behavior.
  Execution validates later rows against the inferred schema.
- A source inspection and every derived model report method, inspected count,
  truncation, confidence, ambiguity, parser options where applicable,
  provenance, and stable fingerprints without row payloads.
- Differential tests compare inferred schemas to actual results for the
  qualified seven-engine portable matrix, including empty/all-null fields,
  type promotion, nullability, joins, unions, aggregates, and unsupported
  actions. Source and target adapter tests verify metadata-first inspection,
  bounded sampling where necessary, and no-row-leak behavior.
- Every unresolved type or unsupported semantic yields a stable actionable
  diagnostic. Explicit hints are validated against the observed schema and
  cannot silently override a contradiction.
- Session export round-trips through `PipelineDefinition` and normal
  validate/plan/generate paths. A durable export cannot succeed with an
  unbound in-memory source or one-shot iterator, ambiguous required type, or
  unreviewed source/target drift.
- Repeated inference from identical source/target snapshots, write modes,
  hints, and portable expressions produces identical definitions, plans, and
  contract artifacts. Existing explicit pipelines retain their fingerprints
  and behavior.
- Optional backend imports remain lazy; inspection, previews, and exports are
  bounded; source rows and secrets never appear in metadata or diagnostics.
- Documentation examples execute, conformance and security suites pass, and
  the published capability matrix names exactly which source forms, target
  forms, portable actions, engines, write modes, and export modes are
  available.

## Evidence and Open Decisions

Required evidence: a public API walkthrough; a source-by-engine and
target-by-write-mode matrix for every first-party surface named above;
frame/relation/file/connector inspection fixtures; one-shot replay and
bounded-infinite-iterator fixtures; text parsing and type-ambiguity cases;
forward/backward schema-transfer golden corpus; seven-engine differential
campaign; present/absent/unknown destination and concurrent-creation fixtures;
write-compatibility and round-trip fixtures; import-safety and no-row-leak
checks; bounded-preview benchmarks; and reviewed durable-export examples for
an existing and a new target.

Before freezing the API, decide whether the public handle is named `Frame`,
`Dataset`, or another term; how users provide field hints; whether a provisional
`Data` model is exposed before publication; and the default CSV type parsing
policy and record sampling limits. Also decide the public target-inspection
handle and the exact optional inspector capability for third-party sinks.
Resolve these choices with executable examples and the exit gates above,
without changing the phase's ownership or security boundaries.
