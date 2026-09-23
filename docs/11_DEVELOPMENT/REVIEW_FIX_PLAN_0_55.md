---
title: ETLantic 0.55 Full Review Fix Plan
description: Ordered closure plan for the remaining 0.55 inferred model authoring review findings.
plan_status: planned
plan_last_reviewed: 0.55.0-blocker-review
---

# ETLantic 0.55 Full Review Fix Plan

This is the implementation plan for the findings from the full 0.55 phase
review. It supplements the [0.55 execution plan](EXECUTION_PLAN_0_55.md) and
the broader [inference remediation plan](INFERENCE_REMEDIATION_PLAN_0_55.md).
It is the current checklist for closing the remaining release blockers and
hardening gaps.

This revision incorporates the full 0.55 review findings: transformation
actions being dropped from durable definitions, cumulative-frame lineage
replay, missing lineage fingerprints, source-mapping ambiguity, provider
failure handling, target-observation metadata loss, Decimal precision loss,
non-deterministic durable fingerprints, discarded dataframe previews,
fail-open target diagnostics and append capability checks, and incomplete
evidence qualification.

This plan tracks the full 0.55 scope. The evidence index may qualify only the
capabilities listed in its `qualification_scope`; every excluded adapter or
write mode remains explicitly unsupported. No broader availability claim is
implied by a scoped qualification.

## 1. Review closure map

| Priority | Finding | Closure work package |
|---|---|---|
| P0 | Backward propagation is name based and does not solve qualified lineage constraints | F4 |
| P0 | Sequential data-first transformations can replay old actions against a current schema | F3/F6 |
| P0 | Inference results do not produce durable, validated ETLantic definitions | F6 |
| P0 | Source/target qualification matrix and evidence are incomplete | F7 |
| P0 | Durable definitions omit action parameters, intermediate contracts, target observations, and multi-input edges | F6 |
| P0 | Target-guided output schemas relabel observations instead of preserving an observed schema and a target hypothesis | F4 |
| P1 | Target nullability and requiredness are ignored during backfill | F4/F5 |
| P1 | Write modes share one compatibility path | F5 |
| P1 | Malformed target payloads fail open | F3 |
| P1 | Provider metadata and diagnostics are not closed or JSON safe | F0 |
| P1 | Serialized metadata can retain source values under unapproved keys | F0/F8 |
| P1 | Dataframe and provider conversions can materialize unbounded inputs | F2 |
| P1 | Provider conversion failures are raised or silently downgraded instead of diagnosed | F2/F7 |
| P1 | No target revision pinning or stale-target check exists | F3/F5 |
| P1 | Target observation metadata and revision are lost by compatibility checks | F3/F5 |
| P1 | No explicit missing-target output/create proposal exists | F5/F6 |
| P1 | Create proposals advertise capability without provider negotiation | F5 |
| P1 | Missing expression references are not diagnosed | F3 |
| P1 | Decimal compatibility and date/datetime promotion are incomplete | F1/F5 |
| P1 | Decimal-to-number runtime conversion loses precision | F1/F5 |
| P1 | A single mapping is misclassified as a provider schema instead of a record | F2 |
| P1 | Write modes allow undeclared provider capabilities | F5 |
| P1 | Provider type normalization stringifies arbitrary objects and misses qualified aliases | F1 |
| P1 | Durable fingerprints include elapsed timing and differ across identical runs | F0/F6 |
| P1 | Pandas and Polars handles infer schemas but discard their bounded previews | F2/F7 |
| P1 | Synchronous target adapters return a fingerprint instead of an explicit revision | F3/F5 |
| P1 | Target inspector error diagnostics are ignored when a schema is present | F3/F5 |
| P1 | Direct malformed source schemas and invalid CSV options can raise instead of diagnosing | F2/F7 |
| P1 | Optional non-nullable model fields accept explicit nulls | F1/F6 |
| P1 | Runtime preview evaluation diverges from portable null and scalar semantics | F1/F3/F7 |
| P1 | Unknown provider types can produce a valid-looking schema without a diagnostic | F1/F7 |
| P1 | The evidence checker validates manifests but does not scan serialized or in-memory wire payloads | F8 |
| P2 | Default path identities collide and can reveal path structure | F0/F2 |
| P2 | Wire models lack complete version and round-trip rules | F0 |
| P2 | Transformation diagnostics are unbounded | F3 |
| P2 | Transformation metadata can exceed the configured diagnostic budget | F3 |
| P2 | Provider Python classes are mapped to stringified class names | F1 |
| P2 | Pyright reports five unsafe provider/schema operations | F2 |
| P2 | Default records and file facade names collide across independent sources | F0/F2 |
| P2 | Evidence is accumulated on every transformation without a bounded history policy | F0/F3 |
| P2 | Runtime generic iterable conversion still uses an unbounded list materialization | F2 |
| P2 | Inference result and observation wire versions are inconsistent | F0 |

## 2. Invariants for every work package

- Observed source facts remain distinct from target constraints, conversions,
  and validated compatibility.
- Durable definitions preserve every portable transformation as a validated
  step node and edge; top-level transformation metadata is not executable
  graph structure.
- Backward propagation uses qualified lineage rules. Unknown, lossy,
  ambiguous, or native operations stop propagation with a stable diagnostic.
- A transformed frame carries a delta or a root schema explicitly. Historical
  actions are never replayed against an already-transformed schema.
- Every source and provider adapter enforces row, byte, and cooperative time
  limits before converting or materializing data.
- A mapping is treated as a record or a schema only after an explicit,
  deterministic disambiguation rule. Provider failures produce stable
  diagnostics and never silently fall back to weaker evidence.
- Target inspection is read-only, revision aware, and fail closed for denied,
  malformed, unknown, or stale state.
- Target observation metadata, revisions, capabilities, keys, and partitions
  remain attached through compatibility and publication checks.
- Wire payloads contain primitive values, schema metadata, fingerprints,
  limits, revisions, and diagnostics only. They contain no rows, source
  values, secrets, absolute paths, or arbitrary provider objects.
- Existing typed pipeline fingerprints and public `/1` protocols remain
  unchanged unless a versioned migration is explicitly accepted.

## 3. Ordered work packages

### F0 — Close the wire, metadata, and security boundary

**Scope**

1. Version `InferenceObservation`, `TargetObservation`, `FieldConstraint`,
   `WriteCompatibility`, lineage payloads, and diagnostic payloads. Define
   accepted versions, unknown-field handling, and old-payload migration.
2. Add one recursive serializer/redactor shared by source metadata, target
   metadata, diagnostics, field metadata, and evidence. Permit only JSON
   primitives, bounded lists/maps, and approved metadata keys. Reject or
   replace row-like keys (`rows`, `records`, `sample`, `values`, `data`) even
   when their values are JSON primitives. Redact values whose names or paths
   indicate credentials, tokens, passwords, headers, or source data.
3. Replace default `kind:path.name` identities with a deterministic,
   privacy-preserving identity. Keep an explicit caller-supplied identity when
   stable cross-run history is required and diagnose identity collisions.
4. Add compatibility fixtures for existing observations, field constraints,
   diagnostics, and Decimal fingerprints. Preserve the historical typed
   contract canonicalization while allowing inferred Decimal precision.
5. Define a versioned lineage wire payload and migrate legacy dictionary
   payloads. Unknown fields must be ignored only when the payload version is
   supported; unsupported versions must fail closed with a stable diagnostic.

**Tests and gate**

- JSON round trips for current and legacy payloads;
- primitive-only recursive metadata tests, including provider objects and
  `Diagnostic` instances;
- row-like metadata keys and nested source-value scans that prove plans,
  definitions, reports, evidence, and history contain no source values;
- row/value/secret/absolute-path scans over plans, evidence, and history; and
- deterministic identity and collision tests.

F0 passes when serialized inference artifacts are closed, versioned, stable,
and row free.

### F1 — Establish one logical type lattice and provider normalizer

**Scope**

1. Add a shared public normalizer for Python classes and provider type names.
Map `int`, `float`, `Decimal`, `date`, `datetime`, `bool`, bytes, and common
qualified logical names without stringifying Python class objects or arbitrary
provider instances. Parse parameterized names such as `decimal(18,2)`,
`decimal128(10,2)`, `timestamp[us]`, and provider-qualified aliases.
2. Define promotion rules for null, boolean, integer, Decimal, number/float,
   date, datetime, string, binary, and unknown. In particular, mixed date and
   datetime values promote to datetime; Decimal and number use an explicit
   precision-preserving policy.
3. Define the runtime cast policy used by target compatibility. A Decimal to
   number promotion must state whether precision is retained, rounded, or
   rejected. The selected policy must be used by preview conversion, replay,
   compatibility obligations, and all-values validation.
4. Make CSV, records, source providers, target providers, and compatibility
   checks call the same normalizer.

**Tests and gate**

- promotion property tests and mixed date/datetime fixtures;
- large Decimal CSV values without float round trips;
- Python-class provider schemas (`int` becomes `integer`); and
- arbitrary provider objects and parameterized provider aliases;
- Decimal/number compatibility and cast-obligation regressions.

F1 passes when equivalent values and provider schemas produce the same
logical type and the existing fingerprint suite remains unchanged.

### F2 — Enforce bounded adapter materialization

**Scope**

1. Centralize effective limits, including defaults when callers omit limits.
   Defaults must include bounded byte and cooperative-time budgets, with an
   explicit opt-in for a provider that can prove a stronger bound.
2. Define a bounded adapter protocol with metadata-first inspection and a
   `head`/bounded-record operation. Require providers to prove a bounded view
   before calling `to_dict`, `to_dicts`, or equivalent conversion.
3. Update local, Pandas, Polars, generic iterable, CSV, JSON, and optional
   provider paths. A failed bounded conversion must not fall back to an
   unbounded conversion. One-shot replay must describe the inspected prefix
   and remaining stream accurately.
4. Disambiguate a single mapping deterministically: explicit schema envelopes
   and provider schema objects use metadata inspection; a mapping with record
   values uses the records kernel. Ambiguous mappings return a diagnostic.
5. Convert provider exceptions, denied inspection, and rejected conversion
   into stable diagnostics without a weaker fallback that consumes the source.
6. Fix all five current Pyright errors by narrowing provider/schema values at
   the adapter boundary rather than suppressing type checking.

**Tests and gate**

- fakes that fail if full dataframe conversion is called;
- infinite and very large iterables with row/byte/time limits;
- a single mapping record, an explicit schema envelope, and an ambiguous
  mapping;
- replay-prefix and remainder tests;
- metadata-first provider tests; and
- denied inspection and conversion-error diagnostics; and
- `pyright src/etlantic/inference --level warning` with zero errors.

F2 passes when no supported path can materialize beyond its declared bound
before inference.

### F3 — Make schemas and target observations qualified and diagnostic

**Scope**

1. Replace name-only lineage metadata with a typed graph that identifies
   source field, operation, alias, nullability, requiredness, and invertibility.
   Give each node and edge a stable identity and compute a canonical graph
   fingerprint from sorted primitive payloads.
2. Cover direct reference, rename, projection, cast, arithmetic, scalar call,
   filter, sort, limit, distinct, union, join, aggregate, and explode. Mark
   pass-through, widening, narrowing, lossy, and non-invertible rules.
   Represent a frame action delta separately from the root action history so
   repeated data-first transformations cannot replay old actions.
3. Emit `INFER_LINEAGE_MISSING` for missing expression references and stable
   collision diagnostics for duplicate aliases, renames, and projections.
4. Strictly validate target inspection payloads. Distinguish absent,
   unknown, present-empty, and present-with-schema. Invalid `fields` shapes
   become `INFER_TARGET_UNSUPPORTED` rather than a schema-less present target.
5. Cap and deduplicate diagnostics at every transformation using
   `InferenceLimits.max_diagnostics`; preserve prior evidence and diagnostics.
6. Keep graph serialization primitive-only and give it a deterministic
   fingerprint.
7. Preserve target-observation metadata while normalizing malformed fields;
   validate keys, partitions, capabilities, revisions, and async inspector
   payloads through the same strict path.

**Tests and gate**

- missing references, duplicate aliases, rename collisions, and malformed
  target payloads;
- lineage golden files for each operation category;
- unsupported local evaluation diagnostics;
- bounded diagnostic chains after repeated transformations; and
- deterministic graph fingerprints.
- cumulative-frame regressions that retain qualified source fields; and
- synchronous/asynchronous target metadata and revision parity.

F3 passes when every output field has one qualified identity or an explicit
unknown/conflict diagnostic and target state cannot be misclassified.

### F4 — Implement the target-guided backward solver

**Scope**

1. Inspect and pin the target observation, including identity, revision,
   fields, type, nullability, requiredness, keys, defaults, generated fields,
   partitions, and mode capabilities.
2. Map target fields to output lineage nodes, seed `FieldConstraint` values,
   and walk only sound inverse rules toward source fields.
3. Merge constraints across branches and retain conflicts. Handle nullable to
   non-nullable targets, required target fields, aliases, explicit casts,
   narrowing, and all-values conversion obligations.
4. Bound iterations and constraint growth. Emit
   `INFER_BACKWARD_NONCONVERGENT` when a fixed point cannot be reached and
   `INFER_BACKWARD_UNSUPPORTED` at a non-invertible barrier.
5. Re-run forward inference with the resulting parse/cast policy while
   preserving the original observed schema as a separate value. The resolved
   model may carry a target-compatible hypothesis only when the observation,
   conversion, and validation obligation remain attached. Return a reviewable
   explanation that labels each field as observed, constrained, converted,
   conditional, or conflicting.
6. Key every propagated constraint by the qualified lineage source node, not
   the output alias. Conflicting targets must retain every branch and must not
   be overwritten by a later target pass.

**Required regression cases**

- CSV string to existing integer through direct projection;
- string plus integer arithmetic, which must stop at the arithmetic barrier;
- explicit cast barriers and invalid numeric values;
- nullable source to required/non-null target;
- two targets with conflicting requirements; and
- target revision changing between inspection and compatibility;
- chained rename/project/rename lineage; and
- target-compatible hypotheses that preserve the original observed type and
  all runtime conversion obligations.

F4 passes when target constraints backfill prior models only through sound
lineage and never relabel observed source evidence.

### F5 — Make write compatibility and proposals mode aware

**Scope**

1. Add provider capability declarations and required-field semantics for
   append, overwrite, merge, upsert, and partition replacement. Do not treat
   the mode as metadata only. An undeclared mode must fail closed for every
   provider, including append and overwrite.
2. Validate target required fields, nullability, keys, generated/default
   columns, partition requirements, and runtime conversion obligations for all
   source fields and rows represented by the write contract.
3. Compare the pinned target revision immediately before compatibility and
   publication, carrying the revision from `TargetObservation` rather than
   reconstructing it from schema metadata. Return `INFER_TARGET_STALE` on
   mismatch and do not publish a stale compatibility result.
4. Add an explicit output proposal for absent targets. A proposal may contain
   a normalized schema, lineage, evidence, and create requirements, but it
   cannot imply creation or write without explicit create intent and a
   negotiated provider create capability. Never hard-code `create` for an
   arbitrary target.

**Tests and gate**

- all five write modes against append-only, keyed, partitioned, and generated
  column target fakes;
- required and nullable field failures;
- stale revisions and concurrent target appearance;
- absent, present-empty, and unsupported create proposals; and
- Decimal/date conversion obligations;
- undeclared append/overwrite/merge/upsert/partition capabilities; and
- target metadata parity for sync and async inspectors.

F5 passes when compatibility is mode-specific, revision-aware, and fail
closed, and missing-target output is an explicit proposal.

### F6 — Integrate with durable ETLantic authoring

**Scope**

1. Make `InferredDataset.definition()` and `.plan()` produce the existing
   validated/bindable `PipelineDefinition` surface, including source,
   portable transforms, target observation, lineage, and row-free evidence.
   Emit a `NodeDefinition(kind="step")` and an edge for every portable action;
   transformations must not remain unattached entries in the definition.
2. Reuse normal `validate`, `plan`, `compile`, and `generate` paths. Preserve
   class-authored definitions and existing fingerprints.
   Planning a transformed data-first dataset must expose the same logical
   graph and transformation order as the runtime facade.
3. Expose explicit review/approval boundaries for target-guided casts and
   create proposals. Inference must not execute writes or silently create
   targets.

**Tests and gate**

- end-to-end records/CSV to definition, validate, plan, and generate;
- chained filter/project/rename definitions whose planned graph contains each
  step and preserves action order;
- existing-target constraint flow through the durable definition;
- absent-target proposal requiring create intent; and
- serialized definition scans for rows, values, secrets, and provider objects.

F6 passes when data-first authoring uses the same validated public pipeline
surface as class-authored pipelines.

### F7 — Qualify the complete source and target matrix

**Scope**

1. Add metadata-first adapters and conformance fixtures for records, CSV,
   JSON, Pandas, Polars, PySpark, DataFusion, SQL/DuckDB, Parquet, schema
   documents/registries, and each first-party storage/connector surface that
   advertises schema inspection.
2. Keep optional dependencies isolated and test import safety with each
   dependency absent. Record whether evidence is metadata based, bounded
   sample based, schema-document based, or hint only.
3. Add equivalent-schema differential fixtures across qualified engines and a
   source/target/write-mode capability matrix in machine-readable evidence.
4. Qualify denied, malformed, opaque, and conversion-error providers as
   distinct states. A provider exception must produce a stable diagnostic or
   an explicit unsupported result; it must never silently consume a weaker
   record path.

**Tests and gate**

- adapter conformance suite and optional-import matrix;
- equivalent logical schema differential tests;
- denied/inaccessible/opaque provider states;
- provider conversion exceptions and mapping/schema disambiguation; and
- first-party connector and target inspector fixtures.

F7 passes when every advertised source and target has a qualified evidence
path or a stable unsupported diagnostic, with no core optional imports.

### F8 — Run the release evidence campaign

**Scope**

1. Create `docs/11_DEVELOPMENT/evidence/inference_0_55/` with an index,
   capability matrix, fixture digests, package versions, limitations,
   unsupported cases, and generated result summaries.
2. Add property tests for type promotion, Decimal precision, replay, limits,
   identity, fingerprints, lineage, solver convergence, and wire closure.
3. Add security scans for rows, values, secrets, absolute paths, arbitrary
   objects, and unbounded metadata. Add race tests for target appearance,
   revision changes, and concurrent writes.
4. Update capability and roadmap status only after every gate passes. Until
   then, keep the phase and public docs marked planned.
5. Add a machine-readable finding ledger linking every review finding to its
   implementation commit, regression test, evidence artifact, and gate. The
   ledger must fail the release check when a P0/P1 finding lacks all four
   links.

**Release commands**

```text
ruff check src/etlantic/inference src/etlantic/schema_drift.py \
  src/etlantic/dataframe/local.py src/etlantic/storage/protocol.py tests/inference
pyright src/etlantic/inference --level warning
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q tests/inference
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q
.venv/bin/python scripts/check_docs.py
.venv/bin/python scripts/check_adaptive_0_52.py
```

Add a repository security/evidence command before the final gate and record
its output under the inference evidence index. The command must scan both
serialized definitions and in-memory-to-wire conversion fixtures, including
row-like metadata keys and provider failure payloads.

F8 passes when focused, full-suite, typing, documentation, adaptive,
security, optional-dependency, differential, race, and evidence checks are
reproducible.

The repository evidence manifest and gate campaign can be checked with
`uv run python scripts/check_inference_0_55.py --verify PATH`; this validates
the row-free shape, commit-pinned gate results, and explicit unsupported
optional surfaces before qualification is accepted. Use
`--run-gates --output PATH` to produce the machine-readable campaign.

## 4. Concrete regression inventory

The following cases are release regressions. Each must have a focused test and
an entry in the evidence ledger before the phase can advance.

| Case | Expected result |
|---|---|
| `infer_source({"id": 1})` | Infer one integer record, not a provider type named `"1"`. |
| Provider `head()` plus `to_dicts()` with a byte/time budget | Conversion is bounded or returns `INFER_SOURCE_UNBOUNDED`; it never ignores the budget. |
| Provider schema inspection raises or conversion raises | Stable denied/unsupported diagnostic; no silent fallback or uncaught provider exception. |
| `rename → select(alias) → rename` | Qualified source lineage and fingerprint remain stable. |
| Data-first definition with three actions | Definition contains three validated step nodes and ordered edges. |
| Two targets require incompatible types through an alias | Both qualified constraints remain, with `INFER_BACKWARD_CONFLICT`. |
| `TargetObservation(revision="v1", metadata={"keys": ...})` | Compatibility uses the observation revision and keys. |
| `create_intent=True` without provider create capability | Proposal remains non-creatable and carries a capability diagnostic. |
| Decimal with more precision than binary float to a number target | The declared precision policy is applied and the obligation is reported. |
| Provider type `decimal(18,2)` or an arbitrary type object | Stable logical type or `unknown`; no memory-address string. |
| Metadata containing `sample_rows` or `values` | Wire payload redacts or rejects the content and remains row free. |
| `max_diagnostics=1` with repeated missing references | Both runtime and serialized metadata respect the configured cap. |
| Two identical source runs | Observations, definitions, and pipeline fingerprints are byte identical. |
| `from_pandas(df)` / `from_polars(df)` | Schema and bounded preview are both available under the shared facade. |
| Target inspector returns a schema plus an error diagnostic | Backfill and compatibility fail closed; they do not publish a proven result. |
| Synchronous target schema mapping with `revision="v1"` | `TargetObservation.revision` is exactly `"v1"`, matching async inspection. |
| Target capabilities omit `append` | Append is unsupported until explicitly declared. |
| Malformed source fields or invalid CSV parser options | Stable diagnostic result; no uncaught provider/parser exception. |
| Optional non-nullable model field | Missing value is accepted; explicit `None` is rejected. |
| `lower(None)`, `if_null`, `case_when`, and `abs` | Preview evaluation and inferred schema follow the same portable null/type rules. |
| Durable three-step transformed definition | Parameters, intermediate contracts, bindings, and ordered executable edges survive round trip. |
| Join/union durable definition | Both source nodes and all input edges are present, or export fails explicitly. |

## 5. Dependency and merge order

1. F0 freezes wire and security rules.
2. F1 provides the shared type and provider normalizer.
3. F2 closes bounded adapter behavior and typing.
4. F3 supplies qualified lineage, strict target parsing, and diagnostic caps.
5. F4 implements the backward solver on that graph.
6. F5 adds mode-aware compatibility, revisions, and create proposals.
7. F6 connects the result to durable definitions.
8. F7 qualifies the source/target matrix.
9. F8 runs the evidence and release campaign.

Each work package must leave the existing suite passing, include focused
regression tests, pass `git diff --check`, and avoid changing phase status.
Parallel implementation is allowed only after its dependency contract is
merged; a later package must not infer an unstabilized wire or lineage shape.

## 5A. Blocker execution sequence

The following sequence is the implementation order for the latest review
findings. Each step produces a reviewable checkpoint before the next package
depends on it.

### B0 — Freeze the observation and wire contracts

1. Add explicit observed-schema, target-hypothesis, conversion-obligation, and
   target-snapshot sections to the public result models. Keep target guidance
   separate from observed source facts.
2. Move elapsed time and other run-local measurements out of durable
   observations. Durable fingerprints may use counts, limits, methods, and
   stable evidence only.
3. Replace `_json_safe` with a shared allowlist serializer. It must recurse
   through arbitrary keys, reject row-like aliases such as `sampleRows`,
   redact secrets and path-like values, reject non-finite numbers, and convert
   provider objects to stable type tokens. Apply it to diagnostics, evidence,
   target metadata, lineage, definitions, and history payloads.
4. Add `finding_ledger.json` with one entry per P0/P1 finding. Every entry
   must link to a code change, regression test, evidence artifact, and gate.

Checkpoint: repeated inference produces byte-identical observations and
pipeline definitions, and the wire scanner finds no rows, values, secrets,
paths, or provider objects.

### B1 — Close the type, model, and bounded-source kernel

1. Route records, CSV, JSON, dataframe, target, and compatibility paths
   through one logical-type lattice and provider alias parser. Unknown types
   emit `INFER_UNKNOWN_TYPE` with provider/path context.
2. Define and test the Decimal-to-number policy once, then reuse it for
   preview rows, replay, target backfill, compatibility obligations, and
   all-values validation.
3. Make generated models enforce `required` and `nullable` independently;
   an optional non-nullable field must reject explicit null.
4. Introduce one bounded adapter boundary. Providers must prove a bounded
   view before conversion; CSV/JSON must enforce byte and cooperative-time
   limits before parsing an oversized record. Generic runtime materialization
   must use the same boundary.
5. Make Pandas and Polars constructors retain the bounded preview promised by
   the common facade, including metadata-first frames that expose a schema.
6. Return stable diagnostics for malformed provider payloads and invalid CSV
   options. Add an explicit ambiguous-mapping result instead of silently
   selecting the schema path.

Checkpoint: provider fakes cannot trigger unbounded conversion, all source
constructors have consistent preview behavior, and model validation agrees
with normalized nullability.

### B2 — Build qualified lineage and runtime semantic parity

1. Represent every source field, output field, action, alias, and edge with a
   stable qualified identity. Store action deltas separately from root history.
2. Add explicit multi-input source nodes and edges for joins, unions, and set
   operations. Unsupported or non-invertible operations must stop backward
   propagation with a diagnostic.
3. Align the bounded local evaluator with the portable function vocabulary,
   especially null propagation, `if_null`, `null_if`, `case_when`, numeric
   scalar functions, and explicit casts. Unsupported evaluation must never
   silently manufacture a preview value.
4. Add golden lineage fixtures for rename/project/rename, arithmetic barriers,
   joins, unions, and duplicate aliases.

Checkpoint: every output field has one qualified lineage path or an explicit
unknown/conflict diagnostic, and preview rows match the inferred model for all
qualified functions.

### B3 — Implement target-guided solving and fail-closed compatibility

1. Carry target identity, revision, keys, partitions, capabilities, defaults,
   generated fields, and inspector diagnostics in a pinned target snapshot.
2. Seed constraints from target fields, walk sound inverse rules toward root
   fields, preserve branch conflicts, and retain the original observed schema
   beside any target-compatible hypothesis.
3. Make every compatibility mode capability-driven, including append. An
   undeclared mode, invalid capability payload, target inspector error, or
   stale revision must return a conflict/unknown result.
4. Make create proposals carry lineage/evidence and require explicit create
   intent plus negotiated provider capability.
5. Add race fixtures for target appearance and revision changes between
   inspection and compatibility/publication.

Checkpoint: target constraints are reviewable, revision-aware, mode-specific,
and cannot turn an observed source fact into an unqualified target fact.

### B4 — Make durable authoring executable and rebindable

1. Build one contract per source/intermediate/output state. Preserve the
   source binding or reject durable export for an unbound one-shot source.
2. Put complete portable action parameters in the executable transformation
   plan and attach implementation/compiler references required by normal
   planning. Namespace step metadata keys.
3. Attach target snapshots, proposals, lineage, obligations, and row-free
   evidence to the definition through approved metadata fields.
4. Route `definition()` and `plan()` through normal validation. Invalid,
   ambiguous, unsupported, stale, or unbound sessions must fail before export.
5. Add end-to-end round trips through `validate`, `plan`, `compile`, and
   `generate`, including a multi-input graph and an existing-target cast.

Checkpoint: a serialized definition can be reloaded and executed from its
bindings, while an unbound or unsafe session is rejected before durable export.

### B5 — Qualify adapters and run the evidence campaign

1. Add direct inference conformance tests for Pandas, Polars, DataFusion,
   PySpark, SQL/DuckDB, Parquet, schema registries, and first-party target
   inspectors. Record absent-dependency results separately from failures.
2. Replace the manifest-only checker with a repository security/evidence
   command that scans definitions, observations, target payloads, diagnostics,
   in-memory wire fixtures, and evidence artifacts.
3. Generate fixture digests, package versions, unsupported cases, race
   results, differential results, and finding-ledger status under
   `evidence/inference_0_55/`.
4. Keep qualification limited to the explicitly supported matrix. Mark that
   scope qualified only after every required gate is reproducible; excluded
   capabilities remain unsupported until they have their own evidence.

Checkpoint: the evidence index is sufficient to independently decide the
0.55 exit without relying on source inspection or undocumented local state.

## 6. Definition of done

The review is closed when:

- target constraints reach prior models only through qualified lineage;
- sequential data-first transformations preserve their action graph and
  lineage when definitions are validated and planned;
- nullability, requiredness, modes, revisions, and conversion obligations are
  explicit;
- malformed schemas, missing references, unsupported operations, and stale
  targets fail closed;
- all source paths are bounded before materialization;
- mappings, provider schemas, denied providers, and conversion failures have
  deterministic dispatch and diagnostics;
- Decimal/date behavior, Python provider mappings, and existing fingerprints
  are covered by regression tests;
- wire payloads are versioned, primitive-only, row-free, and JSON safe;
- normal ETLantic definition/validate/plan/generate flows work end to end;
- every included source/target capability has reproducible evidence, while
  unsupported capabilities are explicitly excluded; and
- the scoped 0.55 qualification can be marked qualified only after F8 passes.
