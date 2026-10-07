---
status: available
since: "0.56.0"
current_minor: "0.56"
audience: adopter
---

# What's new in 0.56

> **Status: ETLantic 0.56.0 is the published Beta release.**

Phase 0.56 completes the application-facing managed ETL path. Applications can
submit work through one preparation and acceptance path, use managed workers,
observe durable run results and lineage, and request recovery actions through
the same managed service.

## Included in the release

- Bounded live PostgreSQL partition reads and transactional selected-partition
  replacement, including empty-output clearing and idempotent retries.
- Managed repair and backfill admission, execution, status and lineage.
- Lockstep 0.56.0 packages and clean-wheel compatibility qualification
  qualification.

Partition repair/backfill requires a configured `partition_column`; unsupported
providers fail closed. Provider selectors are bounded and validated, and writes
replace only the selected partition in the same transaction as effect
recording.

See the [0.56 exit gate](../11_DEVELOPMENT/EXIT_GATE_0_56.md), [Migration 0.55 → 0.56](../11_DEVELOPMENT/MIGRATION_0_55_TO_0_56.md), and [local
qualification record](../11_DEVELOPMENT/evidence/phase_0_56/LOCAL_QUALIFICATION.md).
Install matching 0.56.x core and first-party packages. See the
[release artifact verification guide](RELEASE_ARTIFACT_VERIFICATION.md) and
[migration guide](../11_DEVELOPMENT/MIGRATION_0_55_TO_0_56.md).
