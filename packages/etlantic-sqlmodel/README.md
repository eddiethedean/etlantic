# etlantic-sqlmodel

Optional bridge between ETLantic `Data` contracts and
[SQLModel](https://sqlmodel.tiangolo.com/) table models, plus optional CP1
control-plane reference stores.

Package version remains **0.39.0** until the 0.39 exit wave.

## Install

```bash
pip install etlantic-sqlmodel
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

## Control-plane reference stores (CP1)

Request-scoped sessions and SQLModel-backed `DefinitionRepository` /
`SubmissionStore` implementations. Persistence models are separate from HTTP
response models. `create_control_plane_tables` is for tests and local demos —
not a production migration strategy.

```python
from etlantic_sqlmodel.control_plane import (
    SQLModelDefinitionRepository,
    SQLModelSubmissionStore,
    create_control_plane_tables,
    create_sqlite_engine,
)

engine = create_sqlite_engine("sqlite:///cp.db")
create_control_plane_tables(engine)
definitions = SQLModelDefinitionRepository(engine)
submissions = SQLModelSubmissionStore(engine)
```

These stores honor scoped idempotency and survive process restart when backed
by a durable database URL. They are not a production multi-tenant claim.

## Links

[Optional packages](https://etlantic.readthedocs.io/en/v0.39.0/10_REFERENCE/OPTIONAL_PACKAGES/) ·
[Source](https://github.com/eddiethedean/etlantic/tree/main/packages/etlantic-sqlmodel) ·
[Issues](https://github.com/eddiethedean/etlantic/issues)
