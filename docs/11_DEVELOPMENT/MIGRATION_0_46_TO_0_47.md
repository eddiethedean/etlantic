# Migration 0.46 → 0.47

> **Status: Available for ETLantic 0.47.0.** Upgrade notes for adopters moving
> from the published 0.46 streaming line to the gate-ready 0.47 scheduler
> service and remote-federation line.

## Summary

| Area | Change |
|---|---|
| Package pin | `etlantic==0.47.0` (do not mix 0.46 and 0.47 minors) |
| Plugin floor | `etlantic>=0.47.0,<0.48` |
| New surface | Scheduler/worker CLI + FastAPI schedule routes (gateway only) |
| New wire | `etlantic.schedule/1`, `etlantic.firing/1`, `etlantic.remote-runtime/1` |
| New protocol | `etlantic.resource/1` (Experimental extras implement it) |
| New profile field | `resource_provider_allowlist` |
| SQLModel | Migration `004_schedules_0_47` after `003_cp4_governance` |
| Experimental extras | `etlantic-k8s`, `etlantic-spark-connect` (fake-first; not Available in core) |
| Diagnostics | `PMSVC*`, `PMFIRE*`, `PMFED*`, `PMRES*` (do not overload `PMSCHED*`) |

## Upgrade steps

1. Complete adoption on **0.46.x**.

2. Pin core and official plugins / Medallantic together:

   ```bash
   python -m pip install --upgrade 'etlantic==0.47.0'
   # plus matching plugins / medallantic at ==0.47.0
   ```

3. Production: keep `plugin_allowlist` explicit. If you select a resource
   provider (`etlantic-k8s` / `etlantic-spark-connect`), also set
   `resource_provider_allowlist`:

   ```python
   from etlantic import Profile

   profile = Profile(
       name="production",
       security_mode="production",
       plugin_allowlist={"etlantic-k8s": "==0.47.0"},
       resource_provider_allowlist={"etlantic-k8s": "==0.47.0"},
   )
   ```

   Empty production allowlists fail closed (`PMPLUG*` / `PMRES140`).
   `MemoryScheduleStore` is rejected in production (`PMSVC100`).

4. Apply SQLModel migrations through `004_schedules_0_47` when using
   `etlantic-sqlmodel` schedule persistence.

5. Do not execute pipelines inside FastAPI handlers or `BackgroundTasks`.
   Run `etlantic scheduler serve` and `etlantic worker serve` as separate
   processes. Compilers that cannot preserve map/branch/stream still
   reject (`PMDYN130` / `PMFED*`).

## Rollback

Re-pin **0.46.0** core, plugins, and Medallantic together. Schedule tables from
`004` are unused on 0.46; leave them in place or roll back the SQLModel
schema with `downgrade(..., target="003_cp4_governance")`.
