# ETLantic 0.24 Programmatic Authoring Plan

**Status: historical design record — shipped in ETLantic 0.24.0.**

For the usable guide, see
[Programmatic authoring](../05_PIPELINES/PROGRAMMATIC_AUTHORING.md).
This page remains the detailed design companion and exit-gate narrative.

ETLantic 0.24 makes pipelines fully authorable, editable, serializable, and
executable without requiring Python class declarations. Class authoring remains
supported, but classes, functional builders, JSON documents, graphical editors,
and service applications converge on one canonical `PipelineDefinition`.

This plan is the detailed companion to the
[0.24 roadmap phase](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md#024--programmatic-authoring-and-lossless-json).
Names below match the shipped 0.24 public contract; prefer the
[Programmatic authoring](../05_PIPELINES/PROGRAMMATIC_AUTHORING.md) guide for
current usage.

## Product outcome

An independent application can build an ETLantic pipeline visually:

```text
Frontend GUI
    ↕ generated API client
FastAPI application
    ↕ public ETLantic service facade
PipelineDefinition ↔ etlantic.pipeline/1 JSON
    ↓
validate → plan → compile / generate / visualize / run
```

Neither the GUI nor the service must generate a `Pipeline` subclass. The same
definition can also be created with functional Python builders or normalized
from existing class-based authoring.

## Canonical artifacts

| Artifact | Purpose |
|---|---|
| `PipelineDefinition` | Immutable, unresolved, authoring-complete pipeline model |
| `etlantic.pipeline/1` | Canonical JSON representation of `PipelineDefinition` |
| `PipelinePlan` / `etlantic.plan/1` | Resolved execution plan; not an authoring round-trip format |
| [ODCS](../03_DATA_CONTRACTS/ODCS.md) / [DTCS](../04_TRANSFORMATIONS/DTCS.md) / [DPCS](../05_PIPELINES/DPCS.md) | Standards-based contract interchange |
| Authoring catalog | Discoverable components and UI-safe metadata |
| Edit command | Immutable operation applied to a definition |
| Diagnostic | Machine-readable problem tied to stable document paths |

`etlantic.pipeline/1` preserves the information needed to continue editing:
contracts, transformation interfaces, portable definitions, nodes, ports,
edges, parameter values, profiles and policy references, reliability
declarations, metadata, provenance, extensions, and stable identities.

## Equivalent authoring paths

All supported paths normalize to the same canonical model:

```text
Pipeline classes ───────┐
Functional builders ────┼──▶ PipelineDefinition
Canonical JSON ─────────┤          │
GUI edit commands ──────┘          ▼
                            one validation and
                            lifecycle contract
```

Every documented class primitive must have a functional equivalent. Equivalent
definitions must produce the same logical semantics, diagnostics, canonical
JSON, and fingerprint regardless of how they were authored.

## Functional authoring

The public functional surface covers:

- data contracts;
- transformation inputs, outputs, parameters, and portable definitions;
- extracts, loads, steps, edges, and nested subpipelines;
- profiles, policies, reliability declarations, and extensions;
- incremental composition, cloning, and immutable updates;
- validation, inspection, planning, execution, compilation, generation,
  visualization, and diffing.

The functional API operates on public immutable models. It does not generate
hidden user classes or require metaclass behavior.

## JSON round trips

All in-scope public semantic artifacts expose consistent dictionary and JSON
codecs. Canonical serialization has explicit schema identifiers, deterministic
ordering, stable fingerprints, bounded parsing, and migration rules.

The core invariant is:

```text
pipeline → JSON → PipelineDefinition → JSON
```

The second JSON document is byte-identical to the first for the same supported
schema version. Semantic round trips also preserve generated ODCS, DTCS, and
DPCS meaning.

JSON does not contain executable Python. Native implementations, providers,
schedulers, and plugins appear as stable registry references with version and
capability requirements. A loaded definition can be inspected and structurally
validated before registry resolution. It can run only after the host resolves
and authorizes every required reference.

## Visual-builder contract

ETLantic publishes a machine-readable catalog so a GUI can discover:

- contracts and transformations;
- typed ports and compatible connection endpoints;
- parameters, defaults, constraints, and enumerated choices;
- portable operations;
- profiles, policies, and reliability declarations;
- providers, schedulers, plugins, and required capabilities;
- display names, descriptions, deprecations, and sensitivity markers.

Public edit operations cover adding, removing, connecting, disconnecting,
moving, cloning, and updating definition elements. Stable paths identify
documents, fields, nodes, ports, and edges. Diagnostics use those same paths,
allowing a GUI to highlight the responsible form control or graph element.

Incremental validation and planning previews must not execute a pipeline,
resolve secrets, write data, access the network, or import untrusted plugins.

Canonical JSON supports application-level autosave, revision history, undo and
redo, source control, and collaborative storage. ETLantic supplies deterministic
documents and concurrency tokens; the application owns persistence and
collaboration behavior.

## Application service contract

The GUI-facing service boundary remains transport-neutral. Public request and
response models cover:

- catalog and capability discovery;
- definition creation, retrieval, replacement, and edit application;
- validation and planning previews;
- compilation, contract generation, and visualization;
- run submission and cancellation;
- run status, events, reports, and authorized artifact metadata.

Models expose OpenAPI-compatible JSON Schema without custom application
encoders. Stable envelopes carry schema versions, definition fingerprints,
optimistic concurrency tokens, idempotency keys, diagnostics, and errors.

Potentially long-running execution uses explicit submission and status
contracts. It must not rely on a web worker's in-process background-task
facility for durability.

## FastAPI boundary

A thin FastAPI reference adapter or optional package proves that the
transport-neutral service models work over HTTP and can generate a typed
frontend client from OpenAPI.

ETLantic core does not depend on FastAPI, Starlette, an ASGI server, a database,
or a job queue. The surrounding application owns:

- authentication and user management;
- authorization policy and tenant/workspace membership;
- CORS, CSRF, rate limiting, security headers, and request limits;
- definition persistence and revision history;
- durable queues, workers, and run-event transport;
- deployment, scaling, and process isolation.

The host supplies an authorized policy context containing the caller's allowed
tenant, environment, profile, assets, plugins, and lifecycle actions. Values in
the client request cannot expand that authority.

The 0.24 adapter proves the authoring and service contract. It does not replace
the production-grade [FastAPI Control API](FASTAPI_INTEGRATION_PLAN.md) planned
across the 0.40–0.44 control-plane program.

## Security invariants

- Only bounded data and stable references cross the JSON/API boundary.
- Pickles, bytecode, closures, arbitrary import paths, native backend objects,
  live connections, and resolved secrets are rejected.
- Deserialization performs no imports, plugin loading, secret resolution,
  network access, storage access, or user-code execution.
- Production registry resolution continues to require plugin allowlists and
  version policy.
- Unknown versions and fields fail explicitly; loaders never silently discard
  unsupported meaning.
- Oversized, deeply nested, stale, unauthorized, or incompatible requests fail
  without partial mutation or execution.
- API responses, diagnostics, plans, reports, and OpenAPI examples remain
  secret-free.

## Release proof

The 0.24 exit suite includes:

1. class, functional, and JSON parity fixtures;
2. byte-stable and property-based round trips across supported Python versions;
3. hostile-input and trust-boundary tests;
4. an independent visual-builder fixture using no private ETLantic APIs;
5. a FastAPI/OpenAPI reference adapter;
6. a generated frontend client that discovers components, edits a pipeline,
   validates and plans it, submits and cancels a run, and retrieves status and
   its report.

Until these gates pass, the 0.24 names on this page are future design rather
than supported 0.23 APIs.
