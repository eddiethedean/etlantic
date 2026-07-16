# Benchmarks

Pipelantic benchmarks measure modeling, validation, planning, and
coordination overhead. They do not claim ownership of Pandas, Polars, SQL, or
Spark engine performance.

## Dataframe scale harness (0.5)

A lightweight correctness/timing harness lives at
`benchmarks/dataframe_scale.py`:

```bash
uv run --group dataframes python benchmarks/dataframe_scale.py polars
uv run --group dataframes python benchmarks/dataframe_scale.py pandas
```

Publish dataset shape, warm-up count, environment, and elapsed seconds with
any regression notes. Thresholds are advisory during 0.x.

## Goals

Benchmarks should answer:

- How quickly can models be introspected?
- How does validation scale with graph size?
- How deterministic and efficient is planning?
- What overhead does sync/async normalization add?
- How expensive is plugin discovery?
- What benefits do SQL and Spark execution-region optimizations provide?

## Benchmark Categories

### Startup

Measure:

- Import time
- Runtime construction
- Configuration loading
- Plugin discovery disabled and enabled

The core package should not import heavyweight optional backends at startup.

### Authoring and Introspection

Measure class creation and inspection for:

- 10, 100, 1,000 transformations
- Multiple inputs and outputs
- Deep inheritance
- `Annotated` metadata

### Validation

Measure:

- Linear pipelines
- Wide fan-out
- Deep fan-in
- Subpipelines
- Invalid graphs with many diagnostics
- Cross-contract compatibility checks

### Planning

Measure:

- Binding resolution
- Capability negotiation
- Implementation selection
- Execution-region formation
- Canonical plan serialization

### Local Runtime Overhead

Measure framework overhead around no-op or controlled operations:

- `def` invocation through worker threads
- `async def` invocation
- Independent DAG branches
- Hook dispatch
- Resource acquisition and cleanup

Do not present no-op throughput as real ETL throughput.

### SQL Optimization

Compare:

- Materialized multi-step execution
- Fused SQL execution
- Predicate and projection pushdown
- Generated query size and compilation time

### Spark Optimization

Compare:

- Logical step regions
- Materialization boundaries
- Native expressions versus Python UDFs
- Plan construction overhead

Spark engine execution results must be identified as environment-dependent.

## Dataset Shapes

Use named benchmark scenarios:

```text
tiny-linear       10 nodes
medium-linear     100 nodes
wide-dag          1,000 nodes
deep-subpipeline  nested reusable pipelines
mixed-backend     SQL, Polars, and storage boundaries
```

Fixtures and seeds must be version-controlled.

## Methodology

- Warm and cold measurements must be separated.
- Record Python and dependency versions.
- Record operating system and hardware.
- Run enough samples to report distributions.
- Avoid network benchmarks in the default suite.
- Store raw results alongside summaries.

## Tools

Possible tooling:

- `pytest-benchmark`
- `pyperf`
- `memray`
- `tracemalloc`
- Backend-native explain plans

## Regression Thresholds

CI may enforce broad thresholds on stable microbenchmarks. Noisy distributed or
I/O benchmarks should run on controlled infrastructure and report trends rather
than block every change.

## Performance Budgets

Initial directional goals:

- Lightweight root import
- Near-linear graph validation
- Deterministic planning
- No eager plugin imports
- No data materialization during planning
- Bounded concurrency and memory growth

Hard numeric budgets should be adopted only after a working baseline exists.

## Reporting

Every published result should distinguish:

```text
Pipelantic overhead
Backend execution time
I/O time
Environment setup time
```

This prevents misleading comparisons between orchestration overhead and
data-engine performance.

## Optimization Rule

Optimize only after profiling a representative workload. Architectural clarity,
correctness, and stable semantics take priority over speculative micro-
optimizations.

