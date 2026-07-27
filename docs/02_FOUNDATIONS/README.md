# Foundations

The Foundations section defines ETLantic's product identity, architectural
boundaries, vocabulary, and documentation stability model.

## Recommended Order

**Start here (required):**

1. [Documentation Status](DOCUMENTATION_STATUS.md) — how to read Available vs Future design
2. [Core Concepts](CORE_CONCEPTS.md)
3. [Architecture](ARCHITECTURE.md)
4. [Security Model](SECURITY.md)
5. [Glossary](GLOSSARY.md)

**Optional philosophy** (same thesis, different angles—skip on the first pass):

- [Vision](VISION.md)
- [Why ETLantic](WHY_ETLANTIC.md)
- [FastAPI Philosophy](FASTAPI_PHILOSOPHY.md)
- [Design Principles](DESIGN_PRINCIPLES.md)
- [Manifesto](../ETLANTIC_MANIFESTO.md)

## Foundation in One Sentence

> ETLantic uses typed Python declarations and three portable contract
> standards to build a validated logical pipeline, resolves that pipeline into
> a deterministic `PipelinePlan`, and delegates realization to external
> backends through plugins.

Version 0.24 plans to generalize “typed Python declarations” into equivalent
class, functional, JSON, and visual authoring over one canonical
`PipelineDefinition`. See the
[0.24 Programmatic Authoring Plan](../11_DEVELOPMENT/PROGRAMMATIC_AUTHORING_0_24.md).

## Non-Negotiable Boundaries

- ODCS, DTCS, and DPCS own contract semantics.
- ContractModel operationalizes data contracts.
- ETLantic owns typed authoring, validation, planning, and coordination.
- Plugins own backend adaptation.
- External systems perform computation, scheduling, and persistence.
