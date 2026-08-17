# ADR-023: Scheduler Service, Execution Host, and Remote Federation

Date: 2026-08-17
Status: Proposed (ETLantic **0.47** planning freeze)

## Context

ETLantic 0.46.0 closed bounded dynamic control, stream semantics, and
Experimental Kafka / schema-registry extras. ROADMAP § 0.47 and
[IMPLEMENTATION_PLAN_0_47](../IMPLEMENTATION_PLAN_0_47.md) require an optional
FastAPI-fronted scheduler and runner service plus remote execution
federation—without turning FastAPI into a runtime, embedding Kubernetes or
Spark SDKs in core, or replacing CP3 durable work.

Today, `ExecutionScheduler` / `LocalScheduler` (`etlantic.scheduler/1`) execute
an already-resolved plan in-process. CP3 `DurableWorkStore` accepts work, leases
it, and fences attempts, but **core does not embed a broker or worker
supervisor** ([ADR-018](ADR-018-DURABLE-SUBMISSION-AND-STATE.md)). Queue drain
and timer leadership remain adopter-owned. Prefect deploy/serve and durable
cron were deferred past the 0.16 local MVP. A discoverable resource-provider
protocol is still a design stub.

Without a freeze, implementations will run pipelines in FastAPI
`BackgroundTasks`, conflate scheduler-leader leases with CP3 execution leases,
merge timer-service discovery into `etlantic.scheduler/1` or
`etlantic.orchestration/1`, treat live Kind/Databricks as 0.47 blockers, or
silently rewrite 0.46 map/branch/stream plans on remote hosts.

Authoritative sequencing:
[IMPLEMENTATION_PLAN_0_47](../IMPLEMENTATION_PLAN_0_47.md), ROADMAP § 0.47,
[ADR-018](ADR-018-DURABLE-SUBMISSION-AND-STATE.md),
[ADR-022](ADR-022-DYNAMIC-CONTROL-AND-STREAMING.md),
[FASTAPI_INTEGRATION_PLAN](../FASTAPI_INTEGRATION_PLAN.md), and
[SCHEDULER_AND_PREFECT_PLAN](../SCHEDULER_AND_PREFECT_PLAN.md). Live
Kubernetes and managed Spark production packs remain
[0.51](../IMPLEMENTATION_PLAN_0_51.md).

## Decision

### Wrap, do not replace

0.47 wraps existing public contracts. It does not merge discovery systems or
redefine pipeline semantics.

- [ADR-018](ADR-018-DURABLE-SUBMISSION-AND-STATE.md) remains authority for
  accept-is-not-execute, outbox, execution leases, fencing tokens, and
  known/unknown external effects.
- `etlantic.scheduler/1` remains the in-process direct-execution protocol
  (`LocalScheduler`, optional Prefect). Timer evaluation is a **service role**,
  not a new `ExecutionScheduler`.
- `etlantic.orchestration/1` remains compile/submit/poll for external
  platforms (Airflow). `compile_plan` stays independently usable.
- `Pipeline.run` / `arun`, Prefect local MVP, and Airflow compile remain
  compatible.
- [ADR-022](ADR-022-DYNAMIC-CONTROL-AND-STREAMING.md) identities, expansion
  bounds, compensation/failure semantics, dead-letter identifiers, and report
  correlation are consumed by federation. Remote hosts preserve them or reject
  during negotiation. 0.47 does not redefine them.
- [ADR-021](ADR-021-OPTIMIZER-PASS-PROTOCOL.md) stays advisory. Federation
  must not silently rewrite map/branch/stream plans.

Connectors (`etlantic.source/1`, `sink/1`, `storage/1`) stay I/O. Resource
providers acquire compute runtimes. Spark region execution stays
`etlantic.spark/1`.

### Process split

Production supervises three roles against one transactional store:

1. FastAPI gateway — authorized schedule and run mutations only.
2. Scheduler — leader-elected timer loop; atomic firing-to-run acceptance.
3. Execution host — claims CP3 leases, fences, heartbeats, executes validated
   plans via `PipelineRuntime` + `LocalOrchestrator`, publishes terminal
   results.

Single-process composition is development-only. FastAPI never executes
pipelines in request handlers, `BackgroundTasks`, or lifespan hooks. Execution
hosts must not import FastAPI (import-graph test at ship).

Scheduler-leader leases (advance next-fire) are distinct from CP3 execution
leases (own an attempt). Only the current leader may advance next-fire; only
the current execution fencing token may checkpoint or finalize work.

### Core vs FastAPI vs provider ownership

Core owns `ScheduleStore`, injectable `Clock`, firing-key canonicalization,
scheduler and execution-host loops, `etlantic.remote-runtime/1` negotiation,
discoverable `etlantic.resource/1`, and diagnostics. CLI commands live in core
with lazy optional extras.

`etlantic-fastapi` owns HTTP surfaces only: schedule CRUD, preview, trigger,
firing history, and authorized scheduler/worker health. It injects
`ScheduleStore` and continues CP3 dual-write to `DurableWorkStore`.

`etlantic-sqlmodel` owns migration `004_schedules_0_47` after
`003_cp4_governance`. Firing creation and `DurableWorkStore.accept` are one
transaction.

Optional packages named before implementation:

| Extra / PyPI name | Role | Target |
|---|---|---|
| `etlantic-k8s` | Kubernetes Job resource provider + `FakeKubernetes` | **Experimental** |
| `etlantic-spark-connect` | Spark Connect `SparkProvider` + in-process fake | **Experimental** |

Core installs neither Kubernetes nor Spark Connect SDKs. Live Kind/cluster
(`047-K-01`) and live Databricks/EMR/Spark Connect (`047-S-01`) are
Experimental skips. Production hardening is 0.51.

No new broker package: default wake-up is polling. An optional wake-transport
protocol may exist; vendor brokers remain provider choices.

### Firing identity and bounds

The logical firing key is `(schedule_id, revision_id, nominal_fire_time)`.
Re-evaluation, API retries, or leader failover return the original accepted
run. Catch-up and execution retry are separately bounded. An outage cannot
create an unbounded firing or retry storm.

Schedule records store revision selection, profile identity, policy
fingerprints, bounded parameters, and opaque secret references — never
resolved secrets or source rows.

### Fake vs live (0.46 Kafka pattern)

Protocol plus in-process fakes are the 0.47 gate. Live cluster/cloud is an
explicit Experimental skip. Helm/OCI production images are out of 0.47
(0.51 `051-D`).

### Production trust

- Production `plugin_allowlist` covers k8s / spark-connect plugins.
- Production `Profile.resource_provider_allowlist` fails closed when a
  resource provider is selected (same shape as `schema_registry_allowlist`).
- Production rejects `MemoryScheduleStore` and missing shared durability.
- Network delivery does not imply exactly-once effects. Unknown remote commit
  states stay `unknown` and are never silently retried.

### Diagnostic families (preview until ship)

Do not overload `PMSCHED*` (`etlantic.scheduler/1` plugin analysis).

- `PMSVC*` — topology / role / production store
- `PMFIRE*` — schedule / firing / DST / misfire / catch-up
- `PMFED*` — remote negotiation / skew / fencing / unknown-commit
- `PMRES*` — resource providers / `resource_provider_allowlist`

## Consequences

- Adopters can keep Prefect, Airflow compile, and in-process `Pipeline.run`
  without adopting the optional service.
- The control-plane gateway remains optional; workers stay FastAPI-free.
- Kubernetes and Spark Connect extras may ship Experimental fakes without a
  live-cluster CI requirement.
- Remote hosts that cannot preserve 0.46 control-flow or stream evidence fail
  closed at negotiation rather than flattening the plan.

## Alternatives

| Alternative | Why rejected |
|---|---|
| Execute pipelines in FastAPI `BackgroundTasks` or lifespan | Violates ADR-018; accept is not execute |
| Merge timer service into `etlantic.scheduler/1` | Conflates in-process execute with durable cron leadership |
| Kubernetes/Spark SDK in core | Violates optional-package boundary; core stays engine-free |
| Make live Kind/Databricks a 0.47 blocker | Collides with 0.51 packs; 0.46 used fakes + live skips |
| Reuse CP3 execution lease for timer leadership | Duplicate ticks could advance next-fire from a non-leader |
| Silent remote flatten of map/branch/stream | Loses 0.46 child identity and compensation semantics |
| New message-broker package in 0.47 | Core must not embed a broker; polling is the reference |

## Compatibility

- Additive control-plane HTTP routes and CLI commands when implemented;
  existing `/v1/*` and `etlantic.scheduler/1` stay `/1`.
- No public API, package, or extra exists in this planning freeze.
- Official plugins remain on the 0.46 lockstep (`etlantic>=0.46.0,<0.47`)
  until 0.47 implementation begins.

## See also

- [IMPLEMENTATION_PLAN_0_47](../IMPLEMENTATION_PLAN_0_47.md)
- [EXIT_GATE_0_47](../EXIT_GATE_0_47.md)
- [FINDINGS_0_47](../FINDINGS_0_47.md)
- [IMPLEMENTATION_PLAN_0_51](../IMPLEMENTATION_PLAN_0_51.md)
- [ADR-018](ADR-018-DURABLE-SUBMISSION-AND-STATE.md)
- [ADR-021](ADR-021-OPTIMIZER-PASS-PROTOCOL.md)
- [ADR-022](ADR-022-DYNAMIC-CONTROL-AND-STREAMING.md)
