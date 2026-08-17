# Exit Gate 0.47 — FastAPI Scheduler/Runner Service and Remote Execution Federation

> **Status: Not started.** Planning freeze after ETLantic **0.46.0**. See
> [IMPLEMENTATION_PLAN_0_47](IMPLEMENTATION_PLAN_0_47.md) and
> [ADR-023](adr/ADR-023-SCHEDULER-SERVICE-AND-FEDERATION.md) (Proposed).
> Do not describe 0.47 surfaces as Available.

| Deliverable | Status |
|---|---|
| Planning: this exit gate / findings / ADR-023 | **Met** (Proposed ADR-023; freeze recorded) |
| What's New / migration (ship artifacts) | **Not started** |
| Schedule contracts (047-SC) | **Not started** |
| Schedule store (047-ST) | **Not started** |
| Scheduler service (047-SD) | **Not started** |
| Execution host (047-EH) | **Not started** |
| Gateway and CLI (047-API) | **Not started** |
| Durable providers (047-PR) | **Not started** |
| Negotiation (047-N) | **Not started** |
| Remote protocol (047-P) | **Not started** |
| Artifacts (047-A) | **Not started** |
| Placement (047-L) | **Not started** |
| Kubernetes provider (047-K) | **Not started** (Experimental fake; live skip `047-K-01`) |
| Spark Connect provider (047-S) | **Not started** (Experimental fake; live skip `047-S-01`) |
| Operations (047-O) | **Not started** |
| Lockstep version 0.47.0 | **Not started** |

## Supported claim (target freeze)

From [IMPLEMENTATION_PLAN_0_47](IMPLEMENTATION_PLAN_0_47.md). Claims only;
nothing below is Available until this gate records Met evidence.

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
| 1 | 047-SC schedule contracts + fake-clock DST/misfire/catch-up | Pass | **Not started** |
| 2 | 047-ST ScheduleStore + leader lease distinct from CP3 | Pass | **Not started** |
| 3 | 047-SD scheduler service dual-replica one-firing | Pass | **Not started** |
| 4 | 047-EH execution host wraps CP3; no FastAPI import | Pass | **Not started** |
| 5 | 047-API FastAPI/CLI frozen names; authz/non-enumeration | Pass | **Not started** |
| 6 | 047-PR SQLModel `004` + memory; polling wake-up | Pass | **Not started** |
| 7 | 047-N negotiation + 0.46 dyn/stream caps or reject | Pass | **Not started** |
| 8 | 047-P remote protocol state machine + fault injection | Pass | **Not started** |
| 9 | 047-A signed-plan/artifact fakes; no secrets in artifacts | Pass | **Not started** |
| 10 | 047-L placement rejects before transfer | Pass | **Not started** |
| 11 | 047-K `etlantic-k8s` Experimental FakeKubernetes | Pass | **Not started** |
| 12 | 047-S `etlantic-spark-connect` Experimental fake | Pass | **Not started** |
| 13 | 047-O split-role ops/runbooks (no live cluster required) | Pass | **Not started** |
| 14 | Two replicas → one durable run per logical firing | Pass | **Not started** |
| 15 | Unknown commit never auto-retry; worker-loss explicit | Pass | **Not started** |
| 16 | Production allowlists fail closed; memory store rejected | Pass | **Not started** |
| 17 | Existing `Pipeline.run`/`arun`, LocalScheduler, Prefect, Airflow compile unchanged | Pass | **Not started** |
| 18 | No unresolved P0 in [FINDINGS_0_47](FINDINGS_0_47.md) | 0 | **Not started** |
| 19 | Release record: supported vs experimental | Pass | **Not started** |

## Evidence map

| Gate item | Evidence |
|---|---|
| Implementation plan | [IMPLEMENTATION_PLAN_0_47](IMPLEMENTATION_PLAN_0_47.md) |
| ADR | [ADR-023](adr/ADR-023-SCHEDULER-SERVICE-AND-FEDERATION.md) (Proposed) |
| Findings | [FINDINGS_0_47](FINDINGS_0_47.md) |
| Conformance JSON | Not written in this freeze |
| Migration | Future `MIGRATION_0_46_TO_0_47` (do not publish as Available) |
| What's New | Future `WHATS_NEW_0_47` (do not publish as Available) |
| Tests | Not started |
| Docs / agents | `uv run python scripts/check_docs.py`; `uv run python scripts/check_agent_guidance.py` |

## Go / no-go

**No-go — planning freeze only.** Implementation must not begin until this
record exists and ADR-023 is the ownership freeze. Live Kind (`047-K-01`) and
live Spark Connect (`047-S-01`) remain explicitly deferred Experimental skips
and must not block the later 0.47 gate. Do not describe scheduler/worker
commands, schedule HTTP routes, `etlantic-k8s`, or `etlantic-spark-connect` as
Available.
