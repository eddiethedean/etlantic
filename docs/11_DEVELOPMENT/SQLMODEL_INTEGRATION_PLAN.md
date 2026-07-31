# SQLModel Integration Plan

> **Plan status: partially shipped; reference persistence remains planned.**
>
> **Current 0.36 boundary:** The optional `etlantic-sqlmodel` package provides
> the documented contract-to-SQLModel bridge. Sessions, Alembic workflows,
> repository helpers, and durable multi-tenant control-plane providers remain
> future work.
>
> **Authority:** The
> [optional-packages reference](../10_REFERENCE/OPTIONAL_PACKAGES.md) defines
> the shipped bridge. This plan owns future persistence goals subject to the
> [control-plane gates](MULTI_TENANT_CONTROL_PLANE_PLAN.md). See the
> [Planning Hub](PLAN_INDEX.md).
>
> **Review trigger:** Update when the optional package adds persistence or
> migration scope, or its supported SQLModel dependency range changes.

## Purpose

SQLModel combines Pydantic models with SQLAlchemy table models through standard
Python type annotations. That developer experience aligns strongly with
ETLantic and its planned FastAPI control plane.

The reference persistence work is governed by the
[Multi-Tenant Control Plane Plan](MULTI_TENANT_CONTROL_PLANE_PLAN.md).
SQLModel can implement isolation contracts, but it does not create an
authorization or tenant boundary by itself.

ETLantic should support SQLModel as an optional integration in three places:

1. generating or adapting relational table models from `Data` contracts;
2. implementing typed SQL-backed control-plane providers;
3. reducing duplication between FastAPI schemas and persistence models.

SQLModel should not replace ETLantic's domain models, ContractModel,
SQLAlchemy Core-based SQL execution, or provider protocols.

## Architectural Boundary

```text
ContractModel / ETLantic Data
    authoritative logical data contract
                 │
                 ├── optional generation or adaptation
                 ▼
          SQLModel table model
    relational application representation

ETLantic provider protocols
                 │
                 ├── optional reference implementation
                 ▼
       SQLModel-backed persistence

ETLantic SQL execution plugin
                 │
                 ▼
        SQLAlchemy Core / dialect
```

The three layers remain distinct:

- `Data` defines contractual meaning;
- SQLModel may define a convenient relational Python representation;
- SQL execution plugins compile and execute portable SQL intent.

## Goals

The integration should:

- accept existing SQLModel table models as relational schema sources;
- generate draft SQLModel models from compatible `Data` contracts;
- compare SQLModel metadata with declared contracts and observed database
  schemas;
- provide typed reference stores for registries, runs, reports, events, schema
  observations, reliability evidence, approvals, and incremental state;
- share appropriate Pydantic schemas with `etlantic-fastapi`;
- preserve editor completion and static typing;
- use explicit migrations and transactional repositories;
- remain optional and replaceable.

## Non-Goals

ETLantic will not:

- make SQLModel a core dependency;
- require users to model warehouse tables as ORM entities;
- treat a SQLModel table as the authoritative data contract automatically;
- use ORM relationships to define pipeline lineage or dependencies;
- expose SQLModel sessions from public core APIs;
- use `SQLModel.metadata.create_all()` as a production migration strategy;
- replace SQLAlchemy Core expressions in SQL transformation implementations;
- infer unrestricted database access from the presence of a table model;
- serialize live ORM objects into plans, reports, or contracts.

## Package Shape

A separate integration package is preferred:

```text
etlantic-sqlmodel
├── contract adapters
├── model generation
├── metadata inspection
├── repository helpers
├── reference providers
├── FastAPI dependencies
└── conformance tests
```

Candidate installation:

```bash
pip install etlantic-sqlmodel
```

The package may depend on SQLModel, ETLantic, an explicitly selected database
driver, and Alembic in a migration extra or application dependency.

## Contract and Table Model Mapping

### SQLModel to `Data`

An adapter may inspect a SQLModel table class and produce a draft `Data`
contract or comparison representation.

Useful metadata includes:

- field names and Python annotations;
- SQL column types;
- nullability;
- primary and foreign keys;
- uniqueness and indexes;
- defaults and generated values;
- length, precision, and scale;
- table and schema identity.

The result must identify information that cannot be represented reliably or
requires human review.

### `Data` to SQLModel

Generation should create reviewable Python source rather than hidden dynamic
classes for production use.

```python
from etlantic_sqlmodel import generate_model

result = generate_model(
    Customer,
    table_name="customer",
    primary_key=("customer_id",),
)
```

Generation must require explicit relational choices that a data contract alone
cannot safely determine:

- table and schema name;
- primary and foreign keys;
- identity and sequence behavior;
- indexes and uniqueness;
- database-specific types;
- relationships;
- persistence defaults;
- cascade and deletion behavior.

Generated source should include provenance and be safe to edit normally.

### Multiple representations

The integration should encourage separate models when write, database, and
public API shapes differ:

```text
Customer contract
CustomerRow table model
CustomerCreate request model
CustomerPublic response model
```

Shared inheritance may reduce duplication, but security-sensitive or
database-only fields must not leak into public API schemas.

## Control-Plane Persistence

SQLModel is a good candidate for reference implementations of ETLantic's
provider protocols:

- pipeline and contract registry;
- run and report store;
- lifecycle event store;
- schema observation and acknowledgement history;
- freshness, reconciliation, quality, and statistical evidence history;
- profile and environment revision history;
- policy decision and approval records;
- incremental state and checkpoint store;
- idempotency and submission records.

Public code should depend on provider protocols, not SQLModel repositories.
The optional package may implement those protocols using SQLModel sessions and
transactions.

Every tenant-owned repository lookup must take immutable tenant/workspace scope
as part of its key. Reference shared-table stores require compound constraints,
application-layer scope enforcement, and an independent database control such
as row-level security. Unscoped `get(id)` repository APIs are non-conforming.

## FastAPI Integration

`etlantic-fastapi` may offer an optional SQLModel persistence bundle:

```python
from etlantic_fastapi import ETLanticAPI
from etlantic_sqlmodel import SQLModelControlPlane

control_plane = SQLModelControlPlane.from_url(database_url)

api = ETLanticAPI(
    registry=control_plane.registry,
    run_store=control_plane.runs,
    report_store=control_plane.reports,
    event_store=control_plane.events,
)
```

FastAPI dependencies may provide request-scoped sessions to integration
repositories. Those sessions must not become pipeline runtime resources or be
passed to transformations.

Request, persistence, and response models should remain separate where their
security or lifecycle differs.

## SQL Execution Integration

SQLModel table models may be accepted as convenient relation descriptors:

```python
source = Source[Customer](
    relation=SQLModelRelation(CustomerRow),
)
```

The adapter should translate table metadata into ETLantic's SQL relation and
binding models. The SQL plugin continues to use SQLAlchemy Core and dialect
capabilities for query construction, transactions, execution, compilation,
write intents, inspection, and reconciliation.

ORM instance loading must not be the default mechanism for bulk ETL.

## Migrations and Schema Evolution

SQLModel metadata describes a desired relational model but does not replace a
migration system.

The integration should:

- generate migration proposals or metadata suitable for Alembic;
- compare contract, SQLModel, observed database, and migration-head schemas;
- integrate differences with schema drift and compatibility analysis;
- require review for destructive or lossy changes;
- record migration revision and database schema fingerprint in plans and
  reports;
- prevent automatic production `create_all()` behavior.

```text
Declared Data contract
        │
SQLModel table model
        │
Alembic migration head
        │
Observed database schema
```

Each mismatch has different meaning and remediation.

## Developer Experience

The integration should provide:

- completion and type checking for generated models;
- navigation between a `Data` contract and SQLModel table;
- contract-versus-table diagnostics;
- safe quick fixes for deterministic field mappings;
- generated model previews;
- migration impact previews;
- FastAPI schema-exposure checks;
- warnings when table fields could leak through API responses;
- CodeLens actions for generate, compare, inspect, and propose migration.

Notebook display may show bounded model and metadata comparisons without
opening a database connection implicitly.

## Security

SQLModel does not create a security boundary.

The integration must:

- use parameterized SQL and approved engines;
- keep database URLs and credentials in secret providers;
- separate control-plane and pipeline-data credentials;
- enforce tenant and workspace filters in repositories;
- prevent mass assignment of protected fields;
- distinguish request, persistence, and response models;
- bound queries, pagination, eager loading, and relationship traversal;
- avoid returning ORM objects directly from generic APIs;
- prohibit automatic schema creation or destructive migration in production;
- audit migrations, approvals, state changes, and administrative writes;
- avoid embedding session, engine, metadata, or ORM state in serialized
  ETLantic models.

## Testing

The integration conformance suite should cover:

- SQLModel and `Data` type mapping;
- nullability, defaults, precision, keys, indexes, and relationships;
- unsupported and lossy mappings;
- deterministic source generation;
- contract, model, migration, and observed-schema comparisons;
- sync and async repository behavior where supported;
- transaction rollback and concurrent updates;
- tenant isolation and pagination;
- idempotent run submission and state transitions;
- FastAPI request and response field separation;
- migration safety and production `create_all()` prohibition;
- compatibility with supported SQLModel, Pydantic, SQLAlchemy, and Python
  versions.

## Roadmap Placement

Rows before 0.39 preserve the plan's original implementation decomposition;
they do not independently claim that every item in a row is shipped. Use the
current boundary at the top of this page and the
[optional-packages reference](../10_REFERENCE/OPTIONAL_PACKAGES.md) for
availability. Rows from 0.39 onward are future sequence.

| Release | SQLModel capability |
|---|---|
| 0.3 | Adapter and mapping protocols, source-generation design |
| 0.6 | SQLModel relation descriptors accepted by SQL plugins |
| 0.9 | Optional package scaffold, generator CLI, conformance suite |
| 0.39 | Request-scoped control-plane repository foundation |
| 0.40 | Tenant-aware registry, revision, and history reference providers |
| 0.41 | State, checkpoint, outbox, lease, and idempotency providers |
| 0.42 | Policy/audit evidence stores and migration hardening |
| 0.43 | Graduated multi-tenant reference persistence bundle |
| 0.44 | IDE generation, navigation, comparison, and migration actions |
| Later 0.x | Mature Alembic integration and provider templates |

## Graduation Gates

The existing bridge can remain useful without claiming reference persistence.
A future SQLModel-backed control-plane bundle graduates only when:

- ETLantic's provider protocols remain usable without SQLModel installed;
- every repository operation applies immutable tenant and workspace scope;
- sync and async transaction, rollback, concurrency, and pagination suites
  pass against supported databases;
- schema changes use reviewed, reversible migrations and production startup
  never calls `create_all()` automatically;
- idempotency, outbox, lease, checkpoint, and state-transition behavior passes
  failure-injection tests;
- backup, restore, retention, and upgrade rehearsals preserve identity and
  audit evidence;
- request, persistence, and response models prevent protected-field exposure;
- dependency, migration, deployment, and incident runbooks are published with
  an explicit compatibility matrix.

Passing model-generation tests alone is not sufficient for a persistence or
multi-tenant production claim.

## Decision

ETLantic should incorporate SQLModel as:

> An optional typed bridge between contracts, relational application models,
> FastAPI schemas, and reference persistence providers.

It should not become:

> The pipeline model, the data contract model, or the SQL execution engine.
