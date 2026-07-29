# What's New in ETLantic 0.34

> **Status: Available in ETLantic 0.34.0.** Operations, Evidence, and Production
> Readiness (Medallantic **M6**): observability providers, durable run history,
> event consumers, and production conformance.

!!! note "Milestone name vs enterprise claim"
    “Production readiness” here means the M6 observability/history *pilot*
    slice. It does **not** mean unrestricted enterprise production. See
    [Production readiness](../06_EXECUTION/PRODUCTION_READINESS.md) and
    CHANGELOG `[Unreleased]` for post-cut hardening that may land in later
    0.34.x patches.

## Highlights

- **Lifecycle event correlation** — `plan_id`, `region_id`, `backend`, and
  facade-safe `annotations` on `etlantic.lifecycle_event/1`
- **Observability provider protocol** (`etlantic.observability/1`) with reference
  JSON console and optional OpenTelemetry adapter
- **Run history providers** — in-memory and file-backed reference implementations
  with conformance suite (`create` / `append` / `read` / `list`)
- **Event consumers** — reference trend consumer; `etlantic reliability
  quality-trends` uses consumer summaries when no inline `--values` given
- **Profile composition** — `observability_providers`, `run_history_provider`,
  `event_consumers`, `observability_delivery` (`best_effort` | `durable_audit`)
- **Runtime bridge** — EventBus and structured logs fan out to registered
  providers; terminal reports include observability metadata
- **CLI** — workspace `.etlantic/history/` file history; `etlantic report query`
- **Medallantic M6** — `explain_medallion_plan`, layer lifecycle views,
  `medallion_*_profile()` templates
- [Migration 0.33 → 0.34](../11_DEVELOPMENT/MIGRATION_0_33_TO_0_34.md) and
  [Exit gate 0.34](../11_DEVELOPMENT/EXIT_GATE_0_34.md)

## Not in 0.34

- SparkForge migration inventory (**0.35 / M7**)
- First-party SQL/Delta run-history PyPI plugins
- Multi-tenant control plane

## Upgrade

Pin core and plugins to the same minor:

```bash
python -m pip install --upgrade 'etlantic==0.34.0'
python -m pip install --upgrade 'medallantic==0.34.0'
```

Plugin authors: pin `etlantic>=0.34.0,<0.35`.
