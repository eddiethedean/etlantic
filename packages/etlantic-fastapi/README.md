# etlantic-fastapi

Optional FastAPI adapter for ETLantic **0.40.0**. Use **CP1/CP2** (`ETLanticAPI`)
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
pip install 'etlantic-fastapi==0.40.0'
# keep core on the same pin:
# pip install 'etlantic==0.40.0'
```

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

### Auth adapters

- Inject an app-defined principal dependency (`principal_dependency=`).
- OAuth2/OIDC: validate tokens in the host, then map claims with
  `oauth2_oidc_principal_hook` (placeholder; no bundled IdP client).

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
