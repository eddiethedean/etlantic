# Exit Gate 0.46 — Streaming and Event-Driven Pipelines

> **Status: Not started — planning freeze.** ETLantic **0.45.0** remains the
> published line. Bounded dynamic control, stream semantics, record-error
> policy, and optional Kafka / schema-registry providers are **not Available**.
> See [IMPLEMENTATION_PLAN_0_46](IMPLEMENTATION_PLAN_0_46.md) and
> [ADR-022](adr/ADR-022-DYNAMIC-CONTROL-AND-STREAMING.md) (Proposed).

| Deliverable | Status |
|---|---|
| Planning: this exit gate / findings / ADR-022 | **In progress** (freeze) |
| What's New / migration (ship artifacts) | **Not started** |
| Dynamic control (046-D) | **Not started** |
| Stream model (046-M) | **Not started** |
| Change envelope (046-E) | **Not started** |
| State and checkpoints (046-S) | **Not started** |
| Snapshot handoff (046-H) | **Not started** |
| Kafka provider (046-K) | **Not started** |
| Record errors / DLQ (046-Q) | **Not started** |
| Schema registries (046-G) | **Not started** |
| Reliability and reporting (046-R) | **Not started** |
| Compatibility / operations (046-C) | **Not started** |
| Lockstep version 0.46.0 | **Not started** |

## Supported claim (target freeze)

From [IMPLEMENTATION_PLAN_0_46](IMPLEMENTATION_PLAN_0_46.md). Not Available
until Current is Met.

| Surface | Target | Notes |
|---|---|---|
| Bounded dynamic control types | **Supported** (core) | Explicit, serializable, bounded |
| Plan/report expansion identity | **Supported** (core) | Deterministic for declared input identity |
| Stream semantic model | **Supported** (core) | Fail closed if unprovable |
| Change-envelope metadata | **Supported** (core) | No event payloads |
| Record-error policy vocabulary | **Supported** (core) | Identifiers + bounded metadata |
| Checkpoint/offset identities | **Supported** (core) | Reuse 0.38/0.41 |
| In-memory fixtures | **Supported** (tests) | No live cluster |
| Kafka reference (`etlantic-kafka`) | **Experimental** | Optional package |
| Schema registry (`etlantic-schemaregistry`) | **Experimental** | Optional package |
| Live DLQ storage / redrive | **Experimental** | Provider-owned |
| Rescale / rolling-upgrade campaigns | **Experimental** | Ops evidence |

## Quantified exit scorecard

From [IMPLEMENTATION_PLAN_0_46](IMPLEMENTATION_PLAN_0_46.md):

| # | Measure | Required | Current |
|---|---|---:|---|
| 1 | 046-D dynamic control types, identity, bounds | Pass | **Not met** |
| 2 | 046-M stream semantic model + batch/stream fixtures | Pass | **Not met** |
| 3 | 046-E change-envelope metadata (no payloads) | Pass | **Not met** |
| 4 | 046-S checkpoint/offset identities reuse 0.38/0.41 | Pass | **Not met** |
| 5 | 046-H snapshot-to-stream handoff protocol | Pass | **Not met** |
| 6 | 046-K Kafka provider Experimental | Pass | **Not met** |
| 7 | 046-Q record-error policy + DLQ identity | Pass | **Not met** |
| 8 | 046-G schema-registry protocol Experimental | Pass | **Not met** |
| 9 | 046-R continuous reports: watermark, lag, backpressure | Pass | **Not met** |
| 10 | 046-C envelope/state migration + rolling upgrade | Pass | **Not met** |
| 11 | Optimizer cannot expand/stream-rewrite without new proof kinds | Pass | **Not met** |
| 12 | Production allowlists fail closed; no payload in artifacts | Pass | **Not met** |
| 13 | No unresolved P0 in [FINDINGS_0_46](FINDINGS_0_46.md) | 0 | **Not met** |
| 14 | Release record: supported vs experimental | Pass | **Not met** — this freeze |

## Evidence map

| Gate item | Evidence |
|---|---|
| Implementation plan | [IMPLEMENTATION_PLAN_0_46](IMPLEMENTATION_PLAN_0_46.md) |
| ADR | [ADR-022](adr/ADR-022-DYNAMIC-CONTROL-AND-STREAMING.md) (Proposed) |
| Findings | [FINDINGS_0_46](FINDINGS_0_46.md) |
| Conformance JSON | Planned at ship (not created in this freeze) |
| Migration | Planned `MIGRATION_0_45_TO_0_46` at ship |
| What's New | Planned `WHATS_NEW_0_46` at ship |
| In-memory fixtures / Kafka / registry tests | Not started |

## Go / no-go

**Not ready.** No scorecard row is Met. Do not bump package versions off
`0.45.0` and do not describe 0.46 as Available.

## Explicit non-claims

- No Kafka client or Confluent registry in core
- No universal stream cost model or cross-provider cost currency
- No remote execution federation (0.47)
- No AI-proposed optimizations or repairs (0.48)
- No event payloads, source rows, or secrets in plans, reports, diagnostics,
  audit, or fixtures
- No inference of control flow from arbitrary Python branching
- Optimization does not expand or stream-rewrite graphs until new proof kinds
  exist (default remains baseline `off`)
