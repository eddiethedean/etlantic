# Architecture Decisions

ETLantic uses Architecture Decision Records (ADRs) for choices that affect
module boundaries, public protocols, persistent formats, or multiple
subsystems.

## ADR Template

```markdown
# ADR-NNN: Title

Date: YYYY-MM-DD
Status: Proposed | Accepted | Superseded | Rejected

## Context

What problem or constraint requires a decision?

## Decision

What will the project do?

## Consequences

What becomes easier, harder, required, or prohibited?

## Alternatives

What other approaches were considered?

## Compatibility

How does this affect public APIs, plugins, plans, or generated artifacts?
```

ADRs should be stored in:

```text
docs/11_DEVELOPMENT/adr/
```

Current proposal:

- [ADR-013: Closed Portable Transformation IR](adr/ADR-013-PORTABLE-TRANSFORMATION-IR.md)

## Foundational ADRs

The initial implementation should formalize at least these records.

### ADR-001: Layered Architecture

```text
Authoring
    ↓
Introspection
    ↓
Validation
    ↓
Planning
    ↓
Pipeline Plan
    ↓
Plugins and Compilers
```

Dependencies flow downward. Execution plugins must not mutate authoring models.

### ADR-002: Immutable Pipeline Plan

`PipelinePlan` is an immutable, serializable intermediate representation.
Planner working state remains internal and mutable only during construction.

### ADR-003: Async Plugin Boundary

Orchestration-facing plugin protocols are asynchronous. Synchronous libraries
are adapted through managed worker boundaries.

### ADR-004: Explicit Runtime Container

Registries, configuration, plugins, and resource providers belong to a scoped
runtime object rather than mutable process-wide globals.

This enables deterministic tests and multiple isolated runtimes in one process.

### ADR-005: Protocols Over Deep Inheritance

Plugin and integration APIs prefer small protocols and composition. Base
classes may offer convenience behavior but must not be required for
conformance.

### ADR-006: Stable Identity

Pipelines, transformations, steps, ports, contracts, and generated artifacts
require stable identities that do not depend on memory addresses or incidental
class ordering.

### ADR-007: Plugin Discovery Through Entry Points

Installed plugins may be discovered through Python entry points. Direct,
explicit registration remains available and should be preferred in tests.

Discovery must be deterministic and inspectable.

### ADR-008: Source-Aware Diagnostics

The introspection and loading layers retain enough origin information to map
diagnostics to Python declarations and contract files.

### ADR-009: No Secrets in Plans

Plans may contain resource references but never resolved credentials. Secret
resolution occurs at runtime through resource providers.

### ADR-010: Backend Capability Negotiation

The planner compares required semantics with declared plugin capabilities.
Unsupported behavior fails during planning rather than being silently
approximated during execution.

### ADR-011: Logical and Physical Graphs Remain Distinct

The logical pipeline preserves user-visible step identity. A physical backend
may fuse or expand execution units, but it must retain mappings for lineage,
diagnostics, and failure attribution.

### ADR-012: Pure Python Core

The core is implemented in Python. Native engines are accessed through plugins.
Optional acceleration must remain behind stable Python interfaces.

## Dependency Rules

Suggested package dependency direction:

```text
typing + identifiers + diagnostics
                 ↓
authoring + contracts + introspection
                 ↓
validation + graph
                 ↓
planning + plan model
                 ↓
sdk protocols
                 ↓
runtime + compilers + cli
```

The core must not import Pandas, Polars, PySpark, Airflow, or SQLAlchemy as
required dependencies.

## When an ADR Is Required

Write an ADR when a change:

- Adds or changes a public protocol
- Alters `PipelinePlan`
- Introduces a new plugin category
- Changes dependency direction
- Changes contract-generation meaning
- Adds persistent configuration
- Alters security boundaries
- Is difficult to reverse

Minor refactors and local implementation choices do not require ADRs.
