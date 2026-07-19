# Portable Transformation Compiler Protocol

!!! success "Available since ETLantic 0.17 (docs target 0.18.0)"
    `etlantic.transform-compiler/1` is importable. Polars, PySpark, Pandas, and
    SQL claim `portable-relational-kernel/1` and `portable-relational/1`. Third
    parties must pass `run_portable_transform_conformance_suite` for every
    advertised claim. In 0.17, Polars and PySpark additionally claim the
    graduated Wave 1 / Wave 2 families; continuation families remain
    unclaimed.

A portable transformation compiler translates a validated
`dtcs.transform-plan/2` (and readable v1) into backend-native expressions without changing its
DTCS-defined meaning.

## Boundary

```text
DTCS TransformationPlan
      │
      ├── support analysis (pure)
      ├── compilation (no data access)
      ▼
CompiledTransform
      │
      └── execution with runtime inputs and parameters
```

Support analysis and compilation belong to planning. Execution belongs to the
runtime. A serialized `PipelinePlan` contains IR, requirements, compiler
identity, and fingerprints—not live compiled objects or closures.

## Protocol

```python
@runtime_checkable
class PortableTransformCompiler(Protocol):
    @property
    def info(self) -> TransformCompilerInfo: ...

    def analyze(
        self,
        definition: TransformationPlan,
        *,
        context: TransformPlanningContext,
    ) -> TransformSupportReport: ...

    def compile(
        self,
        definition: TransformationPlan,
        *,
        context: TransformCompileContext,
    ) -> CompiledTransform: ...

    async def execute(
        self,
        compiled: CompiledTransform,
        *,
        inputs: Mapping[str, Any],
        parameters: Mapping[str, Any],
        context: TransformExecutionContext,
    ) -> TransformOutputBundle: ...
```

Plugins MAY separate compilation and execution into cooperating objects. SQL
and orchestration plugins MAY compile artifacts for execution outside the local
process.

## Compiler information

```python
TransformCompilerInfo(
    name="etlantic-polars",
    version="...",
    engine="polars",
    compiler_protocol="etlantic.transform-compiler/1",
    dtcs_plan_versions=("dtcs.transform-plan/2", "dtcs.transform-plan/1"),
    capabilities=TransformCapabilities(...),
)
```

Capabilities are an ETLantic adapter over the DTCS Engine Capability Model.
They list exact registered Semantic Action/Function versions, portable types,
semantic modes, maximum supported plan size, lazy/eager behavior, and artifact
ownership. Plans and reports preserve the originating DTCS capability
identifiers.

The compiler reports support against the published profiles, never a vague
"PySpark compatible" flag:

| DTCS profile | Compiler claim |
|---|---|
| `dtcs:profile/portable-relational-kernel/1` | all required kernel actions, expressions, operators, and functions |
| `dtcs:profile/portable-relational/1` | full relational joins, unions, grouping, aggregation, ordering, deduplication, and limits |
| `dtcs:profile/portable-window/1` | experimental windows, functions, and row/range frames |
| `dtcs:profile/portable-complex-types/1` | experimental composite types and access operations |

A compiler may advertise a subset as individual capabilities. It may advertise
a profile only when every requirement and DTCS conformance fixture in that
profile passes.

### Baseline and 0.17 claim matrix

`etlantic-polars`, `etlantic-pyspark`, and `etlantic-pandas` **must** claim
and pass the public conformance fixtures for:

| Item | 0.13–0.14 requirement |
|---|---|
| Profiles | `dtcs:profile/portable-relational-kernel/1` and `dtcs:profile/portable-relational/1` |
| Plan shape | Accept `dtcs.transform-plan/2` (and readable v1); `/2` profile requirements are metadata aliases of `/1` |
| Kernel actions | project, filter, with_fields, rename/drop, scalar expressions |
| Relational actions | join, union, aggregate, sort, distinct, deduplicate, limit with exact modes |
| Modes | Eager required; Pandas additionally `lazy=False`; join `collisionPolicy` **fail** only |
| Outside claim set | Fail closed in `analyze()` / planning (`PMXFORM3xx`) with action/expression paths |

All four official compilers claim this baseline (SQL joined in 0.15). In 0.17,
Polars and PySpark additionally claim string-advanced, conversion, statistics,
window `/1`, complex-types, complex-values, and reshape `/1`. Pandas and SQL
remain baseline-only. Relational-extended, temporal-IANA, nondeterministic, and
window `/2` remain unclaimed.

## Support reports

`analyze()` is deterministic and side-effect free. It returns one finding per
unsupported or conditional requirement:

```python
TransformSupportReport(
    supported=False,
    findings=(
        TransformSupportFinding(
            code="PMXFORM301",
            expression_path="outputs.result.project.full_name",
            requirement="function:dtcs:concat_ws",
            reason="function is not implemented",
        ),
    ),
)
```

It MUST NOT import arbitrary user modules, resolve secrets, acquire resources,
read data, or contact a backend. Optional backend capability probing is a
separate explicitly requested operation and cannot weaken fail-closed planning.

Analysis MUST cover each required profile, Semantic Action, Function,
Operator, logical type, action mode, value-state behavior, ordering guarantee,
and resource limit. A backend that supports `join` but not, for example,
`nullSafe`, `semi`, or collision policy handling reports the exact unsupported
mode rather than claiming generic join support.

## Compiled transform

A compiled transform contains:

- compiler and engine identity
- source IR fingerprint
- logical output mapping
- required runtime parameter names
- materialization and ownership requirements
- backend-native plan held only in runtime memory or a safe generated artifact
- explain metadata without secrets or row data

Compilation MUST be deterministic for equivalent IR, compiler version, and
compile context. Backend-native objects MUST NOT be serialized into the
portable `PipelinePlan`.

## Execution output

Execution normalizes results into:

```python
TransformOutputBundle(
    valid={"result": value},
    invalid={},
    side={},
    diagnostics=[],
    metrics=TransformMetrics(...),
)
```

The existing dataframe output bundle may be generalized or adapted rather than
duplicated. Output port roles and logical identities must survive compilation.

## Compiler responsibilities

A compiler MUST:

- preserve normative portable semantics
- reject unsupported operations before execution
- validate identifiers and bind values safely
- retain logical expression and output mappings
- preserve validation and security-domain boundaries
- expose collection, copy, and materialization requirements
- emit structured, redacted diagnostics
- enforce advertised limits

A compiler MUST NOT:

- silently approximate an operation
- inject UDFs or raw SQL as a fallback
- collect lazy values during planning or compilation
- embed secret values in compiled or explained artifacts
- optimize across security, validation, retry, or materialization boundaries
- report capabilities it does not pass in conformance tests

## Backend expectations

### Polars

Compile to `pl.Expr` and `LazyFrame` operations. Preserve laziness until the
plan declares collection. Avoid row conversion between compatible Polars
steps.

### Pandas

Compile to dataframe and series operations. Declare eager execution, copying,
index treatment, and unsupported operations precisely. Portable semantics must
not depend on a meaningful Pandas index.

### SQL (shipped in 0.15)

Lower kernel + `portable-relational/1` into typed `etlantic.sql/1` IR before
dialect compilation (`etlantic-sql`). Use bound parameters, validate
identifiers, retain relation lineage, and prohibit trusted SQL fragments in
portable definitions. Under `require`, fail when the dialect cannot claim the
profile; under `prefer`, select an explicit native SQL implementation only —
never silent portable emulation or an implicit dataframe-engine fallback.

### PySpark

Compile to native DataFrame and Column expressions. Preserve Catalyst-visible
operations. Python and Pandas UDF fallback is forbidden unless a future,
explicitly non-portable capability is selected.

## Discovery

The shipped entry-point group is:

```toml
[project.entry-points."etlantic.transform_compilers"]
polars = "etlantic_polars:create_transform_compiler"
pandas = "etlantic_pandas:create_transform_compiler"
pyspark = "etlantic_pyspark:create_transform_compiler"
sql = "etlantic_sql:create_transform_compiler"
```

An existing engine plugin MAY expose its compiler through its primary plugin
object. Discovery must still produce an explicit compiler descriptor so plans
can record protocol and capability compatibility.

Production profiles require plugin allowlisting and version policy. Compiler
discovery is a trust decision because Python entry points execute with host
process privileges.

## Conformance

**0.15** ships the public suite (Polars, PySpark, Pandas, SQL):

```python
from etlantic.testing import run_portable_transform_conformance_suite

run_portable_transform_conformance_suite(create_transform_compiler())
```

Also available as `etlantic.testing.portable_transform_conformance`.

Required fixture families (public suite):

- capability accuracy
- deterministic compilation
- scalar and relational semantics
- nulls, NaN, overflow, decimal, and casts
- timestamps and ordering
- joins and aggregations
- multiple output roles
- lazy/eager and ownership behavior
- unsupported-operation diagnostics
- bounded hostile IR
- secret and parameter redaction
- cross-engine result equivalence

Fixtures are selected from advertised capabilities. Claiming a profile or
operation without its mandatory fixture family fails the suite. Graduated
0.17 fixtures run for Polars and PySpark; continuation-family fixtures do not
imply a compiler claim.

Advertised capability coverage, not plugin name, determines which fixtures are
mandatory.

## Versioning

Compiler packages declare compatible core, plan-schema, and transform-protocol
versions. Unknown IR major versions fail closed. Capability additions may be
minor releases; changing an existing operation's meaning requires a new IR
major version.
