---
title: ETLantic 0.56 Exit Gate
status: candidate
current_minor: "0.56"
---

# ETLantic 0.56 Exit Gate — Complete Application ETL Backend

**Decision (2026-10-07): GO for the ETLantic 0.56.0 release.** All 44
acceptance criteria are qualified, the final candidate is merged to `main` at
`d9edb360652de8ebd5265e8f0bbfe6ab3f5618d3`, and its full CI run passed. This
approves proceeding with the tagged release workflow; it does not claim that
0.56.0 has been tagged or published.

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

- ETLantic 0.56.0 is approved for release, but is not a published or supported
  package release until the release workflow completes successfully.
- The published 0.55.x line remains the production installation target until
  0.56.0 publication succeeds.
- `etlantic-foundry` is a new PyPI project; use the release workflow's paced
  first-project creation and verify the upload before declaring publication.
- PostgreSQL repair/backfill requires an explicit `partition_column` and
  allowlisted partition capabilities. Other providers fail closed.
- This decision does not create a tag or publish packages. Follow the
  [release process](RELEASE_PROCESS.md) for tagging and publication.

See the [implementation plan](IMPLEMENTATION_PLAN_0_56.md), [execution
plan](EXECUTION_PLAN_0_56.md), and [review findings](FINDINGS_0_56.md).
