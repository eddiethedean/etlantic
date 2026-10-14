# Managed Prefect on Posit Connect

!!! warning "Status: Available in ETLantic 0.59.0 Beta (deployment recipe only)"
    The managed Prefect path has not been live-qualified on Posit Connect. This
    guide describes a host composition; it does not add Connect to ETLantic's
    supported hosting matrix.

This layout runs the FastAPI control plane as a Connect ASGI app, while a
separately supervised Prefect dispatcher and Process worker handle execution.
The API accepts durable work into the shared PostgreSQL control-plane store.
The dispatcher creates Prefect flow runs for the pinned route, and the worker
executes the accepted ETLantic envelope.

## Prepare the route and database

Build and review a `ManagedDeploymentSpec`, register it with
`PrefectDeploymentRegistrar`, and retain the returned binding. Registration
and worker setup are described in the [`etlantic-prefect` guide](https://github.com/eddiethedean/etlantic/blob/main/packages/etlantic-prefect/README.md).
Configure the API host with that exact `binding.execution_route`. The route is
trusted deployment configuration: callers cannot select it, and accepted
submissions stay pinned if the API's default route changes later.

Apply the SQLModel migrations as a separate deployment step before starting
the API. The API and dispatcher must use the same database, `store_id`, and
compatible server-derived tenant/workspace context. Give runtime processes
only the database grants required for their role; keep schema changes with the
migration identity. Store the database URL and any credentials in the hosting
environment's secret settings. Do not put them in source files, deployment
manifests, logs, or the ETLantic route value.

## Compose the FastAPI app

The host application supplies its own authorization, principal-to-scope
mapping, and production profile. These are deliberately deployment-owned; do
not derive tenant, workspace, security domain, database URL, or execution
route from request data.

```python
# connect_app.py
import os

from etlantic_fastapi import ManagedBackendConfig, create_managed_app

from deployment_auth import build_authorizer, build_context_factory
from deployment_profile import build_profile

app = create_managed_app(
    ManagedBackendConfig(
        database_url=os.environ["ETLANTIC_CP_DATABASE_URL"],
        store_id="production-control-plane",
        profile=build_profile(),
        execution_route=os.environ["ETLANTIC_PREFECT_EXECUTION_ROUTE"],
    ),
    authorizer=build_authorizer(),
    context_factory=build_context_factory(),
)
```

Set `ETLANTIC_PREFECT_EXECUTION_ROUTE` from the reviewed deployment binding,
not from an operator-supplied request or an unverified deployment name. Keep
the API's production `Profile` plugin and resource-provider allowlists aligned
with the separately installed worker environment. The app constructor checks
schema readiness and owns its connection pool; it does not run migrations.

## Deploy the API

Pin ETLantic packages on the same release line in the app's dependency file.
For the 0.59.0 release, the managed adapter installation is:

```text
etlantic==0.59.0
etlantic-fastapi[managed]==0.59.0
```

Install and configure `rsconnect-python` in the publishing environment, then
deploy the app directory with its explicit module and object entrypoint:

```bash
rsconnect deploy fastapi --entrypoint connect_app:app ./connect-api
```

Posit documents `rsconnect deploy fastapi` for ASGI apps and the
`module:object` entrypoint convention in its [FastAPI guide](https://docs.posit.co/connect/user/fastapi/)
and [Python publishing guide](https://docs.posit.co/connect/user/publishing-cli-apps/).
Use the publishing CLI version approved by the Connect operator.

## Run dispatcher and worker separately

Run the Prefect dispatcher under an external supervisor with the trusted
environment and shared backend configuration. Run the registered Process
worker in its own deployment or service using the exact binding injected by
`PrefectDeploymentRegistrar`. Keep both roles alive independently of API
instances and Connect request lifetimes. Do not start a dispatcher loop,
Prefect flow, or ETL worker from a FastAPI request handler or app lifespan.

The dispatcher needs network access to the Prefect API and control-plane
database. Process workers need Prefect server access, the shared control-plane
database, and access to the configured source, sink, resources, and artifact
storage. If the API enables routes that project Prefect state or request remote
cancellation, it also needs the corresponding Prefect API access. Every role
that handles production work must receive credentials through its own trusted
secret configuration and must use the registered versioned deployment.

## Qualification boundary

Before relying on this hosting layout in a deployment, verify app startup and
shutdown, database pool limits, proxy/authentication behavior, environment and
secret rotation, network paths, and recovery while Connect or a separately
supervised dispatcher/worker restarts. These checks are deployment-specific
operational guidance, not phase 0.58 evidence requirements. Phase 0.58
qualification applies only to the declared self-hosted support profile;
Posit Connect remains a documented recipe with no hosting support claim.
