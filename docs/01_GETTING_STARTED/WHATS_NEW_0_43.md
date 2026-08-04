# What's New in ETLantic 0.43

> **Status: Available in ETLantic 0.43.0.** CP-GA graduation: production
> multi-tenant support for **frozen** isolation profiles only.
> **Beta** maturity retained; support remains community **non-SLA**.

## Highlights

- **Production multi-tenant claim (bounded)** — Supported profiles:
  `isolated-deployment` and `dedicated-schema` with full two-tenant / two-workspace
  evidence across CP1–CP4 and FastAPI paths
- **Compatibility policy** — plugins require `etlantic>=0.43.0,<0.44`; migration
  and OpenAPI stability evidence published
- **Resilience** — dual-host durable + dual-API campaign evidence (lease fencing,
  cancel, stale publish, failover without crossed scope)
- **Recovery** — install / upgrade / backup / restore / key-rotation drills
- **Capacity** — measured envelopes + overload fail-closed + quota WRR under
  shared pressure; explicit non-SLA
- **GitOps** — preview → SoD approval → promote → rollback → cleanup proof
- **Objectives / erasure** — restart-safe evaluation and false-completion-closed
  erasure campaigns
- **Evidence** — [cp_ga_traceability_0_43.json](../11_DEVELOPMENT/cp_ga_traceability_0_43.json)

## Adopter actions

| Who | Action |
|---|---|
| Everyone on 0.43.x | Upgrade to `etlantic==0.43.0` with matching plugins; see [migration](../11_DEVELOPMENT/MIGRATION_0_42_TO_0_43.md) |
| Multi-tenant operators | Use only Supported isolation profiles; treat `shared-service` as Experimental |
| Control-plane hosts | Review [CP-GA operator runbook](../11_DEVELOPMENT/CP_GA_OPERATOR_RUNBOOK_0_43.md) |

## Not in 0.43

- Formal enterprise SLA / unbounded scale
- `shared-service` production isolation (needs real RLS pack)
- Embedded IdP or embedded OPA evaluate
- Operator Console (0.50)

## See also

- [Migration 0.42 → 0.43](../11_DEVELOPMENT/MIGRATION_0_42_TO_0_43.md)
- [Exit gate 0.43](../11_DEVELOPMENT/EXIT_GATE_0_43.md)
- [Findings ledger 0.43](../11_DEVELOPMENT/FINDINGS_0_43.md)
- [Implementation plan 0.43](../11_DEVELOPMENT/IMPLEMENTATION_PLAN_0_43.md)
- [Support matrix](../11_DEVELOPMENT/cp_ga_support_matrix_0_43.json)
