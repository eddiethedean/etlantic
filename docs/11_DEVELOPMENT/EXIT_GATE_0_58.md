---
title: ETLantic 0.58 Exit Gate
status: candidate
current_minor: "0.60"
---

# ETLantic 0.58 Exit Gate — Managed Prefect Execution

**Candidate decision: QUALIFIED for the bounded support profile.** The phase
implementation from PR [#300](https://github.com/eddiethedean/etlantic/pull/300)
was merged into `main` as `188f0ec1c5f37db8a81845acabe2a6be0902090e`.
Publication of version 0.58.0 remains a separate release action.

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
Candidate qualification evidence establishes this profile only; broader
provider and runtime combinations remain outside its scope.

No SQLModel migration was added. The schema migration head remains
`014_cp1_complete_principal_idempotency_0_56`.

## 0.58.0 release preparation

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
- [ ] Merge the release-preparation change before tagging or publishing.

Local check results: `scripts/check_docs.py`, `mkdocs build --strict`,
`scripts/check_plugin_manifests.py`, `scripts/check_release.py`, and
`git diff --check` passed. The release checker reports that the 0.58.0 versions
are not yet on PyPI for all 25 projects; that is expected before publication.

The current published line remains 0.57.x until the 0.58.0 tag and publication
workflow complete. See the [release process](RELEASE_PROCESS.md) before any
tag or publish operation.
