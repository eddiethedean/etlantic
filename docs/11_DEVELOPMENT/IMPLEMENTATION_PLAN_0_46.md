---
title: ETLantic 0.46 Implementation Plan
description: Implementation-grade plan for bounded dynamic control flow, streaming, and event-driven pipelines.
plan_status: current
plan_last_reviewed: 0.45.0
---

# ETLantic 0.46 Implementation Plan

> **Status: Current — not started.** Planning freeze after ETLantic **0.45.0**.
> See [ADR-022](adr/ADR-022-DYNAMIC-CONTROL-AND-STREAMING.md) (Proposed) and
> [EXIT_GATE_0_46](EXIT_GATE_0_46.md). Do not describe 0.46 surfaces as
> Available. Implementation of map/reduce, streaming engines, DLQ storage, or
> schema-registry packages is **out of scope for this freeze**.

Phase 0.46 extends ETLantic's bounded state and reliability semantics to
runtime-expanded work and continuous event pipelines. It reuses the durable
state, idempotency, checkpoint, policy, and external-effect contracts from 0.38
and 0.41–0.42 instead of inventing separate dynamic or streaming control planes.

## Outcome

Pipelines can declare bounded runtime mapping/reduction, explicit conditional,
failure, and compensation branches, event-time, watermarks, triggers, state,
ordering, late-data handling, replay, change envelopes, record-error outcomes,
and schema-registry requirements. Providers can prove restart,
snapshot-to-stream handoff, dead-letter, redrive, and schema-compatibility
behavior; plans and reports expose expansion, branch, backpressure, lateness,
gaps, duplicates, rejected records, and capability limits.

## Prerequisites And Non-Goals

- Durable state-provider, lease/fencing, policy, and reliability contracts have
  closed their 0.41–0.43 gates. The 0.45 optimization SDK is shipped and remains
  advisory ([ADR-021](adr/ADR-021-OPTIMIZER-PASS-PROTOCOL.md)).
- Batch and stream paths share logical contracts, identity, state provenance, and
  reporting; provider-specific engines remain optional packages.
- Dynamic control flow is explicit, serializable, bounded, and deterministic
  for a given declared input identity. Arbitrary Python branching, recursion,
  or unbounded runtime graph mutation is not a portable plan surface.
- Dead-letter payloads remain in authorized provider-owned storage. ETLantic
  plans, reports, diagnostics, and audit evidence contain identifiers and
  bounded metadata only.
- Unsupported event-time, ordering, retraction, transaction, or sink semantics
  fail capability validation. ETLantic does not emulate guarantees it cannot
  prove.

## Optional packages (named before implementation)

Per [FORWARD_IMPLEMENTATION_PLANS](FORWARD_IMPLEMENTATION_PLANS.md) Shared
Entry Criteria §3, extras are named now. None of these packages exist yet.

| Extra / PyPI name | Role | Target maturity |
|---|---|---|
| `etlantic-kafka` | Kafka reference source/sink, partitions, transactions, backpressure | **Experimental** |
| `etlantic-schemaregistry` | Confluent-compatible Avro/Protobuf/JSON Schema adapter | **Experimental** |

Core gains no Kafka, registry, or streaming-engine dependency. Live DLQ
storage stays provider-owned. Production discovery of these plugins fails
closed on `Profile.plugin_allowlist`; registry adapters additionally require
a non-empty `Profile.schema_registry_allowlist` (name → optional version pin)
under `security_mode="production"`.

## Supported vs Experimental target freeze

Claims only. Nothing below is Available until [EXIT_GATE_0_46](EXIT_GATE_0_46.md)
records Met evidence.

| Surface | Target | Notes |
|---|---|---|
| Bounded dynamic control types (map/reduce, conditional, failure, compensation) | **Supported** (core) | Explicit, serializable, bounded |
| Plan/report expansion identity and child fingerprints | **Supported** (core) | Deterministic for a declared input identity |
| Stream semantic model (event-time, watermark, trigger, lateness) | **Supported** (core) | Capability-closed if unprovable |
| Change-envelope **metadata** (op, position, order, schema identity) | **Supported** (core) | Never event payloads |
| Record-error **policy** vocabulary (fail/skip/quarantine/dead-letter) | **Supported** (core) | Identifiers + bounded metadata only |
| Checkpoint/offset **identities** | **Supported** (core) | Reuse 0.38/0.41 `cursor:` / `watermark:` / `partition:` |
| In-memory dynamic and stream fixtures | **Supported** (core tests) | No live cluster |
| Kafka reference provider | **Experimental** | `etlantic-kafka` |
| Confluent-compatible registry path | **Experimental** | `etlantic-schemaregistry` |
| Live DLQ storage and redrive against a real broker | **Experimental** | Provider-owned storage |
| Rescale / rolling-upgrade live campaigns | **Experimental** | Mixed-version ops evidence |

## 0.45 optimizer interaction

Optimization stays advisory. Default `plan` / `run` emit the baseline.
Until 0.46 ships new proof kinds for expansion and stream rewrite:

- a pass MUST NOT expand a graph, introduce stream-time semantics, or rewrite
  map/branch/compensation edges;
- missing proof kinds fail closed with a stable diagnostic (planned `PMOPT*`),
  never a silent flatten-to-DAG;
- `optimization_policy` default remains `off`.

Do not implement those proof kinds in this freeze.

## Fail-closed production trust

- Production `plugin_allowlist` covers Kafka and other streaming connectors.
- Production `schema_registry_allowlist` covers registry adapters.
- Plans, reports, diagnostics, audit, and fixtures never contain event
  payloads, source rows, or resolved secrets (FORWARD invariant).
- Capability gaps fail during planning; they do not degrade to append-only.

## Workstreams

| ID | Workstream | Deliverables | Completion evidence |
|---|---|---|---|
| 046-D | Dynamic control model | Typed map/reduce, conditional, failure, and compensation nodes/edges; stable child identity; declared decision evidence; expansion/depth/concurrency/payload/duration bounds | Deterministic expansion/branch corpus, bound-exhaustion tests, replay/cancel/resume matrix, and [DPCS](../05_PIPELINES/DPCS.md) round trips |
| 046-M | Stream model | Event-time, processing-time, watermark, trigger, state, late-data, replay, ordering, bounded/unbounded semantics | Model validation and batch/stream semantic fixtures |
| 046-E | Change envelope | Versioned insert/update/delete/tombstone/transaction/source-position/order/schema envelope | Compatibility, evolution, ordering, and malformed-envelope tests |
| 046-S | State and checkpoints | Offset/cursor, watermark, dedupe, state snapshot, atomic checkpoint/effect acknowledgement | Crash/restart matrix at every read, state, sink, and acknowledge boundary |
| 046-H | Snapshot handoff | Bounded snapshot plus stream cutover protocol with gap/overlap detection | Concurrent-change fixtures proving no loss, duplicate, or unreported gap |
| 046-K | Providers | Kafka reference provider and provider protocol for sources, sinks, partitions, transactions, and backpressure | Provider conformance, rebalance, partition-change, and outage tests |
| 046-Q | Record errors and dead letters | Fail/skip/quarantine/dead-letter policy; poison-record retry bounds; offset/checkpoint rules; external DLQ identity; retention; redrive provenance; reconciliation | Poison-record crash matrix, unauthorized-payload tests, offset invariants, redrive and retention evidence |
| 046-G | Schema registries | Provider protocol and Confluent-compatible reference for Avro/Protobuf/JSON Schema identity, lookup, compatibility, versioning, caching, and outage policy | Compatibility/evolution corpus, cache-staleness tests, outage matrix, and multi-format conformance |
| 046-R | Reliability and reporting | Continuous quality windows, late-data policy, lag/backpressure health, replay/repair reports | Golden reports and threshold transition tests |
| 046-C | Compatibility/operations | State/envelope migrations, rolling upgrade, rescale, retention, replay, recovery runbooks | Mixed-version and state-migration campaign |

## Quantified scorecard

All **Current** cells are **Not started**. Implementation must not begin until
this freeze is recorded and [EXIT_GATE_0_46](EXIT_GATE_0_46.md) exists.

| # | Measure | Required | Current |
|---|---|---:|---|
| 1 | 046-D dynamic control types, identity, bounds | Pass | **Not started** |
| 2 | 046-M stream semantic model + batch/stream fixtures | Pass | **Not started** |
| 3 | 046-E change-envelope metadata (no payloads) | Pass | **Not started** |
| 4 | 046-S checkpoint/offset identities reuse 0.38/0.41 | Pass | **Not started** |
| 5 | 046-H snapshot-to-stream handoff protocol | Pass | **Not started** |
| 6 | 046-K Kafka provider (`etlantic-kafka`) Experimental | Pass | **Not started** |
| 7 | 046-Q record-error policy + DLQ identity (no payloads) | Pass | **Not started** |
| 8 | 046-G schema-registry protocol (`etlantic-schemaregistry`) Experimental | Pass | **Not started** |
| 9 | 046-R continuous reports: watermark, lag, backpressure | Pass | **Not started** |
| 10 | 046-C envelope/state migration + rolling upgrade | Pass | **Not started** |
| 11 | Optimizer cannot expand/stream-rewrite without new proof kinds | Pass | **Not started** |
| 12 | Production allowlists fail closed; no payload in artifacts | Pass | **Not started** |
| 13 | No unresolved P0 in [FINDINGS_0_46](FINDINGS_0_46.md) | 0 | **Not started** |
| 14 | Claim freeze recorded on [EXIT_GATE_0_46](EXIT_GATE_0_46.md) | Pass | **Not started** |

## Delivery Sequence

1. Freeze dynamic-control, stream, record-error, and schema-registry semantics
   before provider code (this document + ADR-022).
2. Extend [DPCS](../05_PIPELINES/DPCS.md) and plan codecs, planner capability
   negotiation, and state-provider conformance for expansion and branch
   evidence.
3. Implement bounded dynamic fixtures and in-memory streaming fixtures, then
   the Kafka reference provider.
4. Add poison-record/DLQ handling and the Confluent-compatible registry path.
5. Add snapshot handoff, continuous reliability, and event-trigger
   backpressure.
6. Add rolling upgrade, rescale, replay, redrive, and migration behavior.
7. Execute expansion, branching, crash/restart, and batch/stream equivalence
   campaigns.

## Exit Gates

- Equivalent bounded batch and stream inputs produce equivalent declared results
  or a documented semantic difference rejected at plan time.
- Identical declared expansion input produces identical child identities,
  dependency closure, branch decisions, and report structure; expansion limits
  fail before unbounded work or state is accepted.
- Retry, replay, cancellation, and resume preserve dynamic map/reduce, failure,
  and compensation semantics; compilers that cannot preserve required control
  flow reject the plan before emitting runnable artifacts.
- Restart, rebalance, replay, rescale, and sink retry do not silently lose or
  duplicate effects; unknown outcomes are explicit.
- Snapshot-to-stream handoff detects and prevents an unreported gap or overlap
  during concurrent source changes and schema evolution.
- Plans and reports expose watermark, lateness, lag, backpressure, replay window,
  dedupe horizon, state version, and provider guarantee.
- Unsupported provider semantics fail with a capability diagnostic before work
  is accepted.
- Poison records cannot cause unbounded retry, silent offset/checkpoint advance,
  unauthorized payload disclosure, or an unreconciled dead-letter result;
  redrive is idempotent and provenance-linked.
- Registry incompatibility, ambiguity, staleness, or outage follows an explicit
  fail-closed policy and cannot silently reinterpret an event.
- Envelope and state migrations pass mixed-version rolling-upgrade and rollback
  boundaries without losing audit/replay provenance.

## Required Release Evidence

Planning freeze (now):

- This implementation plan
- [ADR-022](adr/ADR-022-DYNAMIC-CONTROL-AND-STREAMING.md)
- [EXIT_GATE_0_46](EXIT_GATE_0_46.md)
- [FINDINGS_0_46](FINDINGS_0_46.md)

At ship (not written in this freeze):

- Batch/stream equivalence corpus
- Dynamic expansion, branch, replay, cancellation, compensation, and bounds
  corpus
- Crash, rebalance, retry, and recovery matrix
- Poison-record/DLQ offset, redrive, retention, authorization, and
  reconciliation report
- Avro/Protobuf/JSON Schema registry compatibility and outage report
- Snapshot-handoff concurrent-change report
- Kafka provider conformance and capacity results
- State/envelope compatibility and rolling-upgrade report
- Future `WHATS_NEW_0_46` / `MIGRATION_0_45_TO_0_46` and conformance JSON
  (do not publish as Available until the exit gate is Met)
