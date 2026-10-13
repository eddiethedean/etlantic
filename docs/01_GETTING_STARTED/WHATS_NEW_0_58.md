---
title: What's New in ETLantic 0.58
status: candidate
since: "0.58.0"
current_minor: "0.59"
---

# What's New in ETLantic 0.58

> **Status: ETLantic 0.58.0 Beta release candidate; publication is pending.**
> The latest published and supported package line remains 0.57.x.

ETLantic 0.58 adds an opt-in managed execution path through the optional
`etlantic-prefect` package. It connects ETLantic's durable accepted-work model
to versioned Prefect deployments and self-hosted Process workers. Existing
direct Prefect execution remains available.

## Qualified support profile

The release qualification covers static `etlantic.plan/1` batch work on Ubuntu
24.04 x86_64 with Python 3.11.15, 3.12.13, or 3.13.16, Prefect 3.7.8,
PostgreSQL 16.15, and the Prefect Process worker pool. The Prefect API is
self-hosted and backed by PostgreSQL. Qualified data paths are CSV to
PostgreSQL and PostgreSQL to PostgreSQL using replace mode.

Within this profile, durable acceptance and dispatch, versioned deployment
creation, authorization and credential checks before effects, status and
cancellation reconciliation, schedule admission and routing, and recovery
behavior passed the phase acceptance gates. Headless service construction and
the FastAPI adapter share the same behavior. See the
[qualification decision](../11_DEVELOPMENT/evidence/phase_0_58/FINAL_QUALIFICATION_DECISION_2026-10-12.json)
for gate-by-gate evidence.

These results define a bounded support profile. They do not establish support
for other operating systems, Python patch levels, Prefect pools or services,
databases, connectors, or plan families. Follow the
the [Migration 0.57 → 0.58 guide](../11_DEVELOPMENT/MIGRATION_0_57_TO_0_58.md) before enabling
managed execution.

## Compatibility and release status

The core and first-party distribution versions are aligned at 0.58.0. The
SQLModel migration head remains
`014_cp1_complete_principal_idempotency_0_56`; 0.58 introduces no database
migration. Existing direct Prefect execution and existing pipelines continue
to work without enabling the managed path.

Version 0.58.0 is a release candidate and is not yet available from PyPI. The
latest published package is 0.57.2. Candidate installation and validation
instructions are in [Installation](INSTALLATION.md) and the
[release exit gate](../11_DEVELOPMENT/EXIT_GATE_0_58.md).
