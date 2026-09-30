---
title: ETLantic 0.56 Isolated Connector Action Workers
description: Public action job contract, handler registration, and bounded execution behavior.
---

# Isolated connector action workers

The managed backend accepts the `connector.test`, `connector.catalog`,
`connector.schema.inspect`, and `connector.preflight` actions as durable jobs.
HTTP only validates and authorizes a typed request, stores the job, and returns
its receipt. A separately created `ActionExecutionHost` claims the job, rebuilds
the accepted caller scope, checks action and object permissions again, and
executes an asynchronous handler under the recorded deadline.

```python
from etlantic_fastapi import ManagedBackendConfig
from etlantic.runtime import ActionExecutionHost, ActionHandler

async def test_connection(ctx, request):
    # Resolve connection_id from a server-side, owner-scoped connection store.
    # The request never contains a password, token, DSN, or binding document.
    ...

config = ManagedBackendConfig(
    database_url=managed_database_url,
    action_handlers={"connector.test": test_connection},
)
```

`connector.catalog` has a built-in handler that uses the active profile's
authorized connector catalog and fingerprinted pagination cursors. The other
provider actions require an asynchronous handler registered under the exact
action name. This keeps connection storage, provider construction, and secret
resolution in the deployment's trusted provider integration. A missing handler
finishes the accepted job with the stable `handler_unavailable` code.

Requests have closed schemas. Test and schema inspection refer only to a
provider and a saved `connection_id`; preflight refers to a saved definition
and revision selector. Unknown fields, including inline credentials, are
rejected before acceptance. The worker repeats request parsing and checks
authorization for the action and every declared connector, connection, or
definition reference before invoking a handler.

Handlers receive the job's accepted `ControlPlaneContext`, including principal,
tenant, workspace, environment, security domain, and resource owner. They must
resolve named resources within that scope, pass the trusted identity through to
secret and resource providers, honor coroutine cancellation, and return a
JSON-object receipt without raw secret values or source rows. Provider exception
messages and exception-defined codes are never copied into receipts.

The API bounds requested deadlines to 1–300 seconds. Standard managed backend
configuration requires the worker lease to exceed the configured maximum
deadline. The worker also caps each tick at 100 jobs and each result at 64 KiB,
100 items per array, and 32 nested levels. Oversized results fail with
`result_limit_exceeded`; successful results pass through control-plane
redaction before persistence. Receipts are idempotent by caller, action, and
idempotency key, and list/query operations remain owner-scoped and paginated.

```python
worker = backend.create_action_execution_host(worker_id="connector-actions-1")
processed = worker.tick(trusted_worker_context, limit=20)
```

The registered handlers must be asynchronous and must not run inside gateway
routes. Deployments should run action workers as separately monitored worker
processes with provider-specific network and secret permissions. Local
qualification exercises the durable HTTP/headless boundary, worker fencing,
authorization recheck, cancellation, result bounds, redaction, and catalog
execution. Provider-specific live connection, schema, and preflight coverage
remains recorded per provider in the phase release index.
