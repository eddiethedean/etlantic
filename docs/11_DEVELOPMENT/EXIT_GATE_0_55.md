---
title: ETLantic 0.55 Exit Gate
status: candidate
current_minor: "0.55"
---

# ETLantic 0.55 Exit Gate — Inferred Model Authoring

**Decision: gate-ready for the scoped 0.55.0 Beta release.** This
decision qualifies only the capabilities recorded in the machine-readable
[inference evidence index](evidence/inference_0_55/index.json). It does not
promote inferred-model authoring beyond Experimental.

## Evidence reviewed

- Evidence index, capability matrix, and finding ledger agree on `qualified`.
- All 22 required review findings are marked verified.
- All nine required gate families are covered: wire security, bounded
  materialization, lineage solving, target revisions, durable definitions,
  optional dependencies, differential fixtures, race tests, and full
  regression.
- The CI run on the release preparation commit must pass before tagging; the
  local campaign is reproducible with the command below.

```bash
uv run python scripts/check_inference_0_55.py
```

The check runs the full gate campaign and verifies its temporary, commit-pinned
results against the committed evidence index, matrix, and ledger. Its generated
gate reports include environment, dependency, test-count, and digest metadata.

## Qualified scope

| Surface | Qualification |
|---|---|
| Records, CSV, JSON | Bounded source inference and replay rules |
| Pandas, Polars | Bounded adapters and previews |
| PySpark, DataFusion | Metadata-only frame inspection |
| SQL/DuckDB | Metadata-only relation inspection |
| Parquet | Bounded footer inspection and durable read-only source binding |
| Schema registry | Read-only JSON Schema and Avro subject inspection |
| Join and union | Two-input bound definitions with explicit collision rejection |
| Append, overwrite, merge, upsert, partition replace | Transactional SQLite reference target |

## Release boundary

- Inferred-model authoring remains Experimental; unsupported inference fails
  with a diagnostic or requires an explicit hint.
- PySpark, DataFusion, and DuckDB durable provider replay requires explicit
  rebinding. Parquet has no qualified write capability.
- Protobuf inference, live registry availability, and non-SQLite provider
  write-mode implementations are outside this qualification.
- Target inspection never writes or creates a target. Source observations,
  target constraints, and output proposals remain distinct.
- Definitions, plans, reports, and histories contain no source rows, sampled
  values, credentials, or absolute source paths.
- Existing typed pipeline APIs and their fingerprints remain unchanged.

See the [execution plan](EXECUTION_PLAN_0_55.md), [full review fix plan](REVIEW_FIX_PLAN_0_55.md),
and [0.55 evidence index](evidence/inference_0_55/index.json) for the complete
scope and limitations.
