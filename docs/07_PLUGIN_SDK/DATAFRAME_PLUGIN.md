# Dataframe Plugin

A **Dataframe Plugin** implements the ETLantic Dataframe Plugin API for a
specific dataframe engine.

**Status: shipped in 0.5.0** (`etlantic.dataframe/1`).

!!! note "Future compiler role"
    The shipped protocol invokes native transformation callables. In 0.12+,
    dataframe plugins may additionally implement the
    [portable transformation compiler](PORTABLE_TRANSFORM_COMPILER.md). The two
    protocols remain separately versioned.

## Responsibilities

- Materialize logical inputs into native frames
- Invoke registered `@Transformation.implementation(engine)` callables
- Validate outputs against contracts
- Inspect schemas into `NormalizedSchema`
- Enforce ownership / mutation isolation
- Collect lazy values only when the plan declares a boundary

Plugins are **not** responsible for pipeline planning, graph scheduling, or
contract generation.

## Discovery

Plugins register via the `etlantic.dataframe_plugins` entry-point group.
`PipelineRuntime` discovers installed plugins at construction time. You can
also call `runtime.register_dataframe_plugin(engine, plugin)`.

## Conformance

Use `etlantic.testing.run_conformance_suite(plugin, engine=..., sample_rows=...)`
to exercise discovery, materialization, validation, schema inspection, and
ownership helpers.
