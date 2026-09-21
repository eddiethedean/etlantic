---
title: ETLantic 0.55 Execution Plan
description: Implementation sequence for bidirectional schema inference across portable sources, transformations, and write targets.
plan_status: planned
plan_last_reviewed: 0.54.0
---

# ETLantic 0.55 Execution Plan — Bidirectional Schema Inference

This document turns the [0.55 implementation plan](IMPLEMENTATION_PLAN_0_55.md)
into an ordered engineering sequence. The implementation plan owns the phase
scope and exit claims. This document owns the work breakdown, code boundaries,
test fixtures, evidence artifacts, and merge gates.

The [inference remediation plan](INFERENCE_REMEDIATION_PLAN_0_55.md) is the
review-driven hardening sequence for this execution plan. The [full review fix
plan](REVIEW_FIX_PLAN_0_55.md) is the current finding-by-finding closure
checklist. Both must be completed before the phase can move from planned to
qualified.

The phase is complete only when a source can produce a normalized model, a
portable graph can propagate that model forward, an existing target can
constrain ambiguous upstream types through qualified lineage, and a missing
target can receive an explicit output-derived proposal. A target observation
never silently changes an observed source fact.

## 1. Working rules

- Keep inference engine-neutral. Core code must not import Pandas, Polars,
  SQLAlchemy, Spark, DataFusion, DuckDB, cloud SDKs, or connector packages.
- Keep observations row-free. Store schema, fingerprints, counts, limits,
  parser settings, source/target identity, revision, method, confidence, and
  diagnostics. Never store source values, secrets, credentials, or sampled
  rows in definitions, plans, reports, or schema history.
- Prefer metadata over data sampling. Sampling is bounded, explicitly marked
  provisional, and used only when a source has no stronger schema metadata.
- Fail closed. Unknown types, denied inspection, unknown target existence,
  unsupported inverse rules, stale target revisions, and provider gaps produce
  stable diagnostics instead of guesses or implicit writes.
- Preserve existing behavior. The explicit `Data`/`Extract`/`Load` API,
  existing fingerprints, `/1` protocols, optional dependency boundaries, and
  production plugin trust rules remain unchanged when the new facade is unused.
- Use portable [DTCS](../04_TRANSFORMATIONS/DTCS.md) expressions for new
  transformation behavior. Do not infer
  schema by executing sample rows through native UDFs or arbitrary Python.

## 2. Public contract to freeze first

Before implementation, write and review one small public contract. Names may
change during this gate, but the semantics must not.

### Source and session handles

Proposed public entry points:

```text
etl.infer_records(records, *, hints=None, limits=None)
etl.from_records(records, *, name, hints=None, limits=None)
etl.read_csv(path, *, name, options=None, hints=None, limits=None)
etl.from_pandas(frame, *, name, hints=None, limits=None)
etl.from_polars(frame, *, name, hints=None, limits=None)
```

All source constructors return the same data-first handle. It exposes:

- `schema`: the current canonical logical schema;
- `model`: an optional generated `Data` view;
- `diagnostics`: stable, actionable findings;
- `provenance`: secret-free source and inference evidence;
- `preview()`: an explicit bounded preview; and
- `definition()` / `plan()` only after normal validation and binding rules pass.

`infer_records` returns an inspection result without building a pipeline. A
one-shot iterable result owns a single-use replay stream. It must not claim
that the iterator is replayable or silently materialize an unbounded source.

### Observation models

Add a versioned, serializable model layer under `src/etlantic/inference/` (the
final module names are decided at the contract gate):

- `InferenceLimits`: row, byte, and cooperative elapsed-time budgets;
- `SchemaEvidence`: method, confidence, inspected/truncated counts, parser or
  provider options, limitations, and source/target revision;
- `InferenceResult`: `NormalizedSchema`, diagnostics, evidence, and optional
  single-use replay handle;
- `TargetObservation`: `exists` with `present | absent | unknown`, target
  identity, revision, normalized schema, constraints, and evidence;
- `FieldConstraint`: a target requirement linked to a field lineage path,
  operation rule, and confidence; and
- `WriteCompatibility`: `proven | conditional | conflict` with field-level
  findings and required runtime validations.

Do not overload `NormalizedSchema` to hide target guidance. Its metadata may
carry stable evidence, but observed fields, inferred fields, target
requirements, and write compatibility remain distinguishable in the result.

### Diagnostic families

Reserve stable diagnostic keys before adapters are written. The minimum set is:

`INFER_LIMIT`, `INFER_EMPTY`, `INFER_UNKNOWN_TYPE`, `INFER_MIXED_TYPE`,
`INFER_MISSING_FIELD`, `INFER_INVALID_KEY`, `INFER_NESTED_UNSUPPORTED`,
`INFER_CSV_HEADER`, `INFER_CSV_ROW`, `INFER_CSV_PARSE`, `INFER_SOURCE_UNSUPPORTED`,
`INFER_TARGET_UNKNOWN`, `INFER_TARGET_STALE`, `INFER_TARGET_UNSUPPORTED`,
`INFER_TARGET_CONFLICT`, `INFER_BACKWARD_UNSUPPORTED`, `INFER_BACKWARD_CONFLICT`,
`INFER_BACKWARD_NONCONVERGENT`, `INFER_WRITE_INCOMPATIBLE`, and
`INFER_RUNTIME_CONVERSION`.

Each diagnostic must identify a field or lineage path, operation, provider,
and remediation without including the offending value.

## 3. Delivery sequence

### 055-E0 — Contract and evidence skeleton

Create the implementation ADR and fixture layout before writing adapters.

Code and docs:

- add the `etlantic.inference` public namespace and lazy root exports only for
  approved stable names;
- add wire/serialization definitions for observations and compatibility
  results, using the existing freeze and fingerprint helpers;
- add diagnostic inventory entries and stability tests;
- add `tests/inference/`, `tests/inference/fixtures/`, and
  `docs/11_DEVELOPMENT/evidence/inference_0_55/`; and
- record the source/target capability matrix as data, not only prose.

Gate E0: names, wire versions, forbidden payload keys, diagnostic keys, and
fingerprint inputs are reviewed. No runtime behavior is advertised yet.

### 055-E1 — Core record kernel

Implement the engine-neutral records path first.

Likely modules:

- `src/etlantic/inference/records.py`: `Iterable[Mapping[str, object]]`
  validation, field order, missing versus explicit null, nested-value policy,
  and one-shot replay;
- `src/etlantic/inference/types.py`: scalar type lattice and deterministic
  promotion (`unknown`, null, boolean, integer, decimal, float, date,
  timestamp, string, binary, and qualified complex values);
- `src/etlantic/inference/sampling.py`: row/byte budgets, cooperative time
  checks, truncation evidence, and bounded iterator handling; and
- `src/etlantic/inference/diagnostics.py`: redacted, stable findings.

Implement hints as a validated input policy. A hint can resolve an unknown
type or parsing rule, but cannot contradict a definitive physical observation
without a diagnostic and explicit conversion.

Fixtures and tests:

- empty input, header-only shape, all-null field, missing key, explicit null;
- integer/decimal/float promotion and incompatible scalar types;
- late fields, duplicate/non-string keys, nested values, and unbounded
  generators;
- exact-once replay of the inspected prefix and untouched remainder; and
- deterministic results across repeated runs and Python hash seeds.

Gate E1: `infer_records` works with lists, tuples, generators, and bounded
infinite iterators; no row payload reaches a serialized result; all unresolved
cases have stable diagnostics.

### 055-E2 — Text and file source adapters

Build CSV and JSON adapters on the record kernel, then add qualified Parquet
metadata inspection.

- CSV uses safe path handling, header validation, delimiter/quote/encoding/null
  options, bounded reads, and deterministic text-to-logical parsing.
- JSON arrays and JSON Lines parse only bounded mappings and reuse record
  promotion. Non-mapping roots and malformed lines are diagnosed.
- Parquet uses the qualified footer/schema path. Do not deserialize untrusted
  extension metadata, and do not turn a read-only source into a write claim.
- Existing `CsvStorage`, `JsonStorage`, local-file connector, and Parquet
  adapters become callers of shared normalized inspection where appropriate;
  they retain their current read/write lifecycle semantics.

Fixtures cover malformed headers, ragged rows, duplicate columns, empty files,
ambiguous text, invalid numeric values, safe-I/O limits, JSON Lines failures,
Parquet footer limits, and no-value diagnostics.

Gate E2: `read_csv` and the file inspectors agree with `infer_records` for
equivalent parsed mappings, and their provenance identifies all parsing rules.

### 055-E3 — Frame and relation source adapters

Normalize existing inspection hooks into one source observation without making
optional packages mandatory.

Adapter order:

1. Local records and memory bindings.
2. Pandas and Polars frame metadata.
3. PySpark and DataFusion frame metadata.
4. SQL and DuckDB relation/catalog metadata.
5. First-party connector/storage inspectors: local-files, PostgreSQL,
   Snowflake, Iceberg, S3, and qualified Parquet.
6. Schema-document sources such as Kafka/registry providers.

Each adapter declares whether evidence is metadata-based, bounded-sample and
provisional, schema-document based, or hint-only. Missing, inaccessible, and
unsupported are separate states. Streaming sources are never consumed merely
to infer a plan.

Add source-matrix fixtures for every first-party package and a contract test
that compares equivalent logical schemas across engines. Keep engine imports
inside optional adapters.

Gate E3: every schema-bearing qualified source has a normalized observation;
opaque sources produce a stable unsupported/hint diagnostic; import safety and
plugin allowlists pass.

### 055-E4 — Forward portable schema transfer

Implement a pure schema transfer module over the existing DTCS action tree.
It consumes input schemas and produces output schemas plus field lineage; it
never executes a transformation.

Implement in this order:

1. direct fields, projection, rename, drop, filter, sort, limit, distinct;
2. literals, nullability, explicit casts, arithmetic, and common scalar calls;
3. union and join field alignment, collision policy, and outer-join
   nullability;
4. grouping and aggregate output signatures; and
5. qualified continuation families only after their compiler matrix is frozen.

Every rule must state output type, nullability, field identity, and whether it
can be inverted. Unsupported or ambiguous expressions stop at a diagnostic.

Golden corpus:

- empty and all-null input fields;
- decimal, date, timestamp, string, and complex values;
- union promotion and missing columns;
- join keys, collisions, outer nullability, and multi-input lineage;
- aggregate signatures and aliases; and
- unsupported/native expressions.

Gate E4: Local, Pandas, Polars, SQL, PySpark, DataFusion, and DuckDB
qualified cases derive equivalent canonical output schemas and DTCS lineage.

### 055-E5 — Target inspection and write compatibility

Add a separate optional target-inspection capability. Do not change the frozen
`etlantic.sink/1` lifecycle protocol. A sink or storage provider may expose a
target inspector through an adapter or capability negotiation.

Implement:

- tri-state existence (`present`, `absent`, `unknown`) with an explicit
  `empty-but-present` case;
- target identity and revision/snapshot token;
- fields, nullability, keys, defaults, generated columns, partitions, and
  provider constraints;
- adapters for SQL/DuckDB, local CSV/JSON/memory, S3/Parquet metadata, and
  first-party connector fakes before live-provider paths; and
- target inspection that performs no writes or implicit creation.

Write compatibility is mode-specific. Test append, overwrite/replace,
merge/upsert, and partition replace only where the provider advertises them.
Creation proposals require explicit intent and a provider create capability.

Gate E5: existing, absent, unknown, empty, denied, stale, and concurrently
created targets are distinguishable, and compatibility checks fail closed.

### 055-E6 — Backward constraint solver

Build the target-guided pass on top of forward schemas and lineage.

Algorithm:

1. inspect and pin the existing target observation;
2. map target fields to output fields explicitly;
3. seed field constraints from target logical types, nullability, keys,
   partitions, and write mode;
4. walk qualified lineage in reverse using only sound inverse rules;
5. merge compatible constraints and retain conflicts by branch;
6. rerun forward inference with parse policies and validated hints;
7. stop at a bounded fixed point, or emit `INFER_BACKWARD_NONCONVERGENT`; and
8. produce compatibility obligations and a reviewable explanation.

Required rules are direct projection/rename/pass-through, explicit cast
barriers, CSV/text parsing, nullability, union promotion, join branches, and
qualified scalar signatures. Arithmetic, aggregates, windows, opaque
functions, and native implementations remain unknown unless an inverse rule
is proven.

Golden examples include text-to-integer CSV, definite string-to-integer
conflict, invalid numeric values, nullable-to-non-null targets, two targets
with conflicting requirements, and a target schema changing between inspect
and publish. The solver must never relabel observed source evidence.

Gate E6: backward results are deterministic, bounded, provenance-rich, and
distinguish hypotheses, explicit conversions, proven compatibility, conditional
compatibility, and conflicts.

### 055-E7 — Data-first facade and definition integration

Build the user experience only after E1–E6 have stable result models.

- Add source constructors and result handles behind lazy optional imports.
- Build implicit source/step/load definitions from the same public authoring
  builders used by typed pipelines.
- Attach source, target, forward-transfer, and backward-constraint provenance
  to `ContractDefinition` metadata without embedding rows.
- Generate an optional runtime `Data` view and a code/stub export path.
- Keep `preview()` explicit, bounded, and local; never inspect a live source
  during module import or unrelated validation/planning.
- Export only stable, rebindable assets to durable `PipelineDefinition` and
  normal validate/plan/generate flows.

End-to-end examples:

1. records → filter/project → new memory/CSV target;
2. CSV text → target integer column → backward parse proposal and runtime
   validation;
3. Pandas/Polars → portable transforms → existing SQL target compatibility;
4. one-shot iterator → preview/run exactly once; and
5. source/target revision change → proposal/diff, no silent mutation.

Gate E7: the public walkthrough works without handwritten source,
transformation, or output models, and explicit class-authored pipelines retain
their fingerprints.

### 055-E8 — Qualification, hardening, and release evidence

Run the complete evidence campaign:

- source-by-engine and target-by-write-mode matrix;
- seven-engine differential schema corpus;
- connector conformance and optional-dependency import tests;
- property tests for type promotion, fingerprints, replay, and boundedness;
- security tests for safe paths, plugin trust, redaction, row/payload leakage,
  tenant scope, and schema-history metadata;
- race tests for target appearance and revision changes;
- benchmark sampling, metadata inspection, backward solving, and preview;
- docs examples and generated artifacts through validate/plan/generate; and
- compatibility run against the full existing test suite.

Create a signed, machine-readable evidence index under
`docs/11_DEVELOPMENT/evidence/inference_0_55/`. It must list each matrix row,
fixture digest, package/version, method, confidence, limitations, and result.

Gate E8: all required rows are evidence-complete, unsupported rows are
explicitly marked, no source rows or secrets appear in artifacts, and the
0.55 exit decision can be reproduced from the evidence index.

## 4. Suggested change map

| Area | Primary implementation locations | Primary tests |
|---|---|---|
| Core inference | `src/etlantic/inference/`, `src/etlantic/schema_drift.py` | `tests/inference/test_records.py`, `test_types.py`, `test_replay.py` |
| File sources | `src/etlantic/storage/`, `src/etlantic/connectors/local_files.py` | `tests/inference/test_csv_json.py`, `tests/storage/`, `tests/connectors/` |
| Engine sources | optional plugin adapters and `src/etlantic/dataframe/` | `tests/dataframe/`, `tests/*_compiler/`, `tests/inference/test_source_matrix.py` |
| Target inspection | `src/etlantic/connectors/`, `src/etlantic/sql/`, optional plugin adapters | `tests/inference/test_targets.py`, connector conformance suites |
| Forward transfer | `src/etlantic/transform/`, new inference transfer module | `tests/inference/test_forward_transfer.py`, portable differential fixtures |
| Backward constraints | new inference solver and provenance models | `tests/inference/test_backward_solver.py`, compatibility fixtures |
| Facade/export | `src/etlantic/authoring/`, root lazy exports, definition serialization | `tests/inference/test_facade.py`, `tests/authoring/`, `tests/cli/` |
| Evidence/docs | `docs/11_DEVELOPMENT/evidence/inference_0_55/`, capability docs | `tests/docs/`, `scripts/check_docs.py` |

The exact file placement may change after E0, but new code should remain behind
public protocols and avoid private imports from optional plugins.

## 5. Merge and release order

Merge in slices that leave the repository valid:

1. E0 contract and empty protocol types;
2. E1 records kernel and tests;
3. E2 file adapters;
4. E3 source matrix adapters;
5. E4 forward transfer;
6. E5 target inspection;
7. E6 backward solver;
8. E7 facade/export;
9. E8 evidence, docs, and capability claims.

Each slice must pass `git diff --check`, focused tests, the relevant optional
dependency matrix, and the repository documentation checks. Do not advertise
the 0.55 capability in `CAPABILITIES.md` or release notes until E8 is complete
and the exit gate changes the claim from Planned.

## 6. Definition of done

0.55 is ready for its exit review when:

- records, files, frames, relations, connectors, and schema-document sources
  have a qualified normalized inference path or an explicit unsupported/hint
  result;
- forward portable transfer and target-guided backward constraints are
  deterministic and bounded;
- existing targets are inspected read-only and checked against a pinned
  revision before publication;
- missing targets receive proposals only through explicit create intent;
- the text-to-integer example validates every value and reports bad values
  without rewriting the observed source type;
- generated models, definitions, plans, reports, and histories contain no
  source rows or secrets;
- explicit pipelines preserve their existing fingerprints and behavior;
- optional imports remain lazy and production trust/safe-I/O gates remain in
  force; and
- the evidence index, docs examples, conformance suites, security campaign,
  and full regression suite all pass.
