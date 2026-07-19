# Arrow and DataFusion Integration Plan (0.18+)

This plan defines ETLantic's Arrow and DataFusion direction after 0.17. It is
intentionally gated: Arrow is the physical interchange foundation, and
DataFusion must independently prove value before it becomes a recommended
compatibility commitment.

## Decision summary

| Layer | Decision |
|---|---|
| Semantic contracts | Retain Pydantic / ContractModel and ODCS / DTCS / DPCS |
| Logical pipeline and planning | Retain ETLantic models and `PipelinePlan` |
| Physical tabular interchange | Prefer versioned Arrow mechanisms when compatible |
| Local analytical execution | Evaluate `etlantic-datafusion` as an optional plugin |

No infrastructure dependency may redefine ETLantic's contracts, validation,
planning, trust, reliability, lineage, or normalized evidence.

## Work sequence

### A. Arrow before another engine

Formalize Arrow boundary descriptors, capabilities, schemas, ownership,
streaming, collection, fallback, and run evidence. Retrofit Polars and Pandas
and make the conformance suite pass before building DataFusion. This separates
interchange bugs from new-engine bugs.

Required artifacts:

- versioned interchange descriptor and schema;
- plan-explain and run-report rendering;
- Arrow C Data / Stream, IPC stream/file, Parquet, and fallback vocabulary;
- fidelity corpus for null, decimal, temporal/timezone, nested, dictionary,
  extension, and field-order behavior;
- bounded streaming, lifetime, ownership, retry, and branch-isolation tests;
- clean-environment tests with and without PyArrow.

### B. DataFusion kernel experiment

Generalize engine discovery away from fixed engine-name sets, then create
`etlantic-datafusion` with separate runtime and portable-compiler factories.
The first release claims only the DTCS kernel operations it passes in public
conformance.

The user-facing installation is one ETLantic extra:

```bash
pip install "etlantic[datafusion]"
```

That extra installs the independently versioned integration and its compatible
DataFusion / Arrow dependencies. Core-only installation remains unchanged.

Measure against local records and Polars:

- cold import and installation footprint;
- plan/compile and execution latency;
- peak memory and number of materializations/copies;
- batch streaming and time-to-first-batch;
- schema and value fidelity;
- diagnostic quality and logical-step attribution.

Graduation requires conformance plus a distinct measured advantage. A working
adapter that only duplicates Polars is insufficient.

## Stop conditions

Stop or defer a component when:

- it requires backend classes or live objects in core protocols or serialized
  plans;
- it adds a mandatory heavy dependency to the core wheel;
- semantic loss cannot be detected before mutation;
- source rows or resolved secrets would enter plans, diagnostics, reports, or
  schema history;
- it duplicates an existing engine or subsystem without measurable benefit;
- it makes CLI, embedded SDK, or scheduler use depend on another surface.

## Release evidence

Every shipped gate publishes:

- exact capability and compatibility matrices;
- deterministic golden artifacts;
- public conformance and cross-engine differential results;
- clean-environment dependency/import checks;
- failure, cancellation, cleanup, trust, and redaction tests;
- reproducible performance measurements where value is performance-based;
- limitations, fallback behavior, and a migration/rollback note.

The full milestone gates and acceptance scenarios are normative in the
[roadmap](../../ROADMAP.md).
