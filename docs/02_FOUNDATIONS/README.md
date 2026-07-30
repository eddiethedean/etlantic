# Foundations

The Foundations section defines ETLantic's product identity, architectural
boundaries, vocabulary, and documentation stability model.

## Recommended Order

**Start here (required):**

1. [Documentation Status](https://etlantic.readthedocs.io/en/latest/02_FOUNDATIONS/DOCUMENTATION_STATUS/) — how to read Available vs Future design
2. [Core Concepts](https://etlantic.readthedocs.io/en/latest/02_FOUNDATIONS/CORE_CONCEPTS/)
3. [Architecture](https://etlantic.readthedocs.io/en/latest/02_FOUNDATIONS/ARCHITECTURE/)
4. [Security Model](https://etlantic.readthedocs.io/en/latest/02_FOUNDATIONS/SECURITY/)
5. [Glossary](https://etlantic.readthedocs.io/en/latest/02_FOUNDATIONS/GLOSSARY/)

**Optional philosophy** (same thesis, different angles—skip on the first pass):

- [Vision](https://etlantic.readthedocs.io/en/latest/02_FOUNDATIONS/VISION/)
- [Why ETLantic](https://etlantic.readthedocs.io/en/latest/02_FOUNDATIONS/WHY_ETLANTIC/)
- [FastAPI Philosophy](https://etlantic.readthedocs.io/en/latest/02_FOUNDATIONS/FASTAPI_PHILOSOPHY/)
- [Design Principles](https://etlantic.readthedocs.io/en/latest/02_FOUNDATIONS/DESIGN_PRINCIPLES/)
- [Manifesto](https://etlantic.readthedocs.io/en/latest/ETLANTIC_MANIFESTO/)

## Foundation in One Sentence

> ETLantic uses typed Python declarations and three portable contract
> standards to build a validated logical pipeline, resolves that pipeline into
> a deterministic `PipelinePlan`, and delegates realization to external
> backends through plugins.

Since 0.24, ETLantic generalizes typed Python declarations into equivalent
class, functional, JSON, and visual authoring over one canonical
`PipelineDefinition`. See
[Programmatic authoring](https://etlantic.readthedocs.io/en/latest/05_PIPELINES/PROGRAMMATIC_AUTHORING/).

## Non-Negotiable Boundaries

- [ODCS](https://etlantic.readthedocs.io/en/latest/03_DATA_CONTRACTS/ODCS/), [DTCS](https://etlantic.readthedocs.io/en/latest/04_TRANSFORMATIONS/DTCS/), and [DPCS](https://etlantic.readthedocs.io/en/latest/05_PIPELINES/DPCS/) own contract semantics.
- ContractModel operationalizes data contracts.
- ETLantic owns typed authoring, validation, planning, and coordination.
- Plugins own backend adaptation.
- External systems perform computation, scheduling, and persistence.
