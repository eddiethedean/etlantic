# Plugin SDK Overview

The published DTCS 3.0 Transformation Plan model enables ETLantic's planned
portable transformation compiler role for engine plugins. See
[Portable Transformation Compiler](PORTABLE_TRANSFORM_COMPILER.md). It is
planned across ETLantic 0.11-0.15 and is not shipped in 0.10.

Compiler support is expressed through exact DTCS profiles, actions, functions,
operators, types, and modes. Plugin identity alone never implies portable
coverage.

The ETLantic Plugin SDK defines the public interfaces used to extend
ETLantic without modifying its core.

The core framework is responsible for modeling, validation, planning, contract
coordination, common lifecycle semantics, and result normalization. Plugins
provide concrete runtime behavior for execution, storage, orchestration,
resources, and other extension points.

## Purpose

The Plugin SDK exists to:

- Keep the core framework small and stable.
- Enable independent plugin development.
- Support multiple execution technologies.
- Preserve portable pipeline semantics.
- Encourage a healthy ecosystem of community plugins.

## Architecture

```text
ETLantic Core
        │
        ▼
Validation
        │
        ▼
Planning
        │
        ▼
Pipeline Plan (IR)
        │
        ▼
Plugin SDK
        │
 ┌──────┼────────────────────────────────────────┐
 ▼      ▼         ▼         ▼         ▼          ▼
Execution Dataframe Storage Resource Registry Orchestration
 Plugins   Plugins   Plugins  Plugins  Plugins    Plugins
```

Every plugin consumes or contributes to planning, compilation, or execution of
a validated `PipelinePlan`. No plugin changes the meaning of the pipeline.

## Core Principles

The SDK is built around a few simple principles:

- **Stable interfaces** — Public APIs evolve carefully.
- **Capability driven** — Plugins declare what they support.
- **Portable semantics** — Plugins preserve ODCS, DTCS, and DPCS semantics.
- **Independent versioning** — Plugins evolve independently of the core.
- **Loose coupling** — Plugins depend on the SDK, not each other's private APIs.
- **Honest capabilities** — Unsupported semantics fail during planning.
- **Logical traceability** — Physical work maps back to logical identities.
- **Secret safety** — Plans contain references, never resolved credentials.

## Plugin Lifecycle

Every plugin follows the same high-level lifecycle:

1. Discovery
2. Registration
3. Capability declaration
4. Validation
5. Planning participation
6. Runtime execution or service provision
7. Diagnostics
8. Cleanup

## Plugin Categories

ETLantic currently defines several plugin categories:

- Execution Plugins
- Dataframe Plugins
- Orchestration Plugins
- Storage Plugins
- Resource Providers
- Registry Plugins

Additional categories require a demonstrated responsibility that cannot be
expressed cleanly through the existing SDK. New categories should not be added
merely to mirror every external technology.

## Capability Matching

Planning selects plugins based on declared capabilities.

Examples include:

- Async execution
- Parallel execution
- Streaming
- Retry support
- Transactions
- Checkpoints
- Approval workflows

If a plugin cannot satisfy mandatory requirements, planning fails before
execution.

## Version Compatibility

Plugins should publish compatibility information for:

- ETLantic
- ODCS
- DTCS
- DPCS

This allows the ecosystem to evolve while maintaining predictable behavior.

## Best Practices

- Build plugins against the public SDK only.
- Keep implementations focused on one responsibility.
- Preserve observable pipeline behavior.
- Emit structured diagnostics.
- Document capabilities clearly.

## Key Principle

> ETLantic provides the portable execution model. The Plugin SDK enables
> implementations to extend that model while preserving its semantics and
> interoperability.

## Next Step

Continue with [Dataframe Plugin](DATAFRAME_PLUGIN.md) to explore the first
concrete SDK extension interface.
