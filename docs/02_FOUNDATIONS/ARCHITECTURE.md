# Architecture

ETLantic is a typed modeling, validation, planning, and coordination
framework for data pipelines.

It does not implement dataframe computation, distributed scheduling, storage,
or infrastructure. It defines a portable logical pipeline, resolves that model
for a selected environment, and delegates the resulting plan to plugins and
external systems.

## Architectural Boundary

```text
Standards own meaning.
ContractModel operationalizes data contracts.
ETLantic owns the logical model and resolved plan.
Plugins own backend adaptation and execution.
External systems perform the work.
```

This boundary is the primary defense against ETLantic becoming another
monolithic ETL framework.

Security is a cross-cutting architectural constraint, not a plugin feature.
See the [Security Model](SECURITY.md).

## System Overview

```text
┌──────────────────────────────────────────────────────────────┐
│ Authoring and Interchange                                   │
│                                                              │
│ ContractModel classes   Transformation classes   Pipelines   │
│ Portable expressions   ODCS / DTCS / DPCS documents          │
└──────────────────────────────┬───────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────┐
│ Typed Logical Model                                          │
│                                                              │
│ Contracts • ports • steps • edges • parameters • identities │
└──────────────────────────────┬───────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────┐
│ Analysis                                                     │
│                                                              │
│ Introspection • references • validation • diagnostics        │
└──────────────────────────────┬───────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────┐
│ Planning                                                     │
│                                                              │
│ Profiles • bindings • capabilities • execution regions       │
│ resources • materialization boundaries                       │
└──────────────────────────────┬───────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────┐
│ PipelinePlan                                                 │
│                                                              │
│ Immutable • resolved • deterministic • secret-free           │
└──────────────────────┬───────────────┬───────────────────────┘
                       ▼               ▼
              Direct execution     Compilation / generation
                       │               │
                       ▼               ▼
              Runtime plugins      Backend artifacts, docs,
                                   diagrams, lineage
```

## Authoring Layer

ETLantic supports complementary authoring paths.

### Code-first

- `Data` classes define data contracts.
- `Transformation` classes define typed interfaces.
- Portable definitions optionally describe relational behavior once through a
  PySpark-inspired symbolic API (accepted design for 0.11+).
- `Pipeline` classes connect sources, steps, sinks, and subpipelines.

### Contract-first

- ContractModel loads ODCS data contracts.
- ETLantic integrations load DTCS transformations.
- ETLantic loads DPCS pipelines.

Both paths converge on semantically equivalent domain models and one typed
logical pipeline graph. ETLantic does not flatten ODCS, DTCS, and DPCS
into one universal contract object.

## Typed Logical Model

The logical model captures portable meaning:

- Stable identities
- Data-contract references
- Typed transformation ports
- Parameters and defaults
- Sources and sinks
- Step instances
- Edges and dependencies
- Subpipeline interfaces
- Callbacks and declared failure policy
- Lifespan, middleware, and typed resource requirements
- Typed outbound event declarations

It excludes resolved credentials, dataframe objects, scheduler tasks, database
connections, and cluster handles.

Beginning with the proposed 0.11 work, the logical model may also contain a
closed `dtcs.transform-plan/1` expression graph. This graph is data-only and
backend-independent; native Polars, Pandas, SQL, and Spark objects remain
outside core.

The canonical expression and Transformation Plan models belong to the `dtcs`
package. `etlantic.transform` is a PySpark-inspired authoring facade over those
public models, not a parallel semantic model. ETLantic and DTCS share a
publisher, enabling coordinated standard/package evolution under explicit
version and compatibility gates.

## Validation Architecture

Validation is phased so tools can provide precise diagnostics:

1. **Definition validation** — annotations, metadata, identities, and class
   declarations are internally valid.
2. **Contract validation** — ODCS, DTCS, and DPCS artifacts satisfy their
   authorities.
3. **Graph validation** — dependencies, ports, cycles, fan-in, fan-out, and
   subpipeline boundaries are valid.
4. **Compatibility validation** — producer outputs satisfy consumer inputs.
5. **Portable-expression validation** — columns, types, outputs, operations,
   and bounded structure are valid when a portable definition is present.
6. **Profile validation** — bindings and resources are complete.
7. **Capability validation** — selected plugins and compilers can preserve required
   semantics.
8. **Runtime data validation** — actual inputs and outputs satisfy their data
   contracts at configured boundaries.

The first seven phases occur before execution. Runtime data validation occurs
through ContractModel and backend integrations.

## Planning Architecture

Planning combines a valid logical pipeline with a profile.

```text
Logical pipeline
      +
Profile
      +
Installed plugin capabilities
      ↓
Resolved PipelinePlan
```

The planner resolves:

- Transformation implementations
- Portable transformation compiler selection and operation requirements
- Source and sink bindings
- Orchestrator selection
- Resource-provider references
- Execution modes
- Artifact boundaries
- Retry and timeout requirements
- Backend capability constraints
- Portable IR and compiler fingerprints
- SQL or Spark execution regions

Planning must not execute transformations, acquire live credentials, or
materialize data.

Planning should also avoid importing or executing untrusted user modules when a
static discovery path is available.

## PipelinePlan

`PipelinePlan` is the resolved intermediate representation between authoring
and execution.

It should be:

- Immutable after construction
- Deterministic for equivalent inputs
- Serializable where practical
- Fully resolved
- Inspectable
- Versioned
- Free of resolved secrets

The plan preserves mappings between logical nodes and physical execution units.
This is essential because a backend may fuse several logical transformations
into one SQL statement or Spark plan while ETLantic still needs
step-level lineage, diagnostics, and failure attribution.

## Logical and Physical Graphs

ETLantic distinguishes:

```text
Logical graph
User-visible sources, steps, sinks, ports, and contracts

Physical graph
Backend tasks, fused queries, Spark stages, materializations, and submissions
```

Optimizations may change the physical graph. They must not silently change the
observable semantics of the logical graph.

## Execution Regions

Adjacent compatible nodes may be grouped into an execution region:

- A SQL region compiled into one or more statements
- A Polars lazy region collected at a sink
- A Spark region represented by one logical Spark plan
- A local Python region coordinated by the reference orchestrator

Region formation depends on:

- Available implementations
- Shared execution environment
- Validation boundaries
- Retry and failure boundaries
- Reuse and fan-out
- Backend capabilities
- Required materialization
- Portable-expression compatibility and compiler support

## Plugin Architecture

The core depends on public protocols rather than backend packages.

Primary extension families are:

| Extension | Responsibility |
|---|---|
| Dataframe plugin | Execute transformation implementations with a dataframe engine |
| Portable transformation compiler | Compile DTCS Transformation Plans to native backend operations |
| SQL plugin and dialect | Compile and execute SQL-native regions |
| PySpark plugin | Build and submit Spark-native regions |
| Orchestrator plugin | Coordinate or compile pipeline execution |
| Storage plugin | Read and write persistent datasets |
| Resource provider | Acquire managed runtime dependencies |
| Observability provider | Route logs, metrics, traces, and lifecycle events |
| Notification provider | Deliver typed outbound events |

Plugins advertise capabilities. The planner selects them only when those
capabilities satisfy the logical model.

## Runtime Architecture

The runtime boundary is async-first.

```text
async def callable
    → await directly

def callable
    → managed worker boundary

CPU-heavy Python
    → process or external mode when declared

Airflow, Spark, dbt, remote service
    → plugin-managed external execution
```

ETLantic coordinates invocation, concurrency limits, cancellation,
timeouts, context propagation, and cleanup. It does not assume worker threads
make CPU-heavy Python parallel.

## Lifecycle Extension Architecture

ETLantic uses separate mechanisms for distinct lifecycle concerns:

```text
Runtime lifespan
    └── initialize and clean up shared runtime state

Run and step middleware
    └── wrap matching logical operations

Resource injection
    └── acquire typed services required by callables

Lifecycle callbacks
    └── respond to specific outcomes with declarative actions

Outbound event declarations
    └── document and deliver typed external notifications
```

These mechanisms remain separate so ordering, cleanup, portability, and failure
semantics are predictable.

## Resource Architecture

Logical models refer to named resources. Profiles bind those names to resource
providers.

```text
Transformation requires "warehouse"
                 ↓
Production profile selects SQLAlchemy provider
                 ↓
Provider resolves credentials at runtime
                 ↓
Managed connection is injected and cleaned up
```

Resolved secrets must never enter contracts, generated documentation, or a
serialized `PipelinePlan`.

## Generation Architecture

Validated models and plans can generate:

- ODCS, DTCS, and DPCS artifacts
- Mermaid and Graphviz diagrams
- HTML documentation
- Lineage
- Pipeline interface descriptions
- SQL scripts
- Airflow DAGs
- Plugin-defined deployment artifacts

Generation must be deterministic and suitable for a CI `--check` workflow.

## Repository and Dependency Direction

The intended dependency direction is:

```text
identities + typing + diagnostics
              ↓
authoring + contract integrations
              ↓
logical graph + validation
              ↓
profiles + planning + PipelinePlan
              ↓
Plugin SDK
              ↓
runtime + compilers + CLI
```

The core package must not require Pandas, Polars, PySpark, Airflow, or a SQL
engine.

## Architectural Invariants

1. Importing a pipeline never executes it.
2. Planning never materializes user data.
3. Profiles do not redefine portable semantics.
4. Plugins preserve logical meaning or planning fails.
5. Generated artifacts derive from validated models or plans.
6. Resolved secrets never enter portable artifacts.
7. Physical optimization retains logical identity mappings.
8. Sync and async implementations produce equivalent framework behavior.
9. Domain standards remain authoritative for contract meaning.
10. Execution technology never becomes the source of truth.

## Related Reading

- [Core Concepts](CORE_CONCEPTS.md)
- [Design Principles](DESIGN_PRINCIPLES.md)
- [Planning](../05_PIPELINES/PLANNING.md)
- [Execution Model](../06_EXECUTION/EXECUTION_MODEL.md)
- [Plugin SDK](../07_PLUGIN_SDK/README.md)
- [Architecture Decisions](../11_DEVELOPMENT/ARCHITECTURE_DECISIONS.md)
