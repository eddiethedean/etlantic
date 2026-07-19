# What's New in 0.16

> **Status: Historical release notes for ETLantic 0.16.0.** Current line is
> **0.18.0** — see [What's new in 0.18](WHATS_NEW_0_18.md).

ETLantic 0.16.0 completes authoring vocabulary cleanup and ships an optional
Prefect direct-execution scheduler.

## Authoring vocabulary (Gate A)

Public `Source`, `Sink`, `binding=`, `Profile(bindings=...)`, and
`RunRequest(binding_overrides=...)` are removed. Use:

- `Extract` / `Load` with `asset=`
- `Profile(assets=...)`
- `RunRequest(asset_overrides=...)`

Plan/DPCS/plugin wire names (`binding`, source/sink kinds) are unchanged.
See [Migration 0.15 → 0.16](../11_DEVELOPMENT/MIGRATION_0_15_TO_0_16.md).

## Prefect scheduler (Gate B)

Install `etlantic[prefect]` and select `Profile(orchestrator="prefect")`.
Prefect implements `ExecutionScheduler` (`etlantic.scheduler/1`) for local
direct invocation — not Airflow-style `compile_plan`. `LocalScheduler` remains
the default; Airflow remains the external compiler via `etlantic-airflow`.

## Decision table

| Path | How |
|---|---|
| Local / tests / notebooks | `orchestrator="local"` (default) |
| Prefect coordination | `orchestrator="prefect"` + `etlantic-prefect` |
| Airflow DAG artifacts | `etlantic compile --target airflow` |
