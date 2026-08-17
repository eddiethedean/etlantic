# Exit Gate 0.47 — FastAPI Scheduler/Runner Service and Remote Execution Federation

> **Status: Met — gate-ready for tag/publish (no tag in this commit).** ETLantic
> **0.47.0** closes the scheduler/runner service and remote-federation freeze
> with Experimental FakeKubernetes / FakeSparkConnect. Live Kind (`047-K-01`)
> and live Databricks/EMR/Spark Connect (`047-S-01`) remain skipped. See
> [IMPLEMENTATION_PLAN_0_47](IMPLEMENTATION_PLAN_0_47.md) and
> [ADR-023](adr/ADR-023-SCHEDULER-SERVICE-AND-FEDERATION.md) (Accepted).

| Deliverable | Status |
|---|---|
| Planning: this exit gate / findings / ADR-023 | **Met** (Accepted ADR-023) |
| What's New / migration (ship artifacts) | **Met** |
| Schedule contracts (047-SC) | **Met** |
| Schedule store (047-ST) | **Met** |
| Scheduler service (047-SD) | **Met** |
| Execution host (047-EH) | **Met** |
| Gateway and CLI (047-API) | **Met** |
| Durable providers (047-PR) | **Met** |
| Negotiation (047-N) | **Met** |
| Remote protocol (047-P) | **Met** |
| Artifacts (047-A) | **Met** |
| Placement (047-L) | **Met** |
| Kubernetes provider (047-K) | **Met** (Experimental fake; live skip `047-K-01`) |
| Spark Connect provider (047-S) | **Met** (Experimental fake; live skip `047-S-01`) |
| Operations (047-O) | **Met** (in-process; no live cluster) |
| Lockstep version 0.47.0 | **Met** (in-tree; no git tag) |

## Supported claim (target freeze)

From [IMPLEMENTATION_PLAN_0_47](IMPLEMENTATION_PLAN_0_47.md).

| Surface | Target | Notes |
|---|---|---|
| Schedule contracts + fake-clock DST/misfire/catch-up | **Supported** (core) | Deterministic |
| `ScheduleStore` + memory test provider | **Supported** (core tests) | Production rejects memory |
| Scheduler + execution-host loops | **Supported** (core CLI) | Split-role required in production |
| SQLModel schedule provider + `004` | **Supported** (`etlantic-sqlmodel`) | Optional package |
| FastAPI/CLI schedule surfaces | **Supported** (`etlantic-fastapi`) | Gateway only |
| In-process fake remote host + signed-plan/artifact fakes | **Supported** (core tests) | No network credentials |
| Wake-up adapter (broker-style) | **Experimental** | Protocol + polling fallback |
| Kubernetes reference (`etlantic-k8s`) | **Experimental** | `FakeKubernetes`; live Kind skip `047-K-01` |
| Spark Connect (`etlantic-spark-connect`) | **Experimental** | Fake; live Databricks/EMR skip `047-S-01` |
| Helm/OCI production images | **Out of 0.47** | 0.51 `051-D` |

## Quantified exit scorecard

From [IMPLEMENTATION_PLAN_0_47](IMPLEMENTATION_PLAN_0_47.md):

| # | Measure | Required | Current |
|---|---|---:|---|
| 1 | 047-SC schedule contracts + fake-clock DST/misfire/catch-up | Pass | **Met** |
| 2 | 047-ST ScheduleStore + leader lease distinct from CP3 | Pass | **Met** |
| 3 | 047-SD scheduler service dual-replica one-firing | Pass | **Met** |
| 4 | 047-EH execution host wraps CP3; no FastAPI import | Pass | **Met** |
| 5 | 047-API FastAPI/CLI frozen names; authz/non-enumeration | Pass | **Met** |
| 6 | 047-PR SQLModel `004` + memory; polling wake-up | Pass | **Met** |
| 7 | 047-N negotiation + 0.46 dyn/stream caps or reject | Pass | **Met** |
| 8 | 047-P remote protocol state machine + fault injection | Pass | **Met** |
| 9 | 047-A signed-plan/artifact fakes; no secrets in artifacts | Pass | **Met** |
| 10 | 047-L placement rejects before transfer | Pass | **Met** |
| 11 | 047-K `etlantic-k8s` Experimental FakeKubernetes | Pass | **Met** (live skip) |
| 12 | 047-S `etlantic-spark-connect` Experimental fake | Pass | **Met** (live skip) |
| 13 | 047-O split-role ops/runbooks (no live cluster required) | Pass | **Met** |
| 14 | Two replicas → one durable run per logical firing | Pass | **Met** |
| 15 | Unknown commit never auto-retry; worker-loss explicit | Pass | **Met** |
| 16 | Production allowlists fail closed; memory store rejected | Pass | **Met** |
| 17 | Existing `Pipeline.run`/`arun`, LocalScheduler, Prefect, Airflow compile unchanged | Pass | **Met** |
| 18 | No unresolved P0 in [FINDINGS_0_47](FINDINGS_0_47.md) | 0 | **Met** |
| 19 | Release record: supported vs experimental | Pass | **Met** |

## Evidence map

| Gate item | Evidence |
|---|---|
| Implementation plan | [IMPLEMENTATION_PLAN_0_47](IMPLEMENTATION_PLAN_0_47.md) |
| ADR | [ADR-023](adr/ADR-023-SCHEDULER-SERVICE-AND-FEDERATION.md) (Accepted) |
| Findings | [FINDINGS_0_47](FINDINGS_0_47.md) |
| Conformance JSON | [schedule](schedule_conformance_0_47.json), [federation](federation_conformance_0_47.json), [k8s](k8s_conformance_0_47.json), [spark-connect](spark_connect_conformance_0_47.json) |
| Migration | [MIGRATION_0_46_TO_0_47](MIGRATION_0_46_TO_0_47.md) |
| What's New | [WHATS_NEW_0_47](../01_GETTING_STARTED/WHATS_NEW_0_47.md) |
| OpenAPI | `tests/fastapi/openapi_cp1_snapshot.json` |
| Capacity | [capacity_envelope_0_47.json](capacity_envelope_0_47.json) |
