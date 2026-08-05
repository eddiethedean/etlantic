# Application Integration (0.39)

> **Status: Available in ETLantic 0.45.0.** Framework-agnostic authoring contract
> plus the optional FastAPI package dual surface (CP1 primary; sync reference
> demo secondary).

## Artifacts

| Artifact | Role |
|---|---|
| `PipelineDefinition` / `etlantic.pipeline/1` | Authoring-complete document |
| Authoring catalog | Discoverable components + UI metadata |
| `EditCommand` | Immutable graph edits |
| Diagnostics with document paths | Highlight fields/nodes/edges |
| Service facade (`etlantic.service`) | Transport-neutral request/response ops |

## Required host responsibilities

- Persist definitions and concurrency tokens
- Supply `PolicyContext` (tenant, profile, allowed actions/plugins)
- Register native implementation callables before run
- Own authn/authz, queues, and durable job storage

## Service facade (in-process)

```python
import etlantic as etl
from etlantic.service import AuthoringService, PolicyContext

service = AuthoringService(
    policy=PolicyContext(
        tenant="acme",
        environment="development",
        profile="development",
        allowed_actions=("catalog", "validate", "plan", "edit", "run"),
    )
)

service.put_definition("demo", document)
service.validate("demo")
service.plan("demo")
# submit_run is synchronous on this reference facade — it completes before return
job = service.submit_run("demo")
```

## FastAPI dual surface

Install the optional package (same minor as core):

```bash
python -m pip install 'etlantic-fastapi==0.45.0'
# or: python -m pip install 'etlantic[fastapi]==0.45.0'
```

| Surface | Entry points | Role |
|---|---|---|
| **CP1 (primary)** | `ETLanticAPI`, `include_router`, `create_app` | Embeddable, authz’d, durable-accept HTTP API + SSE |
| **Reference (non-CP)** | `create_reference_app` | Sync `AuthoringService` demo only |

### CP1 control plane (primary)

Adopter guide: [Control plane (CP1)](../06_EXECUTION/CONTROL_PLANE.md).
Contracts: [ADR-016](../11_DEVELOPMENT/adr/ADR-016-CONTROL-PLANE-IDENTITY.md).

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
    membership_context_factory,
    principal_from_header,
)

api = ETLanticAPI(
    authorizer=MemoryAuthorizer(),
    definitions=MemoryDefinitionRepository(),
    submissions=MemorySubmissionStore(),
    events=MemoryEventStore(),
    context_factory=membership_context_factory(
        {"alice": ("tenant-a", "ws-1", "development", "default")}
    ),
    principal_dependency=principal_from_header,
)
app = create_app(api)
# Or: include_router(host_app, api) when the host owns lifespan/handlers
```

CP1 highlights:

- Durable **202** accept; never FastAPI `BackgroundTasks` for heavy work
- Authz before lookup; cross-tenant → opaque **404**
- SSE resume; unknown cursor → **410**
- `GET /health` liveness vs `GET /ready` (**503** when stores missing)

### Reference app (non-CP sync demo)

```python
from etlantic_fastapi import create_reference_app

app = create_reference_app()
# uvicorn etlantic_fastapi:create_reference_app --factory
```

`create_reference_app` is a proof adapter for the sync authoring facade. Runs
complete before return; `cancel_run` reports in-flight cancel unsupported. It is
**not** the production control API and must not be confused with CP1.

## Related

- [Control plane (CP1)](../06_EXECUTION/CONTROL_PLANE.md)
- [etlantic-fastapi API](../10_REFERENCE/api_optional/etlantic_fastapi.md)
- [Programmatic authoring](../05_PIPELINES/PROGRAMMATIC_AUTHORING.md)
- [API — Authoring](../10_REFERENCE/API_AUTHORING.md) (`etlantic.authoring`, `etlantic.service`)
- [ADR-016](../11_DEVELOPMENT/adr/ADR-016-CONTROL-PLANE-IDENTITY.md)
