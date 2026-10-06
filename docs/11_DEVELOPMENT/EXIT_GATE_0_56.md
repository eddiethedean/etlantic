---
title: ETLantic 0.56 Exit Gate
status: candidate
current_minor: "0.56"
---

# ETLantic 0.56 Exit Gate — Complete Application ETL Backend

**Decision: all 44 acceptance criteria are qualified; release review remains open.**
This gate records the in-tree implementation and local evidence for the phase.
The published 0.56.0 release remains pending.

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

- The 0.56.0 candidate is not a published or supported package release.
- The published 0.55.x line remains the production installation target until
  an authorized release is prepared.
- PostgreSQL repair/backfill requires an explicit `partition_column` and
  allowlisted partition capabilities. Other providers fail closed.
- Candidate gate evidence does not create a tag, publish packages, or replace
  the final release review.

See the [implementation plan](IMPLEMENTATION_PLAN_0_56.md), [execution
plan](EXECUTION_PLAN_0_56.md), and [review findings](FINDINGS_0_56.md).
