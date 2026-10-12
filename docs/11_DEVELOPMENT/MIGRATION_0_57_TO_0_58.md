---
title: Migration from 0.57 to 0.58
status: available
since: "0.58.0"
current_minor: "0.58"
---

# Migration from 0.57 to 0.58

> **Status: Migration guide for the published ETLantic 0.58.0 release.**

For existing 0.57 deployments, the 0.58 upgrade keeps package versions in
lockstep and adds an optional managed Prefect execution path. Existing pipeline
definitions and direct Prefect execution do not need to change. Only adopters
who opt into the managed path need the additional Prefect configuration below.

## Package upgrade

Install ETLantic and any first-party plugins at the same version. The published
version is `0.58.0`; install it and its plugins from PyPI.

First-party plugins declare the compatible core floor `etlantic>=0.58.0`;
deployment lockfiles should pin the core and selected plugins to `0.58.0`.

## Database state

ETLantic 0.58 adds no SQLModel migration. The migration head remains
`014_cp1_complete_principal_idempotency_0_56`. Continue to apply migrations as
an explicit deployment operation and use the provider's read-only schema
inspection during runtime construction.

## Opting into managed Prefect

Managed execution is provided by the optional `etlantic-prefect` package. Its
qualified profile requires static `etlantic.plan/1` batches, a self-hosted
Prefect 3.7.8 API backed by PostgreSQL 16.15, Process workers, and Ubuntu 24.04
x86_64 with Python 3.11.15, 3.12.13, or 3.13.16. The qualified data paths are
CSV to PostgreSQL and PostgreSQL to PostgreSQL in replace mode. Review the
[qualification evidence](evidence/phase_0_58/FINAL_QUALIFICATION_DECISION_2026-10-12.json)
and configure the managed service through the documented public APIs before
routing production submissions to it.

Keep schedule admission and ownership in ETLantic. Prefect-native schedules
are not part of this support profile. Keep the Prefect API, PostgreSQL store,
dispatcher, and Process workers under your deployment's supervision and
provisioning controls.

## Rollout

1. Upgrade the core and the plugins used by the deployment to matching 0.58.0
   release artifacts.
2. Apply the deployment's normal database migration procedure and confirm the
   existing schema is at a compatible head; no 0.58 migration is expected.
3. Keep existing direct Prefect flows unchanged while validating managed
   service configuration and worker credentials in a non-production profile.
4. Enable managed routing only for the qualified profile and verify status,
   cancellation, and recovery through the shared ETLantic service interface.

See [What's New in 0.58](../01_GETTING_STARTED/WHATS_NEW_0_58.md) and the
[release exit gate](EXIT_GATE_0_58.md) for the published support boundary and
qualification evidence.
