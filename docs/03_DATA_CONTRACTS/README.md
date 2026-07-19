# Data Contracts

Data contracts are the foundation of every ETLantic pipeline.

They describe the structure, constraints, and meaning of the data that flows through sources, transformations, and sinks. In ETLantic, data contracts are authored as **ContractModel-compatible Pydantic classes** and represented portably through the **Open Data Contract Standard (ODCS)**.

## What This Section Covers

This section explains how to:

- Define data contracts with Python classes
- Use Pydantic types and constraints
- Add contract metadata
- Validate data against contracts
- Generate ODCS documents
- Load existing ODCS contracts
- Version and evolve contracts safely
- Reference data contracts from transformations and pipelines

## The Authoring Model

A data contract begins as a normal Python class:

```python
from typing import Annotated

from pydantic import Field

from etlantic import Data, load_data_contract


class Customer(Data):
    customer_id: Annotated[int, Field(gt=0)]
    first_name: str
    last_name: str
    email: str | None = None
```

The class remains a Pydantic-compatible model, so it can validate ordinary Python data:

```python
customer = Customer(
    customer_id=42,
    first_name="Ada",
    last_name="Lovelace",
)
```

At the same time, ContractModel can operationalize the class as a data contract and expose the metadata ETLantic needs.

## Relationship to ContractModel

ETLantic does not replace ContractModel.

ContractModel remains responsible for:

- Data-contract authoring
- Pydantic integration
- Runtime data validation
- Schema and constraint handling
- ODCS mapping
- Data-contract compatibility
- Data-contract-specific code generation

ETLantic consumes those contract classes and uses them to:

- Type transformation inputs and outputs
- Validate pipeline wiring
- Generate pipeline-wide contract bundles
- Build documentation and diagrams
- Validate execution plans
- Connect sources and sinks to declared data interfaces

The division is intentional:

```text
ContractModel
    Defines and operationalizes data contracts

ETLantic
    Connects those contracts through transformations and pipelines
```

## Relationship to ODCS

ODCS is the portable standard representation of a data contract.

ETLantic should not invent a competing data-contract format. Instead, ContractModel-compatible classes should generate ODCS-compliant documents whenever possible.

```text
Python Data
          │
          ▼
   ContractModel metadata
          │
          ▼
       ODCS document
```

The Python class is the preferred authoring interface.

The ODCS document is the preferred portable artifact.

## Data Contracts in Transformations

Transformation annotations reference data-contract classes directly:

```python
from etlantic import Input, Output, Transformation


class NormalizeCustomers(Transformation):
    customers: Input[RawCustomer]
    result: Output[Customer]
```

ETLantic can use those annotations to determine:

- Which contract governs each input
- Which contract governs each output
- Whether connected pipeline nodes are compatible
- Which ODCS documents belong in the generated contract bundle
- Which validation steps apply before and after execution

## Data Contracts in Pipelines

Sources and sinks also reference data-contract classes:

```python
from etlantic import Pipeline, Sink, Source


class CustomerPipeline(Pipeline):
    raw: Extract[RawCustomer] = Extract(
        binding="customer_csv",
    )

    normalized = NormalizeCustomers.step(
        customers=raw,
    )

    curated: Load[Customer] = Load(
        input=normalized.result,
        binding="customer_warehouse",
    )
```

The source declares the contract of incoming data.

The sink declares the contract of published data.

The transformation connects those two typed boundaries.

## Code-First and Contract-First Workflows

ETLantic should support both workflows.

### Code-first

Developers define ContractModel classes and generate ODCS artifacts:

```python
from etlantic import write_odcs

write_odcs(Customer, "contracts/data/customer.odcs.yaml")
```

### Contract-first

Developers load an existing ODCS document and construct a compatible Python model:

```python
Customer = load_data_contract(
    "contracts/data/customer.odcs.yaml",
)
```

### Hybrid

Teams may load upstream contracts while authoring internal contracts in Python.

The two workflows should interoperate without changing how transformations and pipelines reference the resulting classes.

## Validation Boundaries

Data may be validated at several points:

1. After a source reads data
2. Before a transformation receives data
3. After a transformation produces data
4. Before a sink writes or publishes data

ETLantic coordinates when validation occurs.

ContractModel performs the actual data-contract validation.

Execution plugins provide engine-specific handling for Pandas, Polars, SQL, Arrow, or other representations.

## Invalid Data

Invalid input data and invalid output data should be treated differently.

### Invalid input data

The pipeline may:

- fail the node
- reject invalid records
- quarantine invalid records
- continue with valid records
- invoke a callback

### Invalid output data

Invalid output means an implementation failed to satisfy its declared transformation contract.

The default behavior should be to fail the node unless the pipeline explicitly defines another policy.

## Generated Contract Bundles

A pipeline can collect every referenced data contract and write them alongside its DTCS and DPCS artifacts:

```python
CustomerPipeline.write_contracts("contracts/")
```

Example output:

```text
contracts/
├── data/
│   ├── raw-customer.odcs.yaml
│   └── customer.odcs.yaml
├── transformations/
│   └── normalize-customers.dtcs.yaml
└── pipelines/
    └── customer-pipeline.dpcs.yaml
```

Generated data contracts should be deterministic so changes are easy to review in version control.

## Documentation Roadmap

Read this section in the following order:

1. `DATACONTRACTMODEL.md`
2. `PYDANTIC_INTEGRATION.md`
3. `ODCS.md`
4. `VALIDATION.md`
5. `VERSIONING.md`
6. `GENERATION.md`
7. `LOADING.md`

## Key Principles

- Data contracts are authored as ContractModel-compatible Pydantic classes.
- ContractModel owns data-contract semantics and operational behavior.
- ODCS is the canonical portable representation.
- ETLantic references contract classes directly through type annotations.
- Data-contract information should never be duplicated unnecessarily.
- Validation should happen at clear pipeline boundaries.
- Generated contracts should be deterministic and version-controllable.

## Next Step

Continue with **DATACONTRACTMODEL.md** to learn how to define ETLantic-ready data contracts using ContractModel-compatible Pydantic classes.
