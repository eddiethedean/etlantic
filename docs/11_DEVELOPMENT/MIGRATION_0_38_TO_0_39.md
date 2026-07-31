# Migration 0.38 → 0.39

> **Status: Gate-ready for tag/publish rehearsal toward ETLantic 0.39.0.**
> Upgrade guide for adopters moving from the 0.38 connectivity line to the
> 0.39 CP1 control-plane incubation. **CP1 ≠ production multi-tenant**
> (**0.43**).

## Summary

| Area | Change |
|---|---|
| Package pin | Target `etlantic==0.39.0` (do not mix 0.38 and 0.39 minors) |
| Plugin floor | `etlantic>=0.39.0,<0.40` on official plugins / Medallantic |
| Control plane | CP1: typed identity, embeddable API, durable submit, SSE |
| Identity | Frozen: `Principal`, `TenantRef`, `WorkspaceRef`, `EnvironmentRef`, `SecurityDomain`, `ControlPlaneContext` |
| Thin FastAPI adapter | `create_reference_app` remains; is **not** the durable multi-tenant control plane |
| Production multi-tenant | **Not** claimed in 0.39 — reserved for **0.43** |
| Landing watch | Still outside core; use `LandingWatchSubmitter` against durable submit |
| Wire schemas | Prefer additive `/1` control-plane envelopes |

## Upgrade steps

1. Pin core and every official plugin / Medallantic together at `0.39.0`
   (do not mix 0.38 and 0.39 minors):

   ```bash
   python -m pip install --upgrade 'etlantic==0.39.0'
   python -m pip install --upgrade 'medallantic==0.39.0'
   # plus every official plugin you use at ==0.39.0
   ```

2. Update production `plugin_allowlist` pins to `==0.39.0`.

3. If you embed HTTP:

   - Prefer `ETLanticAPI` + `include_router` / `create_app` for CP1.
   - Do not treat `create_reference_app` as durable submission or
     multi-tenant isolation.
   - Expect `202 Accepted` only after durable accept; do not rely on
     process-local background tasks for runs.
   - Subscribe to run events at `GET /v1/runs/{run_id}/events`
     (`text/event-stream`); unknown resume cursors return **410**.

4. Treat path and header tenant fields as routing claims only. Membership and
   policy come from authenticated, server-derived `ControlPlaneContext`.

5. Re-validate and re-plan existing pipelines (connector / landing-zone
   behavior from 0.38 is unchanged by CP1 identity freeze):

   ```bash
   etlantic validate TARGET --format json
   etlantic plan TARGET --format json
   ```

6. Continuous file-drop watching remains a submitter concern outside core —
   point watchers at the durable submission API (`LandingWatchSubmitter` or
   host-equivalent). Never embed file contents in plans or submit bodies.

## Compatibility notes

- 0.38 connector protocols, landing-zone snapshot/incremental modes, and
  reference packages remain the connectivity baseline.
- CP1 does not require a plan-schema reset.
- Event and accept-receipt `/1` shapes are designed for additive 0.41
  migration; prefer dual-read if a `/2` appears later.
- FastAPI and SQLModel remain **optional** extras — core `import etlantic`
  does not pull them.
- Do not announce or configure production shared-service multi-tenant
  isolation on CP1 alone.

## See also

- [What's New in 0.39](../01_GETTING_STARTED/WHATS_NEW_0_39.md)
- [Exit gate 0.39](EXIT_GATE_0_39.md)
- [Findings ledger 0.39](FINDINGS_0_39.md)
- [ADR-016: Control-Plane Identity](adr/ADR-016-CONTROL-PLANE-IDENTITY.md)
- [Implementation plan 0.39](IMPLEMENTATION_PLAN_0_39.md)
- [Migration 0.37 → 0.38](MIGRATION_0_37_TO_0_38.md)
