# Migration 0.41 → 0.42

> **Status: Available for ETLantic 0.42.0.** Upgrade notes for adopters moving
> from the 0.41 CP3 durable-work line to the 0.42 CP4 policy/audit release
> candidate. **CP4 ≠ production multi-tenant** (**0.43**).

## Summary

| Area | Change |
|---|---|
| Package pin | `etlantic==0.42.0` (do not mix 0.41 and 0.42 minors) |
| Control plane | CP4: policy, approvals/SoD, quotas, objectives, erasure, attestations, audit |
| CP1–CP3 APIs | Stable and additive; durable wire shapes unchanged |
| Host ops | New `/v1/policy|approvals|quotas|erasure|audit|attestations` routes |
| Durable HTTP | Effects / repair / diagnose / shadow routes completed (`041-P1-02`) |
| Persistence | SQLModel migration `003_cp4_governance`; normalized durable entity dual-write |
| Production multi-tenant | **Not** claimed in 0.42 — reserved for **0.43** |

## Upgrade steps

1. Complete CP3 adoption on `0.41.0` first (durable accept, leases, previews).

2. Pin core and official plugins / Medallantic together:

   ```bash
   python -m pip install --upgrade 'etlantic==0.42.0'
   # plus matching plugins / medallantic at ==0.42.0
   ```

3. Apply SQLModel migrations when using the optional persistence package:

   ```python
   from etlantic_sqlmodel.migrations import apply_migrations
   apply_migrations(engine)  # includes 003_cp4_governance
   ```

4. Inject CP4 providers into `ETLanticAPI` / `create_app` as needed:

   ```python
   create_app(
       ...,
       policy=MemoryPolicyProvider(),
       approvals=MemoryApprovalStore(),
       quotas=MemoryQuotaProvider(),
       audit=MemoryAuditEvidenceStore(),
       erasure=MemoryErasureStore(),
       attestations=MemoryAttestationStore(),
   )
   ```

5. For protected profiles, require policy on submit/promote (`gate_pre_submit`,
   `gate_pre_promote`). Production profiles continue to require
   `plugin_allowlist`.

6. Re-validate and re-plan existing pipelines after upgrade:

   ```bash
   etlantic validate TARGET --format json
   etlantic plan TARGET --format json
   ```

7. Do not announce production shared-service multi-tenant isolation on CP4
   alone — graduation remains **0.43**.

## Compatibility notes

- Additive relative to ADR-016 / ADR-017 / ADR-018; CP4 wire shapes use `/1`.
- FastAPI and SQLModel remain optional extras.
- Plugin floors move to `etlantic>=0.42.0,<0.43`.
- Soft-continues `041-P1-01` and `041-P1-02` are closed in this release.

## See also

- [What's New in 0.42](../01_GETTING_STARTED/WHATS_NEW_0_42.md)
- [Exit gate 0.42](EXIT_GATE_0_42.md)
- [Findings ledger 0.42](FINDINGS_0_42.md)
- [ADR-019: Policy, Quotas, and Audit](adr/ADR-019-POLICY-QUOTAS-AND-AUDIT.md)
- [Implementation plan 0.42](IMPLEMENTATION_PLAN_0_42.md)
- [CP4 outage matrix](cp4_outage_matrix_0_42.json)
- [Migration 0.40 → 0.41](MIGRATION_0_40_TO_0_41.md)
