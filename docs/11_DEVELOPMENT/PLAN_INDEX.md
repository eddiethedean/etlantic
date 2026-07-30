# Planning Hub

ETLantic's planning documents describe intended outcomes, dependencies, and
release gates. They are **not** a substitute for current product documentation.

!!! important "Use the right source of truth"
    - To learn what **ETLantic 0.35 can do now**, use
      [Capabilities](../01_GETTING_STARTED/CAPABILITIES.md), the
      [CLI reference](../10_REFERENCE/CLI.md), and the
      [Python API reference](../10_REFERENCE/API_REFERENCE.md).
    - To understand **release order**, use the
      [main roadmap](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md).
    - To evaluate **shipped evidence**, use the
      [0.35 exit gate](EXIT_GATE_0_35.md), release notes, and tests.
    - To understand **why a boundary exists**, use
      [architecture decisions](ARCHITECTURE_DECISIONS.md).

No proposed interface becomes public API merely because it appears in a plan.
A capability is available only when the current-version documentation says it
is available and its release gate has passed.

## Portfolio at a glance

Status is relative to ETLantic **0.35.0**.

| Plan | Status | Current boundary | Next horizon or gate |
|---|---|---|---|
| [Main roadmap](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md) | Current sequence | 0.35 shipped (gate closed); 0.36 is next | 0.36 joint compatibility burn-in |
| [Adoption, connectivity, and operations](ADOPTION_ECOSYSTEM_PLAN.md) | Planned program | Testing preview available in 0.35; full foundation graduates later | Continues through 0.53 |
| [Multi-tenant control plane](MULTI_TENANT_CONTROL_PLANE_PLAN.md) | Planned program | 0.35 does not provide a production multi-tenant control plane | Incubation 0.40–0.43; graduation gate 0.44 |
| [User interface and experience](UI_UX_PLAN.md) | Partially shipped, cross-cutting | CLI and generated read-only artifacts exist; interactive, IDE, and hosted phases remain planned | Incremental; hosted work follows control-plane gates |
| [ETL reliability and recovery](ETL_RELIABILITY_PLAN.md) | Partially shipped, living plan | Public models, providers, and local CLI operations exist; managed and advanced capabilities remain planned | Control-plane work begins at 0.40 |
| [Schema drift and evolution](SCHEMA_DRIFT_PLAN.md) | Partially shipped, living plan | File-backed history, inspection, comparison, impact, and acknowledgement workflows exist | Registry-backed history at 0.41 |
| [SQLModel integration](SQLMODEL_INTEGRATION_PLAN.md) | Partially shipped | The optional contract-to-SQLModel bridge exists; reference control-plane persistence remains planned | Persistence work begins at 0.40 |
| [FastAPI integration](FASTAPI_INTEGRATION_PLAN.md) | Reference adapter shipped; control plane planned | The optional thin adapter is not a durable or multi-tenant control plane | Incubation 0.40–0.43; graduation gate 0.44 |
| [Local scheduler and Prefect](SCHEDULER_AND_PREFECT_PLAN.md) | Local MVP shipped | The built-in scheduler and optional local Prefect path exist; deploy and serve workflows remain open | Graduate only with deployment, recovery, and parity evidence |
| [Portable transformations](PORTABLE_TRANSFORM_PLAN.md) | Shipped record with follow-up work | Authoring, planning, conformance, and first-party compilers exist; support remains operation- and backend-specific | Expand only through the published compiler matrix and conformance gates |
| [Versioned tabular interchange](INTEROPERABILITY_FOUNDATION_PLAN.md) | Gate A shipped record | Polars↔Pandas Gate A exists; DataFusion Gate B remains experimental | Gate B graduates only after its explicit criteria pass |
| [ContractModel upgrade](CONTRACTMODEL_UPGRADE_PLAN.md) | Historical review baseline with active follow-ups | The original review targeted ContractModel 0.1.2; ETLantic 0.35 requires ContractModel 0.2.x | Revalidate remaining proposals against the current upstream API |
| [TransformationModel incubation](TRANSFORMATIONMODEL_PLAN.md) | Proposed incubation | No TransformationModel package or API is shipped | Post-foundation 0.53 incubation |
| [Medallantic roadmap](https://github.com/eddiethedean/etlantic/blob/main/packages/medallantic/ROADMAP.md) | Current companion sequence | Medallantic 0.35 / M7 shipped | 0.36 joint burn-in with ETLantic |

## Status vocabulary

Plans use these terms consistently:

- **Planned program** — approved direction and sequencing, but no current
  availability claim.
- **Proposed incubation** — an idea with explicit graduation gates; its package
  and interfaces are not shipped.
- **Partially shipped, living plan** — some documented outcomes are current,
  while later work remains open. The plan must identify the boundary.
- **Shipped record** — historical implementation rationale and acceptance
  evidence. Current user documentation owns the supported interface.
- **Historical review baseline** — analysis of an older dependency or product
  state. It can inform follow-up work but cannot describe the current API on
  its own.

## Authority and ownership

When documents disagree, use this order:

1. Current-version capabilities, API reference, CLI reference, and package
   documentation define shipped behavior.
2. The main roadmap defines release sequence and cross-program dependencies.
3. A domain plan defines its own scope, decisions, non-goals, and graduation
   gates.
4. Accepted architecture decisions lock architectural boundaries.
5. Exit gates, release notes, and tests provide evidence for shipped claims.

Plans never override security boundaries. In particular:

- plans, reports, and generated artifacts must not contain resolved secrets or
  source rows;
- production profiles must explicitly allowlist plugins;
- schema history stores fingerprints and metadata, never source data;
- bronze, silver, and gold vocabulary remains in Medallantic rather than
  ETLantic core.

## Choose a path

### Evaluating ETLantic

Read the [roadmap summary](ROADMAP_SUMMARY.md), then inspect only the relevant
portfolio row above. Verify every needed feature against
[Capabilities](../01_GETTING_STARTED/CAPABILITIES.md).

### Implementing a planned capability

Read the main roadmap milestone, the owning domain plan, related architecture
decisions, and the most recent exit gate. Treat code examples in plans as
illustrative until the public reference documents them.

### Maintaining the portfolio

Update the plan status, roadmap, capabilities page, release notes, and exit-gate
evidence together when availability changes. Do not silently convert future
language into a shipped claim.

## Plan document contract

Every active plan should make these items easy to find:

1. status relative to the current release;
2. current shipped boundary and authoritative current documentation;
3. intended outcome and non-goals;
4. ownership and dependency boundaries;
5. milestones or workstreams;
6. security and data-handling requirements;
7. measurable acceptance or graduation gates;
8. required documentation, tests, and operational evidence;
9. open decisions and a trigger for the next review.

New plans should use this contract. Existing plans retain their detailed
historical material, but their opening status block is the authoritative
summary.

## Related records

- [Programmatic authoring and lossless JSON — 0.24](PROGRAMMATIC_AUTHORING_0_24.md)
- [SparkForge adoption record](SPARKFORGE_ADOPTION.md)
- [Portable transformation evolution](DTCS_PORTABLE_EVOLUTION.md)
- [Design proposals and historical studies](DESIGN_PROPOSALS.md)
- [Archive index](ARCHIVE_INDEX.md)
