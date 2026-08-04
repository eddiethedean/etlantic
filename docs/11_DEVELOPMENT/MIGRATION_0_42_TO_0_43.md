# Migration 0.42 → 0.43

> **Status: Available for ETLantic 0.43.0.** Upgrade notes for adopters moving
> from the 0.42 CP4 release-candidate line to the 0.43 CP-GA graduated line.

## Summary

| Area | Change |
|---|---|
| Package pin | `etlantic==0.43.0` (do not mix 0.42 and 0.43 minors) |
| Plugin floor | `etlantic>=0.43.0,<0.44` |
| Claim | Production multi-tenant **only** for Supported isolation profiles |
| Supported profiles | `isolated-deployment`, `dedicated-schema` |
| Experimental | `shared-service` (not a production isolation claim) |
| Persistence | SQLModel snapshot dual-path remains canonical; entity mirrors unchanged |
| Support terms | Measured envelopes + non-SLA (no formal enterprise SLA) |

## Upgrade steps

1. Complete CP4 adoption on `0.43.0` (policy/quotas/audit as needed).

2. Pin core and official plugins / Medallantic together:

   ```bash
   python -m pip install --upgrade 'etlantic==0.43.0'
   # plus matching plugins / medallantic at ==0.43.0
   ```

3. Apply SQLModel migrations when using optional persistence:

   ```python
   from etlantic_sqlmodel.migrations import apply_migrations
   apply_migrations(engine)
   ```

4. Confirm your deployment matches a **Supported** isolation profile. Do not
   announce production multi-tenant for `shared-service` without a real second
   control (RLS / dedicated credentials).

5. Review [CP-GA operator runbook](CP_GA_OPERATOR_RUNBOOK_0_43.md) and capacity
   envelopes before load testing.

## Compatibility

- CP1–CP4 wire schemas remain additive; OpenAPI operationIds are stable.
- Downgrade to 0.42 is supported only with matching plugin minors and after
  verifying no 0.43-only migrations were applied beyond the documented boundary.

## See also

- [What's New 0.43](../01_GETTING_STARTED/WHATS_NEW_0_43.md)
- [Exit gate 0.43](EXIT_GATE_0_43.md)
- [Support matrix](cp_ga_support_matrix_0_43.json)
