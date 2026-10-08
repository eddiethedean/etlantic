---
status: candidate
since: "0.57.0"
current_minor: "0.57"
audience: adopter
---

# What's new in 0.57

> **Status: 0.57.0 release candidate. Publication is pending the exit gate.**

ETLantic 0.57 makes the standard managed backend independent of the FastAPI
adapter and adds public contracts for schedule commands, provider schema
compatibility, and runtime supervision.

## Candidate scope

- Construct the standard authorized backend and its SQLModel store graph with
  `etlantic_sqlmodel.create_managed_backend`, without FastAPI or an HTTP context
  factory.
- Use `backend.schedule_service` for authorized schedule commands from Python
  or HTTP. The FastAPI adapter reuses the same command service and records.
- Construct managed schedulers with `backend.create_scheduler()`, which wires
  explicit occurrence preparation, submission, and recovery over the shared
  schedule and durable stores.
- Inspect schema requirements and compatibility through
  `etlantic_sqlmodel.schema_requirements()` and
  `etlantic_sqlmodel.inspect_schema(engine)`. Construction remains read-only;
  schema migration remains an operator step.
- Read redacted local role status and request cooperative drain on scheduler,
  run-worker, and action-worker handles.

## Compatibility

Existing FastAPI managed constructors and routes remain supported. No database
migration or persisted-format change is introduced for existing databases at
migration head `014_cp1_complete_principal_idempotency_0_56`. Low-level managed
schedulers now require explicit recovery wiring. Consumers remain responsible
for trusted identity derivation, process liveness, poll threads, grace periods,
and joining drained work.

See the [0.56 → 0.57 migration guide](../11_DEVELOPMENT/MIGRATION_0_56_TO_0_57.md)
and [0.57 exit gate](../11_DEVELOPMENT/EXIT_GATE_0_57.md). This candidate does
not claim production multi-tenant isolation or exactly-once external effects.
