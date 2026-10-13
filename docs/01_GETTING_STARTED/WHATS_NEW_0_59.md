---
title: What's New in ETLantic 0.59
status: candidate
since: "0.59.0"
current_minor: "0.59"
---

# What's New in ETLantic 0.59

> **Status: ETLantic 0.59.0 is a Beta release candidate. Qualification and
> publication are pending; 0.57.x remains the published and supported line.**

ETLantic 0.59 consolidates managed backend configuration, dispatch, and
persistence contracts, then adds an external schedule-trigger boundary. The
release candidate includes the 0.58 managed Prefect work; its prior
qualification evidence does not qualify changes introduced in 0.59.

## Managed backend and persistence

- Headless SQLModel and FastAPI adapters now share canonical managed settings
  and the same core service graph. Install `etlantic[managed-headless]` for a
  headless worker or scheduler without FastAPI.
- Durable dispatch records use provider-neutral backend and remote-run
  identity while retaining compatibility decoding for existing Prefect work.
- SQLModel durable stores use the public snapshot codec and preserve persisted
  state families needed for restart and recovery. Constructors continue to
  inspect schemas without applying DDL.

## External schedule triggers

- Schedules can bind one external timer owner and a workload identity. The
  receiver accepts only a versioned, bounded trigger envelope for the exact
  next scheduled UTC occurrence.
- Occurrence IDs remain stable across delivery attempts. Durable reservations,
  preparation leases, and submission recovery prevent duplicate delivery from
  preparing or submitting the same occurrence twice.
- Trigger receipts have an authorized status reference and remain separate
  from ETL run completion. See the [0.58 → 0.59 migration guide](../11_DEVELOPMENT/MIGRATION_0_58_TO_0_59.md)
  before enabling external ownership.

## Compatibility and release status

The release adds no SQL DDL migration and retains the existing migration head.
Snapshot payloads and schedule ownership records have new versioned fields;
older readers fail closed on externally owned schedules. Back up managed
stores and follow the migration guide before upgrading or rolling back.

The external trigger, store-recovery, installed-package, and security
qualification campaigns remain pending. Do not use the 0.59 additions in
production until the [0.59 exit gate](../11_DEVELOPMENT/EXIT_GATE_0_59.md)
records those results.
