# Application Integration Contract (0.24)

Framework-agnostic contract for visual builders and host applications.

## Artifacts

| Artifact | Role |
|---|---|
| `PipelineDefinition` / `etlantic.pipeline/1` | Authoring-complete document |
| Authoring catalog | Discoverable components + UI metadata |
| `EditCommand` | Immutable graph edits |
| Diagnostics with document paths | Highlight fields/nodes/edges |
| Service facade (`etlantic.service`) | Transport-neutral request/response ops |

## Required host responsibilities

- Persist definitions and concurrency tokens
- Supply `PolicyContext` (tenant, profile, allowed actions/plugins)
- Register native implementation callables before run
- Own authn/authz, queues, and durable job storage

## Reference HTTP adapter

`etlantic-fastapi` publishes OpenAPI from the public schemas. It is a proof
adapter, not the production 1.1 control API.
