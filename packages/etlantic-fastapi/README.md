# etlantic-fastapi

Optional FastAPI adapter for ETLantic **0.56.0**. Use **CP1/CP2** (`ETLanticAPI`)
when you need an embeddable, authz’d, durable-accept control-plane HTTP API.
Use **`create_reference_app`** only for the thin non-CP authoring demo — it is
not the control plane. CP2 is incubation, **not** multi-tenant GA (0.43).

## Two surfaces

| Surface | Entry point | Role |
|---|---|---|
| **CP1 control plane** | `ETLanticAPI`, `include_router`, `create_app` | Embeddable, authz’d, durable-accept HTTP API |
| **Reference (non-CP)** | `create_reference_app` | Sync `AuthoringService` demo only |

Do not treat path/header tenant strings as authority —
`ControlPlaneContext` is server-derived.

Heavy pipeline work must **never** use FastAPI `BackgroundTasks`. Submit returns
`202` only after durable acceptance in an injected store. Optional worker
pollers observe accepted jobs outside the request.

## Install

```bash
pip install 'etlantic-fastapi==0.56.0'
# keep core on the same pin:
# pip install 'etlantic==0.56.0'
```

## Standard SQLModel-backed managed backend

Install the managed extra and apply versioned migrations before creating the
backend. The constructor checks the recorded migration version and fails
closed when the schema is missing or behind. It creates one SQLAlchemy engine
for the SQLModel control-plane stores and owns that engine for the backend
lifetime. The required migration head is
`013_durable_submission_scope_backfill_0_56`, which includes durable
scope-isolated run reports, expiring idempotent lifecycle-event tombstones,
immutable input resources, and indexed result-retention metadata.

```bash
pip install 'etlantic-fastapi[managed]==0.56.0'
```

The migration is an explicit deployment step. Use the public
`etlantic_sqlmodel.migrations.upgrade` function in your deployment command;
the application constructor never mutates the schema:

```python
from sqlalchemy import create_engine
from etlantic_sqlmodel.migrations import upgrade

engine = create_engine(database_url)
try:
    upgrade(engine)
finally:
    engine.dispose()
```

Event idempotency tombstones expire after the configured
`event_idempotency_retention_seconds` window (90 days by default). A delayed
publisher is deduplicated during that window; after expiry, the same key may
append a new event. Expired tombstones are removed in bounded batches during
event writes and history reads.

For a standalone HTTP process, let the app own the connection pool:

```python
from etlantic_fastapi import ManagedBackendConfig, create_managed_app

app = create_managed_app(
    ManagedBackendConfig(
        database_url=database_url,
        store_id="control-plane",
        profile=profile,
    ),
    authorizer=host_authorizer,
    context_factory=host_context_factory,
)
```

`ManagedBackendConfig.database_url` and engine options are omitted from repr.
Do not log the original URL. At startup the app checks store readiness; on
shutdown or partial startup failure it disposes its pool. Accepted definitions
and durable work remain stored for another process to recover. For headless
commands, call `create_managed_backend(...)`, use `backend.api.managed_service`
or its stores, and call `backend.close()` when the owner exits. That constructor
uses the same store composition and migration checks without creating a
synthetic HTTP request.

Run ETL in a separate worker process with the same migrated backend settings:

```python
backend = create_managed_backend(config, authorizer=worker_authorizer,
                                 context_factory=worker_context_factory)
worker = backend.create_execution_host(owner_id="etl-worker-1")
try:
    worker.tick(trusted_worker_context)
finally:
    backend.close()
```

`create_execution_host` installs the packaged runtime adapter and uses the
backend's tenant/workspace-scoped SQLModel report store. Runtime reports remain
queryable from another backend process after worker restart. Local reference
hosts can continue to use the file report store by constructing
`ExecutionHost` directly.

The worker uses the profile configured on `ManagedBackendConfig`. It compares
that profile's plan-safe settings with the profile snapshot accepted for each
run and rejects profile drift before executing effects. Runtime-only I/O roots
remain deployment configuration and are supplied by that same worker profile;
absolute host paths are not stored in the accepted plan.

Durable run-output retention is opt-in. Set
`ManagedBackendConfig.run_artifact_retention_seconds` to a positive number of
seconds to enable it; `None` leaves durable output files available indefinitely.
Each execution-worker tick processes a bounded cleanup batch, limited by
`run_artifact_cleanup_batch_size` (1–1000). Cleanup uses the run's end time,
keeps report history, records artifact availability and a separate cleanup
state in report metadata, and resumes `running` or `failed` cleanup on later
ticks. Headless operators can run the same pass with
`backend.cleanup_expired_run_artifacts(trusted_worker_context)`. The context
must be host-derived and scoped to the tenant/workspace being cleaned.

## Control-plane usage

```python
from etlantic.control_plane import (
    MemoryAuthorizer,
    MemoryDefinitionRepository,
    MemoryEventStore,
    MemorySubmissionStore,
)
from etlantic_fastapi import (
    ETLanticAPI,
    create_app,
    include_router,
    membership_context_factory,
    principal_from_header,
)

authorizer = MemoryAuthorizer()
definitions = MemoryDefinitionRepository()
submissions = MemorySubmissionStore()
events = MemoryEventStore()

api = ETLanticAPI(
    authorizer=authorizer,
    definitions=definitions,
    submissions=submissions,
    events=events,
    context_factory=membership_context_factory(
        {
            "alice": ("tenant-a", "ws-1", "development", "default"),
        }
    ),
    principal_dependency=principal_from_header,
)

# Standalone (installs Problem Details handlers + optional lifespan)
app = create_app(api)

# Or embed without owning host lifespan / middleware / exception handlers:
# from fastapi import FastAPI
# host = FastAPI()
# include_router(host, api)  # host must register Problem Details handlers
#                            # (create_app installs them; include_router does not)
```

Managed services expose `list_run_events(ctx, run_id, cursor=..., limit=...)`
for headless consumers. HTTP clients can use
`GET /v1/runs/{run_id}/events/history` for the same bounded page contract;
`next_cursor` resumes through the scoped workspace event log, while returned
items are filtered to the requested run. The existing
`GET /v1/runs/{run_id}/events` endpoint streams history as server-sent events.
Unknown or expired cursors fail with `410 Gone`.

`MemoryEventStore` and `SqlModelEventStore` also implement the public
`EventRetentionStore` protocol. An operator can call
`prune_before_sequence(ctx, before_sequence)` to remove older rows while
preserving the latest sequence anchor. Keyed-event digests remain as tombstones
for the configured idempotency window: a retry for a pruned key returns
`410 Gone` instead of publishing a duplicate, and changed content returns
`409 Conflict`. After expiry, the key can be accepted again. The managed
backend enforces a per-tenant/workspace event window on append and history
reads. Its default is
100,000 retained events per scope; set
`ManagedBackendConfig.event_retention_max_events_per_scope` to a smaller or
larger positive integer for the deployment. History outside the window returns
`410 Gone`, while sequence numbers remain intact.
Raw event-store constructors accept the same `max_events_per_scope` setting;
`None` leaves automatic count retention disabled for those explicitly composed
stores. `ManagedBackendConfig.event_idempotency_retention_seconds` defaults to
90 days and controls how long delayed retries are deduplicated. Both event
stores remove expired tombstones in bounded batches during event writes and
history reads; operators can also call
`prune_expired_idempotency(ctx, limit=...)`. Raw event-store constructors accept
the same `idempotency_retention_seconds` setting. Migration 012 assigns existing
tombstones the 90-day default expiry; newer tombstones use the configured
window.

### Managed rerun and replay commands

The managed HTTP adapter exposes `POST /v1/runs/{run_id}/rerun` and
`POST /v1/runs/{run_id}/replay`; both require a new `Idempotency-Key` and accept
a child run from the parent's verified, immutable execution envelope. The
parent must be terminal. Rerun preserves its accepted run intent; replay marks
the intent as `replay` and executes the full snapshot from the start. Replay
does not claim checkpoint-resume semantics. Both commands can repeat a
committed effect by explicit request; an unknown or pending effect must be
reconciled first. Each child records parent run/submission lineage and is
recovered through the same durable worker path. `ManagedApplicationService`
provides matching headless `rerun_run(...)` and `replay_run(...)` commands.
Rerun and replay require `run.rerun` and `run.replay` authorization
respectively, and appear in state-aware run-action queries.

Managed workers reconstruct a temporary `TrustedExecutionScope` from the
server-derived `ControlPlaneContext` and pass it to secret providers and
storage/connector calls. Configure `resource_owners` on
`membership_context_factory(...)` (or `resource_owner_id` on
`static_context_factory(...)`) when providers need a distinct owner boundary;
these values come from host configuration, never request bodies. The runtime
secret cache is partitioned by principal, tenant, workspace, environment,
security domain and resource owner. The scope and resolved secret values are
not written to the accepted execution envelope.

### Auth adapters

- Inject an app-defined principal dependency (`principal_dependency=`).
- OAuth2/OIDC: validate tokens in the host, then map claims with
  `oauth2_oidc_principal_hook` (placeholder; no bundled IdP client).

### Collection visibility and safe validation

Collection authorization runs before repository access. Concrete item denials
are filtered using the collection's action, independently of direct-read
permission, before serialization and existing limits. Authorization-service
failure aborts the response; it does not return partially authorized results.
Scope remains server-derived; workspace directories intentionally list within
the caller's tenant and still check each concrete workspace.

Every control-plane route uses public `RedactedValidationRoute`, including
schedule and agent routes. Both `create_app` and `include_router` reject invalid
body/query/header input with HTTP 422 and this fixed `application/json` envelope:

```json
{"detail": [{"type": "request_validation", "loc": [], "msg": "Invalid request"}]}
```

Invalid input, locations, messages, context and request bodies are neither
rendered nor logged by the adapter. Paths, operation IDs and request models
are unchanged. This route-local strategy does not install or replace host
exception handlers, so unrelated host routes keep their own validation behavior.
`install_exception_handlers` continues to register only `ControlPlaneError`.

Public `request_validation_error_handler(request, exc)` also returns the same
envelope for hosts that explicitly want application-wide redaction:

```python
from fastapi.exceptions import RequestValidationError
from etlantic_fastapi import request_validation_error_handler

host.add_exception_handler(RequestValidationError, request_validation_error_handler)
```

Explicit application-wide registration replaces the handler for that exception
key under FastAPI's normal semantics and affects unrelated host routes. To
retain unrelated behavior, use `include_router` without registering this global
handler. Host middleware, access logging and identity dependencies own their
logging policy; avoid logging raw bodies, credentials or sensitive query URLs.

### Operability probes

| Endpoint | Role | Status when stores missing |
|---|---|---|
| `GET /health` | Liveness only (process up) | Always **200** |
| `GET /ready` | Readiness (injected stores present) | **503** with `status=not_ready` |

### Validate / plan (Experimental preview)

`POST .../validate` and `POST .../plan` use the profile injected on
`ETLanticAPI.profile` (default `"development"`).

* Non-production `security_mode` → Experimental structural preview
  (`verify=False` path); responses include `metadata.label = "Experimental"`.
* Production-like `security_mode` → `verify=True` and real validate/plan where
  possible. Exception messages are always redacted in diagnostics.

### Resumable SSE (`GET /v1/runs/{run_id}/events`)

Streams ordered `etlantic.control_plane.event/1` envelopes as
`text/event-stream`. Resume with the opaque `cursor` query parameter or the
`Last-Event-ID` header (query wins when both are set). SSE `id:` fields are
resume cursors (`etlantic.control_plane.sse_cursor/1`).

**History fallback (CP1):** unknown or expired cursors fail closed with
**HTTP 410 Gone** (`PMCP410`) and
`extensions.hint = omit_cursor_or_last_event_id`. Reconnect **without** a
cursor / `Last-Event-ID` to replay from the beginning. CP1 does **not**
silently skip or invent a mid-stream position.

Authorization (`run.events`) runs before existence lookup; cross-tenant runs
map to opaque **404**; in-scope action deny maps to **403**. Default
`follow=false` emits matching history then closes; `follow=true` keeps
polling with a hard cap (default **100** polls / **60** seconds) so CP1 never
blocks unbounded.

Optional WebSocket adapters are experimental and **not** required for the
0.39 exit gate.

### Landing-zone watch submitter (outside core)

Continuous directory watching is a **submitter**, not a third `Extract` kind
and must not live under `src/etlantic/`. Use
`etlantic_fastapi.landing_sensor.LandingWatchSubmitter` (stdlib polling; no
`watchdog` required) or `examples/landing_zone_watch_submitter.py`. Submitters
call durable `POST /v1/definitions/{id}/runs` with 0.38 `local-files`-style
binding refs (`root_ref`, `glob`, `mode`, …) and must **never** embed file
bytes in plans or submit bodies.

### Registry admin (`/v1/registry`, CP2)

Admin directory and revision routes live under **`/v1/registry`** (not
`/v1/admin`) so host-level admin surfaces stay free. Inject
`ETLanticAPI(registry=...)` (memory or SQLModel). Authz runs before lookup;
suspended tenants/workspaces fail closed. Stable operationIds use the
`cp_registry_*` prefix.

To back existing **`/v1/definitions*`** paths with registry revisions (same
operationIds), use `ETLanticAPI.with_registry_definitions(...)` or
`create_app(..., registry=..., definitions_backend="registry")`.
`MemoryDefinitionRepository` remains the default for existing tests.

CLI parity stub (lists tenants / promote-suspend conformance without extending
the public CLI yet):

```bash
uv run python scripts/check_registry_conformance.py --fake
```

## Non-CP reference app

```python
from etlantic_fastapi import create_reference_app

app = create_reference_app()
```

Use only for local evaluation of the sync authoring facade. It is not the
control plane.

## Links

[Documentation](https://etlantic.readthedocs.io/) ·
[Source](https://github.com/eddiethedean/etlantic/tree/main/packages/etlantic-fastapi) ·
[Issues](https://github.com/eddiethedean/etlantic/issues)
