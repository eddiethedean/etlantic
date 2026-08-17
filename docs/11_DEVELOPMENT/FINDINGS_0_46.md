# Findings Ledger 0.46 — Streaming and Event-Driven Pipelines

> **Status: Planning freeze** — not started. Open **P0 count is 0**.
> ETLantic **0.45.0** remains the published line.

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
| Optimizer | Reject expansion/stream rewrite | Until new proof kinds; ADR-021 still off-by-default |
| Production trust | `plugin_allowlist` + `schema_registry_allowlist` | Fail closed |

## Open findings

Open **P0 count is 0** at planning freeze (no implementation yet).

| ID | Severity | Owner | State | Summary | Evidence / disposition |
|---|---|---|---|---|---|
| — | — | — | — | No open P0 | — |

## P1 placeholders (implementation)

| ID | Severity | Owner | State | Summary | Evidence / disposition |
|---|---|---|---|---|---|
| `046-K-01` | P1 | Connectors | Open | Kafka live-cluster vs fake/CI reference | Defer live broker to Experimental; in-memory first |
| `046-G-01` | P1 | Connectors | Open | Confluent live registry vs wire-only protocol | Wire protocol in core; live adapter Experimental |
| `046-O-01` | P1 | Optimization | Open | 0.45 passes must not expand/stream-rewrite | Fail closed until new proof kinds; [ADR-021](adr/ADR-021-OPTIMIZER-PASS-PROTOCOL.md) |

## Soft-continue from prior phases

| ID | Severity | Owner | State | Summary | Evidence / disposition |
|---|---|---|---|---|---|
| `043-R-01` | P1 | Control-plane | Deferred | True multi-process dual-API drill | Out of 0.46 scope |
| `043-M-01` | P1 | Control-plane | Deferred | OpenLineage reconciliation product drill | Out of 0.46 scope |

## Closure rules

A finding closes only with a test, evidence artifact, or explicit deferral row.
Do not reopen ADR-022 locked dispositions without a written finding and
maintainer approval.
