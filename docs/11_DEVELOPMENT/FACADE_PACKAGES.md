# Facade packages

> **Status: Available in ETLantic 0.28.0.** Defines first-party **facade**
> packages — domain-specific authoring layers that lower to ETLantic public
> definitions without adding domain vocabulary to core wire schemas.

## What is a facade package?

A facade package:

- Owns **domain vocabulary** (for example bronze/silver/gold in Medallantic)
- Constructs portable `PipelineDefinition` / `etlantic.pipeline/1` documents
- Calls only **public** ETLantic authoring, plan, profile, and runtime APIs
- Ships as its own PyPI distribution with the same minor as core

A facade package is **not** an execution plugin, compiler, scheduler, storage
adapter, or model bridge.

**Canonical example:** [`medallantic`](https://github.com/eddiethedean/etlantic/tree/main/packages/medallantic) (Medallantic).

## Allowed public imports

Facades may import from:

- `etlantic.authoring`, `etlantic.contracts`, `etlantic.profile`
- `etlantic.plan`, `etlantic.runtime`, `etlantic.reliability`
- `etlantic.capabilities`, `etlantic.diagnostics`, `etlantic.secrets`
- Public `etlantic.testing` for conformance (not private `_` modules)

Facades must **not** depend on private `etlantic._*` modules or first-party
adapter internals.

## Wire schema boundary

Core wire schemas (`etlantic.pipeline/1`, `etlantic.plan/1`, …) must not gain
medallion-specific identifiers. Domain enums and layer names stay in the facade
package and its documentation.

## Release category

| Tier | Examples | Classifier | Core pin |
|---|---|---|---|
| Execution plugins | `etlantic-polars`, `etlantic-sql`, … | Production/Stable | `etlantic>=X.Y,<X.(Y+1)` |
| **Facade** | `medallantic` | Beta (IR/migration adapter) | same |
| Reference adapter | `etlantic-fastapi` | Beta | same |
| Compatibility redirect | `etlantic-sparkforge` | Inactive | depends on facade |
| Experimental | `etlantic-datafusion` | Alpha | same |

Release gates (SBOM, provenance, wheel smoke, compatibility pins) apply to
facade packages the same way as execution plugins. See
[Release process](RELEASE_PROCESS.md).

## Conformance kit (0.29 / M1 stub)

Native medallion authoring (**0.29**) will add a facade conformance kit requiring:

- Definition round-trip (`PipelineDefinition` ↔ JSON)
- Graph equivalence hooks against `etlantic.interchange`
- No parallel execution model outside ETLantic runtime

0.28 documents the boundary only; the kit ships with Medallantic M1.

## See also

- [Medallantic roadmap](https://github.com/eddiethedean/etlantic/blob/main/packages/medallantic/ROADMAP.md)
- [Optional packages](../10_REFERENCE/OPTIONAL_PACKAGES.md)
- [Distribution](../07_PLUGIN_SDK/DISTRIBUTION.md)
- [Exit gate 0.28](EXIT_GATE_0_28.md)
