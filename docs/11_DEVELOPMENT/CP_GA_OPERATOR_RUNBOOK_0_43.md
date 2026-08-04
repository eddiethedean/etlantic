# CP-GA Operator Runbook (0.43)

> **Status: Available for ETLantic 0.43.0.** Production multi-tenant operations
> for **Supported** isolation profiles only.

## Supported claim

| Profile | Status |
|---|---|
| `isolated-deployment` | Supported |
| `dedicated-schema` | Supported |
| `shared-service` | Experimental — do not claim production isolation |

Support terms: community **non-SLA**. Capacity numbers are measured envelopes,
not guarantees.

## Host injection

Inject `authorizer`, `definitions`, `submissions`, `events`, and optional
`durable_work` / CP4 providers on `ETLanticAPI`. Principals come from host
auth (header demo or OIDC claim-mapping hook). Do not embed an IdP.

Problem Details vocabulary: `PMCP401`, `PMCP403`, `PMCP404` (incl. cross-scope
non-enumeration), `PMCP409`, `PMCP501` (provider missing), `PMCP503` (outage).

## Experimental stubs (not CP-GA)

`/v1/runs/{id}/report`, `/v1/runs/{id}/lineage`, and `/v1/reliability` are
**Experimental** stubs unless a history store is injected. Do not treat empty
or stub payloads as authority.

## Isolation

- Always authorize before existence lookup.
- Cross-tenant misses stay opaque **404**.
- Use separate engines/deployments for Supported profiles.

## Durable + CP4

- Drain outbox with adopter-owned workers (≥2 hosts for resilience drills).
- Fence terminal writes and checkpoint CAS with lease tokens.
- Quotas: set `shared_pressure` under contention; expect WRR deferrals.
- Erasure: never claim `completed` while providers are unsupported.
- Attestations: provide an explicit signing secret (no default secret).

## Recovery drills

See [CP_GA_OPERATOR_DRILLS_0_43.md](CP_GA_OPERATOR_DRILLS_0_43.md).

## Evidence

- [isolation_profile_matrix_0_43.json](isolation_profile_matrix_0_43.json)
- [cp_ga_support_matrix_0_43.json](cp_ga_support_matrix_0_43.json)
- [cp_ga_traceability_0_43.json](cp_ga_traceability_0_43.json)
