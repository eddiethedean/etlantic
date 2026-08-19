# Migration 0.47 → 0.48

> **Status: Available for ETLantic 0.48.0.** Upgrade notes for adopters moving
> from the published 0.47 scheduler/federation line to the gate-ready 0.48
> human-governed AI line.

## Summary

| Area | Change |
|---|---|
| Package pin | `etlantic==0.48.0` (do not mix 0.47 and 0.48 minors) |
| Plugin floor | `etlantic>=0.48.0,<0.49` |
| New surface | `etlantic context bundle`, `etlantic proposal validate`, `generate --kind agents` |
| New wire | `etlantic.ai_task/1`, `etlantic.context_bundle/1`, `etlantic.proposal/1` (experimental) |
| New FastAPI | `POST /v1/definitions/{id}/context`, `POST /v1/proposals/validate` (compute only) |
| Approvals | Unchanged `/v1/approvals*` — no second mutation API |
| Experimental extra | `etlantic-mcp` (fake-first; not Available in core) |
| Diagnostics | `PMCTX*`, `PMPROP*`, `PMGUIDE*`, `PMMCP*` (experimental families) |

## Upgrade steps

1. Complete adoption on **0.47.x**.

2. Pin core and official plugins / Medallantic together:

   ```bash
   python -m pip install --upgrade 'etlantic==0.48.0'
   # plus matching plugins / medallantic at ==0.48.0
   ```

3. Production: keep `plugin_allowlist` explicit. If you select `etlantic-mcp`,
   pin it:

   ```python
   from etlantic import Profile

   profile = Profile(
       name="production",
       security_mode="production",
       plugin_allowlist={"etlantic-mcp": "==0.48.0"},
   )
   ```

   Empty production allowlists fail closed (`PMPLUG*` / `PMMCP140`).

4. Agent instruction files remain guidance, not a security boundary. Marked
   user regions are preserved; malformed markers skip overwrite (`PMGUIDE*`).

5. Do not give agents schedule, DLQ, erasure, or run mutation tools. Apply
   stays a current 0.42 approval covering proposal and policy fingerprints.

## Rollback

Re-pin **0.47.0** core, plugins, and Medallantic together. 0.48 adds no SQL
schema. Generated instruction files can stay; they are not a trust boundary.
