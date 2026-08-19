# What's New in ETLantic 0.47

> **Status: Available in ETLantic 0.47.0 (gate-ready Beta).** Scheduler/runner
> service and remote execution federation: split-role FastAPI gateway, timer
> leadership, execution host, SQLModel `004`, and Experimental Kubernetes /
> Spark Connect fakes. Live Kind and Databricks remain skipped.

## Highlights

- **Schedule contracts** — `etlantic.schedule/1` and `etlantic.firing/1` with
  firing key `(schedule_id, revision_id, nominal_fire_time)`, injectable clock,
  5-field cron, DST/misfire/catch-up (`PMFIRE*`)
- **ScheduleStore** — memory (tests/dev) plus SQLModel snapshot + migration
  `004_schedules_0_47`. Production rejects `MemoryScheduleStore` (`PMSVC100`)
- **Scheduler and worker processes** — `etlantic scheduler serve` and
  `etlantic worker serve` wrap CP3 durable work. FastAPI never executes
  pipelines; workers do not import FastAPI
- **Gateway** — FastAPI `/v1/definitions/{id}/schedules`, `/v1/schedules/{id}`,
  scheduler/worker health. Dual-write firing into `DurableWorkStore.accept`
- **CLI** — `etlantic schedule create|list|inspect|pause|resume|delete|preview|trigger`.
  Tutorial: [Scheduler and worker](SCHEDULER_TUTORIAL.md)
- **Remote federation** — `etlantic.remote-runtime/1` negotiate (preserve 0.46
  map/branch/stream or `PMFED*`), signed-plan fakes, placement reject-before-transfer
- **Trust** — `Profile.resource_provider_allowlist` fail-closed when a resource
  provider is selected (`PMRES140`)
- **Experimental extras** — `etlantic-k8s` (`FakeKubernetes`, live skip
  `047-K-01`) and `etlantic-spark-connect` (fake `SparkProvider`, live skip
  `047-S-01`)

## Adopter actions

| Who | Action |
|---|---|
| Everyone on **0.46.x** | Upgrade to `etlantic==0.47.0` with matching plugins; see [Migration 0.46 → 0.47](../11_DEVELOPMENT/MIGRATION_0_46_TO_0_47.md) |
| Operators | Split FastAPI / scheduler / worker in production; never run pipelines in the gateway |
| Resource-provider authors | Pin `plugin_allowlist` and `resource_provider_allowlist` |
| Remote-runtime authors | Preserve map/branch/stream or reject; never auto-retry unknown commits |

## Not in 0.47

- Helm/OCI production images (0.51)
- Live Kind / Databricks / EMR / Spark Connect (skips `047-K-01`, `047-S-01`)
- Broker-backed wake-up (polling is the reference)
- Merging the timer service into `etlantic.scheduler/1`
