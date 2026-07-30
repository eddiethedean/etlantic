# etlantic-sqlmodel

Optional bridge between ETLantic `Data` contracts and
[SQLModel](https://sqlmodel.tiangolo.com/) table models for ETLantic 0.34.

## Install

```bash
pip install etlantic-sqlmodel
```

Sessions, Alembic migrations, and repository helpers are planned across
0.40–0.44.
This package focuses on schema mapping and metadata comparison only.

## Usage

```python
from etlantic import Data
from etlantic_sqlmodel import (
    compare_metadata,
    contract_to_sqlmodel,
    create_plugin,
    sqlmodel_to_contract,
)


class Customer(Data):
    customer_id: int
    name: str


CustomerTable = contract_to_sqlmodel(
    Customer,
    table_name="customer",
    primary_key=("customer_id",),
)

metadata = sqlmodel_to_contract(CustomerTable)
report = compare_metadata(Customer, CustomerTable)
assert report.valid

plugin = create_plugin()
```

This bridge is used explicitly through its public conversion helpers; it does
not require a profile engine setting. Register `create_plugin()` only with
tooling that consumes the schema-mapping plugin object.

Generated SQLModel classes are reviewable starting points — relational choices
such as primary keys and table names must be supplied explicitly.

## Links

[Optional packages](https://etlantic.readthedocs.io/en/latest/10_REFERENCE/OPTIONAL_PACKAGES/) ·
[Source](https://github.com/eddiethedean/etlantic/tree/main/packages/etlantic-sqlmodel) ·
[Issues](https://github.com/eddiethedean/etlantic/issues)
