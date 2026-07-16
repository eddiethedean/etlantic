# Dataframe Plugin

A **Dataframe Plugin** implements the Pipelantic Dataframe Plugin API for a
specific dataframe engine.

**Status: shipped in 0.5.0** (`pipelantic.dataframe/1`).

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

Plugins register via the `pipelantic.dataframe_plugins` entry-point group.
`PipelineRuntime` discovers installed plugins at construction time. You can
also call `runtime.register_dataframe_plugin(engine, plugin)`.

## Conformance

Use `pipelantic.testing.run_conformance_suite(plugin, engine=..., sample_rows=...)`
to exercise discovery, materialization, validation, schema inspection, and
ownership helpers.
