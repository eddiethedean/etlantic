# Application Integration Contract (0.25)

> **Status: Available in ETLantic 0.35.0.**

Framework-agnostic contract for visual builders and host applications.

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

# Put a definition document (dict), then validate / plan
service.put_definition("demo", document)
service.validate("demo")
service.plan("demo")
# submit_run is synchronous on this reference facade — it completes before return
job = service.submit_run("demo")
# cancel_run reports that in-flight cancel is unsupported on the sync reference
```

## FastAPI reference adapter

Install the optional package (same minor as core):

```bash
python -m pip install 'etlantic-fastapi==0.35.0'
# or: python -m pip install 'etlantic[fastapi]==0.35.0'
```

Contributor checkout (editable monorepo):

```bash
uv sync --extra fastapi
```

```python
from etlantic_fastapi import create_reference_app

app = create_reference_app()
# uvicorn etlantic_fastapi:create_reference_app --factory
```

`etlantic-fastapi` publishes OpenAPI from the public schemas. It is a proof
adapter, **not** the production 0.40–0.44 control API. Runs are **synchronous**:
`submit_run` completes before returning; `cancel_run` reports that in-flight
cancel is unsupported on this reference adapter.

## Related

- [Programmatic authoring](../05_PIPELINES/PROGRAMMATIC_AUTHORING.md)
- [API — Authoring](../10_REFERENCE/API_AUTHORING.md) (`etlantic.authoring`, `etlantic.service`)
- Control-plane design and remaining work:
  [FastAPI Integration Plan](../11_DEVELOPMENT/FASTAPI_INTEGRATION_PLAN.md)
