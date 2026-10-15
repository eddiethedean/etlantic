---
title: What's New in ETLantic 0.60
status: candidate
since: "0.60.0"
current_minor: "0.60"
---

# What's New in ETLantic 0.60

> **Status: 0.60.0 is a core Beta candidate. The published and supported core line remains 0.59.x; this candidate has not been released to PyPI.**

Core 0.60 adds the public durable contracts required by the optional 0.61 AWS
adapter. The implementation is locally tested; live AWS qualification and a
production support decision remain deferred.

## Managed execution contracts

- Durable dispatch records carry provider-neutral remote identity while keeping
  Prefect compatibility aliases and historical snapshot readers.
- ECS dispatch intent records its first creation time. After the conservative
  AWS client-token retry window expires, uncertain work is quarantined until an
  operator authorizes a new generation; an expired token is never reused to
  launch a duplicate task.
- Cancellation recovery searches for a task after an uncertain `RunTask`
  response, stops verified tasks, and waits for a confirmed stopped state before
  finalizing cancellation.
- The accepted-work reference and targeted managed execution APIs remain in
  core, so an independently installed worker does not need FastAPI or Prefect.

## Scheduled execution

- Skipped interval occurrences retain their original recurrence grid, including
  after a delayed invocation.
- EventBridge schedule mutations can use a PostgreSQL session advisory lock to
  serialize readback, write, and verification across scheduler processes.

See [Migration 0.59 → 0.60](../11_DEVELOPMENT/MIGRATION_0_59_TO_0_60.md) for
snapshot compatibility and package constraints. The AWS adapter's local
implementation and deferred live qualification are tracked in the
[0.61 implementation plan](../11_DEVELOPMENT/IMPLEMENTATION_PLAN_0_61.md).
