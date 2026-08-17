# Findings Ledger 0.47 — Scheduler Service and Remote Federation

> **Status: Open for 0.47 implementation.** Planning freeze recorded after
> ETLantic **0.46.0**. Open **P0 count is 0**. Live Kind (`047-K-01`) and live
> Spark Connect (`047-S-01`) remain deferred Experimental skips.

## Severity policy

From [IMPLEMENTATION_PLAN_0_47](IMPLEMENTATION_PLAN_0_47.md) and
[ADR-023](adr/ADR-023-SCHEDULER-SERVICE-AND-FEDERATION.md):

| Severity | Meaning | Release treatment |
|---|---|---|
| **P0** | Duplicate durable firing; lost accepted schedule mutation; unknown commit classified as safe-to-retry; FastAPI imports or executes in workers; secret/row/payload in schedule/plan/report/audit; unbounded catch-up or retry storm | Must close before 0.47 |
| **P1** | Material lease, negotiation, placement, or fake-vs-live risk | Close or defer with owner |
| **P2** | Localized usability / maintainability | May defer with owner |
| **P3** | Cosmetic | Backlog |

## Locked dispositions

| Decision | Outcome | Notes |
|---|---|---|
| Protocol ownership | Wrap CP3 / scheduler / orchestration; do not merge discovery | ADR-023; ADR-018 still accept ≠ execute |
| Process split | FastAPI gateway, scheduler, execution host | Production requires separate supervision |
| Firing key | `(schedule_id, revision_id, nominal_fire_time)` | Leader failover returns original accepted run |
| Leader vs execution lease | Distinct | Timer leadership is not a CP3 attempt lease |
| Kubernetes / Spark Connect | Optional Experimental packages | `etlantic-k8s`, `etlantic-spark-connect` |
| Fake vs live | Fakes are the 0.47 gate | Live Kind/Databricks/EMR → 0.51 or skip |
| Wake-up | Polling reference | No new broker package in 0.47 |
| Payloads / secrets | Provider-owned; opaque refs only | FORWARD invariant |
| Optimizer | Advisory; no silent remote rewrite | ADR-021; 0.46 dyn/stream preserved or reject |
| Production trust | `plugin_allowlist` + `resource_provider_allowlist` | Fail closed; reject memory stores |

## Open findings

Open **P0 count is 0**.

| ID | Severity | Owner | State | Summary | Evidence / disposition |
|---|---|---|---|---|---|
| — | — | — | — | No open P0 | Planning freeze; no implementation yet |

## P1 placeholders (implementation)

| ID | Severity | Owner | State | Summary | Evidence / disposition |
|---|---|---|---|---|---|
| `047-K-01` | P1 | Providers | Deferred | Kubernetes live Kind/cluster vs FakeKubernetes | Live skipped unless opt-in env; fake in CI |
| `047-S-01` | P1 | Providers | Deferred | Live Spark Connect / Databricks / EMR vs in-process fake | Live skipped; production packs are 0.51 |

## Soft-continue from prior phases

| ID | Severity | Owner | State | Summary | Evidence / disposition |
|---|---|---|---|---|---|
| `046-K-01` | P1 | Connectors | Deferred | Kafka live-cluster vs fake/CI reference | Out of 0.47 scope; remains 0.46 skip |
| `046-G-01` | P1 | Connectors | Deferred | Confluent live registry vs wire-only protocol | Out of 0.47 scope; remains 0.46 skip |
| `043-R-01` | P1 | Control-plane | Deferred | True multi-process dual-API drill | Split-role chaos is 047-O; live shared-service remains Experimental |

## Closure rules

A finding closes only with a test, evidence artifact, or explicit deferral row.
Do not reopen ADR-023 locked dispositions without a written finding and
maintainer approval.
