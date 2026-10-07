---
title: ETLantic 0.56 Exit Gate
status: released
current_minor: "0.56"
---

# ETLantic 0.56 Exit Gate — Complete Application ETL Backend

**Release decision (2026-10-07): GO; ETLantic 0.56.0 is published.** All 44
acceptance criteria passed. The merged main candidate was tagged `v0.56.0` at
`b4a5f578feadd704e65326c77e72120d55aaa5bb`; release workflow run
[37570780108](https://github.com/eddiethedean/etlantic/actions/runs/37570780108)
passed, and the GitHub release was published at 2026-10-07 04:30:02 UTC.
The [release artifact verification guide](../01_GETTING_STARTED/RELEASE_ARTIFACT_VERIFICATION.md)
lists the published assets and verification steps.

## Evidence

The machine-readable [0.56 release index](evidence/phase_0_56/RELEASE_INDEX.json)
tracks all 44 acceptance criteria as passed, including managed checkpoint
restoration, PostgreSQL partition repair and backfill, and run lineage. AC056-026
was rerun against the current input-store source using an isolated temporary
PostgreSQL 16.13 cluster. Linked artifacts include the package compatibility
report, wheel manifest, local qualification record, live PostgreSQL tests and
managed repair/backfill lifecycle tests.

Candidate qualification commands and environment details are recorded in the
[local qualification record](evidence/phase_0_56/LOCAL_QUALIFICATION.md).
Run the phase package checker with:

```bash
uv run python scripts/qualify_phase056_packages.py --repo-root . --wheel-dir PATH_TO_WHEELS --output docs/11_DEVELOPMENT/evidence/phase_0_56/PACKAGE_COMPATIBILITY_0_56.json
```

## Release boundary

- ETLantic 0.56.x is the published and supported Beta line.
- The release workflow published 25 package distributions across wheels and
  source archives, alongside `release-artifacts.json` and provenance
  attestations. All 25 package projects are present on PyPI.
- SBOM generation was unavailable for this release; the GitHub release records
  this in `sbom-warning.txt`.
- PostgreSQL repair/backfill requires an explicit `partition_column` and
  allowlisted partition capabilities. Other providers fail closed.

See the [implementation plan](IMPLEMENTATION_PLAN_0_56.md), [execution
plan](EXECUTION_PLAN_0_56.md), and [review findings](FINDINGS_0_56.md).
