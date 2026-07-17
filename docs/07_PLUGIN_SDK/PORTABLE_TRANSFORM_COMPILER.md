# Portable Transformation Compiler Protocol

!!! warning "Proposed 0.12+ plugin protocol—not available in ETLantic 0.10"
    This page defines the intended `etlantic.transform-compiler/1` boundary for
    consuming DTCS Transformation Plans. It is not a currently importable SDK.

A portable transformation compiler translates a validated
`dtcs.transform-plan/1` into backend-native expressions without changing its
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

## Proposed protocol

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
    dtcs_plan_versions=("dtcs.transform-plan/1",),
    capabilities=TransformCapabilities(...),
)
```

Capabilities are an ETLantic adapter over the DTCS Engine Capability Model.
They list exact registered Semantic Action/Function versions, portable types,
semantic modes, maximum supported plan size, lazy/eager behavior, and artifact
ownership. Plans and reports preserve the originating DTCS capability
identifiers.

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
            requirement="function:string.concat_ws/1",
            reason="function is not implemented",
        ),
    ),
)
```

It MUST NOT import arbitrary user modules, resolve secrets, acquire resources,
read data, or contact a backend. Optional backend capability probing is a
separate explicitly requested operation and cannot weaken fail-closed planning.

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

### SQL

Lower into the safe ETLantic SQL IR before dialect compilation. Use bound
parameters, validate identifiers, retain relation lineage, and prohibit trusted
SQL fragments in portable definitions.

### PySpark

Compile to native DataFrame and Column expressions. Preserve Catalyst-visible
operations. Python and Pandas UDF fallback is forbidden unless a future,
explicitly non-portable capability is selected.

## Discovery

The proposed entry-point group is:

```toml
[project.entry-points."etlantic.transform_compilers"]
polars = "etlantic_polars:create_transform_compiler"
```

An existing engine plugin MAY expose its compiler through its primary plugin
object. Discovery must still produce an explicit compiler descriptor so plans
can record protocol and capability compatibility.

Production profiles require plugin allowlisting and version policy. Compiler
discovery is a trust decision because Python entry points execute with host
process privileges.

## Conformance

The public suite should expose:

```python
from etlantic.testing import portable_transform_conformance
```

Required fixture families:

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

Advertised capability coverage, not plugin name, determines which fixtures are
mandatory.

## Versioning

Compiler packages declare compatible core, plan-schema, and transform-protocol
versions. Unknown IR major versions fail closed. Capability additions may be
minor releases; changing an existing operation's meaning requires a new IR
major version.
