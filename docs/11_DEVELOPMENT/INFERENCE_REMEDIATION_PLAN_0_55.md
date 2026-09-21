---
title: ETLantic 0.55 Inference Remediation Plan
description: Release-blocker remediation for bounded inference, transformation lineage, target backfill, and data-first model authoring.
plan_status: planned
plan_last_reviewed: 0.54.0
---

# ETLantic 0.55 Inference Remediation Plan

This plan turns the initial implementation review into an ordered set of
changes. It supplements the [0.55 execution plan](EXECUTION_PLAN_0_55.md).
The later [full review fix plan](REVIEW_FIX_PLAN_0_55.md) maps the current
finding list to concrete closure work and is the active checklist for the
remaining blockers.

The implementation must preserve the existing typed pipeline API and existing
schema fingerprints. Inference remains engine-neutral, bounded, row-free in
serialized artifacts, and fail closed when lineage or provider evidence is
insufficient.

## 1. Review findings covered

| Finding | Remediation slice | Priority |
|---|---|---|
| Target constraints do not travel through transformations | R3/R4 | P1 |
| Rename collisions and missing projections silently corrupt models | R2 | P1 |
| Transformations discard diagnostics and evidence | R1/R2 | P1 |
| Dataframe and generic iterable paths materialize unbounded inputs | R1 | P1 |
| Malformed target schemas raise and empty targets are ambiguous | R5 | P1 |
| Source/target matrix and durable definition integration are incomplete | R6 | P1 |
| CSV numeric parsing loses Decimal precision | R1 | P2 |
| Decimal canonicalization changes existing fingerprints | R0 | P1 |
| Absolute file paths enter serialized identities | R0/R5 | P2 |
| Target and compatibility models lack a stable wire surface | R0/R5 | P2 |

## 2. Non-negotiable invariants

- An observed source type is never relabeled solely because a target requests
  another type. The result must distinguish observation, hypothesis, explicit
  cast, and validated compatibility.
- A target constraint may travel upstream only across a declared, sound lineage
  rule. Unknown, lossy, ambiguous, and native operations stop propagation with
  a diagnostic.
- A schema transfer cannot create duplicate field names or silently drop a
  requested field. Collisions and missing references are explicit findings.
- All source adapters apply row, byte, and cooperative time budgets before
  materializing data. Default limits are bounded even when callers omit them.
- Serialized observations contain schema, fingerprints, counts, limits,
  parser/provider metadata, revisions, and diagnostics only. They contain no
  rows, values, credentials, absolute paths, or arbitrary provider objects.
- Existing typed pipelines retain their current fingerprints. Any intentional
  logical-type change requires a versioned migration and compatibility test.

## 3. Delivery sequence

### R0 — Compatibility and wire contract

Freeze the remediation contract before changing inference behavior.

Work:

- Add versioned `to_dict`/`from_dict` or equivalent wire models for
  `InferenceObservation`, `TargetObservation`, `FieldConstraint`, and
  `WriteCompatibility`.
- Define redaction rules for identities, paths, parser options, provider
  metadata, diagnostics, and field metadata.
- Keep the historical `Decimal` normalization/fingerprint behavior for typed
  contracts, or introduce an explicit schema-version migration before changing
  it. Inferred record schemas may retain Decimal precision without silently
  changing existing contract fingerprints.
- Add stable diagnostic entries for malformed schemas, lineage collisions,
  missing lineage, unbounded materialization, and stale target revisions.
- Add compatibility fixtures for old serialized inference results and old
  Decimal fingerprints.

Gate R0: wire payloads are closed and row-free; path and secret scans pass;
legacy fingerprints round-trip unchanged; diagnostic codes are inventoried.

### R1 — Bounded source materialization and scalar fidelity

Make every source path bounded before conversion and preserve numeric meaning.

Work:

- Introduce one effective-limit helper that supplies default limits when the
  caller omits them.
- Apply the helper before `pandas.to_dict`, `polars.to_dicts`, provider
  `to_dicts`, and generic iterable conversion. Never retry an unbounded source
  after a bounded conversion fails.
- Keep replay semantics explicit for one-shot iterables; do not claim replay
  for dataframe/file adapters that cannot preserve the remainder.
- Parse CSV decimal-looking values as Decimal or as a documented provisional
  numeric type without converting through float. Preserve date-only values as
  dates.
- Record parser options, limits, sampling state, and limitations in evidence.

Tests:

- bounded pandas/polars fakes that fail if full conversion occurs;
- infinite and very large iterables;
- byte/time/row limits before materialization;
- large Decimal CSV values and mixed integer/Decimal promotion;
- replay prefix and remainder behavior.

Gate R1: no supported source can materialize beyond its declared bounds before
inference, and precision regression tests pass.

### R2 — Sound forward transfer and diagnostic accumulation

Make transformations deterministic, collision-safe, and evidence-preserving.

Work:

- Add field lineage to forward transfer results, including source path,
  operation, alias, nullability, and invertibility.
- Detect rename/project/with-field collisions and missing field references.
  Return an unknown field plus a stable diagnostic rather than duplicate or
  silently omitted fields.
- Preserve source diagnostics, evidence, provenance, and sampling state when a
  data-first transformation creates a new dataset.
- Preserve target inspection diagnostics when a target schema is available.
- Make the local evaluator return an explicit unsupported result with a
  diagnostic when it cannot evaluate an expression; never turn an unsupported
  operation into an unreported `None`.
- Add deterministic duplicate-alias policy for model generation and schema
  transfer.

Tests:

- rename into an existing field;
- project a missing field;
- duplicate aliases in `select` and `withColumn`;
- source mixed-type and hint diagnostics after every transformation;
- unsupported local arithmetic/function evaluation;
- target inspector warnings retained in the final result.

Gate R2: every output field has one unambiguous identity or an explicit
unknown/conflict diagnostic, and transformation results retain prior evidence.

### R3 — Forward lineage model

Replace name-only transfer with a qualified lineage graph.

Work:

- Define lineage nodes for direct references, rename, projection, cast,
  arithmetic, scalar calls, filter, sort, limit, distinct, union, join,
  aggregate, and explode.
- Mark each rule as pass-through, widening, narrowing, lossy, or non-invertible.
- Carry nullability, requiredness, and target field aliases through the graph.
- Stop propagation at unsupported/native operations and emit
  `INFER_BACKWARD_UNSUPPORTED` with the operation path.
- Add graph serialization that contains no values or rows.

Tests:

- golden lineage for direct projection/rename/cast;
- arithmetic and scalar-call barriers;
- union alignment and join collision/nullability cases;
- aggregate and explode unknown boundaries;
- deterministic graph fingerprints.

Gate R3: forward schemas and lineage are equivalent across the qualified local,
Pandas, Polars, SQL, PySpark, DataFusion, and DuckDB fixtures where the
operation is supported.

### R4 — Target-guided backward solver

Implement the actual target-to-source constraint propagation promised by the
roadmap.

Work:

1. Inspect and pin the target observation, including existence, revision,
   fields, nullability, keys, defaults, partitions, and write mode.
2. Map target fields to output lineage nodes explicitly.
3. Seed field constraints with target requirements and compatibility mode.
4. Walk only sound inverse rules backward through the lineage graph.
5. Merge constraints by branch, retaining conflicts instead of picking one.
6. Re-run forward inference with validated parse/cast policies.
7. Stop at a bounded fixed point or emit
   `INFER_BACKWARD_NONCONVERGENT`.
8. Produce a reviewable explanation and runtime validation obligations.

Required examples:

- CSV string to target integer through a direct projection;
- string plus integer arithmetic where no sound inverse exists;
- explicit cast barriers;
- invalid numeric values in retained and replayed rows;
- nullable source to non-null target;
- two targets with conflicting constraints;
- target revision changed between inspection and compatibility check.

Gate R4: the solver never relabels observed source evidence, and every
backfilled type is labeled as observed, constrained, converted, conditional, or
conflicting.

### R5 — Target inspection and write compatibility

Make target state explicit and fail closed.

Work:

- Normalize malformed provider responses into diagnostics instead of raising.
- Distinguish absent, unknown, present-empty, and present-with-schema states.
- Preserve inspector diagnostics and provider limitations.
- Add target identity, revision/snapshot, keys, defaults, generated columns,
  partitions, and provider capabilities.
- Make compatibility mode-specific for append, overwrite, merge/upsert, and
  partition replacement.
- Validate all required target fields and runtime casts according to the mode.
- Add explicit create proposals for absent targets; never imply creation from a
  schema observation.

Tests:

- malformed, denied, inaccessible, stale, empty, absent, and concurrently
  created targets;
- existing CSV/JSON/memory targets;
- fake SQL/DuckDB and Parquet metadata inspectors;
- each advertised write mode and unsupported mode;
- all-values conversion obligations and failure reporting.

Gate R5: target observations are serializable, read-only, revision-aware, and
compatibility checks fail closed.

### R6 — Source matrix and durable definition integration

Complete the qualified source/target matrix and connect inference to normal
ETLantic authoring.

Work:

- Add metadata-first adapters for local records, Pandas, Polars, PySpark,
  DataFusion, SQL/DuckDB, first-party storage/connectors, Parquet, and schema
  documents, keeping optional imports out of core.
- Add capability matrix data and adapter conformance fixtures.
- Build source/transform/target definitions through the existing public
  authoring builders.
- Attach row-free source, lineage, target, and solver observations to
  `PipelineDefinition` metadata only after validation and binding.
- Add missing-target output proposals requiring explicit create intent.
- Preserve explicit class-authored pipeline fingerprints.

Gate R6: a data-first walkthrough validates, plans, and generates through the
normal public CLI/SDK path without embedding rows or provider secrets.

### R7 — Security, compatibility, and evidence campaign

Run the release campaign after implementation slices are complete.

Work:

- Scan every plan, report, schema history, wire payload, and evidence artifact
  for rows, values, secrets, absolute paths, and arbitrary provider objects.
- Run property tests for promotion, Decimal precision, replay, limits,
  fingerprints, lineage, and solver convergence.
- Run optional dependency import and engine differential matrices.
- Run race tests for target appearance, revision changes, and concurrent writes.
- Regenerate machine-readable inference evidence with package versions,
  fixture digests, confidence, limitations, and unsupported cases.
- Update the 0.55 capability claim only after every required gate passes.

Gate R7: full regression, focused inference, documentation, security, matrix,
and evidence checks pass; the plan status can then move from planned to
qualified.

## 4. Dependency and merge order

1. R0 contract and compatibility fixtures.
2. R1 bounded sources and scalar fidelity.
3. R2 transfer safety and diagnostic accumulation.
4. R3 lineage graph.
5. R4 backward solver.
6. R5 target modes and revision-aware compatibility.
7. R6 source matrix and durable definitions.
8. R7 security, evidence, and release documentation.

Each slice must leave the existing suite passing, include focused regression
tests, and pass `git diff --check`. Do not expose a new public capability or
change `plan_status` until R7 is complete.

## 5. Definition of done

The remediation is complete when:

- transformed target constraints reach prior models only through sound lineage;
- collisions, missing fields, unsupported evaluation, and malformed provider
  schemas fail closed;
- diagnostics and evidence survive every data-first transformation;
- all sources are bounded before materialization;
- Decimal precision and existing fingerprints are protected by compatibility
  tests;
- target states, revisions, modes, and obligations are explicit and
  serializable;
- normal ETLantic definition/validate/plan/generate flows work end to end; and
- security, optional-dependency, differential, documentation, and full-suite
  evidence are reproducible.
