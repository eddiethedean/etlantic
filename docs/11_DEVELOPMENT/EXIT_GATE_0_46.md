# Exit Gate 0.46 — Streaming and Event-Driven Pipelines

> **Status: Met — gate-ready for tag/publish.** ETLantic **0.46.0** closes
> bounded dynamic control, stream semantics, record-error policy, and
> Experimental Kafka / schema-registry extras (in-memory fakes). See
> [IMPLEMENTATION_PLAN_0_46](IMPLEMENTATION_PLAN_0_46.md) and
> [ADR-022](adr/ADR-022-DYNAMIC-CONTROL-AND-STREAMING.md) (Accepted).

| Deliverable | Status |
|---|---|
| Planning: this exit gate / findings / ADR-022 | **Met** (Accepted ADR-022) |
| What's New / migration (ship artifacts) | **Met** |
| Dynamic control (046-D) | **Met** |
| Stream model (046-M) | **Met** |
| Change envelope (046-E) | **Met** |
| State and checkpoints (046-S) | **Met** |
| Snapshot handoff (046-H) | **Met** |
| Kafka provider (046-K) | **Met** (Experimental fake; live skipped) |
| Record errors / DLQ (046-Q) | **Met** |
| Schema registries (046-G) | **Met** (Experimental fake; live skipped) |
| Reliability and reporting (046-R) | **Met** |
| Compatibility / operations (046-C) | **Met** (in-process mixed-version fixtures) |
| Lockstep version 0.46.0 | **Met** |

## Supported claim (target freeze)

From [IMPLEMENTATION_PLAN_0_46](IMPLEMENTATION_PLAN_0_46.md).

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
| Rescale / rolling-upgrade campaigns | **Experimental** | In-process fake versions |

## Quantified exit scorecard

From [IMPLEMENTATION_PLAN_0_46](IMPLEMENTATION_PLAN_0_46.md):

| # | Measure | Required | Current |
|---|---|---:|---|
| 1 | 046-D dynamic control types, identity, bounds | Pass | **Met** |
| 2 | 046-M stream semantic model + batch/stream fixtures | Pass | **Met** |
| 3 | 046-E change-envelope metadata (no payloads) | Pass | **Met** |
| 4 | 046-S checkpoint/offset identities reuse 0.38/0.41 | Pass | **Met** |
| 5 | 046-H snapshot-to-stream handoff protocol | Pass | **Met** |
| 6 | 046-K Kafka provider Experimental | Pass | **Met** (fake; live skipped) |
| 7 | 046-Q record-error policy + DLQ identity | Pass | **Met** |
| 8 | 046-G schema-registry protocol Experimental | Pass | **Met** (fake; live skipped) |
| 9 | 046-R continuous reports: watermark, lag, backpressure | Pass | **Met** |
| 10 | 046-C envelope/state migration + rolling upgrade | Pass | **Met** (in-process fakes) |
| 11 | Optimizer cannot expand/stream-rewrite without new proof kinds | Pass | **Met** (`PMOPT112`) |
| 12 | Production allowlists fail closed; no payload in artifacts | Pass | **Met** |
| 13 | No unresolved P0 in [FINDINGS_0_46](FINDINGS_0_46.md) | 0 | **Met** (P0 = 0) |
| 14 | Release record: supported vs experimental | Pass | **Met** |

## Evidence map

| Gate item | Evidence |
|---|---|
| Implementation plan | [IMPLEMENTATION_PLAN_0_46](IMPLEMENTATION_PLAN_0_46.md) |
| ADR | [ADR-022](adr/ADR-022-DYNAMIC-CONTROL-AND-STREAMING.md) (Accepted) |
| Findings | [FINDINGS_0_46](FINDINGS_0_46.md) |
| Conformance JSON | [streaming_conformance_0_46.json](streaming_conformance_0_46.json), [schema_registry_conformance_0_46.json](schema_registry_conformance_0_46.json), [kafka_fake_conformance_0_46.json](kafka_fake_conformance_0_46.json) |
| Migration | [MIGRATION_0_45_TO_0_46](MIGRATION_0_45_TO_0_46.md) |
| What's New | [WHATS_NEW_0_46](../01_GETTING_STARTED/WHATS_NEW_0_46.md) |
| Tests | `uv run pytest tests/streaming tests/kafka tests/schemaregistry tests/optimization -q` |
| Docs / agents | `uv run python scripts/check_docs.py`; `uv run python scripts/check_agent_guidance.py` |
| Redaction | `tests/streaming/test_envelope_no_payload.py`; report JSON without fixture payloads |
| Production allowlists | `tests/streaming/test_registry_trust.py`; empty production `schema_registry_allowlist` → `PMREG140` |

## Go / no-go

**Go — gate-ready for tag/publish.** Live Kafka (`046-K-01`) and live Confluent
(`046-G-01`) remain explicitly deferred Experimental skips. Do not describe
Kafka or the Confluent adapter as Available in core.
