# CP4 Operator Runbook — Policy, Quotas, Audit (0.42)

> **Claim:** multi-tenant **release candidate**. Not production multi-tenant
> (**0.43**).

## Injection

Wire optional providers on `ETLanticAPI` / `create_app`:

- `policy` — `MemoryPolicyProvider` (or OPA stub/fallback adapter; no embedded evaluate)
- `approvals` — `MemoryApprovalStore`
- `quotas` — `MemoryQuotaProvider`
- `erasure` — `MemoryErasureStore`
- `audit` — `MemoryAuditEvidenceStore` / `SQLModelAuditEvidenceStore`
- `attestations` — `MemoryAttestationStore`
- `objectives` — `MemoryObjectiveStore`

## Fail-closed degraded modes

| Provider outage | Protected mutations | Read-only status |
|---|---|---|
| Policy | Deny (503) | Documented degraded reads only |
| Quota | Deny (503) | May report last known state |
| Approval | Deny promote/privileged | List pending fails closed if store down |
| Audit | Prefer fail closed on privileged write | Export unavailable |

## Emergency containment

```python
quotas.set_contained(ctx, contained=True)
quotas.set_suspended(ctx, suspended=True)
```

Clear only after incident review. Contained workspaces cannot admit new
concurrency, preview, repair, or event budget units.

## Capacity notes

Publish measured envelopes per isolation profile before 0.43 graduation.
0.42 reference budgets (memory defaults): concurrency 10, preview 5,
events 1000, repair 5, storage_bytes 1_000_000 (metadata only).

## Evidence commands

```bash
uv run python scripts/check_cp4_conformance.py --fake
uv run python scripts/check_cp4_chaos.py --fake --write-matrix
uv run python scripts/check_objective_conformance.py --fake
```
