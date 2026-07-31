---
title: ETLantic 0.46 Implementation Plan
description: Implementation-grade plan for bounded dynamic control flow, streaming, and event-driven pipelines.
plan_status: current
plan_last_reviewed: 0.37.0
---

# ETLantic 0.46 Implementation Plan

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
  closed their 0.41–0.43 gates.
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

## Delivery Sequence

1. Freeze dynamic-control, stream, record-error, and schema-registry semantics
   before provider code.
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

- Batch/stream equivalence corpus.
- Dynamic expansion, branch, replay, cancellation, compensation, and bounds
  corpus.
- Crash, rebalance, retry, and recovery matrix.
- Poison-record/DLQ offset, redrive, retention, authorization, and
  reconciliation report.
- Avro/Protobuf/JSON Schema registry compatibility and outage report.
- Snapshot-handoff concurrent-change report.
- Kafka provider conformance and capacity results.
- State/envelope compatibility and rolling-upgrade report.
