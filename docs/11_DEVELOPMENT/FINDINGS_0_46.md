# Findings Ledger 0.46 — Streaming and Event-Driven Pipelines

> **Status: Closed for gate-ready 0.46.0.** Open **P0 count is 0**.
> Live Kafka / live Confluent remain deferred Experimental skips.

## Severity policy

From [IMPLEMENTATION_PLAN_0_46](IMPLEMENTATION_PLAN_0_46.md) and
[ADR-022](adr/ADR-022-DYNAMIC-CONTROL-AND-STREAMING.md):

| Severity | Meaning | Release treatment |
|---|---|---|
| **P0** | Unbounded expansion; silent offset/checkpoint advance; payload leak into plan/report/audit; non-deterministic child identity; capability degrade to append-only; DLQ without authorization identity | Must close before 0.46 |
| **P1** | Material identity, handoff, registry, or optimizer-interaction risk | Close or defer with owner |
| **P2** | Localized usability / maintainability | May defer with owner |
| **P3** | Cosmetic | Backlog |

## Locked dispositions

| Decision | Outcome | Notes |
|---|---|---|
| Protocol ownership | Core plan/report extensions | ADR-022; not a fourth contract family |
| Kafka / registry | Optional Experimental packages | `etlantic-kafka`, `etlantic-schemaregistry` |
| Payloads | Provider-owned storage only | Identifiers + bounded metadata in ETLantic |
| Python branching | Not a plan surface | Explicit [DPCS](../05_PIPELINES/DPCS.md)-representable control flow |
| Optimizer | Reject unknown / expansion rewrite | `PMOPT112`; ADR-021 still off-by-default |
| Production trust | `plugin_allowlist` + `schema_registry_allowlist` | Fail closed |

## Open findings

Open **P0 count is 0**.

| ID | Severity | Owner | State | Summary | Evidence / disposition |
|---|---|---|---|---|---|
| — | — | — | — | No open P0 | Redaction + identity tests in `tests/streaming` |

## P1 placeholders (implementation)

| ID | Severity | Owner | State | Summary | Evidence / disposition |
|---|---|---|---|---|---|
| `046-K-01` | P1 | Connectors | Deferred | Kafka live-cluster vs fake/CI reference | Live skipped unless `ETLANTIC_KAFKA_BOOTSTRAP`; FakeKafka in CI |
| `046-G-01` | P1 | Connectors | Deferred | Confluent live registry vs wire-only protocol | Live skipped unless `ETLANTIC_SCHEMA_REGISTRY_URL`; FakeConfluentRegistry in CI |
| `046-O-01` | P1 | Optimization | Closed | 0.45 passes must not expand/stream-rewrite | `PMOPT112` unknown-kind reject; `tests/streaming/test_runtime_0_46.py` |

## Soft-continue from prior phases

| ID | Severity | Owner | State | Summary | Evidence / disposition |
|---|---|---|---|---|---|
| `043-R-01` | P1 | Control-plane | Deferred | True multi-process dual-API drill | Out of 0.46 scope |
| `043-M-01` | P1 | Control-plane | Deferred | OpenLineage reconciliation product drill | Out of 0.46 scope |

## Closure rules

A finding closes only with a test, evidence artifact, or explicit deferral row.
Do not reopen ADR-022 locked dispositions without a written finding and
maintainer approval.
