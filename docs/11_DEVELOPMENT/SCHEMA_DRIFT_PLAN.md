# Schema Drift and Evolution Plan

## Purpose

Source schemas change independently of pipeline code. Some changes violate a
data contract, while others remain contract-compatible but still matter to ETL
developers, operators, and downstream consumers.

Pipelantic should make those changes visible, explain their impact, preserve
their history, and coordinate an explicit response. It must not silently alter
the authoritative data contract.

The governing model compares three distinct schemas:

```text
Declared schema
    what the data contract promises

Observed schema
    what a source or produced artifact currently exposes

Previous observed schema
    what the same source exposed at an earlier observation
```

This distinction detects:

- **contract drift** — observed data differs from the declared contract; and
- **operational drift** — the observed schema changed over time, even when both
  observations remain contract-compatible.

ContractModel remains authoritative for data-contract diff and compatibility
semantics. Pipelantic owns observation, normalization, history, policies,
lineage-aware impact analysis, reporting, and workflow coordination.

## Goals

Pipelantic should:

1. observe schemas through explicit, capability-bearing backend operations;
2. normalize backend schemas into a stable comparison representation;
3. create deterministic fingerprints without storing source data;
4. compare observations with contracts and prior observations;
5. classify changes beyond a binary breaking or non-breaking result;
6. identify affected fields, transformations, outputs, sinks, and pipelines;
7. apply profile-specific drift policies;
8. record observations, acknowledgements, decisions, and remediation;
9. include drift evidence in diagnostics and run reports;
10. support Git, local, registry, and external history providers;
11. help developers create reviewable adapters and contract updates;
12. expose schema history and impact through CLI, API, IDE, notebook, and AI
    tooling.

## Non-Goals

Pipelantic will not:

- create a fourth top-level contract type;
- redefine ODCS or ContractModel compatibility semantics;
- modify contracts automatically in production;
- query live sources during ordinary loading, validation, or planning;
- infer schema changes by collecting unrestricted source records;
- treat an acknowledged observation as an accepted contract revision;
- require a proprietary schema registry;
- guarantee that schema compatibility implies behavioral compatibility.

## Core Models

### `SchemaObservation`

An immutable observation records:

- stable source, output, or artifact identity;
- normalized schema and deterministic fingerprint;
- observation time, profile, workspace, and environment;
- contract, pipeline, plan, run, and artifact references where applicable;
- inspector plugin and version;
- inference method, confidence, sampling, and known limitations;
- source-system revision or snapshot identity when available;
- provenance and security classification.

Observations must not contain source rows, secret values, credentials, or
unbounded backend metadata.

### `SchemaChange`

A semantic change identifies:

- change kind;
- field or structural path;
- previous and current definitions;
- declared-contract relationship;
- compatibility classification supplied by ContractModel where applicable;
- confidence and backend-normalization notes;
- affected lineage nodes and consumers;
- suggested remediation.

Initial change kinds should include:

- field added, removed, renamed, moved, or reordered;
- type widened, narrowed, or otherwise changed;
- nullability changed;
- default or generated-value behavior changed;
- constraint added, removed, or changed;
- enum or allowed-value set changed;
- nested structure changed;
- key, identity, or partition metadata changed;
- representation changed without a logical-schema change;
- unknown or backend-specific change.

### `SchemaChangeSet`

A change set compares two identified schema states and includes:

- baseline and candidate fingerprints;
- semantic changes;
- overall impact;
- compatibility findings;
- lineage impact;
- policy decision;
- acknowledgement and resolution state.

### Impact levels

Pipelantic should use a richer impact vocabulary:

```python
class DriftImpact(str, Enum):
    INFORMATIONAL = "informational"
    COMPATIBLE = "compatible"
    CONDITIONALLY_COMPATIBLE = "conditionally_compatible"
    BREAKING = "breaking"
    UNKNOWN = "unknown"
```

Compatibility and pipeline impact remain separate. Removing a field may be
contract-breaking while a specific pipeline is unaffected because it never
uses that field.

## Observation Lifecycle

```text
Explicit inspection request or runtime boundary
                    │
                    ▼
Backend schema inspector
                    │
                    ▼
Normalized schema and fingerprint
                    │
           ┌────────┴────────┐
           ▼                 ▼
Declared contract     Previous observation
           │                 │
           └────────┬────────┘
                    ▼
Semantic changes and compatibility
                    │
                    ▼
Lineage-aware impact analysis
                    │
                    ▼
Drift policy decision
                    │
                    ▼
Diagnostics, report, history, and notification
```

Live inspection is an explicit operation because it may require network,
credential, catalog, or storage authority. Static planning must remain
side-effect free.

Supported observation modes should include:

- preflight source inspection;
- runtime source inspection after acquisition;
- post-transformation output inspection;
- sink pre-publication inspection;
- scheduled monitoring without a full pipeline run;
- CI comparison against approved snapshots;
- registry or catalog event ingestion.

## Normalization and Fingerprinting

Backend types must be normalized without erasing meaningful distinctions.

The normalization layer should preserve:

- logical type and physical representation;
- precision, scale, length, timezone, and encoding;
- nullability and defaults;
- nested fields and collection element types;
- key and constraint metadata where discoverable;
- field order as metadata even when it is not semantically significant;
- backend-specific extensions in a namespaced form.

Fingerprints must be:

- deterministic;
- versioned by normalization algorithm;
- independent of irrelevant backend ordering where semantics permit;
- content-addressed;
- safe to include in plans, reports, and registry records.

Changing normalization rules requires a new fingerprint-algorithm version and
must not masquerade as source drift.

## Drift Policies

Profiles may choose a `SchemaDriftPolicy` globally and override it for a source,
output, sink, or change category.

Policy actions should include:

- record;
- warn;
- notify;
- require approval;
- quarantine;
- continue through an explicit adapter;
- block the affected step;
- block the complete run.

Policies may distinguish additions, removals, renames, nullability, widening,
narrowing, constraints, enum values, ordering, and unknown changes.

Unknown compatibility should fail closed in production unless the profile
explicitly permits another action.

Policy decisions must include:

- matched rule and policy revision;
- evidence and change fingerprints;
- decision time and actor;
- acknowledgement or approval reference;
- expiration or review time when applicable.

## History and Tracking

Schema history belongs behind a provider protocol:

```python
class SchemaHistoryProvider(Protocol):
    def record(self, observation: SchemaObservation) -> None: ...
    def latest(self, subject_id: str) -> SchemaObservation | None: ...
    def history(self, subject_id: str) -> Sequence[SchemaObservation]: ...
    def acknowledge(self, decision: DriftAcknowledgement) -> None: ...
```

Planned providers:

- canonical files suitable for Git and CI;
- local development storage;
- SQL or object-storage history;
- Pipelantic registry integration;
- adapters for external catalogs and contract registries.

The system must distinguish:

1. observed;
2. reviewed;
3. acknowledged as the operational baseline;
4. accepted through policy or approval;
5. incorporated into a new authoritative contract revision;
6. resolved through an adapter or source correction.

Acknowledging drift must never rewrite contract history.

## Lineage-Aware Impact Analysis

Pipelantic should trace a changed source field through:

```text
Source field
    → input port
    → transformation usage
    → derived output fields
    → sinks
    → downstream pipelines and consumers
```

Impact results should identify:

- affected and unaffected transformations;
- implementations with different field requirements;
- outputs whose schemas or values may change;
- validation rules and quality gates that reference changed fields;
- sinks and downstream pipelines;
- adapters capable of absorbing the change;
- uncertainty caused by opaque user code or incomplete column lineage.

Dataset-level lineage provides a conservative fallback. Column-level lineage
allows precise impact classifications.

## Remediation Workflows

Pipelantic should support reviewable remediation without hiding changes.

### Adapters

Developers may add explicit transformations that rename fields, provide
defaults, cast types, normalize values, preserve deprecated fields, or
quarantine incompatible records.

### Contract update proposals

A proposal should contain:

- semantic contract diff;
- ContractModel compatibility analysis;
- required version change;
- affected pipelines and consumers;
- migration and adapter suggestions;
- generated or updated tests;
- policy and approval requirements.

### Operational baseline acceptance

Accepting an observation as a baseline records that the team has reviewed the
source state. It does not declare the data contract changed.

### Source correction

If drift is accidental, the resolution should link the observation to the
source-system correction and the later confirming observation.

## CLI and Public API

Planned CLI commands:

```text
pipelantic schema inspect
pipelantic schema check
pipelantic schema diff
pipelantic schema history
pipelantic schema impact
pipelantic schema acknowledge
pipelantic schema propose
pipelantic schema monitor
```

Every command should support structured JSON output. Live inspection and
monitoring require an explicit profile and source authority.

The Python API should expose the same request and result models as the CLI,
FastAPI integration, IDE, notebooks, and agent tools.

## Reporting, Diagnostics, and Notifications

`PipelineRunReport` should include schema-drift results containing:

- declared, previous, and observed fingerprints;
- normalized change set;
- compatibility and pipeline-impact findings;
- policy decision;
- acknowledgement and remediation references;
- inspector provenance and inference limitations.

Drift diagnostics require stable codes and related locations. Notifications
should deduplicate on subject, change-set fingerprint, environment, and policy
revision so an unchanged acknowledged drift does not alert on every run.

SARIF output should connect drift findings to affected source and consumer
locations where possible.

## IDE, Notebook, and AI Experience

The developer-intelligence layer should provide:

- source and port drift indicators;
- declared-versus-observed hover summaries;
- schema-history and change timelines;
- downstream impact previews;
- navigation to affected fields, transformations, and rules;
- reviewable contract-update and adapter proposals;
- safe quick fixes only when the change is deterministic;
- bounded notebook comparisons and history displays;
- agent-readable, redacted change sets and impact reports.

Editors and notebooks must not query production sources automatically.

AI assistants may propose adapters, migrations, tests, and contract revisions,
but cannot accept drift, mutate the authoritative contract, access source data,
or submit runs without explicit human authority.

## Security and Privacy

Schema metadata can reveal confidential field names, system structure, tenant
identities, classifications, and business behavior.

Controls include:

- explicit inspection authority;
- workspace, tenant, profile, and security-domain isolation;
- metadata redaction and classification;
- bounded source metadata and samples;
- no source values in observations by default;
- encryption and access control for history providers;
- audit events for inspection, acknowledgement, approval, and baseline changes;
- no implicit remote resolution during analysis;
- protection against forged observations and cross-environment baseline reuse.

Production observations should be signed or otherwise integrity-protected when
used for approvals, deployment gates, or audit evidence.

## Testing and Conformance

The conformance suite should cover:

- deterministic normalization and fingerprinting;
- semantic diff invariants;
- type widening and narrowing matrices;
- nested, enum, nullability, precision, and constraint changes;
- backend-equivalent schema normalization;
- unknown and lossy conversions;
- policy precedence and fail-closed behavior;
- history-provider concurrency and idempotency;
- notification deduplication;
- lineage impact with complete and incomplete field lineage;
- redaction and tenant isolation;
- equivalent CLI, API, IDE, notebook, and report results.

Golden fixtures should include representative Polars, Pandas, Arrow, SQL,
Spark, Delta, JSON, and nested schemas.

## Roadmap Placement

| Release | Schema-drift capability |
|---|---|
| 0.3 | Normalized schema, fingerprints, change models, impact vocabulary |
| 0.4 | Runtime observations, policy decisions, reports, events |
| 0.5–0.7 | Dataframe, SQL, Spark, streaming, and storage inspectors |
| 0.9 | CLI, diagnostics, provider protocols, SARIF, notifications |
| 1.1 | FastAPI inspection, history, impact, and acknowledgement routes |
| 1.2 | Registry-backed history, search, promotion, and cross-pipeline impact |
| 1.3 | Baselines, state linkage, replay, concurrency, reproducibility |
| 1.4 | Approval, governance, signed observations, retention, policy evidence |
| 1.5 | IDE and notebook history, impact, proposals, and navigation |
| 1.9 | Human-governed AI remediation proposals |

## Success Criteria

The feature is successful when an ETL developer can answer:

- What changed?
- When and where was it observed?
- Does it violate the contract?
- Is it operationally significant even if compatible?
- Which transformations, fields, sinks, and pipelines are affected?
- What policy decision was made?
- Who reviewed or acknowledged it?
- What adapter, source correction, or contract revision resolved it?
- Can the complete history and evidence be reproduced later?

The core principle is:

> Pipelantic records what was declared, what was observed, what changed, who is
> affected, and what decision was made—without silently redefining the
> contract.
