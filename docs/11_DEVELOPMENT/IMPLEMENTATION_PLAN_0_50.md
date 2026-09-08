---
title: ETLantic 0.50 Implementation Plan
description: Implementation-grade plan for baseline portable execution across seven first-party engines and pushdown conformance.
plan_status: current
plan_last_reviewed: 0.49.0
---

# ETLantic 0.50 Implementation Plan

Phase 0.50 makes ETLantic's baseline portable transformation syntax executable
across Local, Polars, Pandas, SQL, PySpark, DataFusion, and DuckDB. It closes
the gap between portable authoring, compiler capability claims, runtime
dispatch, pushdown behavior, and reproducible release evidence. The full
DuckDB package is delivered by phase 0.49, then must pass this phase's same
baseline and pushdown contract before it is a qualified seventh engine.

The phase is governed by
[epic #102](https://github.com/eddiethedean/etlantic/issues/102), the
[0.50 milestone](https://github.com/eddiethedean/etlantic/milestone/2), and the
[0.50 exit gate](EXIT_GATE_0_50.md).

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
| SQL | Baseline analysis/compile plus selected-engine routing | `portable_compiled` dispatch shipped in 0.49 | Partial direct-compiler and generic-routing evidence | Complete SQLite/PostgreSQL runtime qualification and prove typed-handle preservation |
| PySpark | Baseline and advanced claims | Runs with `pyspark` identity | Partial real-JVM coverage | Full real-Spark gate and canonical alias resolution |
| DataFusion | Provisional compiler/dataframe implementation | Partial baseline execution | Contract artifacts only | Complete native baseline and qualification evidence |
| DuckDB | Seven-action/four-function 0.49 package subset | Runs through the optional native package | Reproducible 0.49 package evidence and 0.50 handoff | Complete the frozen baseline and pass independent pushdown qualification |

This table is a planning baseline, not an availability claim. The exit gate
replaces it with evidence produced from the release candidate.

## Phase-Entry Compatibility Locks

Phase 0.50 builds on the released 0.49 surfaces instead of redesigning them:

- `@Transformation.portable` continues to emit `dtcs.transform-plan/2`.
- `etlantic.transform-compiler/1` remains the plugin protocol. Requirement-level
  evidence is added through optional records and fields; no existing plugin is
  required to implement a new protocol method.
- `TransformSupportReport.supported` remains a compatibility summary. The
  normalized requirement findings become authoritative for 0.50 qualification
  and later adaptive eligibility.
- A legacy compiler with no requirement-level positive evidence remains
  structurally discoverable and inspectable, but its omissions normalize to
  `unknown`. It cannot satisfy a required portable requirement, claim
  `etlantic.portable-baseline/1`, or receive positive adaptive preference.
  Third-party distributions must repin to the 0.50 lockstep line and rerun the
  public conformance suite before restoring claims.
- The `etlantic.plan/1` reader remains compatible. Stored 0.49 plans that omit
  or fingerprint stale evidence are readable for inspection but fail runtime
  preflight before I/O and must be replanned. Newly generated 0.50 `/1` bytes
  may add evidence through existing extension points; no shipped field changes
  meaning. An incompatible plan or compiler shape requires a new protocol major
  and is outside this phase.
- Production discovery still authorizes a plugin from
  `Profile.plugin_allowlist` before import. None of the new analysis paths may
  resolve secrets, read rows, connect to a backend, or import an unapproved
  plugin.

## Frozen Target Contract

The phase publishes `etlantic.portable-baseline/1` in
`portable_baseline_contract_0_50.json`. That manifest, rather than the union or
intersection of installed compiler claims, is the authority for the common
baseline.

### Baseline inventory

| Dimension | Frozen content |
|---|---|
| Plan/profile identity | `dtcs.transform-plan/2`; `dtcs:profile/portable-relational-kernel/1`; `dtcs:profile/portable-relational/1` |
| Kernel actions (5) | `filter`, `project`, `with_fields`, `drop_fields`, `rename_fields` |
| Relational actions (7) | `join`, `union`, `aggregate`, `sort`, `distinct`, `deduplicate`, `limit` |
| Scalar functions (23) | `lower`, `upper`, `concat`, `concat_ws`, `substr`, `replace`, `length`, `contains`, `starts_with`, `ends_with`, `case_when`, `coalesce`, `if_null`, `null_if`, `is_null`, `abs`, `round`, `floor`, `ceil`, `power`, `sqrt`, `least`, `greatest` |
| Aggregate functions (7) | `sum`, `average`, `min`, `max`, `count`, `count_all`, `count_distinct` |
| Operators | comparison `eq`, `not_eq`, `lt`, `lte`, `gt`, `gte`; null-safe `null_safe_eq`; boolean `and`, `or`, `not`; arithmetic `add`, `subtract`, `multiply`, `divide`, `modulo`, `negate`; membership `in` |
| Literal values | `null`, `boolean`, `integer`, `decimal`, and UTF-8 `string`; `missing` and `invalid` remain distinct semantic states |
| Join/collision behavior | `inner`, `left`, `right`, `full`, `semi`, `anti`, and explicit `cross`; collision policy `fail` only; `outer` is a normalized alias of `full`, not an eighth semantic mode |
| Union behavior | `byName` and `byPosition`, with manifest-declared missing-field and duplicate policies |
| Execution behavior | Each engine must satisfy its declared eager/lazy row; the phase does not claim one shared physical evaluation strategy |

All function names above are `dtcs:` identifiers in the artifact. Membership
is a governed operator requirement even though the current authoring IR emits
it as the `dtcs:in` call. Requirement normalization must produce one canonical
membership requirement rather than double-counting the call and operator.

The manifest also freezes function arity, parameter/literal constraints,
aggregate empty-input results, numeric promotion and overflow behavior, divide
and modulo errors, string/Unicode behavior, null propagation, missing/invalid
rejection or routing, sort direction and null placement, deterministic versus
explicitly nondeterministic limit/deduplication, multiple-input identity,
field-collision behavior, and contract-shaped output validation. A fixture ID
is attached to every leaf requirement.

`portable-relational-kernel/2` and `portable-relational/2` are accepted only as
metadata aliases where the manifest proves them semantically identical to the
listed `/1` baseline content. Alias normalization emits a stable finding and
never grants a `/2`-only operation. If that proof cannot be frozen in increment
I0, the alias is removed with migration guidance instead of being guessed from
an engine claim.

A compiler must advertise every governed dimension truthfully and must not
promote a partial implementation into a profile-wide claim. Unknown, omitted,
unsupported, or currently unavailable required behavior fails during
validation or planning with a stable diagnostic and never triggers a silent
native fallback.

### Pushdown conformance contract

Pushdown is a requirement-level claim, not an engine-wide performance label.
For every applicable logical action and expression, each engine must report a
bounded pushdown finding at every declared source, relational, and sink
boundary:

- `pushed_exact` means the backend executes the required semantics at that
  boundary without collecting rows into the host runtime;
- `pushed_with_lowering` names a deterministic, versioned rewrite and records
  its proof, conditions, and physical effects;
- `not_pushed` records an explicit, semantics-preserving host-side execution
  boundary; it is eligible only when pushdown is `preferred` or
  `informational`, never when the requirement is `required`;
- `unsupported`, `unavailable`, and `unknown` fail closed for a required
  pushdown requirement; and
- every finding identifies the boundary, action/expression, target identity,
  explain evidence, and whether collection, transfer, materialization, or
  lost fusion occurred.

Pushdown-result coverage is required for all seven engines; universal external
source/sink pushdown is not. Applicability and obligation are frozen by the
manifest rather than inferred from the engine name:

| Target/boundary | 0.50 obligation |
|---|---|
| Local, Pandas, or Polars with only host-owned inputs/outputs | Boundary is explicitly `not_applicable`; native/host execution is still proved by baseline conformance |
| SQL SQLite/PostgreSQL relation path | Preserving a typed relation/query handle and bound parameters through every eligible relational action is `required`; the declared fetch/materialization boundary ends pushdown |
| DuckDB relation path | Native relation lowering and the declared source-to-relational chain are `required`; sink pushdown is required only for a sink capability qualified by the manifest |
| PySpark or DataFusion native logical plan | Native expression lowering with no Python/Pandas UDF or host-row fallback is `required`; connector-specific source/sink pushdown is `not_applicable` unless that connector row is separately declared |
| Any optional connector or sink without a qualified row | `not_applicable` or `unknown`, never optimistic `pushed_exact`; it cannot satisfy a required placement |

`not_applicable` is an applicability result, not a sixth support state and not a
pushdown success. It carries a stable reason and boundary identity but does not
enter the support denominator. `not_pushed` applies only where the boundary is
applicable and host execution actually occurs.

An engine cannot claim pushdown from package installation, generic compiler
success, or an opaque backend plan. Conformance fixtures must prove accepted
and rejected pushdown, no silent host fallback, and equivalent results at the
declared boundary. These findings are part of the immutable 0.50 evidence and
are consumed by 0.51 adaptive placement and objective scoring.

## Requirement And Support Contract

Phase 0.50 replaces engine-wide support booleans with two independent axes plus
an explicit applicability decision. A requirement has an obligation level; a
compiler or execution target reports an evidence-backed support state for that
exact requirement only when the manifest says it is applicable.

| Axis | Values | Meaning |
|---|---|---|
| Applicability | `applicable`, `not_applicable` | Whether the frozen target/boundary rule requires a support finding; `not_applicable` requires a stable manifest rule and reason |
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

### Canonical records and fingerprints

The public schema is `etlantic.portable-requirement-support/1`. Requirement IDs
use the stable form
`<vocabulary>@<version>/<scope>/<semantic-id>#<canonical-path>`; paths address
logical plan or contract structure and never contain user values. The schema
contains separate `requirements`, `findings`, and `evidence` arrays plus a
typed `target` object. Each applicable requirement has exactly one finding per
complete target. A
duplicate, missing, or unrecognized record is a schema error rather than an
implicit support result.

Canonical JSON uses sorted object keys, manifest-defined array order, UTF-8,
and no timestamps in the hashed payload. The SHA-256 fingerprint covers the
baseline-manifest digest, normalized requirements, findings, resolved static
conditions, compiler/engine/protocol/package identities, lowering identities,
and evidence digests. Repository commit, command, timestamp, host details, and
absolute paths are provenance outside the semantic fingerprint.

The public implementation inherits the existing portable-definition ceilings
and adds these fail-closed report limits:

| Limit | 0.50 default | Behavior at the limit |
|---|---:|---|
| Normalized requirements per definition | 100,000 | Reject planning; never drop a requirement |
| Findings per target | 100,000 | Reject an incomplete target report |
| Serialized support report | 8 MiB | Emit a stable size diagnostic; no eligibility result |
| Conditions or physical effects per finding | 64 | Reject the finding as invalid evidence |
| Reason text per finding | 1,024 UTF-8 characters | Reject plugin evidence rather than truncate hashed meaning |

Display surfaces may emit a bounded summary with omitted counts, but planning,
qualification, and fingerprinting operate only on the complete validated
record set. Engine-provided free-form metadata is never copied into the schema;
only typed, allowlisted fields are accepted.

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
**baseline-qualified for 0.50 only when every required item in the frozen
manifest and pushdown contract passes conformance**. Partial support may be
documented or used by a later adaptive planner; it cannot satisfy or shrink the
seven-engine release gate. DuckDB's phase 0.49 manifest is a prerequisite, not
a qualification exemption.

## Phase 0.51 Adaptive-Planning Handoff

Phase 0.50 owns the portable semantic vocabulary and produces the immutable
requirement/support evidence consumed by phase 0.51. Phase 0.51 must not infer
node eligibility from an engine name, package installation, or the aggregate
0.50 qualification label.

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

| ID | Workstream | Deliverables | Completion evidence | Issues |
|---|---|---|---|---|
| 050-C | Contract and capability vocabulary | Normative manifest; obligation/support axes; requirement-level findings; lowering proofs; deterministic fail-closed matching | Schema round trips, legacy `/1` goldens, alias decisions, seeded canonicalization/fingerprint tests, and limit failures | [story #103](https://github.com/eddiethedean/etlantic/issues/103), [task #106](https://github.com/eddiethedean/etlantic/issues/106) |
| 050-T | Public conformance | Mandatory claim-to-fixture coverage, truthful partial/conditional/negative claims, and public third-party runner | Claim/fixture bijection, all obligation/support/pushdown states, mutation tests for omitted dimensions, and public fake-compiler suite | [task #107](https://github.com/eddiethedean/etlantic/issues/107) |
| 050-L | Local | Dependency-free baseline interpreter/compiler over Local artifacts | Core-only clean environment, full manifest/differential pass, explicit host-boundary applicability, and no optional imports | [#96](https://github.com/eddiethedean/etlantic/issues/96) |
| 050-P | Polars | Complete eager/lazy baseline qualification; advanced claims remain separate | Full baseline in both modes, lazy-plan evidence before collection, normalized dtype/null results, and advanced-claim isolation | [#97](https://github.com/eddiethedean/etlantic/issues/97) |
| 050-D | Pandas | Complete eager, index-neutral, dtype/null baseline qualification | Full eager baseline, index/randomized-label invariance, nullable dtype corpus, and explicit no-lazy claim | [#98](https://github.com/eddiethedean/etlantic/issues/98) |
| 050-Q | SQL | Typed `etlantic.sql/1` lowering through shipped dispatch, relation/query handle preservation, SQLite/PostgreSQL evidence | Both real dialect jobs, handle/parameter/fetch trace, raw-fragment rejection, transaction cleanup, and normalized differential pass | [#99](https://github.com/eddiethedean/etlantic/issues/99) |
| 050-S | PySpark | Complete real-JVM baseline qualification and `spark`/`pyspark` identity resolution | Real JVM matrix, Catalyst logical/physical plans, no Python/Pandas UDF nodes, alias authorization, and normalized results | [#100](https://github.com/eddiethedean/etlantic/issues/100) |
| 050-F | DataFusion | Native compiler/runtime implementation, exact capabilities, and baseline graduation | Real DataFusion/Arrow execution, structured negative analysis, native logical plan, Arrow ownership/boundary checks, and isolated install | [#101](https://github.com/eddiethedean/etlantic/issues/101) |
| 050-U | DuckDB | Consume the 0.49 package, qualify the seventh engine, and prove the source/relational/sink pushdown contract | Full manifest pass, relation/explain trace, accepted/rejected boundary matrix, evidence-drift rejection, and 0.49 security regression | [task #118](https://github.com/eddiethedean/etlantic/issues/118), [package epic #110](https://github.com/eddiethedean/etlantic/issues/110) |
| 050-X | Cross-engine proof | Canonical authored pipeline, normalized differential corpus, partial-support negatives, isolated install/CI matrix, and 0.51 handoff fixture | 7/7 immutable artifact set plus partial-target, graph-invalid, registration-order, and evidence-drift campaigns | [story #105](https://github.com/eddiethedean/etlantic/issues/105), [task #108](https://github.com/eddiethedean/etlantic/issues/108) |
| 050-R | Release and migration | Requirement-level generated matrix, 0.51 consumption guidance, examples, evidence ledger, and go/no-go decision | Executed example, docs/link checks, artifact-index verification, zero open critical/high findings, and approved decision | [task #109](https://github.com/eddiethedean/etlantic/issues/109) |

Engine implementation work is grouped under
[story #104](https://github.com/eddiethedean/etlantic/issues/104).

## Task Ledger

GitHub sub-issue relationships remain the operational source of truth. This
ledger fixes phase-plan traceability without copying task acceptance criteria.

| Story | Tasks |
|---|---|
| [#103](https://github.com/eddiethedean/etlantic/issues/103) — contract and conformance | [#106](https://github.com/eddiethedean/etlantic/issues/106), [#107](https://github.com/eddiethedean/etlantic/issues/107) |
| [#104](https://github.com/eddiethedean/etlantic/issues/104) — first-party engines | [#96](https://github.com/eddiethedean/etlantic/issues/96), [#97](https://github.com/eddiethedean/etlantic/issues/97), [#98](https://github.com/eddiethedean/etlantic/issues/98), [#99](https://github.com/eddiethedean/etlantic/issues/99), [#100](https://github.com/eddiethedean/etlantic/issues/100), [#101](https://github.com/eddiethedean/etlantic/issues/101), [#118](https://github.com/eddiethedean/etlantic/issues/118) |
| [#105](https://github.com/eddiethedean/etlantic/issues/105) — cross-engine proof and release | [#108](https://github.com/eddiethedean/etlantic/issues/108), [#109](https://github.com/eddiethedean/etlantic/issues/109) |

## Delivery Increments

Each increment is independently mergeable. Incomplete increments may expose
experimental records or tooling, but cannot advertise a later availability
claim.

| Increment | Task spine | Merge condition | Public state after merge |
|---|---|---|---|
| **I0 — contract freeze** | #106 | Baseline, alias, applicability, support, pushdown, lowering, reason-code, budget, fingerprint, and artifact schemas are accepted; `/1` reader and fail-closed 0.49-plan compatibility fixtures pass | Existing plan documents remain inspectable; stale or evidence-free plans require replanning; no engine is qualified |
| **I1 — conformance authority** | #107 | Public `etlantic.testing` runner proves complete claim-to-fixture bijection, all positive/negative states, deterministic serialization, bounds, and third-party partial claims | Engines may emit requirement-level reports; aggregate `supported` remains compatibility-only |
| **I2 — engine closure** | #96–#101, #118 | Each engine passes its isolated manifest subset, execution-mode row, pushdown-applicability row, dependency boundary, and security campaign | Individual rows may be evidence-complete, but no shared seven-engine claim exists |
| **I3 — seven-engine proof** | #108 | One authored pipeline, full normalized corpus, and boundary matrix pass in real engine environments; the 0.51 handoff consumes only exact evidence | The release candidate may publish a generated provisional 7/7 matrix |
| **I4 — release decision** | #109 | Docs, examples, migration/rollback, evidence index, finding triage, and every exit-gate row pass review | Only the signed gate decision may mark the seven-engine baseline Available |

The task-level critical path is:

```text
#106 -> #107 -> (#96 | #97 | #98 | #99 | #100 | #101 | #118)
     -> #108 -> #109
```

Engine implementation may prototype against a draft I0 schema, but no engine
claim merges before I0 and its matching I1 fixtures. I2 tasks run in parallel;
I3 begins only after all seven evidence rows are complete. Documentation drafts
may start earlier, while #109 alone records the final decision.

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
- Local, Polars, Pandas, SQL, PySpark, DataFusion, and DuckDB each validate,
  plan, and execute a portable-only baseline pipeline under a require policy.
- The complete normalized corpus and pushdown fixtures produce equivalent
  observable results across all seven engines, with stable, documented normalization where physical types
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
- The phase 0.50 evidence artifact is sufficient for phase 0.51 to evaluate
  exact per-node requirements, lowering effects, and evidence drift without
  inferring support from an engine name or aggregate maturity label.
- Every row in [EXIT_GATE_0_50](EXIT_GATE_0_50.md) links reproducible evidence,
  and no critical/high correctness, compatibility, security, or data-loss
  finding remains open.

## Explicit Non-Goals

- Making every facade method or advanced
  [DTCS](../04_TRANSFORMATIONS/DTCS.md) profile portable across engines.
- Identical physical plans, dataframe types, execution latency, or memory use.
- Adaptive heterogeneous placement or physical DAG execution; that is phase
  0.51.
- Streaming, federated, remote-provider, or external-orchestrator execution.
- Silent conversion to native implementation bodies, Python/Pandas UDFs, raw
  SQL, or another engine.
- Adding Polars, Pandas, SQL-driver, PySpark, Arrow/DataFusion, or vendor
  dependencies to ETLantic core.

## Required Release Evidence

All machine-readable artifacts live under
`docs/11_DEVELOPMENT/evidence/portable_0_50/`. The frozen filenames and required
metadata are defined by [EXIT_GATE_0_50](EXIT_GATE_0_50.md). A single
`portable_evidence_index_0_50.json` records schema versions, relative artifact
paths, SHA-256 digests, generating commands, repository commit, environment
identities, and outcomes. CI rejects an absolute path, missing artifact, digest
mismatch, duplicate logical artifact, or evidence generated from another
commit.

`scripts/check_portable_0_50.py` is the release verifier. It regenerates or
checks the manifest, support matrix, claim coverage, isolated-engine reports,
canonical differential and pushdown results, adaptive handoff, dependency and
security campaigns, documentation matrix, and exit-gate completeness. It must
run after `etlantic validate TARGET --format json` and deterministic
`etlantic plan TARGET --format json` fixtures; engine jobs may add their native
test commands but may not bypass the common verifier.

## Evidence Ownership

| Evidence | Owner |
|---|---|
| Baseline manifest, aliases, requirement/support and pushdown schemas, fingerprint rules | #106 |
| Claim coverage, public conformance runner, negative states, report budgets | #107 |
| Local, Polars, Pandas, SQL, PySpark, DataFusion, DuckDB isolated reports | #96–#101, #118 respectively |
| Canonical 7/7 differential, pushdown matrix, dependency/security campaign, 0.51 handoff | #108 |
| Generated public matrix, migration/rollback, findings ledger, evidence index, final decision | #109 |

The exit gate is binary. Per-engine evidence may document a useful partial
implementation, but a missing or failing row cannot be waived by shrinking the
manifest, marking a fixture optional, substituting a fake backend, or relabeling
required pushdown as preferred after I0.
