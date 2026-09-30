# Phase 0.56 Local Qualification

**Decision: OPEN.** This record reports local implementation evidence; it does
not claim that AC056-001–044 have all passed. The evidence index leaves each
criterion open until its complete documented case has been observed.

## Candidate environment

- Date: 2026-09-29
- Host: macOS 25.5.0, arm64
- Python: 3.11.15
- Live database: isolated local PostgreSQL 16.14 container
- Workspace base: `e7fd6b866dbecab646cf68b73405ee06ea4437e5`
- Candidate packages: core and companions currently build as 0.55.0; this is
  implementation work against the 0.55 compatibility baseline, not a release.

## Executed evidence

- Default non-optional suite:
  `uv run pytest -q -m "not medallantic and not polars and not pandas and not sql and not spark and not real_pyspark and not airflow and not prefect and not keyring and not sqlmodel and not datafusion"`
  observed 2,705 passed, 67 skipped, 586 deselected, and one failure in the
  pinned adaptive-evidence regeneration case. That failure identified a stale
  0.52 evidence snapshot after a managed-service source edit. The snapshot was
  regenerated again after the final source move; the exact regression case then
  passed. The entire default suite was not rerun after that evidence refresh.
- Live PostgreSQL connector and multiprocess acceptance:
  `ETLANTIC_SQL_TEST_URL=... ETLANTIC_CP_TEST_URL=... uv run pytest -q tests/sql/test_postgresql_live_0_56.py tests/sqlmodel/test_durable_postgresql_multiprocess_0_56.py` — 4 passed.
- SQLModel migration campaign against SQLite and isolated PostgreSQL schemas:
  `ETLANTIC_SQLMODEL_TEST_URL=... uv run pytest -q tests/sqlmodel/test_cp1_migrations_0_51.py` — 8 passed.
- CP1 authorization matrix: 48 passed.
- Managed HTTP malformed revision-selector boundary: 1 passed.
- Native staged-checkpoint deadline rollback: 2 parameter cases passed.
- Wheel build: all 25 workspace wheels built successfully.
- Clean install smoke: core, FastAPI, PostgreSQL SQL, Foundry and SQLModel
  wheels installed into a fresh Python 3.11 environment; public imports and
  Foundry configuration-schema discovery passed.
- Public CLI: sample pipeline validation passed with no diagnostics; plan
  generation returned fingerprint
  `8f3879b301b3b0ea1b87434eef3dd0a58ef0cbe8342ced056323cc9d6d5b19da`.
- Plugin manifests: 16 packages passed.
- Final `scripts/check_adaptive_0_52.py --write` refreshed and verified 10
  artifacts across 18 prior-phase acceptance criteria; its exact CI regression
  test passed afterward.
- `scripts/check_pyright.sh` passed: 784 suppressions matched the locked
  inventory, the strict shadow scan matched its 10,452-diagnostic baseline,
  and raw Pyright reported zero errors and warnings.
- `ruff check .`, `git diff --check`, plugin-manifest checks and `uv lock --check`
  passed.

## Open release requirements

- AC056-020–026: isolated action jobs, previews/provisioning, scoped secret
  lifecycle and immutable upload leases are not fully implemented and observed.
- AC056-027–032: scheduler admission parity, complete lifecycle commands,
  qualified pause/amendment and runnable replay/repair/backfill remain open.
- AC056-034 and AC056-036: no isolated live Foundry account is configured.
  The required two independent Foundry scopes and all 12 real-worker pairings
  have not been exercised; mock transport tests do not qualify them.
- AC056-037–044: independent private-provider, full disclosure campaign,
  PostgreSQL backup/restore/failure, version-skew/rollback, complete advanced
  engine matrix, managed adaptive `/2`, and generic consumer evidence remain
  open.

See [`RELEASE_INDEX.json`](RELEASE_INDEX.json) for the per-criterion status,
case references, provider tuple and open reason. These limitations keep the
0.56 release decision open even though the implemented local gates pass.
