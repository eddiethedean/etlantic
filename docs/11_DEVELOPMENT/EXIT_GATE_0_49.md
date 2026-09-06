# Exit Gate 0.49 — Baseline Portable Execution Across First-Party Engines

> **Status: Not started.** This document defines the evidence contract before
> implementation. It does not upgrade any current engine capability claim. The
> final decision is recorded by
> [task #109](https://github.com/eddiethedean/etlantic/issues/109).

See the [0.49 implementation plan](IMPLEMENTATION_PLAN_0_49.md),
[epic #102](https://github.com/eddiethedean/etlantic/issues/102), and
[0.49 milestone](https://github.com/eddiethedean/etlantic/milestone/2).

## Target Claim

| Surface | Target at gate | Entry state |
|---|---|---|
| Baseline manifest | Public, versioned, machine-readable authority | Overlapping compiler claims; no complete manifest |
| Requirement/support protocol | Public two-axis obligation and support model with requirement-level evidence | Aggregate support report is currently too coarse |
| Local | Baseline Available without optional dataframe/database dependencies | No portable compiler |
| Polars | Baseline Available for declared eager/lazy modes | Runs; public claim coverage incomplete |
| Pandas | Baseline Available for declared eager mode | Runs; public claim coverage incomplete |
| SQL | Baseline Available through normal runtime for SQLite and PostgreSQL | Direct compiler path exists; pipeline dispatch rejects portable SQL |
| PySpark | Baseline Available on real JVM Spark with canonical engine identity | Runs as `pyspark`; real-JVM coverage and alias behavior incomplete |
| DataFusion | Baseline Available through native expressions | Discoverable zero-capability stub |
| Advanced profiles | Engine-specific, separately claimed | Uneven by design |
| Native implementation bodies | Explicit escape hatch only | Available; must not become implicit fallback |
| Adaptive, streaming, remote, and federated execution | No 0.49 claim | Out of scope |

No engine row may be omitted from the phase decision. A failing row makes the
shared six-engine claim a no-go; documentation may still record independently
passing implementations without calling the phase complete.

## Quantified Exit Scorecard

| # | Measure | Required | Current | Owner |
|---|---|---:|---|---|
| 1 | Normative manifest freezes both profiles, 12 actions, shared functions, operators, modes, joins, unions, collisions, and semantic edge cases | Pass | **Not started** | #103, #106 |
| 2 | Every advertised baseline claim maps to a mandatory public fixture and every required baseline item is claimed | 100% | **Not started** | #107 |
| 3 | Requirement obligation (`required`, `preferred`, `informational`) and target support (`supported_exact`, `supported_with_lowering`, `unsupported`, `unavailable`, `unknown`) are independently represented and fingerprinted | Pass | **Not started** | #103, #106 |
| 4 | Required unknown, omitted, unsupported, unavailable, ambiguous, and unresolved-conditional requirements fail during validation/planning with stable diagnostics | Pass | **Not started** | #103, #106, #107 |
| 5 | Lowering-backed support records a stable lowering identity, resolved conditions, proof evidence, and physical effects; invalid or data-dependent conditions fail closed | Pass | **Not started** | #106, #107 |
| 6 | Local validates, plans, and runs the canonical portable-only pipeline with no optional engine dependency | Pass | **Not started** | #96 |
| 7 | Polars passes the complete baseline in both claimed eager/lazy modes | Pass | **Not started** | #97 |
| 8 | Pandas passes the complete baseline with index-neutral, explicit dtype/null behavior | Pass | **Not started** | #98 |
| 9 | SQLite and PostgreSQL run portable SQL through normal pipeline dispatch and preserve handles until declared boundaries | Pass | **Not started** | #99 |
| 10 | SQL parameters remain bound and portable syntax cannot introduce raw/trusted fragments | Pass | **Not started** | #99 |
| 11 | Real JVM PySpark passes the complete baseline without Python/Pandas UDF fallback | Pass | **Not started** | #100 |
| 12 | `spark` and `pyspark` resolve to one authorized identity, or the alias is removed with compatibility evidence | Pass | **Not started** | #100 |
| 13 | DataFusion analysis, native lowering, execution, and Arrow boundaries pass the complete baseline | Pass | **Not started** | #101 |
| 14 | Every engine emits truthful requirement-level evidence for supported, partial, unavailable, unknown, and rejected slices; only complete manifest coverage earns baseline qualification | Pass | **Not started** | #96–#108 |
| 15 | One unchanged authored pipeline validates, plans, and runs on all six engines | 6/6 | **Not started** | #108 |
| 16 | Normalized differential corpus agrees for nulls, empty input, Unicode, numerics, ordering, joins, unions, aggregation, and deduplication | 6/6 | **Not started** | #108 |
| 17 | The 0.49 evidence artifact drives a 0.50-style per-node eligibility fixture without engine-name or aggregate-qualification inference | Pass | **Not started** | #106–#109 |
| 18 | Required support failures eliminate candidates before preference scoring; preferred unknowns receive no positive benefit | Pass | **Not started** | #107, #108 |
| 19 | Every optional engine passes clean isolated install/import and core dependency-boundary checks | Pass | **Not started** | #96–#101, #108 |
| 20 | Plans, reports, diagnostics, examples, and evidence contain no source rows, executable objects, raw SQL escape hatches, or secrets | Pass | **Not started** | #106–#109 |
| 21 | Capability matrix is generated from or verified against machine-readable requirement-level release evidence | Pass | **Not started** | #108, #109 |
| 22 | Reference, migration, rollback, 0.50 handoff, example, and explicit non-claim documentation passes strict checks | Pass | **Not started** | #109 |
| 23 | No unresolved critical/high correctness, compatibility, security, or data-loss finding | 0 | **Not started** | #109 |
| 24 | Final evidence locations, commands, outcomes, approvers, limitations, and decision are recorded | Pass | **Not started** | #109 |

## Required Evidence Manifest

Filenames are frozen so CI and the final decision can validate completeness.
Each JSON artifact must include a schema/version, repository commit, command,
environment summary, result, and reproducible test links. Artifacts must be
bounded and contain no source rows or secrets.

| Artifact | Required content | Status |
|---|---|---|
| `portable_baseline_contract_0_49.json` | Normative profiles/actions/functions/operators/modes, semantic rules, obligation levels, and applicability | Planned |
| `portable_requirement_support_0_49.json` | Requirement-level support states, compiler/target identities, reason codes, evidence fingerprints, conditional/lowering proofs, and physical effects | Planned |
| `portable_claim_coverage_0_49.json` | Compiler claim-to-mandatory-fixture coverage with no orphan, missing, overstated, or falsely aggregate rows | Planned |
| `portable_local_conformance_0_49.json` | Dependency-free Local planning, execution, diagnostics, and dependency boundary | Planned |
| `portable_polars_conformance_0_49.json` | Complete baseline in every claimed eager/lazy mode | Planned |
| `portable_pandas_conformance_0_49.json` | Complete baseline with dtype, null, index, and eager semantics | Planned |
| `portable_sql_conformance_0_49.json` | SQLite/PostgreSQL runtime, handles, parameters, boundaries, dialect rejection | Planned |
| `portable_pyspark_conformance_0_49.json` | Real-JVM baseline, alias identity, Catalyst plan, no-UDF evidence | Planned |
| `portable_datafusion_conformance_0_49.json` | Native analysis/lowering/runtime and Arrow-boundary evidence | Planned |
| `portable_cross_engine_0_49.json` | Canonical pipeline plus normalized differential corpus across all engine rows | Planned |
| `portable_adaptive_handoff_0_49.json` | 0.50-style partial-engine per-node eligibility, hard-failure, preferred-unknown, lowering-effect, and drift fixtures | Planned |
| `portable_dependency_security_0_49.json` | Isolated installs, core dependency boundary, fail-closed and redaction scans | Planned |
| `FINDINGS_0_49.md` | Triaged findings with zero unresolved critical/high at decision time | Planned |
| `MIGRATION_0_48_TO_0_49.md` | Baseline contract, engine selection/aliases, native bodies, rollback | Planned |
| `WHATS_NEW_0_49.md` | Exact Available matrix and explicit advanced/non-engine claims | Planned |

## Canonical End-To-End Fixture

The same authored pipeline must run without engine-specific transformation
bodies:

```text
bounded source
  -> filter + projected/derived fields
  -> multi-input join
  -> grouped aggregate
  -> union + deterministic sort/deduplicate/limit
  -> contract validation
  -> normalized result
```

Separate focused fixtures cover every baseline function/operator, empty inputs,
all join and union modes, collisions, missing/invalid rejection, Unicode,
decimal/numeric boundaries, and declared materialization behavior. SQL fixtures
also record handle/fetch boundaries; PySpark records Catalyst plans; DataFusion
records native logical plans.

## Rollback Trigger And Procedure

Trigger rollback for any confirmed cross-engine semantic divergence, silent
native/engine fallback, SQL injection or early row fetch, Python UDF fallback in
the PySpark baseline, dependency leakage into core, nondeterministic result, or
secret/source-row leak.

1. Remove or downgrade the affected capability claim and fail closed for new
   plans; do not redirect work silently to another engine.
2. Invalidate cached plans whose selected compiler capability fingerprint has
   changed.
3. Preserve diagnostics and affected plan fingerprints without retaining source
   rows or secrets.
4. Restore the last passing compiler/runtime package combination or require an
   explicit native implementation body.
5. Update the published matrix and reopen the owning engine and cross-engine
   gate rows before restoring the claim.

## Go / No-Go

**Not decided.** #109 records the dated decision only after all 24 scorecard
rows link to passing evidence. Missing or skipped evidence, any engine below the
baseline, or any unresolved critical/high phase finding is a no-go for the
six-engine portable-baseline claim.

## Explicit Non-Claims

- No common advanced, window-frame, three-state, streaming, adaptive, remote,
  or federated syntax claim.
- No guarantee of identical physical types, plans, latency, memory use, or
  optimization across engines.
- No automatic fallback to native bodies, Python/Pandas UDFs, raw SQL, or a
  different engine.
- No maturity inheritance: one passing compiler, plugin, dialect, or fake does
  not qualify another.
