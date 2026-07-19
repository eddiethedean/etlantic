# Documentation Status and Conventions

ETLantic **0.14.0** implements the typed modeling kernel, contract
interoperability, Validation / Pipeline Plan IR, the local runtime /
operational model, dataframe execution (Polars reference + Pandas
compatibility), SQL-native execution (`etlantic-sql`), distributed Spark batch
execution (`etlantic-pyspark`), external orchestration compilation
(`etlantic-airflow`), CLI/SDK tooling with Graphviz/HTML lineage exporters,
optional `etlantic-keyring` / `etlantic-sqlmodel`, the SparkForge migration
adapter (`etlantic-sparkforge`), `@Transformation.portable` /
`etlantic.transform` authoring to `dtcs.transform-plan/2`, and Polars +
PySpark portable compilers for kernel + `portable-relational/1`. Structured
Streaming APIs are experimental. Pandas and SQL portable compilers remain
0.14–0.15—keep `@implementation(...)` for those engines and for profiles
outside the advertised claim set.

Prefer pages marked **Available in 0.14** and the Green path on the docs home.
Design Proposals and **Future design** chapters describe intended 1.0 surfaces
and are not current APIs. Documentation serves three related purposes:

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
| Available in 0.14 | Tested against the current package |
| Shipped in 0.x | Available since that milestone (still current) |
| Experimental | Public APIs that may change without a major version bump |
| Partially available | Shipped and future behavior are explicitly separated |
| Future design | Not a current API or installation guide |
| Normative specification | Contract requirements, not package behavior |
| Internal project plan | Maintainer sequencing and implementation notes |

Unless a chapter says otherwise, user-guide code beyond the shipped 0.14
modeling, contracts, validation, planning, local runtime, **dataframe
plugin**, **SQL plugin**, **PySpark batch**, **Airflow compilation**,
**CLI/viz tooling**, **SparkForge adapter**, **portable authoring**,
**Polars/PySpark/Pandas relational compilers**, and **public portable
conformance SDK** surface should be read as an **accepted design example**,
not as evidence of a published package API. The 0.14 surface is defined by
the package, [API reference](../10_REFERENCE/API_REFERENCE.md), tests, and
changelog.

**Shipped in 0.5:** dataframe execution protocol, `etlantic-polars`, and
`etlantic-pandas` (see Execution → Polars / Pandas and the Dataframe Plugin
protocol page).

**Shipped in 0.6:** SQL execution protocol (`etlantic.sql/1`),
`etlantic-sql`, `Profile.sql_engine`, and SQL→SQL fusion without intermediate
Python fetch (see Execution → SQL and the SQL Plugin protocol page).

**Shipped in 0.7:** Spark execution protocol (`etlantic.spark/1`),
`etlantic-pyspark`, local Spark provider, lazy Spark regions, Delta-compatible
write intents, and `Profile.spark_engine` (see Execution → PySpark).

**Shipped in 0.8:** Orchestration protocol (`etlantic.orchestration/1`),
`etlantic-airflow`, `compile_plan`, and `Profile.orchestrator` /
schedule / execution intents (see Execution → Airflow).

**Shipped in 0.9:** CLI surfaces, SARIF, plugin allowlists, Graphviz DOT /
HTML lineage exporters (`etlantic.viz`), `etlantic-keyring`,
`etlantic-sqlmodel`.

**Shipped in 0.10+:** SparkForge migration adapter (`etlantic-sparkforge`).

**Shipped in 0.11:** `@Transformation.portable` / `etlantic.transform`
authoring emitting `dtcs.transform-plan/2`.

**Shipped in 0.12:** `Profile.portable_transform_policy`, portable planning
selection, and Polars **kernel** portable compilation / execution via
`etlantic-polars` (`etlantic.transform_compilers`).

**Shipped in 0.13:** Polars + PySpark compilers claim
`portable-relational/1` (joins, unions, aggregates, sort/dedupe/limit) with
private differential fixtures; portable Spark path forbids UDF fallback.

**Shipped in 0.14:** Pandas eager index-neutral relational compiler with the
same kernel + relational `/1` claims; public
`etlantic.testing.portable_transform_conformance` suite enforced in CI for
Polars, PySpark, and Pandas.

**Experimental in 0.7+:** Structured Streaming foundation APIs.

**Still accepted design until later milestones:** managed Spark providers
(Databricks/EMR/Connect), Dagster/Prefect compilers, remaining Plugin SDK
surfaces, and SQL lowering / profile graduation (0.15+).

## Normative Authority

The source of truth depends on the subject:

| Subject | Authority |
|---|---|
| Data-contract meaning | Upstream ODCS specification |
| Transformation-contract meaning | [DTCS 3.0 specification](https://github.com/eddiethedean/dtcs/blob/main/SPEC.md) |
| Portable Transformation Plan meaning and canonical models | DTCS 3.0 specification and `dtcs>=0.13` |
| PySpark-inspired portable authoring UX | ETLantic `etlantic.transform/1` profile |
| Portable compiler lifecycle | ETLantic Plugin SDK (`etlantic.transform-compiler/1`) |
| Pipeline-contract meaning | `DPCS_SPEC.md` |
| ContractModel behavior | ContractModel project |
| ETLantic architecture and API | This documentation until code and tests supersede it |
| Backend behavior | Plugin documentation and conformance tests |

Integration guides explain how ETLantic uses a standard; they do not
replace normative specifications.

ETLantic and DTCS share a publisher, so portable requirements may drive
coordinated DTCS specification and package releases. Until a DTCS change is
published and included in ETLantic's compatible dependency range, it remains a
proposal rather than normative shipped behavior.

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
