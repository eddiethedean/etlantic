# etlantic-sqlmodel

Optional bridge between ETLantic `Data` contracts and
[SQLModel](https://sqlmodel.tiangolo.com/) table models, plus optional CP1
control-plane reference stores. Install when you need `contract_to_sqlmodel`
helpers or SQLModel-backed definition/submission stores for local CP1 demos.
Package version is **0.39.0** — pin with core.

## Install

```bash
pip install 'etlantic-sqlmodel==0.40.0'
# pip install 'etlantic==0.40.0'
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
apply_migrations(engine)  # CP2 registry tables (001_registry_cp2)
registry = SqlModelRegistryProvider(engine)
definitions = SQLModelDefinitionRepository(engine)
submissions = SQLModelSubmissionStore(engine)
```

Registry conformance (memory vs SQLModel promote/suspend):

```bash
uv run python scripts/check_registry_conformance.py --fake
```

These stores honor scoped idempotency and survive process restart when backed
by a durable database URL. They are not a production multi-tenant claim.

## Links

[Optional packages](https://etlantic.readthedocs.io/en/v0.40.0/10_REFERENCE/OPTIONAL_PACKAGES/) ·
[Source](https://github.com/eddiethedean/etlantic/tree/main/packages/etlantic-sqlmodel) ·
[Issues](https://github.com/eddiethedean/etlantic/issues)
