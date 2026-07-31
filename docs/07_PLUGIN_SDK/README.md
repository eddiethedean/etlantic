# Plugin SDK

> **Status: Available in ETLantic 0.40.0.**

!!! tip "Start here when creating a plugin"
    Follow [Building an ETLantic Plugin](BUILDING_A_PLUGIN.md) for the canonical
    package-from-zero workflow and release checklist. All reference and
    third-party plugins should follow that guide; the category pages below
    define the detailed protocols.

!!! note "Portable transformation compilers"
    The
    [Portable Transformation Compiler Protocol](PORTABLE_TRANSFORM_COMPILER.md)
    defines how plugins compile [DTCS](../04_TRANSFORMATIONS/DTCS.md) Transformation Plans. Polars, PySpark,
    and Pandas ship relational `/1` compilers; third parties must pass
    `run_portable_transform_conformance_suite` for advertised claims.

The Plugin SDK enables developers to extend ETLantic with new execution
engines, dataframe backends, storage providers, resource providers,
orchestration platforms, registries, and future extension points.

ETLantic is intentionally designed around a small, stable core and a rich
plugin ecosystem. The SDK defines the public interfaces, lifecycle, and
conformance requirements for building those plugins.

## Public imports (0.34)

Recommended application and tutorial style:

```python
import etlantic as etl
```

Curated root symbols include `etl.Data`, `etl.Transformation`, `etl.Pipeline`,
`etl.Extract`, `etl.Load`, `etl.Input`, `etl.Output`, `etl.Parameter`,
`etl.Profile`, `etl.PipelineRuntime`, plus plan/report helpers. Lazy namespaces
stay import-safe until accessed:

- `etl.dataframe` / `etlantic.dataframe` — dataframe protocol + discovery
- `etl.sql` / `etlantic.sql` — SQL protocol + discovery
- `etl.spark` / `etlantic.spark` — Spark protocol + discovery
- `etl.orchestration` / `etlantic.orchestration` — orchestrator protocol + `compile_plan`
- `etl.transform` / `etlantic.transform` — portable authoring
- `etl.authoring` / `etlantic.authoring` — `PipelineDefinition`, builders, JSON codecs
- `etl.service` / `etlantic.service` — authoring/service facade (HTTP adapters optional)
- `etl.secrets` / `etlantic.secrets` — secret refs / providers
- `etl.viz` / `etlantic.viz` — Graphviz DOT / HTML / lineage export
- `etl.testing` / `etlantic.testing` — conformance suites (dataframe, SQL, Spark,
  orchestrator, scheduler, secrets, write-semantics, portable transform)

`from etlantic import Data, Pipeline` remains supported. Specialist symbols
belong on owning modules or lazy namespaces — demoted root aliases were
removed in 0.37.0.

Also see [Capability Vocabulary](CAPABILITY_VOCABULARY.md),
[Protocol Evolution](PROTOCOL_EVOLUTION.md), and
[`etlantic plugin compatibility`](../10_REFERENCE/CLI.md).

Production profiles should set `Profile.plugin_allowlist` (names + optional
version pins). Discovery fails closed when the allowlist rejects a plugin.

## What This Section Covers

This section explains how to:

- Build plugins
- Register plugins
- Declare capabilities
- Implement execution interfaces
- Extend ETLantic safely
- Test plugins
- Version plugins
- Publish plugins
- Maintain compatibility

## Philosophy

ETLantic defines the portable modeling layer.

Plugins provide implementation-specific behavior.

```text
        ETLantic Core
                │
                ▼
            Plugin SDK
                │
     ┌──────────┼──────────┐
     ▼          ▼          ▼
 Execution  Dataframe   Storage
  Plugins     Plugins    Plugins
     │          │          │
     └──────┬───┴──────┬───┘
            ▼          ▼
      Resource     Registry
      Providers     Plugins
                │
                ▼
       Orchestration Plugins
```

The SDK allows the ecosystem to grow without expanding the responsibilities of
the core library.

## Design Goals

The Plugin SDK should:

- Keep the core framework small.
- Provide stable extension interfaces.
- Preserve ETLantic semantics.
- Support independent plugin releases.
- Encourage interoperability.
- Enable community-developed plugins.

## Plugin Lifecycle

Typical lifecycle:

1. Discover
2. Register
3. Validate
4. Advertise capabilities
5. Participate in planning
6. Execute or provide services
7. Report diagnostics
8. Clean up resources

## Plugin Categories

The SDK supports plugin categories such as:

- Execution plugins
- Dataframe plugins
- Orchestration plugins
- Storage plugins
- Resource providers
- Secret providers
- Registry plugins
- Observability providers
- Future extension types

Each category has its own specialized interface while sharing common lifecycle
and capability concepts.

## Capability-Driven Architecture

Plugins explicitly advertise the features they support.

Planning uses these capabilities to determine whether a plugin can satisfy a
Pipeline Plan without changing its semantics.

## Versioning

Plugins should declare compatibility with:

- ETLantic
- [ODCS](../03_DATA_CONTRACTS/ODCS.md)
- DTCS
- [DPCS](../05_PIPELINES/DPCS.md)

Independent versioning allows plugins to evolve without forcing synchronized
releases across the ecosystem.

## Documentation Roadmap

Read this section in the following order:

1. [Building an ETLantic Plugin](BUILDING_A_PLUGIN.md)
2. [Overview](OVERVIEW.md)
3. The protocol page for your plugin category
4. [Testing Plugins](TESTING_PLUGINS.md)
5. [Capability Vocabulary](CAPABILITY_VOCABULARY.md)
6. [Protocol Evolution](PROTOCOL_EVOLUTION.md)
7. [Distribution](DISTRIBUTION.md)

## Key Principles

- The core owns modeling.
- Plugins own implementation.
- Capability matching drives planning.
- Plugins preserve, not redefine, pipeline semantics.
- Stable SDK interfaces encourage a healthy ecosystem.
- Plugin discovery is a trust decision because Python plugins execute code.
- Production profiles should support allowlists and pinned plugin versions.

Plugin authors should read the
[Security Model](../02_FOUNDATIONS/SECURITY.md).

## Next Step

Continue with the [Plugin SDK Overview](OVERVIEW.md) to learn the foundational
design of the ETLantic Plugin SDK.
