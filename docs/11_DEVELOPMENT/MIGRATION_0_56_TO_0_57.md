---
title: ETLantic 0.56 to 0.57 Migration
description: Move managed backend construction and schedule commands out of the FastAPI adapter.
---

# Migration from 0.56 to 0.57

0.57 adds a transport-independent managed backend and schedule application
service, explicit scheduler occurrence collaborators, provider-owned schema
inspection, and runtime role status/drain contracts. The 0.57.0 release
candidate preserves the SQLModel migration head; it adds no database migration
or persisted-format change.

## Database preparation

Continue applying the existing `etlantic-sqlmodel` migration chain as an
operator-owned deployment step. The managed backend performs bounded,
read-only compatibility inspection during construction. A fresh, behind,
partial, corrupt, unknown, or unreachable schema fails closed. Construction
does not create tables, advance a migration marker, or commit a migration.

```python
from sqlalchemy import create_engine
from etlantic_sqlmodel.migrations import upgrade

engine = create_engine(database_url)
try:
    upgrade(engine)  # explicit operator migration step
finally:
    engine.dispose()
```

Deployments that already use migration head
`014_cp1_complete_principal_idempotency_0_56` require no database migration
for 0.57. Use `etlantic_sqlmodel.schema_requirements()` to read the provider's
structural requirements and `etlantic_sqlmodel.inspect_schema(engine)` to
inspect a specific database. These results describe schema compatibility, not
database topology or deployment policy.

Install the matching core release with the provider package:

```bash
python -m pip install "etlantic>=0.57.0" "etlantic-sqlmodel>=0.57.0"
```

## Construct a headless backend

Applications that previously assembled the standard managed graph through
`ETLanticAPI.enable_managed_execution()` can construct it without FastAPI:

```python
from etlantic_sqlmodel import SQLModelBackendConfig, create_managed_backend

backend = create_managed_backend(
    SQLModelBackendConfig(
        database_url=database_url,
        store_id="control-plane",
        profile=profile,
    ),
    authorizer=authorizer,
)
try:
    service = backend.managed_service
    schedule_service = backend.schedule_service
finally:
    backend.close()
```

The consumer still owns authentication and trusted `ControlPlaneContext`
creation. Pass that context to authorized service operations; the backend does
not authenticate caller-supplied principals. A factory-created engine belongs
to the backend. An injected engine remains caller-owned. Close the backend only
after consumer-owned execution threads and dispatched work have settled.

FastAPI applications can adapt the same backend with
`etlantic_fastapi.adapt_managed_backend(backend, context_factory=...)`. The
adapter derives request identity and translates HTTP requests and responses;
the core schedule service remains shared.

## Schedule commands and scheduler construction

Use `backend.schedule_service` for create, amend, pause, resume, preview,
trigger, get, filtered list, and firing reads. Amendment requires the current
`expected_revision_id`. Authorization and workload binding happen before
reference validation or persistence. Existing schedule HTTP routes delegate to
this service and retain their response shapes and operation IDs.

Use `backend.create_scheduler(owner_id=...)` for the standard managed scheduler.
It supplies the shared schedule and durable stores and the explicit occurrence
prepare/submit/recover collaborator. `owner_id` must be a stable, unique runtime
identity. Advanced low-level `SchedulerService` construction must provide the
complete occurrence collaborator; callback-only operation is an explicit
reference path and cannot claim managed recovery.

## Runtime supervision

Scheduler, run-worker, and action-worker handles expose `status()` and
`request_drain()`. Status is a local snapshot, not a liveness or workload
health probe. New roles start with unknown prerequisites. Consumers own probe
transport, freshness policy, process signals, tick threads, grace periods, and
joining. Drain is nonblocking and prevents later claims; already-dispatched
work remains in flight until it finishes or is recovered under existing
fencing rules. Call `backend.close()` after roles settle.

## Compatibility and release boundary

FastAPI constructor and app-lifespan facades remain available. The legacy
standard scheduler constructor continues to work through the same provider
graph. The implicit bound-method recovery inference is removed from managed
construction; supply an explicit occurrence service in low-level integrations.
There is no new exactly-once external-effect guarantee and no cross-store atomic
transaction.

See the [0.57 implementation plan](IMPLEMENTATION_PLAN_0_57.md),
[exit gate](EXIT_GATE_0_57.md), and
[release notes](../01_GETTING_STARTED/WHATS_NEW_0_57.md) for qualification
limits and final candidate evidence.
