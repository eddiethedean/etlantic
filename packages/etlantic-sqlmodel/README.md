# etlantic-sqlmodel

Optional bridge between ETLantic `Data` contracts and
[SQLModel](https://sqlmodel.tiangolo.com/) table models, plus optional CP1
control-plane reference stores. Install when you need `contract_to_sqlmodel`
helpers or SQLModel-backed definition/submission stores for local CP1 demos.
Package version is **0.57.0** — pin with core.

## Install

```bash
pip install 'etlantic-sqlmodel==0.57.1'
# pip install 'etlantic==0.57.1'
```

## Schema bridge

```python
from etlantic import Data
from etlantic_sqlmodel import contract_to_sqlmodel, compare_metadata


class Customer(Data):
    customer_id: int
    name: str


CustomerTable = contract_to_sqlmodel(
    Customer,
    table_name="customer",
    primary_key=("customer_id",),
)
assert compare_metadata(Customer, CustomerTable).valid
```

## Control-plane reference stores (CP1/CP2)

Request-scoped sessions and SQLModel-backed `DefinitionRepository` /
`SubmissionStore` / CP2 `RegistryProvider` implementations. Persistence models
are separate from HTTP response models. **`create_control_plane_tables` and
`create_registry_tables` are for tests and local demos only** — production must
apply versioned migrations via `etlantic_sqlmodel.migrations` (do not use
`create_all` as the sole schema path).

```python
from etlantic_sqlmodel.control_plane import (
    SQLModelDefinitionRepository,
    SQLModelSubmissionStore,
    SqlModelRegistryProvider,
    create_sqlite_engine,
)
from etlantic_sqlmodel.migrations import apply_migrations

engine = create_sqlite_engine("sqlite:///cp.db")
apply_migrations(engine)  # all provider-owned CP1–CP4 tables
registry = SqlModelRegistryProvider(engine)
definitions = SQLModelDefinitionRepository(engine)
submissions = SQLModelSubmissionStore(engine)
```

Registry conformance (memory vs SQLModel promote/suspend):

```bash
uv run python scripts/check_registry_conformance.py --fake
```

These stores honor scoped idempotency and survive process restart when backed
by a durable database URL. For CP-GA Supported profiles, treat **snapshots as
canonical** for backup/restore; entity dual-write rows are denormalized mirrors
for isolation queries. Use separate engines/schemas per tenant for
`isolated-deployment` / `dedicated-schema`.

## Managed backend and schema inspection (0.57.0)

`create_managed_backend` builds the authorized service graph without importing
FastAPI or requiring an HTTP context factory. The factory owns an engine it
creates; an injected engine remains caller-owned. Both paths require explicit
migrations and perform read-only compatibility inspection before returning.

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

# The context must come from the consumer's trusted identity boundary.
schedule = backend.schedule_service
worker = backend.create_execution_host(owner_id="etl-worker-1")
action_worker = backend.create_action_execution_host(worker_id="actions-1")
scheduler = backend.create_scheduler(owner_id="scheduler-1")
```

Each role exposes `status()`, `request_drain()`, and a `ready()` convenience
method. Run blocking ticks on consumer-owned threads. After requesting drain,
join those threads before calling `backend.close()`; close refuses to dispose an
owned engine while a role tick remains active. The schedule service owns command
authorization and trigger recovery for both headless and HTTP callers.

`schema_requirements()` publishes required managed-store tables, columns, primary
keys, and unique keys. `inspect_schema(engine)` returns one of `fresh`, `behind`,
`compatible`, `unknown_or_ahead`, `partial_or_corrupt`, or `unreachable`, with
redacted reason codes. It does not create or upgrade schema objects. Apply
`etlantic_sqlmodel.migrations.upgrade(engine)` as an explicit deployment step.

## Links

[Optional packages](https://etlantic.readthedocs.io/en/v0.57.0/10_REFERENCE/OPTIONAL_PACKAGES/) ·
[Source](https://github.com/eddiethedean/etlantic/tree/main/packages/etlantic-sqlmodel) ·
[Issues](https://github.com/eddiethedean/etlantic/issues)
