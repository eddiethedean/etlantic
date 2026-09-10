# Exit Gate 0.51 — Adaptive Heterogeneous Planning and Executable Physical DAGs

> **Status: Not started.** This document defines the evidence contract before
> implementation. It does not claim that adaptive planning or `/2` execution is
> currently available. The final decision is owned by
> [#95](https://github.com/eddiethedean/etlantic/issues/95).

See the [0.51 implementation plan](IMPLEMENTATION_PLAN_0_51.md),
[epic #30](https://github.com/eddiethedean/etlantic/issues/30), and
[0.51 milestone](https://github.com/eddiethedean/etlantic/milestone/1).

## Target Claim

| Surface | Target at gate | Current |
|---|---|---|
| Existing explicit profiles and canonical `etlantic.plan/1` | Available, unchanged | Existing behavior; 0.51 regression evidence pending |
| `StepRunReport.metadata` built-in engine keys | Namespaced writer output with warning-free 0.50 bare-key reads under `etlantic.run_report/1` | Migration evidence pending |
| Adaptive Profile policy and `etlantic.plan/2` authoring/inspection | Available for the frozen bounded contract | Not implemented |
| Local static-batch physical-DAG execution | Available only for qualified combinations | Not implemented |
| Local Python, Polars, and Pandas single-target adaptive plans | Available after per-row evidence | Not qualified |
| DuckDB single-target adaptive plans | Experimental candidate after the 0.50 seven-engine/pushdown gate and independent `/2` physical-DAG evidence | Not qualified |
| Polars → Pandas and Pandas → Polars | Available through directional `etlantic.interchange/1` Gate A evidence | Not qualified |
| DuckDB ↔ Local/Polars/Pandas | No availability claim until each directional handoff is independently qualified | Not qualified |
| Third-party placement claims | Public conformance protocol; maturity remains provider-owned | Not implemented |
| SQL, PySpark, DataFusion, remote warehouse combinations | No 0.51 adaptive availability claim | Out of target matrix |
| External compilation, control-plane, durable/federated `/2` execution | Reject before acceptance or external I/O | Rejection evidence pending |
| Streaming and runtime-expanded adaptive graphs | Reject with stable diagnostics | Rejection evidence pending |

The final gate may narrow the qualified matrix. It cannot widen it without the
same compatibility, trust, directional interchange, differential, cleanup, and
documentation evidence required of the initial rows.

## Quantified Exit Scorecard

| # | Measure | Required | Current | Owner |
|---|---|---:|---|---|
| 1 | ADR freezes Profile precedence, target identity, `/1`–`/2`, unit protocol, fallback, selection, bounds, and diagnostics | Pass | **Not started** | #41 |
| 2 | Explicit profiles retain canonical `/1` bytes, fingerprints, semantics, and reader behavior | Pass | **Not started** | #42–#44 |
| 3 | Unsupported old readers and all unqualified `/2` consumers reject before external I/O | Pass | **Not started** | #44, #90, #92, #94 |
| 4 | Production discovery authorizes before load across every applicable extension family | Pass | **Not started** | #45–#49, #78 |
| 5 | Every selected node has a complete, truthful, bounded target candidate set or stable rejection | Pass | **Not started** | #50–#54 |
| 6 | Solver matches the independent oracle and remains invariant under semantic-preserving permutations | Pass | **Not started** | #55–#59, #91, #93 |
| 7 | 256-node, 8-target, 2,048-record, 1,000,000-work-unit, 4-MiB explain, and 256-MiB memory limits enforce stable outcomes | Pass | **Not started** | #41, #57, #74, #77, #91 |
| 8 | Region identity and fusion preserve target, effect, retry, checkpoint, selection, security, validation, and publication boundaries | Pass | **Not started** | #60–#63 |
| 9 | All seven physical-unit kinds validate, round-trip, reject tampering, and remain secret/source-row free | Pass | **Not started** | #43, #64–#68, #93 |
| 10 | Whole-DAG admission validates every live dependency before read, acquisition, staging, or mutation | Pass | **Not started** | #90 |
| 11 | Local runtime schedules `/2` physical dependencies and never silently falls back to logical scheduling | Pass | **Not started** | #69–#73, #88–#89 |
| 12 | Partial selection is planned before placement; selection drift requires re-planning | Pass | **Not started** | #41, #65, #69, #73 |
| 13 | Retry, cancellation, timeout, cleanup, validation, and publication match the explicit baseline or fail earlier safely | Pass | **Not started** | #71–#73, #81, #89 |
| 14 | Explain/diff projections are deterministic, bounded, redacted, and consistent across Python, CLI, IDE, and notebook surfaces | Pass | **Not started** | #74–#77, #94 |
| 15 | Polars↔Pandas directional fixtures prove exact target regions, Arrow handoff, second-target dispatch, and publication | Pass | **Not started** | #79–#81 |
| 16 | Qualified single-target and cross-target combinations pass public conformance and differential campaigns | Pass | **Not started** | #78–#81 |
| 17 | Plans, evidence, diagnostics, explain artifacts, and reports contain no resolved secrets or source rows | Pass | **Not started** | #44, #68, #77, #82 |
| 18 | Concepts, operations, rollback, plugin, migration, reference, release, and executable-example documentation passes strict checks | Pass | **Not started** | #83–#87, #94 |
| 19 | Runtime writers emit only `etlantic.dataframe`, `etlantic.sql`, `etlantic.spark`, and `etlantic.spark_schema`; 0.50 bare aliases load warning-free, namespaced values win collisions, bare aliases are removed, and migration is deterministic and idempotent | Pass | **Not started** | #41, #69–#73, #83–#87, #94 |
| 20 | No unresolved critical/high security, correctness, compatibility, or data-loss finding | 0 | **Not started** | #82, #95 |
| 21 | Final matrix, weakest-link maturity, owners, residual risks, and rollback trigger are recorded | Pass | **Not started** | #95 |

## Required Evidence Manifest

Filenames are frozen so CI and the final decision can validate completeness.
Each JSON artifact must include schema/version, generated-at time, repository
commit, command, environment summary, result, and links to reproducible tests;
it must not contain secrets or source rows.

| Artifact | Required content | Status |
|---|---|---|
| `adaptive_wire_compatibility_0_51.json` | `/1` byte/fingerprint goldens; `/2` reader/writer/verify/JSON-Schema matrix | Planned |
| `runtime_metadata_namespace_compatibility_0_51.json` | Namespaced-only writer output; 0.50 fixtures for `dataframe`, `sql`, `spark`, and `spark_schema`; namespaced-wins collisions; warning-free deterministic/idempotent migration and reserialization | Planned |
| `adaptive_inventory_conformance_0_51.json` | Target inventory, authorize-before-load, directional pair, and unknown-evidence fixtures | Planned |
| `adaptive_solver_conformance_0_51.json` | Objective boundaries, oracle equality, permutation invariance, fallback, and replay seeds | Planned |
| `adaptive_resource_budget_0_51.json` | Limit-boundary cases, work units, peak planner memory, serialized explain size, and measured duration | Planned |
| `adaptive_physical_dag_conformance_0_51.json` | Seven unit kinds, topology, logical coverage, tamper rejection, and redaction | Planned |
| `adaptive_runtime_conformance_0_51.json` | Admission, dispatch, selection, retry, cancellation, cleanup, and publication | Planned |
| `adaptive_consumer_matrix_0_51.json` | Local, CLI, compile, control-plane, durable, federated, streaming, and expanded-graph outcomes | Planned |
| `adaptive_explain_identity_0_51.json` | Python/CLI/IDE/notebook parity, diff semantics, truncation, and redaction | Planned |
| `adaptive_security_matrix_0_51.json` | All applicable allowlists, tenant/residency/masking policy, and no-secret/source-row scan | Planned |
| `adaptive_e2e_0_51.json` | Fixed Polars↔Pandas topology, directional handoff, explicit differential, and publication receipts | Planned |
| `FINDINGS_0_51.md` | Triaged phase findings with zero unresolved critical/high at decision time | Planned |
| `MIGRATION_0_50_TO_0_51.md` | Opt-in profile migration, `/1`–`/2`, runtime-report metadata aliases and collision behavior, rollback, and consumer compatibility | Planned |
| `WHATS_NEW_0_51.md` | Exact Available matrix and explicit non-claims | Planned |

## Reference Topology

The primary end-to-end fixture is fixed before implementation:

```text
bounded source
  → predicate + projection on Polars target (proven pushdown/fusion)
  → one directional Arrow Gate A transfer
  → Pandas target transform
  → validation barrier
  → publication unit and receipt
```

The golden evidence records exact candidate decisions, target identities,
region membership, physical-unit kinds and dependencies, handoff descriptor,
logical attribution, output, validations, and publication receipt. A reverse
Pandas → Polars fixture independently proves that interchange direction is not
erased. Separate structural fixtures cover collection, durable materialization,
and reuse units.

## Rollback Trigger And Procedure

Trigger rollback for any confirmed semantic divergence, unsafe retry or
publication, admission after prior mutation, fingerprint nondeterminism,
unauthorized plugin/provider load, secret/source-row leak, or `/2` consumer that
silently follows the logical graph. Also trigger rollback if runtime-report
metadata migration loses a value, resolves an alias collision inconsistently,
or allows new writers to emit the retired bare built-in keys.

1. Disable new adaptive planning through documented configuration.
2. Stop accepting stored `/2` plans and invalidate adaptive plan caches.
3. Drain safe in-flight units; cancel and reconcile unknown or unsafe attempts.
4. Clean or retain staged artifacts according to recorded ownership/retention
   policy; never guess publication outcome.
5. Re-plan new work explicitly as `/1`; do not downgrade stored `/2` documents.
6. Record affected fingerprints, attempts, reconciliation evidence, and the
   condition required before re-enabling adaptive execution.

## Go / No-Go

**Not decided.** #95 records the dated decision only after every required row is
linked to passing evidence. Missing evidence, a skipped required row, or any
unresolved critical/high phase finding is a no-go. Experimental or unavailable
providers cannot inherit the maturity of a passing core planner or engine pair.

## Explicit Non-Claims

- No universal cost currency, statistics-aware join ordering, or performance
  recommendation without a separate benchmark gate.
- No adaptive streaming, runtime expansion, speculative execution, telemetry
  feedback, or runtime re-planning.
- No external-orchestrator compilation or remote/federated `/2` execution claim.
- No SQL, PySpark, DataFusion, GPU, or remote-warehouse adaptive availability
  merely because a plugin can execute explicitly.
- No trust granted by package installation, engine name, or another provider's
  conformance result.
