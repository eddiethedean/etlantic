# Documentation Status and Conventions

Pipelantic 0.6 implements the typed modeling kernel, contract interoperability,
Validation / Pipeline Plan IR, the local runtime / operational model,
dataframe execution (Polars reference + Pandas compatibility), and SQL-native
execution (`pipelantic-sql`). Much of the documentation still describes the
intended 1.0 product. It serves three related purposes:

1. Explain the product vision and user experience.
2. Specify the intended 1.0 architecture and public interfaces.
3. Provide implementation guidance and acceptance criteria for shipped and
   upcoming milestones.

## Stability Labels

Documents use these conceptual stability levels:

| Label | Meaning |
|---|---|
| Foundational | A project boundary or principle expected to remain stable |
| Accepted design | A chosen API or architecture direction pending implementation |
| Proposed | A concrete surface that may change as implementation pressure appears |
| Normative | A requirement defined by a contract specification |
| Example | Illustrative code that expresses intended UX |

Public pages use these visible statuses:

| Page status | Meaning |
|---|---|
| Available in 0.6 | Tested against the current package |
| Partially available | Shipped and future behavior are explicitly separated |
| Future design | Not a current API or installation guide |
| Normative specification | Contract requirements, not package behavior |
| Internal project plan | Maintainer sequencing and implementation notes |

Unless a chapter says otherwise, user-guide code beyond the shipped 0.6
modeling, interchange, validation, planning, local runtime, **dataframe
plugin**, and **SQL plugin** surface should be read as an **accepted design
example**, not as evidence of a published package API. The 0.6 surface is
defined by the package, [API reference](../10_REFERENCE/API_REFERENCE.md),
tests, and changelog.

**Shipped in 0.5:** dataframe execution protocol, `pipelantic-polars`, and
`pipelantic-pandas` (see Execution → Polars / Pandas and the Dataframe Plugin
protocol page).

**Shipped in 0.6:** SQL execution protocol (`pipelantic.sql/1`),
`pipelantic-sql`, `Profile.sql_engine`, and SQL→SQL fusion without intermediate
Python fetch (see Execution → SQL and the SQL Plugin protocol page).

**Still accepted design until later milestones:** Spark, external
orchestration, Graphviz/HTML visualization, and non-dataframe / non-SQL Plugin
SDK surfaces.

## Normative Authority

The source of truth depends on the subject:

| Subject | Authority |
|---|---|
| Data-contract meaning | Upstream ODCS specification |
| Transformation-contract meaning | `DTCS_SPEC.md` |
| Pipeline-contract meaning | `DPCS_SPEC.md` |
| ContractModel behavior | ContractModel project |
| Pipelantic architecture and API | This documentation until code and tests supersede it |
| Backend behavior | Plugin documentation and conformance tests |

Integration guides explain how Pipelantic uses a standard; they do not
replace normative specifications.

## Requirement Language

The DTCS and DPCS specifications use normative requirement terms such as
`MUST`, `SHOULD`, and `MAY`.

User guides generally use plain explanatory language. Reference and development
documents may use `should` to describe intended 1.0 behavior, but those
statements are not contract-standard requirements unless linked to a normative
specification.

## Code Examples

Beginner and runnable examples prioritize executable current behavior. Future
design examples may prioritize the intended authoring model only when their
status is prominent:

```python
class NormalizeCustomers(Transformation):
    customers: Input[RawCustomer]
    result: Output[Customer]
```

For all examples:

- Examples should become executable or syntax-checked.
- Unsupported examples should be marked explicitly.
- Renamed APIs should be updated across the whole documentation set.
- Generated artifacts should be checked in CI.

## Design Versus Runtime

Documentation must preserve this distinction:

```text
Pipeline / Transformation / Contract
Portable meaning

PipelinePlan
Resolved execution-independent plan

Plugin or compiled artifact
Backend realization

Run result and events
Observed execution
```

Avoid using these layers interchangeably.

## Adding or Changing Documentation

When changing a central concept:

1. Update the glossary.
2. Update the relevant design decision.
3. Update architecture and lifecycle diagrams.
4. Update authoring examples.
5. Update reference APIs.
6. Update plugin conformance expectations.
7. Run internal-link and code-fence checks.

## Current Implementation Boundary

The roadmap, not chapter volume, determines implementation status. A detailed
chapter may describe a future backend or SDK surface that has not yet been
built.

See:

- [Roadmap](../11_DEVELOPMENT/ROADMAP.md)
- [Design Decisions](../11_DEVELOPMENT/DESIGN_DECISIONS.md)
- [Architecture Decisions](../11_DEVELOPMENT/ARCHITECTURE_DECISIONS.md)
