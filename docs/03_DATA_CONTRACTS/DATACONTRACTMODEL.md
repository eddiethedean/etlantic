# DataContractModel (removed)

!!! warning "Removed in 0.37.0"
    `DataContractModel` was removed from the public root and
    `etlantic.contracts` in 0.37.0. New code should subclass `Data`. Prefer:

    ```python
    from etlantic import Data

    class Customer(Data):
        customer_id: int
        first_name: str
        last_name: str
    ```

    Accessing `DataContractModel` on `etlantic` raises `AttributeError`.
    This page remains for migration context only. See
    [Migration 0.36 → 0.37](../11_DEVELOPMENT/MIGRATION_0_36_TO_0_37.md).

## Why the rename

ETLantic's preferred public name for a typed dataset contract is `Data`.
Under the hood it remains a thin alias of ContractModel's `ContractModel`.
The older ETLantic-facing name `DataContractModel` confused the boundary
between ContractModel and ETLantic.

## Migration

1. Replace root/`contracts` `DataContractModel` imports with
   `from etlantic import Data` (or `from contractmodel import ContractModel`).
2. Replace `class X(DataContractModel)` with `class X(Data)`.
3. Load [ODCS](ODCS.md) with `load_data_contract(...)` and write with
   `write_odcs(...)` from `etlantic.contracts`.

See [Data Contracts overview](README.md), [ODCS](ODCS.md), and
[Loading](LOADING.md).
