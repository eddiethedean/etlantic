---
title: ETLantic 0.49 Implementation Plan
description: Implementation-grade plan for baseline portable execution across every first-party engine.
plan_status: current
plan_last_reviewed: 0.48.0
---

# ETLantic 0.49 Implementation Plan

Phase 0.49 makes ETLantic's baseline portable transformation syntax executable
across every first-party engine: Local, Polars, Pandas, SQL, PySpark, and
DataFusion. It closes the gap between portable authoring, compiler capability
claims, runtime dispatch, and reproducible release evidence.

The phase is governed by
[epic #102](https://github.com/eddiethedean/etlantic/issues/102), the
[0.49 milestone](https://github.com/eddiethedean/etlantic/milestone/2), and the
[0.49 exit gate](EXIT_GATE_0_49.md).

## Outcome

An author can define a transformation only with `@Transformation.portable`,
select any qualified first-party engine through a Profile, and validate, plan,
and run the same baseline pipeline under
`portable_transform_policy="require"` without adding an engine-specific
implementation body.

The shared guarantee is deliberately the frozen baseline. Advanced profiles,
native escape hatches, physical execution strategies, and performance
characteristics remain engine-specific and separately claimed.

## Current Reality At Phase Entry

| Engine | Portable planning | Normal runtime | Baseline evidence at entry | Principal gap |
|---|---|---|---|---|
| Local | No portable compiler | Native callables only | None | Dependency-free compiler/interpreter |
| Polars | Baseline and advanced claims | Runs portable descriptors | Partial public coverage | Complete claim-to-fixture qualification |
| Pandas | Baseline claims | Runs portable descriptors | Partial public coverage | Exact eager/null/dtype/index qualification |
| SQL | Baseline compiler analysis/direct execution | Normal pipeline dispatch rejects portable SQL | Partial, row-backed compiler path | Typed SQL IR/runtime integration and handle preservation |
| PySpark | Baseline and advanced claims | Runs with `pyspark` identity | Partial real-JVM coverage | Full real-Spark gate and canonical alias resolution |
| DataFusion | Zero-capability stub | Not implemented | None | Native compiler and dataframe/runtime implementation |

This table is a planning baseline, not an availability claim. The exit gate
replaces it with evidence produced from the release candidate.

## Frozen Target Contract

The phase freezes one machine-readable baseline manifest covering:

- `dtcs:profile/portable-relational-kernel/1` and
  `dtcs:profile/portable-relational/1`;
- kernel actions `filter`, `project`, `with_fields`, `drop_fields`, and
  `rename_fields`;
- relational actions `join`, `union`, `aggregate`, `sort`, `distinct`,
  `deduplicate`, and `limit`;
- the shared scalar and aggregate functions named by the manifest;
- comparison, boolean, arithmetic, membership, and null-safe operators;
- join types, by-name/by-position union, fail-only collision handling, and
  declared eager/lazy modes; and
- normative null, missing/invalid, ordering, numeric, Unicode, empty-input,
  multiple-input, and contract-shaped-output behavior.

The manifest, not the union of engine implementations, defines the portable
baseline. A compiler must advertise every governed dimension truthfully and
must not promote a partial implementation into a profile-wide claim. Unknown,
omitted, unsupported, or currently unavailable required behavior fails during
validation or planning with a stable diagnostic and never triggers a silent
native fallback.

## Requirement And Support Contract

Phase 0.49 replaces engine-wide support booleans with two independent axes. A
requirement has an obligation level; a compiler or execution target reports an
evidence-backed support state for that exact requirement.

| Axis | Values | Meaning |
|---|---|---|
| Requirement obligation | `required`, `preferred`, `informational` | Whether failure makes a candidate invalid, affects a later placement preference, or is recorded only for inspection |
| Target support | `supported_exact`, `supported_with_lowering`, `unsupported`, `unavailable`, `unknown` | What the named compiler/target can prove for the requirement in the current version and environment |

`supported_exact` means the ordinary compiler path preserves the normative
semantics. `supported_with_lowering` is reserved for a named deterministic
compatibility rewrite or adapter; ordinary backend compilation is not by itself
a reason to use that state. A lowering-backed finding is valid only when it
records the lowering identifier/version, proof or conformance evidence,
statically resolved conditions, and observable physical consequences such as a
collection, transfer, materialization, or lost fusion opportunity.

`unsupported` means the implementation cannot preserve the requirement.
`unavailable` means support exists in principle but the current target lacks a
required dependency, version, configuration, or qualified runtime capability.
`unknown` means no trustworthy evidence is available. These states remain
distinct in diagnostics and generated capability matrices.

Every normalized requirement and support finding is immutable and bounded and
contains at least:

- stable requirement identifier and vocabulary version;
- scope and parameters, including expression or contract path where relevant;
- obligation and applicability;
- support state and stable reason code;
- compiler, implementation, engine, and relevant protocol/version identity;
- evidence reference and evidence fingerprint; and
- for conditional or lowered support, resolved conditions, lowering identity,
  proof reference, and declared physical effects.

Plans and analysis reports retain the requirement-level findings even when they
also expose a derived candidate summary. They never contain source rows,
resolved secrets, executable backend objects, or unbounded plugin diagnostics.

The eligibility rules are fail closed:

- every applicable `required` requirement must be `supported_exact` or have an
  approved `supported_with_lowering` proof whose conditions are resolved;
- `unsupported`, `unavailable`, or `unknown` on a required requirement rejects
  that compiler/target for the concrete definition before execution or I/O;
- a `preferred` requirement contributes a positive placement benefit only when
  supported by positive evidence; unknown is never treated as a favorable zero;
- informational requirements affect fingerprints and explanation but not
  eligibility; and
- conditions that depend on source values, live trial execution, or unresolved
  runtime state cannot establish planning-time support.

An engine may advertise and execute a truthful subset for definitions whose
complete required vectors fall inside that subset. It is nevertheless
**baseline-qualified for 0.49 only when every required item in the frozen
manifest passes conformance**. Partial support may be documented or used by a
later adaptive planner; it cannot satisfy or shrink the six-engine release gate.

## Phase 0.50 Adaptive-Planning Handoff

Phase 0.49 owns the portable semantic vocabulary and produces the immutable
requirement/support evidence consumed by phase 0.50. Phase 0.50 must not infer
node eligibility from an engine name, package installation, or the aggregate
0.49 qualification label.

For every logical node and complete placement target, the adaptive planner
re-evaluates the node's exact requirement vector and retains all findings. It
then applies the same model to connector behavior, directional interchange,
security and resource policy, region fusion, physical-unit kinds, retry and
publication semantics, and the `/2` runtime consumer. A node-valid assignment
is not graph-valid unless every affected edge, region, unit, and whole-DAG
requirement is also satisfied.

Required findings are hard feasibility constraints applied before locality,
pushdown, transfer, materialization, fusion, or target-priority scoring.
Approved lowering effects enter the candidate physical lowering and therefore
the existing graph objective; the planner does not invent a generic semantic
penalty for a proven-equivalent lowering. Preferred capabilities influence
ranking only through positive evidence.

The `/2` plan fingerprints the exact requirements, findings, compiler/target
versions, evidence, resolved conditions, and lowering identities used for
selection. Whole-DAG runtime preflight revalidates mutable availability and the
fingerprinted capability evidence before any read, resource acquisition,
staging, or mutation. Drift rejects the stored plan and requires replanning; it
never causes runtime re-placement. If no complete adaptive assignment exists,
only the independently validated, policy-permitted explicit `/1` fallback may
run.

## Workstreams And Issue Hierarchy

| ID | Workstream | Deliverables | Issues |
|---|---|---|---|
| 049-C | Contract and capability vocabulary | Normative manifest; obligation/support axes; requirement-level findings; lowering proofs; deterministic fail-closed matching | [story #103](https://github.com/eddiethedean/etlantic/issues/103), [task #106](https://github.com/eddiethedean/etlantic/issues/106) |
| 049-T | Public conformance | Mandatory claim-to-fixture coverage, truthful partial/conditional/negative claims, and public third-party runner | [task #107](https://github.com/eddiethedean/etlantic/issues/107) |
| 049-L | Local | Dependency-free baseline interpreter/compiler over Local artifacts | [#96](https://github.com/eddiethedean/etlantic/issues/96) |
| 049-P | Polars | Complete eager/lazy baseline qualification; advanced claims remain separate | [#97](https://github.com/eddiethedean/etlantic/issues/97) |
| 049-D | Pandas | Complete eager, index-neutral, dtype/null baseline qualification | [#98](https://github.com/eddiethedean/etlantic/issues/98) |
| 049-Q | SQL | Typed `etlantic.sql/1` lowering, normal runtime dispatch, relation/query handle preservation, SQLite/PostgreSQL evidence | [#99](https://github.com/eddiethedean/etlantic/issues/99) |
| 049-S | PySpark | Complete real-JVM baseline qualification and `spark`/`pyspark` identity resolution | [#100](https://github.com/eddiethedean/etlantic/issues/100) |
| 049-F | DataFusion | Native compiler/runtime implementation, exact capabilities, and baseline graduation | [#101](https://github.com/eddiethedean/etlantic/issues/101) |
| 049-X | Cross-engine proof | Canonical authored pipeline, normalized differential corpus, partial-support negatives, isolated install/CI matrix, and 0.50 handoff fixture | [story #105](https://github.com/eddiethedean/etlantic/issues/105), [task #108](https://github.com/eddiethedean/etlantic/issues/108) |
| 049-R | Release and migration | Requirement-level generated matrix, 0.50 consumption guidance, examples, evidence ledger, and go/no-go decision | [task #109](https://github.com/eddiethedean/etlantic/issues/109) |

Engine implementation work is grouped under
[story #104](https://github.com/eddiethedean/etlantic/issues/104).

## Delivery Sequence

1. Freeze the normative baseline manifest, obligation/support axes,
   requirement records, finding states, and lowering evidence before changing
   engine claims.
2. Make public conformance completeness mechanical: every advertised baseline
   claim must map to a mandatory fixture.
3. Implement the missing Local and DataFusion paths and the SQL runtime path in
   parallel with qualification of Polars, Pandas, and PySpark.
4. Run each engine in an isolated dependency environment and close all
   engine-specific semantic gaps without weakening the common baseline.
5. Run the same authored pipeline and normalized edge-case corpus across every
   engine, including real JVM Spark, SQLite, PostgreSQL, and DataFusion; also
   prove truthful partial, unavailable, unknown, and lowered-support outcomes.
6. Verify the requirement-level artifact can drive 0.50 per-node candidate
   eligibility without an engine-wide inference.
7. Generate or verify the published capability matrix from those artifacts,
   complete migration and rollback guidance, and record the gate decision.

## Exit Gates

- The baseline manifest is public, versioned, machine-readable, and the single
  authority for common syntax and semantics.
- Every baseline capability claim has mandatory public conformance coverage;
  CI rejects orphaned claims and missing required capabilities.
- Requirement obligations and target support states remain independent,
  deterministic, fingerprinted, and visible through public analysis reports.
- Required partial, unsupported, unavailable, unknown, conditional, and
  lowering-backed cases produce the specified eligibility and diagnostic
  outcomes; engine-wide qualification never hides a requirement-level failure.
- Local, Polars, Pandas, SQL, PySpark, and DataFusion each validate, plan, and
  execute a portable-only baseline pipeline under a require policy.
- The complete normalized corpus produces equivalent observable results across
  all six engines, with stable, documented normalization where physical types
  differ.
- SQL-to-SQL paths preserve typed relation/query handles and bound parameters
  until a declared materialization boundary; portable definitions cannot inject
  raw or trusted SQL fragments.
- PySpark's release evidence uses a real JVM session and contains no
  Python/Pandas UDF fallback; `spark` and `pyspark` resolve consistently or the
  unsupported alias is removed with migration guidance.
- DataFusion no longer advertises a compiler stub: analysis returns structured
  support reports and the claimed baseline lowers to native expressions.
- Unsupported profiles, actions, functions, operators, modes, and engine
  combinations fail before execution or external I/O without native fallback.
- Optional engine dependencies remain outside core and pass isolated clean
  install/import tests.
- Plans, reports, diagnostics, fixtures, and evidence contain no source rows,
  executable objects, raw SQL escape hatches, or secret values.
- Documentation states the exact common baseline and keeps all advanced,
  adaptive, remote, streaming, and performance claims separate.
- The phase 0.49 evidence artifact is sufficient for phase 0.50 to evaluate
  exact per-node requirements, lowering effects, and evidence drift without
  inferring support from an engine name or aggregate maturity label.
- Every row in [EXIT_GATE_0_49](EXIT_GATE_0_49.md) links reproducible evidence,
  and no critical/high correctness, compatibility, security, or data-loss
  finding remains open.

## Explicit Non-Goals

- Making every facade method or advanced
  [DTCS](../04_TRANSFORMATIONS/DTCS.md) profile portable across engines.
- Identical physical plans, dataframe types, execution latency, or memory use.
- Adaptive heterogeneous placement or physical DAG execution; that is phase
  0.50.
- Streaming, federated, remote-provider, or external-orchestrator execution.
- Silent conversion to native implementation bodies, Python/Pandas UDFs, raw
  SQL, or another engine.
- Adding Polars, Pandas, SQL-driver, PySpark, Arrow/DataFusion, or vendor
  dependencies to ETLantic core.

## Required Release Evidence

- Versioned baseline manifest and claim-to-fixture coverage report.
- Versioned requirement/support schema, lowering-proof records, and stable
  rejection taxonomy.
- Per-engine public conformance reports from isolated environments.
- Six-engine canonical pipeline and normalized differential corpus.
- Partial-support and phase 0.50 adaptive-handoff conformance report.
- SQL SQLite/PostgreSQL handle, parameter, and materialization-boundary report.
- Real-PySpark logical/physical-plan report proving no Python UDF fallback.
- DataFusion native-lowering and Arrow-boundary report.
- Dependency-boundary, security/redaction, and fail-closed diagnostic reports.
- Generated capability matrix, migration guide, runnable example, findings
  ledger, and signed go/no-go record.
