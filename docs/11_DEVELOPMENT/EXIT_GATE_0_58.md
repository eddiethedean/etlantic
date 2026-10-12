---
title: ETLantic 0.58 Exit Gate
status: published
current_minor: "0.58"
---

# ETLantic 0.58 Exit Gate — Managed Prefect Execution

**Release decision: GO; v0.58.0 was published on 2026-10-12.** The phase
implementation from PR [#300](https://github.com/eddiethedean/etlantic/pull/300)
and the P1 Prefect cancellation fix from PR
[#302](https://github.com/eddiethedean/etlantic/pull/302) are merged into
`main` at `f69ab909284d68b0bebfb041f49c5fe5a644a226`. The published release is
[v0.58.0](https://github.com/eddiethedean/etlantic/releases/tag/v0.58.0).

## Qualified support profile

The supported profile is limited to static `etlantic.plan/1` batch execution
on Ubuntu 24.04 x86_64 with Python 3.11.15, 3.12.13, or 3.13.16; self-hosted
Prefect 3.7.8 backed by PostgreSQL 16.15; and the Prefect Process worker pool.
Qualified connectors are CSV to PostgreSQL and PostgreSQL to PostgreSQL
replace. The feature is opt-in through `etlantic-prefect`; direct Prefect
execution remains available.

## Phase qualification evidence

The final phase decision records every AC058 gate, adjacent phase gate, and
acceptance item in #290–#298 as passed:

- [Final qualification decision](evidence/phase_0_58/FINAL_QUALIFICATION_DECISION_2026-10-12.json)
- [Installed-worker Python matrix](evidence/phase_0_58/CI_INSTALLED_WORKER_PYTHON_MATRIX_2026-10-12.json)
- [Phase evidence index](evidence/phase_0_58/RELEASE_INDEX.json)

The qualification run completed 45 checks successfully with two expected
skips and no failures. The installed-wheel Prefect/PostgreSQL suite passed 48
tests on each supported Python version, including headless/FastAPI parity.
Qualification evidence establishes this profile only; broader
provider and runtime combinations remain outside its scope.

No SQLModel migration was added. The schema migration head remains
`014_cp1_complete_principal_idempotency_0_56`.

## 0.58.0 release record

- [x] Align core and first-party distribution versions at 0.58.0.
- [x] Refresh the lockfile and plugin manifest digests.
- [x] Preserve historical release and migration facts during version updates.
- [x] Add 0.58 release notes, migration guidance, and qualification evidence.
- [x] Pass local release readiness, docs, manifest, and release-facts checks.
- [x] Build all 25 distributions as wheels and source distributions.
- [x] Run the Prefect suite (44 passed, 4 skipped) and version-bump regression tests (3 passed).
- [x] Pass the installed-wheel unit and CLI suite (451 passed, 10 skipped).
- [x] Pass Medallantic parity tests (94 passed) and verify the refreshed adaptive
  evidence (18 acceptance criteria).
- [x] Pass full GitHub CI for the release candidate (47 jobs).
- [x] Merge the release-preparation change before tagging or publishing.
- [x] Pass post-merge main CI (run [38306010902](https://github.com/eddiethedean/etlantic/actions/runs/38306010902)).
- [x] Pass the tag-triggered Release workflow (run [38306117142](https://github.com/eddiethedean/etlantic/actions/runs/38306117142)).
- [x] Publish GitHub release `v0.58.0` and the lockstep first-party distributions.

The release was published at 2026-10-12T21:09:14Z. The current supported line
is 0.58.x. See the [release process](RELEASE_PROCESS.md) for the workflow used
to publish this release.
