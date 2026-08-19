# Planning Hub

> **Status: Shipped product docs describe ETLantic 0.48.0 (gate-ready Beta).
> Human-governed AI context/proposal surfaces are Available; MCP extra is
> Experimental. Streaming and bounded dynamic control are Supported in core; Kafka and
> schema-registry extras are Experimental. Developer Intelligence (LSP / IDE /
> notebooks) is Available; CP-GA production multi-tenant remains Supported
> only for isolation profiles graduated in 0.43. `shared-service` remains
> Experimental.**

ETLantic's planning documents describe intended outcomes, dependencies, and
release gates. They are **not** a substitute for current product documentation.

!!! important "Use the right source of truth"
    - To learn what **ETLantic 0.48 can do now**, use
      [Capabilities](../01_GETTING_STARTED/CAPABILITIES.md), the
      [CLI reference](../10_REFERENCE/CLI.md), and the
      [Python API reference](../10_REFERENCE/API_REFERENCE.md).
    - To understand **release order**, use the
      [main roadmap](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md).
    - To evaluate **0.47 scheduler/federation evidence**, use the
      [0.47 exit gate](EXIT_GATE_0_47.md),
      [ADR-023](adr/ADR-023-SCHEDULER-SERVICE-AND-FEDERATION.md) (Accepted),
      [findings](FINDINGS_0_47.md), release notes, and tests.
    - To evaluate **0.48 human-governed AI evidence**, use the
      [0.48 implementation plan](IMPLEMENTATION_PLAN_0_48.md),
      [0.48 exit gate](EXIT_GATE_0_48.md),
      [ADR-024](adr/ADR-024-HUMAN-GOVERNED-AI.md) (Accepted),
      [findings](FINDINGS_0_48.md), and the
      [main roadmap](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md)
      § 0.48.
    - To evaluate **0.46 streaming/dynamic-control evidence**, use the
      [0.46 exit gate](EXIT_GATE_0_46.md), [ADR-022](adr/ADR-022-DYNAMIC-CONTROL-AND-STREAMING.md),
      [findings](FINDINGS_0_46.md), release notes, and tests.
    - To evaluate **0.45 planner/optimization evidence**, use the
      [0.45 exit gate](EXIT_GATE_0_45.md), [ADR-021](adr/ADR-021-OPTIMIZER-PASS-PROTOCOL.md),
      release notes, and tests.
    - To evaluate **CP-GA gate evidence**, use the
      [0.43 exit gate](EXIT_GATE_0_43.md), [support matrix](cp_ga_support_matrix_0_43.json),
      [traceability](cp_ga_traceability_0_43.json), release notes, and tests.
    - To evaluate **CP4 gate evidence**, use the
      [0.42 exit gate](EXIT_GATE_0_42.md), [ADR-019](adr/ADR-019-POLICY-QUOTAS-AND-AUDIT.md),
      release notes, and tests.
    - To evaluate **CP3 gate evidence**, use the
      [0.41 exit gate](EXIT_GATE_0_41.md), [ADR-018](adr/ADR-018-DURABLE-SUBMISSION-AND-STATE.md),
      release notes, and tests.
    - To evaluate **CP2 gate evidence**, use the
      [0.40 exit gate](EXIT_GATE_0_40.md), [ADR-017](adr/ADR-017-REGISTRY-AND-ISOLATION.md),
      release notes, and tests.
    - To evaluate **CP1 gate evidence**, use the
      [0.39 exit gate](EXIT_GATE_0_39.md) and [ADR-016](adr/ADR-016-CONTROL-PLANE-IDENTITY.md).
    - To evaluate **connectivity gate evidence**, use the
      [0.38 exit gate](EXIT_GATE_0_38.md).
    - To understand **why a boundary exists**, use
      [architecture decisions](ARCHITECTURE_DECISIONS.md).

No proposed interface becomes public API merely because it appears in a plan.
A capability is available only when the current-version documentation says it
is available and its release gate has passed.

## Portfolio at a glance

Status is relative to the **0.48** human-governed AI line.
Prior scheduler/federation evidence remains in **0.47**; Streaming evidence remains in **0.46**; Optimization SDK evidence remains
in **0.45**; Developer Intelligence remains in **0.44**; CP-GA evidence remains
in **0.43**; CP4 evidence remains in **0.42**; CP3 evidence remains in **0.41**;
CP2 evidence remains in **0.40**; CP1 evidence remains in **0.39**; connectivity
evidence remains in **0.38**.

| Plan | Status | Current boundary | Next horizon or gate |
|---|---|---|---|
| [Main roadmap](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md) | Current sequence | 0.48 Human-governed AI gate-ready; next 0.49 | [ROADMAP](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md) § 0.49 |
| [0.48 implementation plan](IMPLEMENTATION_PLAN_0_48.md) | Gate-ready milestone | Human-governed AI proposals; reuse 0.42 approvals | [EXIT_GATE_0_48](EXIT_GATE_0_48.md) |
| [ADR-024: Human-governed AI](adr/ADR-024-HUMAN-GOVERNED-AI.md) | Accepted | Proposals untrusted; read-only default; no vendor SDK in core | 0.48 |
| [0.47 implementation plan](IMPLEMENTATION_PLAN_0_47.md) | Gate-ready milestone | Scheduler/runner service + remote federation | [EXIT_GATE_0_47](EXIT_GATE_0_47.md) |
| [ADR-023: Scheduler service and federation](adr/ADR-023-SCHEDULER-SERVICE-AND-FEDERATION.md) | Accepted | FastAPI vs CP3 vs remote/resource; fake vs live | 0.47 |
| [0.46 implementation plan](IMPLEMENTATION_PLAN_0_46.md) | Previous / released | Dynamic control, streaming, Kafka/DLQ/registry | [EXIT_GATE_0_46](EXIT_GATE_0_46.md) |
| [ADR-022: Dynamic control and streaming](adr/ADR-022-DYNAMIC-CONTROL-AND-STREAMING.md) | Accepted | Core vs provider ownership; no payloads in artifacts | 0.46 |
| [0.44 implementation plan](IMPLEMENTATION_PLAN_0_44.md) | Released milestone | LSP / IDE / static analysis | [EXIT_GATE_0_44](EXIT_GATE_0_44.md) |
| [0.45 implementation plan](IMPLEMENTATION_PLAN_0_45.md) | Released milestone | Optimization-pass SDK | [EXIT_GATE_0_45](EXIT_GATE_0_45.md) |
| [0.43 implementation plan](IMPLEMENTATION_PLAN_0_43.md) | Released milestone | CP-GA qualification / graduation | [EXIT_GATE_0_43](EXIT_GATE_0_43.md) |
| [ADR-020: Developer intelligence](adr/ADR-020-DEVELOPER-INTELLIGENCE.md) | Accepted | Editor-neutral protocol + safe analysis | 0.44 |
| [ADR-021: Optimizer pass protocol](adr/ADR-021-OPTIMIZER-PASS-PROTOCOL.md) | Accepted | Advisory optimization-pass SDK | 0.45 |
| [0.42 implementation plan](IMPLEMENTATION_PLAN_0_42.md) | Previous / released | Policy, quotas, audit, objectives, erasure | [EXIT_GATE_0_42](EXIT_GATE_0_42.md) |
| [0.41 implementation plan](IMPLEMENTATION_PLAN_0_41.md) | Gate-ready milestone | Durable submission, leases, state, replay, previews | [EXIT_GATE_0_41](EXIT_GATE_0_41.md) |
| [0.40 implementation plan](IMPLEMENTATION_PLAN_0_40.md) | Previous / gate-ready | Registry records, revisions, isolation profiles, histories, OpenLineage | [EXIT_GATE_0_40](EXIT_GATE_0_40.md) |
| [0.39 implementation plan](IMPLEMENTATION_PLAN_0_39.md) | Previous / gate-ready | Identity, API, durable submit, SSE, landing submitter, optional SQLModel | [EXIT_GATE_0_39](EXIT_GATE_0_39.md) |
| [0.38 implementation plan](IMPLEMENTATION_PLAN_0_38.md) | Previous / gate-ready | Connector protocols, landing-zone modes, reference providers, conformance | [EXIT_GATE_0_38](EXIT_GATE_0_38.md) |
| [Forward implementation plans](FORWARD_IMPLEMENTATION_PLANS.md) | Planned release program | Shared entry/done contract and implementation-grade plans for 0.39–0.52 | 0.41 CP3 gate-ready |
| [0.37 implementation plan](IMPLEMENTATION_PLAN_0_37.md) | Previous milestone | Removals, testing graduation, acceptance 1–21, security matrix, freeze, rehearsal | [EXIT_GATE_0_37](EXIT_GATE_0_37.md) gate-ready |
| [0.36 implementation plan](IMPLEMENTATION_PLAN_0_36.md) | Gate-ready / previous | Joint compatibility burn-in closed in-tree | Immutable docs residual on 0.36 |
| [Adoption, connectivity, and operations](ADOPTION_ECOSYSTEM_PLAN.md) | Planned program | Connectivity gate-ready in 0.38; testing graduated in 0.37 | Continues through 0.52 |
| [Landing-zone file connector](LANDING_ZONE_CONNECTOR_PLAN.md) | Gate-ready (0.38 + 0.39 composition) | Snapshot + incremental in 0.38 Preview; continuous submitters in 0.39 (outside core) | CP1 submitter bridge landed |
| [ADR-015: Connector protocols](adr/ADR-015-CONNECTOR-PROTOCOLS.md) | Accepted | Protocol ids, entry points, capabilities, plan/runtime split, reference set | Maintenance |
| [ADR-016: Control-plane identity](adr/ADR-016-CONTROL-PLANE-IDENTITY.md) | Accepted | Identity vocabulary, non-enumeration, durable accept, SSE cursor shapes | CP1 prior |
| [ADR-017: Registry and isolation](adr/ADR-017-REGISTRY-AND-ISOLATION.md) | Accepted | Directory records, revisions, isolation profiles, metadata-only histories | CP2 prior |
| [ADR-019: Policy, quotas, and audit](adr/ADR-019-POLICY-QUOTAS-AND-AUDIT.md) | Accepted | Policy envelope, quotas, SoD, audit chain | CP4 prior; CP-GA in 0.43 |
| [ADR-018: Durable submission and state](adr/ADR-018-DURABLE-SUBMISSION-AND-STATE.md) | Accepted | Outbox, leases/fencing, effects, preview non-authority | CP3 prior |
| [Multi-tenant control plane](MULTI_TENANT_CONTROL_PLANE_PLAN.md) | Graduated Supported profiles in 0.43 | CPn alone ≠ GA; `shared-service` Experimental | Post-CP-GA hardening / Operator Console 0.50 |
| [User interface and experience](UI_UX_PLAN.md) | Partially shipped, cross-cutting | CLI + 0.44 LSP/IDE + 0.45 optimization SDK released; interactive HTML and hosted Operator Console remain planned | Hosted work follows control-plane gates; Operator Console 0.50 |
| [ETL reliability and recovery](ETL_RELIABILITY_PLAN.md) | Partially shipped, living plan | Public models, providers, and local CLI operations exist; managed and advanced capabilities remain planned | Delivery objectives and governed erasure in 0.42; bounded dynamic control, DLQ, and schema registries in 0.46 |
| [Schema drift and evolution](SCHEMA_DRIFT_PLAN.md) | Partially shipped, living plan | File-backed history, inspection, comparison, impact, and acknowledgement workflows exist | Registry-backed history at 0.40 |
| [SQLModel integration](SQLMODEL_INTEGRATION_PLAN.md) | Partially shipped; CP2 persistence open | The optional contract-to-SQLModel bridge exists; reference registry stores incubate with 0.40 | Request-scoped CP stores |
| [FastAPI integration](FASTAPI_INTEGRATION_PLAN.md) | Graduated host in 0.43 for Supported profiles | `ETLanticAPI` + thin `create_reference_app`; CPn alone ≠ GA; 0.47 schedule routes are Available | [IMPLEMENTATION_PLAN_0_47](IMPLEMENTATION_PLAN_0_47.md); Operator Console 0.50 |
| [Local scheduler and Prefect](SCHEDULER_AND_PREFECT_PLAN.md) | Local MVP shipped | The built-in scheduler and optional local Prefect path exist; durable cron is the 0.47 service (not `etlantic.scheduler/1`) | [IMPLEMENTATION_PLAN_0_47](IMPLEMENTATION_PLAN_0_47.md) |
| [Portable transformations](PORTABLE_TRANSFORM_PLAN.md) | Shipped record with follow-up work | Authoring, planning, conformance, and first-party compilers exist; support remains operation- and backend-specific | Expand only through the published compiler matrix and conformance gates |
| [Versioned tabular interchange](INTEROPERABILITY_FOUNDATION_PLAN.md) | Gate A shipped record | Polars↔Pandas Gate A exists; DataFusion Gate B remains experimental | Gate B graduates only after its explicit criteria pass |
| [ContractModel upgrade](CONTRACTMODEL_UPGRADE_PLAN.md) | Historical review baseline with active follow-ups | The original review targeted ContractModel 0.1.2; ETLantic 0.36 requires ContractModel 0.2.x | Revalidate remaining proposals against the current upstream API |
| [TransformationModel incubation](TRANSFORMATIONMODEL_PLAN.md) | Proposed incubation | No TransformationModel package or API is shipped | Post-foundation 0.52 incubation |
| [Medallantic roadmap](https://github.com/eddiethedean/etlantic/blob/main/packages/medallantic/ROADMAP.md) | Current companion sequence | Medallantic tracks ETLantic matching minor | Matching-minor joint release |

## Forward implementation sequence

The roadmap defines outcomes; these documents define workstreams, ordering,
evidence, and release gates. Read the
[shared forward delivery contract](FORWARD_IMPLEMENTATION_PLANS.md) first.

| Program | Phase implementation plans |
|---|---|
| Control plane | [0.39](IMPLEMENTATION_PLAN_0_39.md) · [0.40](IMPLEMENTATION_PLAN_0_40.md) · [0.41](IMPLEMENTATION_PLAN_0_41.md) · [0.42](IMPLEMENTATION_PLAN_0_42.md) · [0.43](IMPLEMENTATION_PLAN_0_43.md) |
| Intelligence and execution | [0.44](IMPLEMENTATION_PLAN_0_44.md) · [0.45](IMPLEMENTATION_PLAN_0_45.md) · [0.46 dynamic control + streaming](IMPLEMENTATION_PLAN_0_46.md) · [0.47](IMPLEMENTATION_PLAN_0_47.md) · [0.48](IMPLEMENTATION_PLAN_0_48.md) |
| Adoption and incubation | [0.49](IMPLEMENTATION_PLAN_0_49.md) · [0.50](IMPLEMENTATION_PLAN_0_50.md) · [0.51](IMPLEMENTATION_PLAN_0_51.md) · [0.52](IMPLEMENTATION_PLAN_0_52.md) |

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
decisions, the phase implementation plan, and the most recent exit gate. Treat
code examples in plans as illustrative until the public reference documents
them.

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

- [Forward implementation plans and delivery contract](FORWARD_IMPLEMENTATION_PLANS.md)
- [0.37 stable foundation implementation plan](IMPLEMENTATION_PLAN_0_37.md)
- [0.36 joint compatibility burn-in implementation plan](IMPLEMENTATION_PLAN_0_36.md)
- [Programmatic authoring and lossless JSON — 0.24](PROGRAMMATIC_AUTHORING_0_24.md)
- [SparkForge adoption record](SPARKFORGE_ADOPTION.md)
- [Portable transformation evolution](DTCS_PORTABLE_EVOLUTION.md)
- [Design proposals and historical studies](DESIGN_PROPOSALS.md)
- [Archive index](ARCHIVE_INDEX.md)
