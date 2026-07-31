# Findings Ledger 0.40 — Tenant Registry and Persistence Isolation (CP2)

> **Status: Gate-ready** — ETLantic **0.40.0** CP2 exit. Open **P0 count is 0**.
> **CP2 ≠ production multi-tenant** (**0.43**).

## Severity policy

From [IMPLEMENTATION_PLAN_0_40](IMPLEMENTATION_PLAN_0_40.md):

| Severity | Meaning | Release treatment |
|---|---|---|
| **P0** | Cross-tenant disclosure, revision mutation, secret/row leakage in registry/history, isolation-profile false claim, outbound lineage mutating authority | Must close before 0.40 |
| **P1** | Material compatibility, migration, isolation evidence, or adoption risk | Close or defer with owner, mitigation, target phase, and non-blocking rationale |
| **P2** | Localized usability, performance, or maintainability defect | May defer with owner and target |
| **P3** | Cosmetic or opportunistic improvement | Backlog |

Changing severity without written rationale does not close a finding.

## Locked dispositions

Recorded in
[ADR-017: Registry and Isolation](adr/ADR-017-REGISTRY-AND-ISOLATION.md). Do not
reopen without a written finding and migration plan.

| Decision | Outcome | Notes |
|---|---|---|
| Directory records | `TenantRecord`, `WorkspaceRecord`, `EnvironmentRecord`, `SecurityDomainRecord` | Distinct from CP1 refs |
| Lifecycle | `active`, `suspended`, `archived` | Suspended fails closed |
| Revisions | `logical_id` + immutable `revision_id` | Append-only; content fingerprint |
| Aliases / promotions | Alias → revision; `PromotionRecord` | Promote does not mutate prior revision |
| Signature / provenance | Placeholders (metadata only) | No credentials or source rows |
| Provider façade | `RegistryProvider` | Composes directories + revisions |
| Isolation profiles | isolated-deployment, dedicated-schema, shared-service + second control | RLS or tenant credentials |
| Histories / impact | Fingerprints/metadata only | Baselines ≠ contract mutation |
| OpenLineage | Outbound only | Cannot mutate registry |
| CP2 vs GA | CP2 ≠ production multi-tenant | Graduation remains **0.43** |

## Open findings

Open **P0 count is 0**.

| ID | Severity | Owner | State | Summary | Evidence / disposition |
|---|---|---|---|---|---|
| — | — | — | — | No open rows | — |

## Closed at exit (evidence)

| ID | Severity | Owner | State | Summary | Evidence / disposition |
|---|---|---|---|---|---|
| `040-X-01` | P0 (prevented) | CP maintainers | Closed | Cross-tenant registry disclosure | Two-by-two matrix + isolation script |
| `040-X-02` | P0 (prevented) | CP maintainers | Closed | OpenLineage mutates authority | Failing-transport test; exporter never calls mutators on failure |
| `040-X-03` | P0 (prevented) | CP maintainers | Closed | Shared-service WHERE-only claim | Stub proves second control required; matrix JSON |

## Soft-continue from prior phases

| ID | Severity | Owner | State | Summary | Evidence / disposition |
|---|---|---|---|---|---|
| `038-X-01` | P1 | Ecosystem + echo maintainer | Soft-continue | Independent echo connector on PyPI | Non-blocking for CP2; see [FINDINGS_0_39](FINDINGS_0_39.md) |

## Closure rules

1. Every P0 requires a regression test and linked durable evidence before
   severity can move or the finding can close.
2. Deferred P1 rows must name owner, target phase, mitigation, and
   non-blocking rationale.
3. Do not reopen ADR-017 locked dispositions without a written finding and
   migration plan.
