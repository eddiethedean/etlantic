# ADR-013: Closed Portable Transformation IR

Date: 2026-07-17  
Status: Proposed

## Context

ETLantic transformations declare portable typed interfaces but currently need
separate executable implementations for Polars, Pandas, SQL, PySpark, and other
engines. This duplicates common relational logic and makes semantic equivalence
the author's responsibility.

PySpark's DataFrame and Column APIs provide a familiar, rich declarative user
experience. Directly adopting PySpark objects would add a core dependency and
Spark semantics. Translating arbitrary Python or tracing native dataframe APIs
would be unsafe, incomplete, and difficult to serialize deterministically.

## Decision

DTCS will define the closed, versioned portable relational Transformation Plan
and expose canonical models through the `dtcs` package. ETLantic will define a
PySpark-inspired DataFrame, Column, functions, grouping, and window authoring
surface that constructs those DTCS models directly.

`@Transformation.portable` invokes trusted definition code with symbolic input
and parameter objects to construct the IR. It never processes data.

Backend plugins compile supported IR nodes to native expressions. Plugins must
preserve normative DTCS semantics or reject the definition during
planning. Silent approximation, raw SQL fallback, and automatic UDF fallback
are prohibited.

Portable operations and functions use registered `dtcs:` identifiers. DTCS
distinctions among null, missing, and invalid are preserved. ETLantic facade
syntax without a sufficient published DTCS definition remains experimental or
unavailable.

Native `@Transformation.implementation(engine)` registration remains available
for optimized or non-portable behavior. The planner records whether it selected
portable compilation or a native implementation.

The semantic IR belongs to DTCS, not `etlantic.sql`, Spark, or a dataframe
plugin. `etlantic.transform` is the ergonomic facade and compiler integration
surface. The core remains free of backend dependencies.

ETLantic and DTCS share a publisher, so missing normative concepts can be
standardized and released in DTCS as part of one coordinated roadmap. Shared
publishing authority does not bypass explicit versions, compatibility fixtures,
or migration requirements.

## Consequences

Benefits:

- common transformations are authored once
- contract-aware expression validation happens before execution
- plugins can optimize native expression graphs and fuse regions
- plans, lineage, documentation, and diffs can inspect transformation logic
- cross-engine conformance becomes a framework responsibility

Costs:

- ETLantic must specify null, type, ordering, timestamp, join, and aggregate
  semantics precisely
- plugin SDK and plan schema surface grows
- the function set must evolve conservatively
- familiar PySpark syntax may create expectations of unsupported API parity
- differential testing across engines becomes a release gate

Requirements:

- closed data-only IR and canonical serialization
- bounded parsing and validation
- exact operation-level capability negotiation
- stable expression paths and diagnostics
- secret-free parameter and literal policy
- at least two compiler implementations before stabilizing an operation family

## Alternatives

### Continue requiring one implementation per engine

Rejected as the only model because it preserves duplication and provides no
portable transformation semantics. It remains supported as an escape hatch.

### Use PySpark as the canonical IR

Rejected because it would put Spark types and dependencies in core and make
other plugins emulate Spark implementation details rather than ETLantic
semantics.

### Translate arbitrary Python AST or bytecode

Rejected because Python control flow, dynamic calls, imports, mutation, and
runtime values cannot be safely or reliably converted into a closed relational
plan.

### Trace native Polars, Pandas, or PySpark calls

Rejected because traces are backend-shaped, incomplete, difficult to load
safely, and unstable across library versions.

### Use SQL strings as the portable language

Rejected because SQL dialects differ, non-SQL engines need a structured model,
and raw strings weaken typing, lineage, parameter safety, and diagnostics.

## Compatibility

The change is additive to transformation authoring. Existing transformations,
steps, pipelines, and native implementations continue to work.

The feature requires `dtcs.transform-plan/1`, an `etlantic.transform/1`
authoring profile, an `etlantic.transform-compiler/1` plugin protocol, DTCS
package releases, and a versioned `PipelinePlan` schema change. Older plugins remain usable for native
implementations but cannot claim portable compilation.

Unknown IR major versions and unsupported operations fail closed.
