---
status: experimental
since: "0.54.0"
current_minor: "0.54"
audience: developer
---

# What's new in 0.54

0.54.0 is the implementation candidate; publication and independent review are
pending. Explicit execution remains the default. Adaptive execution remains
**Experimental**, not Available or production-qualified.

- Public immutable provider conformance cases/reports and sync/async helpers
  validate before factories, round-trip stored plans and require behavioral oracles.
- A read-only optional Polars Parquet adapter owns finite local snapshots and
  rejects unsafe locations, excess bounds and unsupported source types.
- The exact placement-bound Polars source/equality-filter/projection prefix runs
  as one physical unit and one native collection, then transfers once to Pandas.
- Fresh observations retain actual provenance and full test identities. A
  read-only index verifier requires nine matching actual CI cells for a
  cross-platform claim; missing remote runs do not block implementation handoff.
- Pending graduation safeguards prevent provider conformance or candidate
  metadata from promoting an unreviewed row to Available.

See [candidate usage](../11_DEVELOPMENT/ADAPTIVE_0_54_USAGE.md),
[provider participation](../07_PLUGIN_SDK/ADAPTIVE_CONFORMANCE.md),
[Migration 0.53 → 0.54](../11_DEVELOPMENT/MIGRATION_0_53_TO_0_54.md), and
[local exit gate](../11_DEVELOPMENT/EXIT_GATE_0_54.md).
