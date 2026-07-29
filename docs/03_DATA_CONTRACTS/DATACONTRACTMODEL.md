# DataContractModel (deprecated)

!!! warning "Deprecated alias"
    `DataContractModel` is a deprecated alias for `Data`. New code should
    subclass `Data`. Prefer:

    ```python
    from etlantic import Data

    class Customer(Data):
        customer_id: int
        first_name: str
        last_name: str
    ```

    Importing `DataContractModel` from `etlantic` emits a deprecation
    warning. This page remains for migration context only.

## Why the rename

ETLantic's preferred public name for a typed dataset contract is `Data`.
Under the hood it remains a thin alias of ContractModel's `ContractModel`.
The older ETLantic-facing name `DataContractModel` confused the boundary
between ContractModel and ETLantic.

## Migration

1. Replace `from etlantic import DataContractModel` with
   `from etlantic import Data`.
2. Replace `class X(DataContractModel)` with `class X(Data)`.
3. Load [ODCS](ODCS.md) with `load_data_contract(...)` and write with
   `write_odcs(...)`.

See [Data Contracts overview](README.md), [ODCS](ODCS.md), and
[Loading](LOADING.md).
